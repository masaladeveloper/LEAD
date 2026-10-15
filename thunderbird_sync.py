"""Incremental, replay-safe ingestion of Thunderbird mbox folders."""
from __future__ import annotations

from dataclasses import dataclass, field
from email import policy
from email.parser import BytesParser
from email.utils import parseaddr, parsedate_to_datetime
import hashlib
import json
from pathlib import Path
import re
import time

from bs4 import BeautifulSoup
from crm_database import as_iso_date
from html_parser import parse_html, parse_plain_text, extract_lead_id
from mailbox_reader import decode, get_body
from models import EmailMessage
from thread_parser import clean_reply


@dataclass
class SyncResult:
    emails_read: int = 0
    new_leads: int = 0
    existing_leads: int = 0
    remarks_added: int = 0
    unparsed: int = 0
    pending: int = 0
    errors: list[str] = field(default_factory=list)
    issues: list[dict[str, str]] = field(default_factory=list)


def _to_email_message(message):
    html, text = get_body(message)
    return EmailMessage(sender=decode(message.get('From')), subject=decode(message.get('Subject')),
        date=decode(message.get('Date')), message_id=decode(message.get('Message-ID')),
        in_reply_to=decode(message.get('In-Reply-To')), references=decode(message.get('References')),
        html=html, text=text)


def _messages_since(path: Path, offset: int, settle_seconds=2):
    with path.open('rb') as stream:
        stream.seek(offset)
        start, content = None, []
        while True:
            position = stream.tell()
            line = stream.readline()
            if not line:
                break
            if line.startswith(b'From '):
                if start is not None:
                    yield position, BytesParser(policy=policy.default).parsebytes(b''.join(content))
                start, content = position, []
            elif start is not None:
                content.append(line)
        # Re-read the tail on the next sync. Avoid a record Thunderbird is writing.
        if start is not None and content and time.time() - path.stat().st_mtime >= settle_seconds:
            yield start, BytesParser(policy=policy.default).parsebytes(b''.join(content))


def _prefix_hash(path, length):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        while length:
            chunk = stream.read(min(length, 1024 * 1024))
            if not chunk:
                break
            digest.update(chunk)
            length -= len(chunk)
    return digest.hexdigest()


def _message_ids(mail):
    parents = re.findall(r'<[^>]+>', mail.in_reply_to)
    return parents + list(reversed(re.findall(r'<[^>]+>', mail.references)))


def _lead_from_mail(mail):
    extracted = parse_html(mail.html, mail.subject)
    if not extracted.get('Date') or not extracted.get('Name'):
        extracted = {**extracted, **parse_plain_text(mail.text, mail.subject)}
    if not extracted.get('Date') or not extracted.get('Name'):
        return {}
    mapping = {'Lead ID':'lead_id', 'Date':'enquiry_date', 'Name':'customer_name', 'Contact No.':'contact_no',
        'Email Id':'email_id', 'Alt No.':'alt_no', 'Model No.':'model', 'Category':'category',
        'City':'city', 'Voice of Customer':'voice_of_customer', 'Quantity':'quantity', 'Dealer':'dealer'}
    values = {mapping[k]: v for k, v in extracted.items() if k in mapping}
    values['enquiry_date'] = as_iso_date(values['enquiry_date'])
    values['message_id'] = mail.message_id
    return values


def _reply_text(mail):
    if mail.text:
        return clean_reply(mail.text)
    soup = BeautifulSoup(mail.html, 'lxml')
    for quoted in soup.select('blockquote, .gmail_quote, .moz-cite-prefix, script, style'):
        quoted.decompose()
    return clean_reply(soup.get_text('\n', strip=True))


def _occurred_at(value):
    try:
        return parsedate_to_datetime(value).astimezone().isoformat(sep=' ', timespec='seconds')
    except (ValueError, TypeError, OverflowError):
        return ''


def _resolve_pending(database, my_email, result):
    # Revisit unmatched replies, including ones seen before their parent lead or
    # in an earlier folder. Mapping every reply supports replies-to-replies.
    while True:
        resolved = 0
        pending = database.connection.execute("SELECT * FROM email_messages WHERE kind = 'pending'").fetchall()
        for row in pending:
            payload = json.loads(row['payload'])
            parent = database.find_lead_by_message_id(payload['references'])
            sender = parseaddr(payload['sender'])[1].casefold()
            if not parent and payload['call_id']:
                candidate = database.find_by_call_id(payload['call_id'])
                # A subject alone is insufficient for mail from an unknown sender.
                if candidate and sender in {my_email.casefold(), str(candidate.get('email_id') or '').casefold()} - {''}:
                    parent = candidate
            if not parent:
                continue
            outgoing = sender == my_email.casefold() and bool(my_email)
            with database.transaction():
                # Legacy messages already appended to remarks should not be duplicated.
                legacy = database.connection.execute('SELECT 1 FROM processed_email_updates WHERE message_id = ?', (row['message_id'],)).fetchone()
                if not legacy:
                    result.remarks_added += int(database.add_activity(parent['id'], 'sent' if outgoing else 'received', payload['body'], payload['sender'], payload['date'], row['message_id']))
                database.connection.execute("UPDATE email_messages SET lead_id = ?, kind = 'reply', payload = '' WHERE message_id = ?", (parent['id'], row['message_id']))
                if sender and sender == str(parent.get('email_id') or '').casefold() and not outgoing and parent.get('responded') in ('', 'Not Responded', 'No Answer'):
                    database.update_lead(parent['id'], {'responded':'Responded'}, protect_source=False)
            resolved += 1
        if not resolved:
            break
    result.pending = database.connection.execute("SELECT COUNT(*) FROM email_messages WHERE kind = 'pending'").fetchone()[0]


def _ingest(database, path, senders, my_email, result, force=False, settle_seconds=2):
    path = Path(path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f'Mailbox not found: {path}')
    # Changing source filters must allow previously ignored enquiries to be read.
    key = 'mailbox_v2:' + hashlib.sha256((str(path) + '|' + ','.join(sorted(senders))).encode()).hexdigest()
    try:
        checkpoint = json.loads(database.get_setting(key, '{}'))
        if not isinstance(checkpoint, dict):
            checkpoint = {}
        offset = int(checkpoint.get('offset', 0))
    except (ValueError, TypeError):
        checkpoint, offset = {}, 0
    before = path.stat()
    if force or offset < 0 or offset > before.st_size or checkpoint.get('prefix') != _prefix_hash(path, offset):
        offset = 0
    next_offset = offset
    for next_offset, raw in _messages_since(path, offset, settle_seconds):
        mail = _to_email_message(raw)
        result.emails_read += 1
        sender = parseaddr(mail.sender)[1].casefold()
        content_hash = hashlib.sha256(raw.as_bytes()).hexdigest()
        message_id = mail.message_id.strip().lower() or 'sha256:' + content_hash
        previous = database.connection.execute('SELECT * FROM email_messages WHERE message_id = ?', (message_id,)).fetchone()
        if previous and previous['content_hash'] == content_hash:
            continue
        with database.transaction():
            lead = {}
            parse_error = 'Expected enquiry fields Date and Name were not found.'
            if sender in senders and not _message_ids(mail):
                try:
                    lead = _lead_from_mail(mail)
                except ValueError as error:
                    parse_error = str(error)
            if lead:
                lead['message_id'] = message_id
                try:
                    lead_id, created = database.upsert_source_lead(lead)
                except ValueError as error:
                    result.unparsed += 1
                    if len(result.issues) < 100:
                        result.issues.append({'folder': path.name, 'subject': mail.subject, 'reason': str(error)})
                    continue
                result.new_leads += int(created)
                result.existing_leads += int(not created)
                database.connection.execute("""INSERT INTO email_messages VALUES (?, ?, 'source', '', ?)
                    ON CONFLICT(message_id) DO UPDATE SET lead_id=excluded.lead_id, content_hash=excluded.content_hash, kind='source', payload='' """, (message_id, lead_id, content_hash))
                database.add_activity(lead_id, 'enquiry', f'Enquiry received: {mail.subject}', mail.sender, _occurred_at(mail.date), message_id)
                continue
            references = _message_ids(mail)
            if sender in senders and not references:
                result.unparsed += 1
                if len(result.issues) < 100:
                    result.issues.append({'folder': path.name, 'subject': mail.subject, 'reason': parse_error})
                continue
            call_id = extract_lead_id(mail.subject) if re.search(r'inquiry|enquiry|call\s*id', mail.subject, re.I) else ''
            if not references and not call_id:
                continue
            body = _reply_text(mail)
            if not body:
                continue
            if previous and previous['kind'] == 'reply':
                # A tail record can be completed between scans: update its one activity.
                database.connection.execute('UPDATE activities SET body=? WHERE message_id=?', (body, message_id))
                database.connection.execute('UPDATE email_messages SET content_hash=? WHERE message_id=?', (content_hash, message_id))
                continue
            payload = json.dumps(dict(references=references, call_id=call_id, body=body, sender=mail.sender, date=_occurred_at(mail.date)))
            database.connection.execute("""INSERT INTO email_messages VALUES (?, NULL, 'pending', ?, ?)
                ON CONFLICT(message_id) DO UPDATE SET payload=excluded.payload, content_hash=excluded.content_hash""", (message_id, payload, content_hash))
    after = path.stat()
    if (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
        raise RuntimeError(f'{path.name} changed during sync. It will be retried automatically.')
    database.set_setting(key, json.dumps({'offset':next_offset, 'prefix':_prefix_hash(path, next_offset)}))


def sync_mailboxes(database, mailbox_paths, sender_filter, my_email, *, force=False, settle_seconds=2):
    senders = {parseaddr(s.strip())[1].casefold() for s in sender_filter.split(',') if s.strip()}
    if not senders or any('@' not in s for s in senders):
        raise ValueError('Enter the exact enquiry sender email address in Email settings.')
    result = SyncResult()
    for path in dict.fromkeys(p for p in mailbox_paths if p):
        try:
            _ingest(database, path, senders, my_email, result, force, settle_seconds)
        except (OSError, ValueError, RuntimeError) as error:
            result.errors.append(str(error))
    _resolve_pending(database, my_email, result)
    return result


def sync_mailbox(database, mailbox_path, sender_filter, my_email):
    return sync_mailboxes(database, [mailbox_path], sender_filter, my_email)

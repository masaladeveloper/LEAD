"""Incremental Thunderbird mbox synchronisation for the lead CRM."""

from __future__ import annotations

import re
from dataclasses import dataclass
from email import policy
from email.parser import BytesParser
from pathlib import Path

from crm_database import LeadDatabase, as_iso_date
from html_parser import parse_html
from mailbox_reader import decode, get_body
from models import EmailMessage
from thread_parser import clean_reply


@dataclass
class SyncResult:
    emails_read: int = 0
    source_leads_seen: int = 0
    new_leads: int = 0
    existing_leads: int = 0
    remarks_added: int = 0


def _to_email_message(message) -> EmailMessage:
    html, text = get_body(message)
    return EmailMessage(
        sender=decode(message.get("From")), subject=decode(message.get("Subject")),
        date=decode(message.get("Date")), message_id=decode(message.get("Message-ID")),
        in_reply_to=decode(message.get("In-Reply-To")), references=decode(message.get("References")),
        html=html, text=text,
    )


def _messages_since(path: Path, offset: int):
    """Read only mbox records appended since ``offset``.

    The final record is deliberately read again next time. This makes syncing
    safe when Thunderbird is still writing a newly received email.
    """
    with path.open("rb") as mailbox_file:
        mailbox_file.seek(max(0, offset))
        start = mailbox_file.tell()
        current_start = None
        content: list[bytes] = []
        while True:
            position = mailbox_file.tell()
            line = mailbox_file.readline()
            if not line:
                break
            if line.startswith(b"From "):
                if current_start is not None:
                    yield current_start, position, BytesParser(policy=policy.default).parsebytes(b"".join(content))
                current_start = position
                content = []
            elif current_start is not None:
                content.append(line)
        if current_start is not None and content:
            # Keep this start as the next offset, so this trailing record gets
            # parsed again after Thunderbird has definitely finished writing.
            yield current_start, current_start, BytesParser(policy=policy.default).parsebytes(b"".join(content))


def _message_ids(mail: EmailMessage) -> list[str]:
    return re.findall(r"<[^>]+>", " ".join((mail.in_reply_to, mail.references)))


def _lead_from_mail(mail: EmailMessage) -> dict:
    extracted = parse_html(mail.html, mail.subject)
    if not extracted.get("Date") or not extracted.get("Name"):
        return {}
    return {
        "lead_id": extracted.get("Lead ID", ""), "enquiry_date": as_iso_date(extracted.get("Date")),
        "customer_name": extracted.get("Name", ""), "contact_no": extracted.get("Contact No.", ""),
        "email_id": extracted.get("Email Id", ""), "alt_no": extracted.get("Alt No.", ""),
        "model": extracted.get("Model No.", ""), "category": extracted.get("Category", ""),
        "city": extracted.get("City", ""), "voice_of_customer": extracted.get("Voice of Customer", ""),
        "message_id": mail.message_id,
    }


def sync_mailbox(database: LeadDatabase, mailbox_path: str, sender_filter: str, my_email: str) -> SyncResult:
    path = Path(mailbox_path)
    if not path.is_file():
        raise FileNotFoundError(f"Thunderbird mailbox not found: {path}")
    if not sender_filter.strip():
        raise ValueError("Set the Hyundai sender email in Settings before syncing.")

    size = path.stat().st_size
    offset = int(database.get_setting("mailbox_offset", "0") or 0)
    if offset < 0 or offset > size:
        offset = 0  # Thunderbird compacted/rebuilt the mbox; safely re-scan.
    result = SyncResult()
    next_offset = offset
    for start, end, raw_message in _messages_since(path, offset):
        mail = _to_email_message(raw_message)
        result.emails_read += 1
        next_offset = max(next_offset, end)
        if sender_filter.casefold() in mail.sender.casefold():
            lead = _lead_from_mail(mail)
            if lead:
                result.source_leads_seen += 1
                _, created = database.upsert_source_lead(lead)
                result.new_leads += int(created)
                result.existing_leads += int(not created)
        elif my_email and my_email.casefold() in mail.sender.casefold():
            parent = database.find_lead_by_message_id(_message_ids(mail))
            if parent:
                body = clean_reply(mail.text or mail.html)
                note = f"{mail.date}\n{body}" if body else ""
                if database.append_email_remark(parent["id"], mail.message_id, note):
                    result.remarks_added += 1
    database.set_setting("mailbox_offset", str(next_offset))
    return result

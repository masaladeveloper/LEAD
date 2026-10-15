"""SQLite master record, transaction boundaries, and lead activity history."""
from __future__ import annotations

from contextlib import closing, contextmanager
from datetime import date, datetime
from pathlib import Path
import json
import re
import sqlite3
import uuid
from typing import Any, Iterable

STATUSES = ('New', 'In process', 'Follow-up', 'Quotation Sent', 'Won', 'Lost', 'Closed')
CRM_COLUMNS = ('remark', 'responded', 'relevance', 'deal_temperature', 'outcome', 'status', 'follow_up_date')
SOURCE_COLUMNS = ('dealer', 'lead_id', 'enquiry_date', 'customer_name', 'contact_no', 'email_id', 'alt_no', 'model', 'quantity', 'voice_of_customer', 'category', 'city')


def normalise_phone(value: Any) -> str:
    text = str(value or '').strip()
    if text.endswith('.0'):
        text = text[:-2]
    return ''.join(re.findall(r'\d', text))[-10:]


def normalise_text(value: Any) -> str:
    return ' '.join(str(value or '').split()).casefold()


def as_iso_date(value: Any) -> str:
    if value in (None, ''):
        return ''
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    for pattern in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%m/%d/%Y'):
        try:
            return datetime.strptime(text, pattern).date().isoformat()
        except ValueError:
            pass
    raise ValueError(f'Invalid date: {text}. Use YYYY-MM-DD or DD/MM/YYYY.')


def source_key(lead: dict[str, Any]) -> str:
    call_id = str(lead.get('lead_id') or '').strip()
    if call_id:
        return 'lead:' + call_id.casefold()
    phone = normalise_phone(lead.get('contact_no'))
    enquiry_date = as_iso_date(lead.get('enquiry_date'))
    model = normalise_text(lead.get('model'))
    if phone and enquiry_date:
        return f'contact:{phone}|date:{enquiry_date}|model:{model}'
    return 'manual:' + uuid.uuid4().hex


class LeadDatabase:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path, timeout=20)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute('PRAGMA foreign_keys = ON')
        self.connection.execute('PRAGMA journal_mode = WAL')
        self._depth = 0
        self._create_schema()

    def close(self):
        self.connection.close()

    @contextmanager
    def transaction(self):
        """Nested operations participate in one all-or-nothing transaction."""
        outer = self._depth == 0
        if outer:
            self.connection.execute('BEGIN IMMEDIATE')
        self._depth += 1
        try:
            yield
            if outer:
                self.connection.commit()
        except Exception:
            if outer:
                self.connection.rollback()
            raise
        finally:
            self._depth -= 1

    def _create_schema(self):
        self.connection.executescript('''
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY, source_key TEXT NOT NULL UNIQUE,
                message_id TEXT UNIQUE,
                dealer TEXT NOT NULL DEFAULT 'Muneer Heavy Earthmoving Equipment',
                lead_id TEXT, enquiry_date TEXT, customer_name TEXT, contact_no TEXT,
                email_id TEXT, alt_no TEXT, model TEXT, quantity INTEGER NOT NULL DEFAULT 1,
                voice_of_customer TEXT, category TEXT, city TEXT,
                remark TEXT NOT NULL DEFAULT '', responded TEXT NOT NULL DEFAULT '',
                relevance TEXT NOT NULL DEFAULT '', deal_temperature TEXT NOT NULL DEFAULT '',
                outcome TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'New',
                follow_up_date TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_leads_date ON leads(enquiry_date);
            CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status);
            CREATE INDEX IF NOT EXISTS idx_leads_contact ON leads(contact_no);
            CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL DEFAULT '');
            CREATE TABLE IF NOT EXISTS processed_email_updates (
                message_id TEXT PRIMARY KEY, lead_id INTEGER NOT NULL REFERENCES leads(id),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS activities (
                id INTEGER PRIMARY KEY, lead_id INTEGER NOT NULL REFERENCES leads(id),
                kind TEXT NOT NULL, body TEXT NOT NULL, sender TEXT NOT NULL DEFAULT '',
                occurred_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, message_id TEXT UNIQUE
            );
            CREATE INDEX IF NOT EXISTS idx_activity_lead ON activities(lead_id, occurred_at);
            CREATE TABLE IF NOT EXISTS field_overrides (
                lead_id INTEGER NOT NULL REFERENCES leads(id), field TEXT NOT NULL,
                PRIMARY KEY(lead_id, field)
            );
            CREATE TABLE IF NOT EXISTS email_messages (
                message_id TEXT PRIMARY KEY, lead_id INTEGER REFERENCES leads(id),
                kind TEXT NOT NULL, payload TEXT NOT NULL DEFAULT '',
                content_hash TEXT NOT NULL DEFAULT ''
            );
        ''')
        self.connection.commit()

    def backup(self) -> Path:
        folder = self.path.parent / 'backups'
        folder.mkdir(exist_ok=True)
        target = folder / f'lead_crm-{datetime.now():%Y%m%d-%H%M%S-%f}.db'
        with closing(sqlite3.connect(target)) as destination:
            self.connection.backup(destination)
        return target

    @staticmethod
    def _quantity(value):
        try:
            number = float(value)
            if not number.is_integer() or number < 1:
                raise ValueError
            return int(number)
        except (TypeError, ValueError, OverflowError):
            raise ValueError('Quantity must be a positive whole number.') from None

    def _prepare(self, values):
        result = {}
        for key, value in values.items():
            if key not in (*SOURCE_COLUMNS, *CRM_COLUMNS):
                continue
            if key in ('enquiry_date', 'follow_up_date'):
                result[key] = as_iso_date(value)
            elif key in ('contact_no', 'alt_no'):
                result[key] = normalise_phone(value)
            elif key == 'quantity':
                result[key] = self._quantity(value)
            else:
                result[key] = str(value or '').strip()
        return result

    def find_by_call_id(self, call_id):
        if not str(call_id or '').strip():
            return None
        row = self.connection.execute('SELECT * FROM leads WHERE lower(lead_id) = lower(?)', (str(call_id).strip(),)).fetchone()
        return dict(row) if row else None

    def upsert_source_lead(self, lead: dict[str, Any]) -> tuple[int, bool]:
        # Absent / blank source values never erase known information.
        values = self._prepare({k: v for k, v in lead.items() if k in SOURCE_COLUMNS and v is not None and str(v).strip()})
        key = source_key(values)
        with self.transaction():
            existing = self.find_by_call_id(values.get('lead_id'))
            if not existing and lead.get('message_id'):
                existing = self.find_lead_by_message_id([lead['message_id']])
            if not existing and values.get('contact_no') and values.get('enquiry_date'):
                # Only promote an unidentified record; never merge two distinct Call IDs.
                fallback = source_key({**values, 'lead_id':''})
                row = self.connection.execute("SELECT * FROM leads WHERE source_key = ? AND COALESCE(lead_id, '') = ''", (fallback,)).fetchone()
                existing = dict(row) if row else None
            if existing:
                protected = {r[0] for r in self.connection.execute('SELECT field FROM field_overrides WHERE lead_id = ?', (existing['id'],))}
                changes = {k: v for k, v in values.items() if k not in protected and v != existing.get(k)}
                if changes:
                    merged = {**existing, **changes}
                    changes['source_key'] = source_key(merged) if merged.get('lead_id') or (merged.get('contact_no') and merged.get('enquiry_date')) else existing['source_key']
                    self._write(existing['id'], changes)
                return existing['id'], False
            values['source_key'] = key
            if lead.get('message_id'):
                values['message_id'] = str(lead['message_id']).strip().lower()
            fields = list(values)
            cursor = self.connection.execute(f"INSERT INTO leads ({', '.join(fields)}) VALUES ({', '.join('?' for _ in fields)})", list(values.values()))
            return int(cursor.lastrowid), True

    def _write(self, lead_id, values):
        if values:
            assignments = ', '.join(f'{key} = ?' for key in values)
            self.connection.execute(f'UPDATE leads SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE id = ?', [*values.values(), lead_id])

    def update_lead(self, lead_id: int, values: dict[str, Any], *, protect_source=True):
        prepared = self._prepare(values)
        with self.transaction():
            existing = self.get_lead(lead_id)
            if not existing:
                raise ValueError('Lead no longer exists.')
            if 'customer_name' in prepared and not prepared['customer_name']:
                raise ValueError('Customer name is required.')
            if 'status' in prepared:
                prepared['status'] = prepared['status'] or 'New'
                if prepared['status'] not in STATUSES:
                    raise ValueError('Choose a valid lead status.')
                prepared['outcome'] = prepared['status'] if prepared['status'] in ('Won', 'Lost') else ''
            elif prepared.get('outcome') in ('Won', 'Lost'):
                prepared['status'] = prepared['outcome']
            if 'lead_id' in prepared:
                duplicate = self.find_by_call_id(prepared['lead_id'])
                if duplicate and duplicate['id'] != lead_id:
                    raise ValueError('That Call ID already belongs to another lead.')
            changes = {k: v for k, v in prepared.items() if v != existing.get(k)}
            if not changes:
                return
            if any(k in changes for k in ('lead_id', 'contact_no', 'enquiry_date', 'model')):
                merged = {**existing, **changes}
                changes['source_key'] = source_key(merged)
            if protect_source:
                for key in changes.keys() & set(SOURCE_COLUMNS):
                    self.connection.execute('INSERT OR IGNORE INTO field_overrides VALUES (?, ?)', (lead_id, key))
            try:
                self._write(lead_id, changes)
            except sqlite3.IntegrityError:
                raise ValueError('These details match an existing lead.') from None
            if 'status' in changes:
                self.add_activity(lead_id, 'status', f"Status changed from {existing['status']} to {changes['status']}")

    def get_lead(self, lead_id):
        row = self.connection.execute('SELECT * FROM leads WHERE id = ?', (lead_id,)).fetchone()
        return dict(row) if row else None

    def search(self, term='', limit=10000, status='All leads'):
        clauses, params = [], []
        if term.strip():
            clauses.append('(' + ' OR '.join(f'{k} LIKE ?' for k in ('lead_id', 'customer_name', 'contact_no', 'email_id', 'model', 'city')) + ')')
            params.extend([f'%{term.strip()}%'] * 6)
        if status == 'Follow-ups due':
            clauses.append("follow_up_date <> '' AND follow_up_date <= date('now', 'localtime') AND status NOT IN ('Won', 'Lost', 'Closed')")
        elif status == 'Open leads':
            clauses.append("status NOT IN ('Won', 'Lost', 'Closed')")
        elif status in STATUSES:
            clauses.append('status = ?')
            params.append(status)
        where = ' WHERE ' + ' AND '.join(clauses) if clauses else ''
        rows = self.connection.execute('SELECT * FROM leads' + where + ' ORDER BY enquiry_date DESC, id DESC LIMIT ?', [*params, limit]).fetchall()
        return [dict(row) for row in rows]

    def all_leads(self, from_date='', to_date=''):
        rows = self.connection.execute('SELECT * FROM leads ORDER BY enquiry_date ASC, id ASC').fetchall()
        return [dict(r) for r in rows if (not from_date or (r['enquiry_date'] or '') >= from_date) and (not to_date or (r['enquiry_date'] or '') <= to_date)]

    def counts(self):
        row = self.connection.execute("""SELECT COUNT(*) AS total,
            COALESCE(SUM(status NOT IN ('Won','Lost','Closed')),0) AS open_count,
            COALESCE(SUM(follow_up_date <> '' AND follow_up_date <= date('now','localtime') AND status NOT IN ('Won','Lost','Closed')),0) AS due,
            COALESCE(SUM(status = 'Won'),0) AS won FROM leads""").fetchone()
        return dict(row)

    def get_setting(self, key, default=''):
        row = self.connection.execute('SELECT value FROM settings WHERE key = ?', (key,)).fetchone()
        return row[0] if row else default

    def mailbox_paths(self):
        """Read validated folder settings, including the original single-folder setting."""
        try:
            paths = json.loads(self.get_setting('mailbox_paths', '[]'))
        except ValueError:
            paths = []
        if not isinstance(paths, list) or any(not isinstance(p, str) for p in paths):
            paths = []
        paths = [p.strip() for p in paths if p.strip()]
        legacy = self.get_setting('mailbox_path').strip()
        return paths or ([legacy] if legacy else [])

    def sync_interval_minutes(self):
        """Keep old or invalid saved settings within the desktop's supported range."""
        try:
            minutes = int(self.get_setting('sync_minutes', '1'))
        except ValueError:
            minutes = 1
        return max(1, min(60, minutes))

    def set_setting(self, key, value):
        with self.transaction():
            self.connection.execute('INSERT INTO settings VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value', (key, str(value)))

    def find_lead_by_message_id(self, message_ids: Iterable[str]):
        # Prefer the nearest parent; do not guess between unrelated leads.
        for message_id in message_ids:
            key = message_id.strip().lower()
            row = self.connection.execute('''SELECT leads.* FROM leads WHERE id =
                (SELECT lead_id FROM email_messages WHERE message_id = ?)
                OR lower(message_id) = ? LIMIT 1''', (key, key)).fetchone()
            if row:
                return dict(row)
        return None

    def add_activity(self, lead_id, kind, body, sender='', occurred_at='', message_id=None):
        if not body.strip():
            return False
        with self.transaction():
            cursor = self.connection.execute('''INSERT INTO activities (lead_id,kind,body,sender,occurred_at,message_id)
                VALUES (?,?,?,?,COALESCE(NULLIF(?,''),CURRENT_TIMESTAMP),?)
                ON CONFLICT(message_id) DO NOTHING''', (lead_id, kind, body.strip(), sender, occurred_at, message_id))
            return cursor.rowcount > 0

    def activities(self, lead_id):
        return [dict(r) for r in self.connection.execute('SELECT * FROM activities WHERE lead_id = ? ORDER BY occurred_at DESC, id DESC', (lead_id,))]

    def append_email_remark(self, lead_id, message_id, remark):
        # Preserve the old API while keeping new email history separate from editable notes.
        return self.add_activity(lead_id, 'email', remark, message_id=message_id.lower())

    def import_rows(self, rows):
        added = updated = 0
        with self.transaction():
            for row in rows:
                _, created = self.upsert_source_lead(row)
                added += int(created)
                updated += int(not created)
        return added, updated

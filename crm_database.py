"""Persistent, offline storage for the Lead CRM.

The database deliberately separates source fields from the sales team's fields.
Email/import refreshes can therefore update customer information without erasing
remarks, call outcomes, or deal status entered in the application.
"""

from __future__ import annotations

import re
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable


CRM_COLUMNS = (
    "remark",
    "responded",
    "relevance",
    "deal_temperature",
    "outcome",
    "status",
    "follow_up_date",
)


def normalise_phone(value: Any) -> str:
    return "".join(re.findall(r"\d", str(value or "")))[-10:]


def normalise_text(value: Any) -> str:
    return " ".join(str(value or "").split()).casefold()


def as_iso_date(value: Any) -> str:
    """Return an ISO date for Excel, email, and manual date values."""
    if not value:
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    for pattern in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, pattern).date().isoformat()
        except ValueError:
            pass
    return text


def source_key(lead: dict[str, Any]) -> str:
    lead_id = str(lead.get("lead_id") or "").strip()
    if lead_id:
        return f"lead:{lead_id.casefold()}"
    phone = normalise_phone(lead.get("contact_no"))
    enquiry_date = as_iso_date(lead.get("enquiry_date"))
    model = normalise_text(lead.get("model"))
    if phone or enquiry_date or model:
        return f"contact:{phone}|date:{enquiry_date}|model:{model}"
    # A source record should still be storable if the supplier gave no ID.
    return "manual:" + datetime.now().strftime("%Y%m%d%H%M%S%f")


class LeadDatabase:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self._create_schema()

    def close(self) -> None:
        self.connection.close()

    def _create_schema(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY,
                source_key TEXT NOT NULL UNIQUE,
                message_id TEXT UNIQUE,
                dealer TEXT NOT NULL DEFAULT 'Muneer Heavy Earthmoving Equipment',
                lead_id TEXT,
                enquiry_date TEXT,
                customer_name TEXT,
                contact_no TEXT,
                email_id TEXT,
                alt_no TEXT,
                model TEXT,
                quantity INTEGER NOT NULL DEFAULT 1,
                voice_of_customer TEXT,
                category TEXT,
                city TEXT,
                remark TEXT NOT NULL DEFAULT '',
                responded TEXT NOT NULL DEFAULT '',
                relevance TEXT NOT NULL DEFAULT '',
                deal_temperature TEXT NOT NULL DEFAULT '',
                outcome TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'New',
                follow_up_date TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_leads_date ON leads(enquiry_date);
            CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status);
            CREATE INDEX IF NOT EXISTS idx_leads_contact ON leads(contact_no);
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS processed_email_updates (
                message_id TEXT PRIMARY KEY,
                lead_id INTEGER NOT NULL REFERENCES leads(id),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        self.connection.commit()

    def upsert_source_lead(self, lead: dict[str, Any]) -> tuple[int, bool]:
        """Insert one source lead or update only its source fields.

        Returns (database_id, created). CRM fields are never changed on an
        existing record, which protects user-entered weekly updates.
        """
        prepared = {
            "dealer": str(lead.get("dealer") or "Muneer Heavy Earthmoving Equipment").strip(),
            "lead_id": str(lead.get("lead_id") or "").strip(),
            "enquiry_date": as_iso_date(lead.get("enquiry_date")),
            "customer_name": str(lead.get("customer_name") or "").strip(),
            "contact_no": normalise_phone(lead.get("contact_no")),
            "email_id": str(lead.get("email_id") or "").strip(),
            "alt_no": normalise_phone(lead.get("alt_no")),
            "model": str(lead.get("model") or "").strip(),
            "quantity": self._quantity(lead.get("quantity")),
            "voice_of_customer": str(lead.get("voice_of_customer") or "").strip(),
            "category": str(lead.get("category") or "").strip(),
            "city": str(lead.get("city") or "").strip(),
            "message_id": str(lead.get("message_id") or "").strip() or None,
        }
        prepared["source_key"] = source_key(prepared)

        # A Call ID is the strongest key. It also fixes legacy reports where
        # the same lead was entered with slightly different contact details.
        existing = None
        if prepared["lead_id"]:
            existing = self.connection.execute(
                "SELECT id FROM leads WHERE lower(lead_id) = lower(?) LIMIT 1",
                (prepared["lead_id"],),
            ).fetchone()
        if not existing:
            existing = self.connection.execute(
                "SELECT id FROM leads WHERE source_key = ? LIMIT 1",
                (prepared["source_key"],),
            ).fetchone()
        if existing:
            fields = [key for key in prepared if key not in {"source_key", "message_id"}]
            assignments = ", ".join(f"{field} = ?" for field in fields)
            values = [prepared[field] for field in fields]
            self.connection.execute(
                f"""UPDATE leads SET {assignments},
                    message_id = COALESCE(message_id, ?), updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?""",
                values + [prepared["message_id"], existing["id"]],
            )
            self.connection.commit()
            return int(existing["id"]), False

        fields = list(prepared)
        placeholders = ", ".join("?" for _ in fields)
        cursor = self.connection.execute(
            f"INSERT INTO leads ({', '.join(fields)}) VALUES ({placeholders})",
            [prepared[field] for field in fields],
        )
        self.connection.commit()
        return int(cursor.lastrowid), True

    @staticmethod
    def _quantity(value: Any) -> int:
        try:
            return max(1, int(float(value or 1)))
        except (TypeError, ValueError):
            return 1

    def update_lead(self, lead_id: int, values: dict[str, Any]) -> None:
        allowed = {
            "dealer", "lead_id", "enquiry_date", "customer_name", "contact_no",
            "email_id", "alt_no", "model", "quantity", "voice_of_customer",
            "category", "city", *CRM_COLUMNS,
        }
        values = {key: value for key, value in values.items() if key in allowed}
        if not values:
            return
        # Excel represents empty cells as None. CRM fields are deliberately
        # NOT NULL so that blank cells in a weekly master cannot break an
        # import midway through the file.
        for key in CRM_COLUMNS:
            if key in values:
                values[key] = "" if values[key] is None else str(values[key]).strip()
        if values.get("status", None) == "":
            values["status"] = "New"
        for key in ("enquiry_date", "follow_up_date"):
            if key in values:
                values[key] = as_iso_date(values[key])
        for key in ("contact_no", "alt_no"):
            if key in values:
                values[key] = normalise_phone(values[key])
        if "quantity" in values:
            values["quantity"] = self._quantity(values["quantity"])
        if "lead_id" in values:
            duplicate = self.connection.execute(
                "SELECT id FROM leads WHERE lower(lead_id) = lower(?) AND id != ? LIMIT 1",
                (str(values["lead_id"]).strip(), lead_id),
            ).fetchone()
            if duplicate and str(values["lead_id"]).strip():
                raise ValueError("That Call ID already belongs to another lead.")
        assignments = ", ".join(f"{key} = ?" for key in values)
        self.connection.execute(
            f"UPDATE leads SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            [values[key] for key in values] + [lead_id],
        )
        self.connection.commit()

    def get_lead(self, lead_id: int) -> dict[str, Any] | None:
        row = self.connection.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
        return dict(row) if row else None

    def search(self, term: str = "", limit: int = 2000) -> list[dict[str, Any]]:
        term = term.strip()
        if term:
            token = f"%{term}%"
            rows = self.connection.execute(
                """SELECT * FROM leads WHERE lead_id LIKE ? OR customer_name LIKE ?
                   OR contact_no LIKE ? OR model LIKE ? OR city LIKE ? OR status LIKE ?
                   ORDER BY enquiry_date DESC, id DESC LIMIT ?""",
                (token, token, token, token, token, token, limit),
            ).fetchall()
        else:
            rows = self.connection.execute(
                "SELECT * FROM leads ORDER BY enquiry_date DESC, id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(row) for row in rows]

    def all_leads(self) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT * FROM leads ORDER BY enquiry_date ASC, id ASC"
        ).fetchall()
        return [dict(row) for row in rows]

    def counts(self) -> dict[str, int]:
        row = self.connection.execute(
            """SELECT COUNT(*) AS total,
               SUM(CASE WHEN status IN ('New', 'In process') THEN 1 ELSE 0 END) AS open_count,
               SUM(CASE WHEN follow_up_date <> '' AND follow_up_date < date('now')
                        AND status NOT IN ('Won', 'Lost') THEN 1 ELSE 0 END) AS overdue
               FROM leads"""
        ).fetchone()
        return {key: int(row[key] or 0) for key in row.keys()}

    def get_setting(self, key: str, default: str = "") -> str:
        row = self.connection.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return str(row["value"]) if row else default

    def set_setting(self, key: str, value: Any) -> None:
        self.connection.execute(
            """INSERT INTO settings(key, value) VALUES (?, ?)
               ON CONFLICT(key) DO UPDATE SET value = excluded.value""",
            (key, str(value or "")),
        )
        self.connection.commit()

    def find_lead_by_message_id(self, message_ids: Iterable[str]) -> dict[str, Any] | None:
        identifiers = [item.strip() for item in message_ids if item and item.strip()]
        if not identifiers:
            return None
        placeholders = ", ".join("?" for _ in identifiers)
        row = self.connection.execute(
            f"SELECT * FROM leads WHERE lower(message_id) IN ({placeholders}) LIMIT 1",
            [item.lower() for item in identifiers],
        ).fetchone()
        return dict(row) if row else None

    def append_email_remark(self, lead_id: int, message_id: str, remark: str) -> bool:
        """Append a sales-email update once, without duplicating it on re-sync."""
        if not message_id or not remark.strip():
            return False
        try:
            self.connection.execute(
                "INSERT INTO processed_email_updates(message_id, lead_id) VALUES (?, ?)",
                (message_id.strip().lower(), lead_id),
            )
        except sqlite3.IntegrityError:
            return False
        existing = self.connection.execute("SELECT remark FROM leads WHERE id = ?", (lead_id,)).fetchone()
        previous = str(existing["remark"] or "").strip() if existing else ""
        combined = f"{previous}\n\n{remark.strip()}" if previous else remark.strip()
        self.connection.execute(
            "UPDATE leads SET remark = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (combined, lead_id),
        )
        self.connection.commit()
        return True

    def import_rows(self, rows: Iterable[dict[str, Any]]) -> tuple[int, int]:
        added = updated = 0
        for row in rows:
            _, created = self.upsert_source_lead(row)
            if created:
                added += 1
            else:
                updated += 1
        return added, updated

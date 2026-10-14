# Muneer Lead CRM

A local desktop workspace for Hyundai / IndiaMART enquiries. Thunderbird brings
in the mail; the CRM captures lead details and email activity, tracks your sales
follow-ups, and exports the Excel master when you need to share it.

## Run on Windows

Requires **Python 3.11 or later** (3.11 recommended).

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python lead_crm_app.py
```

The interface uses **PySide6 / Qt**, with SQLite for storage. It runs locally;
there is no web server, account registration, or cloud upload.

### First-time setup

1. **Import Excel**: choose your existing 17-column master or the old extractor's
   10-column workbook. A backup is created before importing. New leads inherit
   the workbook's sales fields. Existing CRM notes, status, outcomes and follow-up
   dates are preserved; edit them in the CRM from now on.
2. **Email settings**: select Thunderbird's **INBOX** file and, ideally, **Sent**.
   These are mbox files without `.msf` extensions. In Thunderbird, find the local
   directory under **Account Settings → Server Settings → Local directory**.
   Enable offline message downloads under **Synchronization & Storage**.
   Thunderbird must use mbox storage; Maildir directories are not supported.
3. Enter the **exact enquiry sender email address** (comma-separated if several)
   and your sales email. Do not use the sender's display name.
4. Save settings. The first sync reads the folders and imports existing enquiries.
   Later checks process appended mail. Automatic sync runs every minute by default,
   including once when the app opens. Set the interval from 1–60 minutes.

**Keep Thunderbird downloading mail and the CRM open or minimized.** Closing the
CRM stops automatic checks. It reads downloaded mail; it does not log in to your
mail provider, send messages, or change your mailbox.

### Daily use

- New supported enquiry emails create leads automatically.
- Replies are attached to a dated activity history using message/thread IDs.
  Sent-folder sync records your outgoing updates. Incoming replies mark a lead as
  responded, but do not guess whether a deal is won/lost or invent follow-up dates.
- **Edit details / follow-up** changes customer fields, pipeline stage, next action
  date, temperature, and sales notes. Your customer-field corrections are protected
  from later source refreshes. Empty source values cannot erase known information.
- **Add note** logs a call or a sales update. The sidebar filters open leads, due
  follow-ups, and won deals. Search by name, Call ID, phone, email, model or city.
- **Export report** writes the established 17-column Excel master, including sales
  notes and email activity. Choose all leads or an enquiry-date range. This export
  is a sharing format, not a complete database backup (e.g. follow-up dates stay
  in the CRM database).
- **Rescan email folders** retries historical messages after mailbox/configuration
  changes. Repeated scans do not duplicate known messages or leads.

## Existing data and backups

The app keeps the original database location:
`%LOCALAPPDATA%\Muneer Lead CRM\lead_crm.db`. Existing leads and notes are retained;
new tables add activity history, message matching, and sync state. The new sync
performs its own initial scan instead of trusting the previous global mailbox offset.

Backups use SQLite's backup API and are stored in the database's `backups` folder:

- before every workbook import;
- before the first email sync each day;
- when you click **Back up database**.

Copy important backups to another device or your normal backup system. To restore:
close all CRM/CLI processes, move the current `lead_crm.db`, `lead_crm.db-wal` and
`lead_crm.db-shm` files out of the data folder if present, then copy the chosen
backup as `lead_crm.db`. Keep the moved files until the restored data is verified.

Old versions could mark blank Excel Win/Lost cells as Won. Existing incorrect
outcomes cannot be distinguished automatically from genuine wins: check your old
records against the original workbook. New imports fix the blank-cell bug.

## What mail formats work?

The parser supports the repository's existing Hyundai table-based enquiry format
(Date, Name, Contact No., Model No., etc., with Call ID at the end of the subject).
This is not a general parser for every supplier's email. Unsupported enquiries
are counted in the sync notice; keep the original mail and use Rescan after adding
support for a new template. Share a redacted sample when extending the parser.

Replies with missing parents wait for a matching lead. A subject-only Call ID
match also requires a known customer or your configured sales email. Unrelated
replies may remain unmatched; they are never guessed onto an arbitrary lead.
HTML-only replies have quoted blocks removed and are shown as plain text.

Mailbox rebuilds are detected by verifying the already-read byte prefix. This
avoids lost mail after compaction/replacement, but large mailboxes require disk
reads during each check. Parsing still starts from the saved position. A mailbox
changing during a scan is retried; the newest record is revisited safely.

## CLI: same database, same rules

The old independent extractor is now a CLI for the shared CRM services:

```powershell
python main.py sync --mailbox "C:\path\INBOX" --mailbox "C:\path\Sent" --sender "leads@example.com" --my-email "sales@example.com"
python main.py sync                         # use desktop settings
python main.py sync --rescan
python main.py import "old-master.xlsx"
python main.py export "weekly.xlsx" --from-date 2026-10-01 --to-date 2026-10-07
python main.py backup
```

Use `--database PATH` before the command to select a separate database. For the
GUI, `LEAD_CRM_DATA_DIR` overrides the data directory (useful for testing).

## Build a Windows executable

Build on Windows, using the environment above:

```powershell
.\.venv\Scripts\Activate.ps1
.\build_exe.ps1
```

The output is `dist\Muneer Lead CRM.exe`. Previously checked-in `dist/` and `build/`
files are historical builds; they do not contain the new interface. Rebuild from
source. The Linux development environment cannot produce a verified Windows exe.

## Tests and structure

```powershell
python -m unittest discover -s tests -v
```

Tests use temporary SQLite databases and synthetic Excel/mail files. Qt tests run
with the offscreen platform; no real account or mailbox is needed. Windows CI runs
the tests and packages the desktop executable as a downloadable artifact.

- `lead_crm_app.py`, `ui_theme.py`: Qt screens, background tasks, styling.
- `crm_database.py`: master records, atomic writes, protected edits, backups.
- `thunderbird_sync.py`: per-folder checkpoints, message identity and reply matching.
- `import_service.py`, `report_service.py`: shared import/export workflows.
- `html_parser.py`, `mailbox_reader.py`, `thread_parser.py`: parsing helpers.
- `main.py`: command-line interface to the same workflows.

Python + Qt is a suitable foundation for this single-user offline desktop app.
If multiple people later need shared live access or a mobile/browser interface,
the service layer can move behind an API with a shared database. That change does
not require throwing away the email and Excel logic.

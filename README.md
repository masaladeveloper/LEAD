# Muneer Lead Workspace

A locally hosted lead workspace for Hyundai / IndiaMART enquiries. Its main job is
turning downloaded Thunderbird emails into an organised lead master, so you can
update the sales fields instead of copying customer details into Excel by hand.

You run it on your Windows PC and use it in your browser at
**http://127.0.0.1:8000**. Python reads the mail and handles storage/reporting;
React provides the compact table, lead details and sharing tools. Everything is
saved on your PC. No account, cloud database or mail-provider login is required.

## What the first version does

- **Collect from mail:** read Inbox and optional Sent folders with one click;
  extract supported enquiries, prevent duplicates and attach matching replies.
- **Review leads:** search by Call ID, name, phone, email, model, city, requirement,
  notes or other recorded fields. Select and resize table columns; browse 25 rows
  per page. Open a customer for the complete details.
- **Edit sales fields:** response, relevance, temperature, notes, next follow-up and
  status (New, In process, Follow-up, Quotation Sent, Won, Lost or Closed).
- **Undo mistakes:** keep up to five previous versions of saved lead edits.
  Preview a version, restore it, or keep current values and clear the undo history
  with **Make permanent**. Email activity and conversations remain in the timeline.
- **Follow up:** schedule dated reminders with notes, view due/upcoming tasks and
  mark them done. Last-updated and email timestamps help track recent work.
- **Download reports:** export every enquiry from the beginning through a selected
  cutoff date in the supplied 17-column Excel layout. Attach it to your weekly
  email yourself.
- **Share a card:** select exactly which details to show, preview a PNG image,
  download it, copy it, or copy it and open WhatsApp Web for manual sharing.

## Start on Windows

### Option A: download the ready-built website

After the changes are merged, open GitHub **Actions → Build Local Web App → Run
workflow**. Download the **Muneer-Lead-Workspace** artifact from the completed run,
unzip it, and open PowerShell in its `Muneer-Lead-Workspace` folder.

Install **Python 3.11 or later**, then run once:

```powershell
.\setup.ps1
```

The download already contains the built interface, so Node.js is unnecessary for
this option. Setup creates an isolated `.web-venv` and installs the Python web
libraries. It does not install Qt or PyInstaller.

Start it each day with:

```powershell
.\start.ps1
```

Your browser opens automatically. Keep the terminal running; press **Ctrl+C** to
stop the server. Closing the browser does not stop the server. If PowerShell's
script policy blocks these local scripts, run them for this process only:

```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1
powershell -ExecutionPolicy Bypass -File .\start.ps1
```

If port 8000 is occupied, choose another:

```powershell
.\start.ps1 -Port 8010
```

### Option B: run from this repository

Install **Python 3.11+** and **Node.js 22+**, then run `setup.ps1` and `start.ps1` as
above. Setup builds the interface if `frontend/dist/index.html` is missing. After
updating frontend source, rebuild with:

```powershell
npm ci --prefix frontend
npm run build --prefix frontend
```

Restart the server after updating Python source, and refresh your browser.

### Linux / macOS or manual setup

```bash
python3 -m venv .web-venv
.web-venv/bin/python -m pip install -r requirements-web.txt
npm ci --prefix frontend
npm run build --prefix frontend
.web-venv/bin/python run_web.py
```

On Windows the equivalent manual Python executable is
`.web-venv\Scripts\python.exe`. Node is used for building and development; the
finished app serves the interface and API through one Python server.

## Connect Thunderbird

1. In Thunderbird, open **Account Settings → Server Settings → Local directory**.
2. Enable offline mail downloads in **Synchronization & Storage**.
3. In this app's **Settings**, enter the full path to the **INBOX** mbox file and,
   ideally, **Sent**. Example: `C:\Users\You\...\Mail\account\INBOX`.
4. Choose the actual mailbox file without `.msf`. Maildir storage/directories are
   not supported. A browser cannot keep unrestricted access through a file picker;
   the backend reads the local paths you enter here.
5. Enter the exact enquiry sender email address (comma-separated for multiple)
   and your sales email, then **Save email settings**.
6. Click **Collect from mail**. Keep Thunderbird downloading the mail.

The first collection scans historical enquiries. Later collections process new
mail and revisit the final record safely. **Rescan folders** retries old mail after
settings or parser changes; it does not duplicate known messages or leads.
Collection runs in the background while you work. Folder errors, unparsed
subjects/reasons (up to 100 per run) and unmatched reply counts are shown.

### Extraction rules and limits

The parser supports the existing Hyundai enquiry table (Date, Name, Contact No.,
Email Id, Model No., Category, City and Voice of Customer), common punctuation/case
variations and supported `Label: value` plain-text equivalents. Dealer and
quantity are captured when supplied. The Call ID comes from trailing digits in
the subject. Without an explicit quantity, the established default is 1. The
phone normalisation follows the existing India workflow and stores the last ten
digits; review international numbers if you use them.

Emails without Date and Name are counted as unparsed. Invalid dates/quantities
are reported rather than stopping the rest of a folder. This is not a universal
parser for every supplier's template. A redacted `.eml` sample is needed to add a
new template reliably; no actual sample was supplied for this rebuild, so tests
use synthetic messages based on the existing format.

Replies use Message-ID / In-Reply-To / References to match their lead. Subject-only
matches also require a known customer or your configured sales address. Unknown
replies remain pending until a matching lead appears. Attached `.eml` messages
cannot replace the enquiry's body. Quoted reply history is removed.

Manual customer-field edits are protected from later source refreshes. Blank
source values cannot erase known details. Incoming replies can mark the customer
as responded, but the app does not infer wins/losses or sales outcomes. Mailboxes
are read without sending messages, logging into a provider or changing the files.
Large mbox folders require prefix reads to detect compaction/replacement, so scan
time depends on mailbox size and disk speed.

## Daily workflow

1. **Collect from mail** and review any extraction notice.
2. Search/filter the compact table. Use **Columns** to choose what stays visible;
   drag a header's right edge to resize it. Column selection is saved in this browser.
3. Click a customer to edit their details and sales fields. Save only your changes.
4. Use **Activity** for call/conversation notes and email history.
5. Use **Follow-ups** to schedule a date/time and a reminder note. Scheduling can
   bring the lead's next-follow-up date forward. Completing it advances that date
   to the next remaining reminder when it corresponds to the completed reminder.
6. Use **Change history** to review the last five saved edits. Restoring also saves
   the current details as an undo point; the oldest point is dropped when over five.
   Source refreshes, conversation notes and reminders are recorded separately and
   do not consume the five manual-edit slots. **Make permanent** clears those slots,
   keeping your current lead, source-field protection and activity.
7. Download your cumulative Excel master or make a share card when needed.

If a lead changes while an edit window is open, saving reports a conflict instead
of overwriting newer data. Click **Reload lead** and reapply your intended edit.

### Reminder notifications

Due reminders are always visible in the **Follow-ups** screen and sidebar count.
Browser notifications are optional: click **Enable notifications** and allow them.
Keep the app tab open; notifications are checked about every 30 seconds and depend
on browser/Windows notification settings. The PC's clock/timezone determines
reminder due times. The app does not run as a Windows background reminder service.

### Sharing a lead image

Open **Create lead card**, choose the fields and check the preview. Unselected
customer details are absent from the image. An imported/manual lead without a
source email timestamp shows **Not recorded**, rather than an invented lead time.

- **Download PNG:** save the image for attachment/sharing.
- **Copy image:** copy the PNG in browsers supporting image clipboard writes.
- **Copy & WhatsApp:** open WhatsApp Web, copy the image, then choose a chat, paste
  with Ctrl+V and send. You control the recipient and final send.

WhatsApp links cannot attach an image automatically. If clipboard permission or
browser support blocks copying, download the PNG and attach it manually.

## Excel output

`templates/lead-master.xlsx` is a sanitised template derived from your supplied
workbook. It contains only headers, formatting and a blank row. Existing workbook
customer records are **not** imported automatically.

The report preserves the established column order, labels, widths, table styling
and date format: Dealer, Call ID, Enq Date, Customer Name, ContactNo, Email Id, Model,
Quantity, Voice of Customer, Remark, Category, Customer Responded or Not, Relevance,
Temperature, Win, Lost and Status. Current notes and received/sent email activity
are included in Remark. Text beginning with `=` remains literal text rather than
an executable Excel formula. Empty reports remain valid workbooks.

The cutoff filters the **enquiry date**, inclusively. Reports are sharing files;
reminders, complete timeline metadata, email checkpoints and undo history stay in
the database. The report is downloaded; email delivery is handled by you.

## Storage, backups and recovery

The default Windows database remains:

```text
%LOCALAPPDATA%\Muneer Lead CRM\lead_crm.db
```

Existing CRM records are retained. New tables add undo snapshots and reminders,
and a revision column protects browser edits. The web server backs up an old
schema before migrating it. Use one application at a time when working on this
shared database; keep the legacy desktop app closed during web use.

Use `LEAD_CRM_DATA_DIR` to select a separate data folder, for example in PowerShell:

```powershell
$env:LEAD_CRM_DATA_DIR = 'D:\LeadWorkspaceData'
.\start.ps1
```

Backups use SQLite's backup API and go to the database's `backups` subfolder:

- before migrating an existing pre-web database;
- before the first mail collection each day;
- when you click **Back up database** in Settings.

Copy important backups to another disk. To restore, stop the server and all
CRM/CLI processes; move `lead_crm.db`, `lead_crm.db-wal` and `lead_crm.db-shm` out of
the data folder if present, then copy the selected backup as `lead_crm.db`. Keep
the moved files until the restored data is verified. Making edits permanent clears
live undo history; an older database backup can still contain those old versions.

## Project structure

```text
web_app.py                 FastAPI routes, local write protection, background sync
run_web.py                 Server entry point and browser opening
setup.ps1 / start.ps1      Windows preparation and daily startup
frontend/src/             React + TypeScript screens, styles and PNG card rendering
frontend/dist/            Built website (generated; included in downloadable ZIP)
crm_database.py            SQLite records, protected edits, five-version undo, reminders
thunderbird_sync.py        Incremental mbox sync, identities, matching and diagnostics
html_parser.py             Supported HTML/plain-text enquiry formats
mailbox_reader.py          MIME/header decoding and attachment exclusion
thread_parser.py           Reply quote removal
report_service.py          Cumulative report selection and communication notes
report_generator.py        Excel writing, literal text and template styling
templates/lead-master.xlsx Sanitised report layout
main.py                    Existing CLI for sync/import/export/backup
build_web_release.py       ZIP packaging excluding customer data and dev tools
tests/                     Synthetic database, email, Excel, desktop and API tests
docs/desktop.md            Legacy Qt application and executable instructions
```

The original desktop entry point `lead_crm_app.py`, its styling and CLI remain
available for compatibility. The web app's installed requirements do not depend
on Qt. The old standalone CLI import workflow remains available, but the web UI
starts with email collection and manual editing rather than workbook import.

## Development and checks

For the complete regression suite, install the development requirements (these
also include Qt for the legacy desktop tests):

```bash
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
python -m ruff check --select F . --exclude frontend/node_modules
npm ci --prefix frontend
npm run build --prefix frontend
```

Tests use temporary databases and synthetic emails/workbooks. They cover repeated
scans, exact sender matching, attachments, source protection, restore/clear-history,
stale edits, reminder completion, search, reports and local request boundaries.

For frontend development, run the API and Vite in separate terminals:

```bash
python -m uvicorn web_app:app --host 127.0.0.1 --port 8000 --reload
npm run dev --prefix frontend
```

Vite proxies `/api` to port 8000. Production use needs only `start.ps1`. By default
the server binds to **127.0.0.1**, so other computers cannot connect. Write requests
use a per-server token and expected browser state. This app is intended for one
PC; adding network access or multiple users requires a separate access design.

GitHub's **Build Local Web App** workflow runs tests on Windows, builds the
interface, verifies PowerShell setup and HTTP startup, then uploads a ready-built
ZIP. Package locally with `python build_web_release.py` after building the frontend.

## Troubleshooting

- **Startup says setup is missing:** run `setup.ps1` once in the project folder.
- **Browser does not open:** visit `http://127.0.0.1:8000` while the terminal is running.
- **Port already in use:** start with `start.ps1 -Port 8010` and use that address.
- **No leads collected:** check sender addresses, mailbox file paths, offline
  downloads and the extraction notice. Display names are not sender addresses.
- **An enquiry is unparsed:** inspect its reported reason; preserve a redacted
  sample, improve the template support and rescan.
- **A reply is unmatched:** collect Inbox and Sent; a missing parent/unknown
  sender can remain pending rather than being attached to the wrong lead.
- **Save says reload:** another operation changed that lead. Reload before saving.
- **No notification:** allow notifications, keep the app tab open and check Windows
  notification settings. Follow-ups remain visible even when notifications are off.
- **Database action fails:** let collection finish and retry; check the terminal
  log and confirm the data folder is writable. Back up before attempting recovery.
- **Old export marked blank Win cells as Won:** historical errors cannot be
  distinguished from genuine wins automatically. Review those records; new
  imports/exports use explicit outcomes.

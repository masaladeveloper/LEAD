"""PC-only HTTP interface to the existing local lead workflows."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager, asynccontextmanager
from dataclasses import asdict
from datetime import date, datetime, timezone
import json
from pathlib import Path
import secrets
import sqlite3
import tempfile
import threading

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ConfigDict
from starlette.background import BackgroundTask
from starlette.middleware.trustedhost import TrustedHostMiddleware

from config import DATABASE_PATH
from crm_database import LeadDatabase, SOURCE_COLUMNS, CRM_COLUMNS, STATUSES, StaleLeadError
from report_service import export_report
from thunderbird_sync import sync_mailboxes

ROOT = Path(__file__).resolve().parent


def local_timestamp(value):
    if not value:
        return value
    stamp = datetime.fromisoformat(value)
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp.astimezone().isoformat(timespec='seconds')


def lead_for_browser(lead):
    return {**lead, 'created_at': local_timestamp(lead['created_at']), 'updated_at': local_timestamp(lead['updated_at'])}


class Edit(BaseModel):
    revision: int = Field(ge=0)
    values: dict[str, str | int | None]


class Revision(BaseModel):
    revision: int = Field(ge=0)


class Reminder(BaseModel):
    due_at: str
    note: str = Field(default='', max_length=4000)


class Note(BaseModel):
    body: str = Field(min_length=1, max_length=20000)


class Settings(BaseModel):
    model_config = ConfigDict(extra='forbid')
    mailbox_paths: list[str] = Field(max_length=2)
    sender_filter: str = ''
    my_email: str = ''


class SyncRequest(BaseModel):
    rescan: bool = False


def create_app(database_path=DATABASE_PATH, static_directory=None):
    path = Path(database_path)
    token = secrets.token_urlsafe(32)
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='mail-sync')
    lock = threading.Lock()
    job = {'running': False, 'result': None, 'error': '', 'finished_at': ''}

    @contextmanager
    def database():
        db = LeadDatabase(path)
        try:
            yield db
        finally:
            db.close()

    @asynccontextmanager
    async def lifespan(app):
        # Use SQLite's backup API before introducing new tables/columns to old data.
        if path.is_file():
            with sqlite3.connect(path) as existing:
                columns = {r[1] for r in existing.execute('PRAGMA table_info(leads)')}
                if columns and 'revision' not in columns:
                    folder = path.parent / 'backups'
                    folder.mkdir(exist_ok=True)
                    with sqlite3.connect(folder / f'pre-web-{datetime.now():%Y%m%d-%H%M%S-%f}.db') as copy:
                        existing.backup(copy)
        with database():
            pass
        yield
        executor.shutdown(wait=True)

    app = FastAPI(title='Muneer Lead Workspace', lifespan=lifespan)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=['localhost', '127.0.0.1', '[::1]', 'testserver'])

    @app.middleware('http')
    async def protect_local_writes(request: Request, call_next):
        if request.url.path.startswith('/api/') and request.method not in ('GET', 'HEAD', 'OPTIONS'):
            if not secrets.compare_digest(request.headers.get('X-CRM-Token', ''), token):
                return JSONResponse({'detail': 'Refresh the app before saving.'}, status_code=403)
        response = await call_next(request)
        if request.url.path.startswith('/api/'):
            response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    @app.exception_handler(ValueError)
    async def invalid_input(request, error):
        return JSONResponse({'detail': str(error)}, status_code=409 if isinstance(error, StaleLeadError) else 400)

    @app.exception_handler(sqlite3.Error)
    async def database_error(request, error):
        return JSONResponse({'detail': 'The database could not complete this action. Retry after collection finishes; check the server log if it persists.'}, status_code=503)

    def required(db, lead_id):
        lead = db.get_lead(lead_id)
        if not lead:
            raise HTTPException(404, 'Lead not found.')
        return lead

    def detail(db, lead_id):
        lead = required(db, lead_id)
        activity = db.activities(lead_id)
        source = next((a for a in reversed(activity) if a['kind'] == 'enquiry'), None)
        for event in activity:
            # Old email events were already stored in PC-local time; preserve those.
            if event['kind'] not in ('sent', 'received', 'enquiry') or datetime.fromisoformat(event['occurred_at']).tzinfo is not None:
                event['occurred_at'] = local_timestamp(event['occurred_at'])
        history = [{**h, 'saved_at': local_timestamp(h['saved_at'])} for h in db.history(lead_id)]
        return {'lead': lead_for_browser(lead), 'activities': activity, 'history': history,
                'reminders': db.reminders(lead_id), 'enquiry_time': source['occurred_at'] if source else ''}

    @app.get('/api/health')
    def health():
        return {'ok': True, 'application': 'Muneer Lead Workspace'}

    @app.get('/api/session')
    def session():
        return {'token': token, 'statuses': STATUSES}

    @app.get('/api/leads')
    def leads(q: str = Query('', max_length=300), status: str = 'All leads', page: int = Query(1, ge=1), size: int = Query(25, ge=10, le=100)):
        if status not in (*STATUSES, 'All leads', 'Open leads', 'Follow-ups due', 'Upcoming follow-ups'):
            raise ValueError('Choose a valid filter.')
        with database() as db:
            # Fetch one extra row to avoid loading the full database for pagination.
            rows = db.search(q, size + 1, status, offset=(page - 1) * size)
            return {'leads': [lead_for_browser(r) for r in rows[:size]], 'has_more': len(rows) > size, 'counts': db.counts()}

    @app.get('/api/leads/{lead_id}')
    def get_lead(lead_id: int):
        with database() as db:
            return detail(db, lead_id)

    @app.post('/api/leads')
    def create_lead(body: Edit):
        with database() as db, db.transaction():
            values = body.values
            if set(values) - set((*SOURCE_COLUMNS, *CRM_COLUMNS)):
                raise ValueError('The edit contains an unsupported field.')
            if not str(values.get('customer_name') or '').strip():
                raise ValueError('Customer name is required.')
            if db.find_by_call_id(values.get('lead_id')):
                raise ValueError('This Call ID already exists.')
            lead_id, created = db.upsert_source_lead(values)
            if not created:
                raise ValueError('A lead with these details already exists.')
            db.update_lead(lead_id, values)
            db.add_activity(lead_id, 'note', 'Lead created manually')
            return detail(db, lead_id)

    @app.patch('/api/leads/{lead_id}')
    def edit_lead(lead_id: int, body: Edit):
        if set(body.values) - set((*SOURCE_COLUMNS, *CRM_COLUMNS)):
            raise ValueError('The edit contains an unsupported field.')
        with database() as db:
            required(db, lead_id)
            db.edit_with_history(lead_id, body.values, body.revision)
            return detail(db, lead_id)

    @app.post('/api/leads/{lead_id}/history/{history_id}/restore')
    def restore(lead_id: int, history_id: int, body: Revision):
        with database() as db:
            db.restore_history(lead_id, history_id, body.revision)
            return detail(db, lead_id)

    @app.delete('/api/leads/{lead_id}/history')
    def permanent(lead_id: int, body: Revision):
        with database() as db:
            db.clear_history(lead_id, body.revision)
            return detail(db, lead_id)

    @app.post('/api/leads/{lead_id}/notes')
    def add_note(lead_id: int, body: Note):
        if not body.body.strip():
            raise ValueError('Enter a note before saving.')
        with database() as db:
            required(db, lead_id)
            db.add_activity(lead_id, 'note', body.body)
            return detail(db, lead_id)

    @app.get('/api/reminders')
    def reminders():
        with database() as db:
            return db.reminders()

    @app.post('/api/leads/{lead_id}/reminders')
    def add_reminder(lead_id: int, body: Reminder):
        with database() as db:
            db.add_reminder(lead_id, body.due_at, body.note)
            return detail(db, lead_id)

    @app.post('/api/reminders/{reminder_id}/complete')
    def complete(reminder_id: int):
        with database() as db:
            db.complete_reminder(reminder_id)
            return {'ok': True}

    @app.get('/api/settings')
    def get_settings():
        with database() as db:
            return {'mailbox_paths': db.mailbox_paths(), 'sender_filter': db.get_setting('sender_filter'),
                    'my_email': db.get_setting('my_email'), 'database_path': str(path.resolve())}

    @app.put('/api/settings')
    def settings(body: Settings):
        from email.utils import parseaddr
        paths = [str(Path(p.strip()).expanduser()) for p in body.mailbox_paths if p.strip()]
        if not paths:
            raise ValueError('Enter the full path to your Inbox mbox file.')
        if any(not Path(p).is_file() or p.lower().endswith('.msf') for p in paths):
            raise ValueError('Choose existing mbox files, not directories or .msf index files.')
        senders = [parseaddr(s.strip())[1] for s in body.sender_filter.split(',')]
        my_email = parseaddr(body.my_email.strip())[1]
        if not senders or any('@' not in s for s in senders) or '@' not in my_email:
            raise ValueError('Enter exact enquiry sender addresses and your sales email address.')
        with database() as db, db.transaction():
            db.set_setting('mailbox_paths', json.dumps(paths))
            db.set_setting('sender_filter', ','.join(senders))
            db.set_setting('my_email', my_email)
        return {'ok': True}

    def collect(rescan):
        try:
            with database() as db:
                if db.get_setting('last_auto_backup') != date.today().isoformat():
                    db.backup()
                    db.set_setting('last_auto_backup', date.today().isoformat())
                result = sync_mailboxes(db, db.mailbox_paths(), db.get_setting('sender_filter'), db.get_setting('my_email'), force=rescan)
                with lock:
                    job['result'] = asdict(result)
        except Exception as error:
            with lock:
                job['error'] = str(error)
        finally:
            with lock:
                job.update(running=False, finished_at=datetime.now().isoformat(timespec='seconds'))

    @app.post('/api/sync', status_code=202)
    def sync(body: SyncRequest):
        with database() as db:
            if not db.mailbox_paths() or not db.get_setting('sender_filter'):
                raise ValueError('Configure Thunderbird in Settings before collecting leads.')
        with lock:
            if job['running']:
                raise HTTPException(409, 'Collection is already running.')
            job.update(running=True, result=None, error='', finished_at='')
            executor.submit(collect, body.rescan)
            return dict(job)

    @app.get('/api/sync')
    def sync_status():
        with lock:
            return dict(job)

    @app.post('/api/backup')
    def backup():
        with database() as db:
            return {'path': str(db.backup())}

    @app.get('/api/report')
    def report(through: str = ''):
        temporary = tempfile.TemporaryDirectory(prefix='lead-report-')
        try:
            destination = Path(temporary.name) / 'Lead Master.xlsx'
            with database() as db:
                export_report(db, destination, to_date=through)
            return FileResponse(destination, filename=f'Lead Master through {through or date.today().isoformat()}.xlsx',
                                media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                                background=BackgroundTask(temporary.cleanup))
        except Exception:
            temporary.cleanup()
            raise

    static = Path(static_directory) if static_directory else ROOT / 'frontend' / 'dist'
    if static.is_dir():
        app.mount('/', StaticFiles(directory=static, html=True), name='frontend')
    else:
        @app.get('/')
        def missing_frontend():
            return JSONResponse({'detail': 'Build the interface with npm ci --prefix frontend and npm run build --prefix frontend.'}, status_code=503)
    return app


app = create_app()

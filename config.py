"""Shared paths. User settings live in the database, never in source code."""
import os
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get('LEAD_CRM_DATA_DIR') or (Path(os.environ.get('LOCALAPPDATA', APP_DIR)) / 'Muneer Lead CRM'))
DATABASE_PATH = DATA_DIR / 'lead_crm.db'
OUTPUT_DIR = Path('output')
LOG_DIR = DATA_DIR / 'logs'
# Compatibility for external scripts; the app asks for the mailbox on first run.
MBOX_FILE = Path(os.environ.get('LEAD_CRM_MAILBOX', 'INBOX'))

"""Shared paths. User settings live in the database, never in source code."""
import os
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get('LEAD_CRM_DATA_DIR') or (Path(os.environ.get('LOCALAPPDATA', APP_DIR)) / 'Muneer Lead CRM'))
DATABASE_PATH = DATA_DIR / 'lead_crm.db'

"""CLI for the same CRM services used by the desktop app."""
from __future__ import annotations

import argparse
import json
from config import DATABASE_PATH
from crm_database import LeadDatabase
from import_service import import_workbook
from report_service import export_report
from thunderbird_sync import sync_mailboxes


def main():
    parser = argparse.ArgumentParser(description='Muneer Lead CRM — shared master database')
    parser.add_argument('--database', default=str(DATABASE_PATH), help='Database file (defaults to the desktop database)')
    commands = parser.add_subparsers(dest='command', required=True)
    sync = commands.add_parser('sync', help='Import new enquiries and email activity')
    sync.add_argument('--mailbox', action='append', help='Mbox file; repeat for Inbox and Sent')
    sync.add_argument('--sender', help='Exact enquiry sender email, or comma-separated addresses')
    sync.add_argument('--my-email', help='Your sales email address')
    sync.add_argument('--rescan', action='store_true', help='Rebuild mailbox positions without duplicating leads or activity')
    imp = commands.add_parser('import', help='Import the existing Excel master or extractor workbook')
    imp.add_argument('workbook')
    report = commands.add_parser('export', help='Export a 17-column Excel master including email updates')
    report.add_argument('destination')
    report.add_argument('--from-date', default='')
    report.add_argument('--to-date', default='')
    commands.add_parser('backup', help='Create a database backup')
    args = parser.parse_args()
    database = LeadDatabase(args.database)
    try:
        if args.command == 'sync':
            paths = args.mailbox or json.loads(database.get_setting('mailbox_paths', '[]'))
            if not paths and database.get_setting('mailbox_path'):
                paths = [database.get_setting('mailbox_path')]
            if not paths:
                parser.error('Configure Email settings or pass --mailbox.')
            result = sync_mailboxes(database, paths, args.sender or database.get_setting('sender_filter'), args.my_email or database.get_setting('my_email'), force=args.rescan)
            print(f'{result.new_leads} new leads; {result.remarks_added} email updates; {result.unparsed} unparsed; {result.pending} unmatched replies')
            if result.errors:
                for error in result.errors:
                    print(error)
                return 1
        elif args.command == 'import':
            result = import_workbook(database, args.workbook)
            print(f'{result.added} added; {result.updated} refreshed. Backup: {result.backup}')
        elif args.command == 'export':
            count = export_report(database, args.destination, args.from_date, args.to_date)
            print(f'Exported {count} leads to {args.destination}')
        else:
            print(database.backup())
    except (ValueError, OSError) as error:
        parser.exit(1, f'{error}\n')
    finally:
        database.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

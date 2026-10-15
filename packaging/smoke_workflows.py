"""Exercise bundled mail and Excel libraries only during the build's smoke check."""
import sys

if '--smoke-test' in sys.argv:
    import mailbox
    import os
    from email.message import EmailMessage
    from pathlib import Path
    from tempfile import TemporaryDirectory

    from crm_database import LeadDatabase
    from import_service import import_workbook
    from report_service import export_report
    from thunderbird_sync import sync_mailboxes

    # Always use synthetic records in a disposable folder, regardless of app settings.
    with TemporaryDirectory() as directory:
        root = Path(directory)
        message = EmailMessage()
        message['From'] = 'leads@example.test'
        message['Subject'] = 'Sales Inquiry - Regular - 123'
        message['Message-ID'] = '<build-check@example.test>'
        message.set_content('<table><tr><td>Name</td><td>Build check</td></tr>'
                            '<tr><td>Date</td><td>2026-01-01</td></tr></table>', subtype='html')
        box = mailbox.mbox(root / 'INBOX')
        try:
            box.add(message)
        finally:
            box.close()
        os.utime(root / 'INBOX', (1, 1))
        database = LeadDatabase(root / 'source.db')
        restored = LeadDatabase(root / 'restored.db')
        try:
            result = sync_mailboxes(database, [root / 'INBOX'], 'leads@example.test',
                                    'sales@example.test', settle_seconds=0)
            if result.errors or result.new_leads != 1:
                raise RuntimeError('Packaged email import failed.')
            export_report(database, root / 'report.xlsx')
            imported = import_workbook(restored, root / 'report.xlsx')
            if imported.added != 1 or restored.find_by_call_id('123')['customer_name'] != 'Build check':
                raise RuntimeError('Packaged Excel round trip failed.')
        finally:
            restored.close()
            database.close()

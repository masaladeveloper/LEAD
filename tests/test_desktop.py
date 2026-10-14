"""Real Qt widgets tested offscreen with a disposable database."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import tempfile
import json
import mailbox
import unittest
from unittest.mock import patch
from pathlib import Path

from PySide6.QtCore import QElapsedTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from lead_crm_app import LeadCRMApp, LeadForm, SettingsDialog
from ui_theme import STYLE


class Desktop(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyle('Fusion')
        cls.app.setStyleSheet(STYLE)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.window = LeadCRMApp(Path(self.temp.name) / 'crm.db', auto_start=False)
        self.window.timer.stop()
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        self.window.close()
        self.app.processEvents()
        self.temp.cleanup()

    def wait_for_job(self):
        clock = QElapsedTimer()
        clock.start()
        while self.window.worker is not None and clock.elapsed() < 5000:
            QTest.qWait(10)
        self.assertIsNone(self.window.worker)

    def test_create_edit_search_and_note(self):
        dialog = LeadForm(self.window)
        dialog.fields['customer_name'].setText('Synthetic Buyer')
        dialog.fields['lead_id'].setText('101')
        dialog.fields['enquiry_date'].setText('2026-10-14')
        dialog.save()
        self.assertEqual(dialog.result(), 1)
        self.window.refresh()
        self.assertEqual(self.window.table.rowCount(), 1)
        with patch('lead_crm_app.QInputDialog.getMultiLineText', return_value=('Called; follow up Friday.', True)):
            self.window.add_note()
        lead = self.window.database.find_by_call_id('101')
        self.assertIn('Called;', self.window.database.activities(lead['id'])[0]['body'])
        dialog = LeadForm(self.window, lead)
        dialog.fields['status'].setCurrentText('Won')
        dialog.save()
        self.assertEqual(self.window.database.get_lead(lead['id'])['outcome'], 'Won')
        self.window.search.setText('no match')
        self.window.refresh()
        self.assertEqual(self.window.table.rowCount(), 0)
        self.assertFalse(self.window.note_button.isEnabled())

    def test_background_error_recovers_controls(self):
        def fail(database):
            raise FileNotFoundError('Synthetic missing mailbox')
        self.window.start_job(fail, lambda result: self.fail('Expected failure'), 'Working')
        self.wait_for_job()
        self.assertIn('Synthetic missing mailbox', self.window.notice.text())
        self.assertTrue(self.window.sync_button.isEnabled())
        self.window.start_job(lambda database: 5, lambda result: self.window.notice.setText(str(result)), 'Retrying')
        self.wait_for_job()
        self.assertEqual(self.window.notice.text(), '5')

    def test_automatic_timer_imports_mail_without_clicking(self):
        from test_workflows import enquiry
        path = Path(self.temp.name) / 'INBOX'
        box = mailbox.mbox(path)
        box.add(enquiry())
        box.close()
        os.utime(path, (1,1))
        self.window.database.set_setting('mailbox_paths', json.dumps([str(path)]))
        self.window.database.set_setting('sender_filter', 'leads@example.test')
        self.window.database.set_setting('my_email', 'sales@example.test')
        self.window.timer.setSingleShot(True)
        self.window.timer.start(10)
        QTest.qWait(30)
        self.wait_for_job()
        self.assertEqual(self.window.table.rowCount(), 1)
        self.assertIn('1 new leads', self.window.notice.text())
        self.assertTrue(list((Path(self.temp.name) / 'backups').glob('*.db')))

    def test_open_form_does_not_revert_new_sync_values(self):
        lead_id, _ = self.window.database.upsert_source_lead({'lead_id':'101','customer_name':'First','city':'Pune'})
        dialog = LeadForm(self.window, self.window.database.get_lead(lead_id))
        self.window.database.upsert_source_lead({'lead_id':'101','city':'Mumbai'})
        dialog.fields['remark'].setPlainText('New note')
        dialog.save()
        self.assertEqual(self.window.database.get_lead(lead_id)['city'], 'Mumbai')
        self.assertEqual(self.window.database.get_lead(lead_id)['remark'], 'New note')

    def test_close_waits_for_pending_completion_signal(self):
        self.window.start_job(lambda database: 1, lambda result: None, 'Working')
        self.assertTrue(self.window.worker.wait(3000))
        # The thread stopped, but its completion signal has not reached the UI yet.
        self.window.close()
        self.assertTrue(self.window.isVisible())
        self.wait_for_job()
        self.assertEqual(self.window.database.counts()['total'], 0)

    def test_settings_reject_missing_files(self):
        dialog = SettingsDialog(self.window)
        dialog.paths[0].setText('/not/a/mailbox')
        dialog.save()
        self.assertEqual(dialog.result(), 0)
        self.assertIn('existing mailbox', dialog.error.text())


if __name__ == '__main__':
    unittest.main()

"""Useful outgoing text and persistent incoming review requests."""
import unittest
import tempfile
from pathlib import Path
from crm_database import LeadDatabase
from thread_parser import clean_update


class ReplyUpdates(unittest.TestCase):
    def test_clean_update_preserves_paragraphs_and_meaningful_thanks(self):
        samples = {
            'Dear Sir,\n\nCustomer needs 215L.\n\nLoan approved.\nThanks & Regards,\nSales': 'Customer needs 215L.\n\nLoan approved.',
            'hello mam\nGreetings of the day!\nWill buy in two months.\nBest regards, Sales': 'Will buy in two months.',
            'Hi Alex, Loan approved.\nRegards,\nSales': 'Loan approved.',
            'Dear John Smith\nFollow up on Friday.\n--\nSales': 'Follow up on Friday.',
            'Thank you for confirming the order.\nThanks to the bank, loan approved.': 'Thank you for confirming the order.\nThanks to the bank, loan approved.',
            'Quotation sent.\nOn Wed, Buyer wrote:\nPlease quote.': 'Quotation sent.',
            'Dear Sir,\nRegards,\nSales': '',
            'Hi team,\nCalled today.\nSent from my iPhone': 'Called today.',
        }
        for source, expected in samples.items():
            with self.subTest(source=source):
                self.assertEqual(clean_update(source), expected)

    def test_upgrade_does_not_backfill_old_received_mail(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'crm.db'
            db = LeadDatabase(path)
            lead, _ = db.upsert_source_lead({'lead_id':'old', 'customer_name':'Existing'})
            db.add_activity(lead, 'received', 'An old reply')
            db.connection.execute('DROP TABLE reply_requests')
            db.connection.commit()
            db.close()
            db = LeadDatabase(path)
            self.assertEqual(db.reply_requests(), [])
            db.add_activity(lead, 'received', 'New request', message_id='<new@test>')
            self.assertEqual(len(db.reply_requests()), 1)
            self.assertEqual(len(db.activities(lead)), 2)
            db.close()

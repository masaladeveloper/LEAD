"""HTTP and storage regressions for the PC-only app, using synthetic data."""
from io import BytesIO
import mailbox
import os
from pathlib import Path
import tempfile
import time
import unittest

from fastapi.testclient import TestClient
from openpyxl import load_workbook
from crm_database import LeadDatabase
from web_app import create_app
from thunderbird_sync import sync_mailboxes
from test_workflows import enquiry


class Web(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.path = self.root / 'crm.db'
        with_db = LeadDatabase(self.path)
        self.lead_id, _ = with_db.upsert_source_lead({'lead_id':'101','customer_name':'Synthetic Buyer',
            'contact_no':'9876543210','enquiry_date':'2026-10-14','city':'Pune','model':'HX220'})
        with_db.close()
        self.client = TestClient(create_app(self.path))
        self.client.__enter__()
        self.token = {'X-CRM-Token':self.client.get('/api/session').json()['token']}

    def tearDown(self):
        self.client.__exit__(None,None,None)
        self.temp.cleanup()

    def request(self, method, path, body=None):
        return self.client.request(method, path, headers=self.token, json=body)

    def detail(self):
        return self.client.get(f'/api/leads/{self.lead_id}').json()

    def edit(self, values):
        d=self.detail()
        response=self.request('PATCH',f'/api/leads/{self.lead_id}',{'revision':d['lead']['revision'],'values':values})
        self.assertEqual(response.status_code,200,response.text)
        return response.json()

    def test_local_write_protection_and_host_validation(self):
        self.assertEqual(self.client.post('/api/backup').status_code,403)
        self.assertEqual(self.client.get('/api/health',headers={'host':'evil.example'}).status_code,400)
        self.assertEqual(self.request('POST','/api/backup').status_code,200)

    def test_edit_restoration_and_five_change_limit(self):
        for number in range(7):
            d=self.edit({'remark':f'Note {number}'})
        self.assertEqual(len(d['history']),5)
        self.assertEqual(d['history'][-1]['snapshot']['remark'],'Note 1')
        target=d['history'][0]
        r=self.request('POST',f'/api/leads/{self.lead_id}/history/{target["id"]}/restore',{'revision':d['lead']['revision']})
        self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(r.json()['lead']['remark'],'Note 5')
        self.assertEqual(r.json()['history'][0]['snapshot']['remark'],'Note 6')

    def test_permanent_keeps_details_notes_and_protection(self):
        d=self.edit({'customer_name':'Corrected','remark':'Keep this'})
        self.request('POST',f'/api/leads/{self.lead_id}/notes',{'body':'A conversation'})
        r=self.request('DELETE',f'/api/leads/{self.lead_id}/history',{'revision':d['lead']['revision']})
        self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(r.json()['history'],[])
        self.assertEqual(r.json()['lead']['remark'],'Keep this')
        self.assertEqual(r.json()['activities'][0]['body'],'A conversation')
        db=LeadDatabase(self.path)
        db.upsert_source_lead({'lead_id':'101','customer_name':'Old email'})
        self.assertEqual(db.get_lead(self.lead_id)['customer_name'],'Corrected')
        db.close()

    def test_restore_recovers_source_override_state(self):
        d=self.edit({'city':'Mumbai'})
        self.request('POST',f'/api/leads/{self.lead_id}/history/{d["history"][0]["id"]}/restore',{'revision':d['lead']['revision']})
        db=LeadDatabase(self.path)
        db.upsert_source_lead({'lead_id':'101','city':'Nagpur'})
        self.assertEqual(db.get_lead(self.lead_id)['city'],'Nagpur')
        db.close()

    def test_stale_edit_cannot_overwrite_and_noop_does_not_add_history(self):
        revision=self.detail()['lead']['revision']
        d=self.edit({'status':'Won'})
        stale=self.request('PATCH',f'/api/leads/{self.lead_id}',{'revision':revision,'values':{'status':'Lost'}})
        self.assertEqual(stale.status_code,409)
        unchanged=self.edit({'status':'Won'})
        self.assertEqual(len(unchanged['history']),len(d['history']))
        self.assertEqual(unchanged['lead']['outcome'],'Won')

    def test_validation_and_conflicts_rollback_history(self):
        db=LeadDatabase(self.path)
        db.upsert_source_lead({'lead_id':'202','customer_name':'Other'})
        db.close()
        revision=self.detail()['lead']['revision']
        for values in ({'lead_id':'202'}, {'enquiry_date':'invalid'}, {'customer_name':''}, {'quantity':0}, {'quantity':10**30}):
            r=self.request('PATCH',f'/api/leads/{self.lead_id}',{'revision':revision,'values':values})
            self.assertEqual(r.status_code,400,r.text)
        self.assertEqual(self.detail()['history'],[])
        self.assertEqual(self.detail()['lead']['lead_id'],'101')

    def test_search_across_notes_source_fields_and_pagination(self):
        self.request('POST',f'/api/leads/{self.lead_id}/notes',{'body':'special conversation'})
        for term in ('9876543210','Synthetic','101','HX220','Pune','special conversation'):
            self.assertEqual(len(self.client.get('/api/leads',params={'q':term}).json()['leads']),1)
        db=LeadDatabase(self.path)
        for n in range(31):
            db.upsert_source_lead({'lead_id':str(500+n),'customer_name':f'Buyer {n}'})
        db.close()
        self.assertTrue(self.client.get('/api/leads').json()['has_more'])
        self.assertEqual(len(self.client.get('/api/leads?page=2').json()['leads']),7)
        self.assertEqual(self.client.get('/api/leads?size=1000').status_code,422)

    def test_schedule_complete_reminder_and_follow_up_filter(self):
        r=self.request('POST',f'/api/leads/{self.lead_id}/reminders',{'due_at':'2000-01-01T10:00','note':'Call about quotation'})
        self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(r.json()['lead']['follow_up_date'],'2000-01-01')
        reminder=r.json()['reminders'][0]
        self.assertEqual(self.request('POST',f'/api/reminders/{reminder["id"]}/complete').status_code,200)
        self.assertTrue(self.client.get('/api/reminders').json()[0]['completed_at'])
        self.assertEqual(self.detail()['lead']['follow_up_date'],'')
        self.edit({'follow_up_date':'2000-01-01'})
        self.assertEqual(len(self.client.get('/api/leads?status=Follow-ups%20due').json()['leads']),1)
        self.edit({'status':'Won'})
        self.assertEqual(self.client.get('/api/leads?status=Follow-ups%20due').json()['leads'],[])
        self.assertEqual(self.request('POST',f'/api/leads/{self.lead_id}/reminders',{'due_at':'bad'}).status_code,400)

    def test_report_uses_supplied_template_and_cumulative_cutoff(self):
        db=LeadDatabase(self.path)
        db.upsert_source_lead({'lead_id':'old','customer_name':'Older','enquiry_date':'2025-01-01'})
        db.close()
        response=self.client.get('/api/report?through=2025-12-31')
        self.assertEqual(response.status_code,200)
        book=load_workbook(BytesIO(response.content))
        template=load_workbook('templates/lead-master.xlsx')
        self.assertEqual([c.value for c in book.active[1]], [c.value for c in template.active[1]])
        self.assertEqual(book.active['D2'].value,'Older')
        self.assertEqual(book.active.max_row,2)
        self.assertEqual(book.active.column_dimensions['F'].width,template.active.column_dimensions['F'].width)
        self.assertEqual(book.active['C2'].number_format,'dd"-"mm"-"yyyy')
        book.close();template.close()
        self.assertEqual(self.client.get('/api/report?through=bad').status_code,400)

    def test_settings_validation_and_background_sync(self):
        self.assertEqual(self.request('POST','/api/sync',{}).status_code,400)
        path=self.root/'INBOX'; box=mailbox.mbox(path)
        box.add(enquiry('303','<lead303@example.test>'));box.close();os.utime(path,(1,1))
        settings={'mailbox_paths':[str(path)],'sender_filter':'leads@example.test','my_email':'sales@example.test'}
        bad={**settings,'mailbox_paths':[str(path)+'.msf']}
        self.assertEqual(self.request('PUT','/api/settings',bad).status_code,400)
        self.assertEqual(self.request('PUT','/api/settings',settings).status_code,200)
        self.assertEqual(self.request('POST','/api/sync',{}).status_code,202)
        for _ in range(100):
            status=self.client.get('/api/sync').json()
            if not status['running']: break
            time.sleep(.02)
        self.assertFalse(status['running'])
        self.assertEqual(status['result']['new_leads'],1)
        self.assertEqual(self.client.get('/api/leads?q=303').json()['leads'][0]['lead_id'],'303')
        self.assertTrue(list((self.root/'backups').glob('*.db')))

    def test_unknown_lead_and_unsupported_fields(self):
        self.assertEqual(self.client.get('/api/leads/999').status_code,404)
        r=self.request('PATCH',f'/api/leads/{self.lead_id}',{'revision':0,'values':{'source_key':'evil'}})
        self.assertEqual(r.status_code,400)
        r=self.request('POST','/api/leads',{'revision':0,'values':{'customer_name':'Invalid','source_key':'evil'}})
        self.assertEqual(r.status_code,400)

    def test_existing_schema_is_backed_up_before_migration(self):
        import sqlite3
        legacy = self.root / 'legacy.db'
        db = LeadDatabase(legacy)
        db.upsert_source_lead({'lead_id':'legacy','customer_name':'Existing synthetic buyer'})
        db.close()
        with sqlite3.connect(legacy) as connection:
            connection.execute('ALTER TABLE leads DROP COLUMN revision')
            connection.execute('DROP TABLE lead_history')
            connection.execute('DROP TABLE reminders')
        with TestClient(create_app(legacy)) as client:
            self.assertEqual(client.get('/api/leads').json()['leads'][0]['customer_name'], 'Existing synthetic buyer')
        backups = list((self.root / 'backups').glob('pre-web-*.db'))
        self.assertEqual(len(backups), 1)
        with sqlite3.connect(backups[0]) as connection:
            self.assertNotIn('revision', {row[1] for row in connection.execute('PRAGMA table_info(leads)')})
            self.assertEqual(connection.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
            self.assertEqual(connection.execute('SELECT customer_name FROM leads').fetchone()[0], 'Existing synthetic buyer')

    def test_manual_lead_create_and_duplicate_validation(self):
        r=self.request('POST','/api/leads',{'revision':0,'values':{'customer_name':'Manual','lead_id':'new','status':'Follow-up'}})
        self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(r.json()['lead']['status'],'Follow-up')
        self.assertEqual(self.request('POST','/api/leads',{'revision':0,'values':{'customer_name':'Duplicate','lead_id':'new'}}).status_code,400)


class Extraction(unittest.TestCase):
    def test_variants_plain_text_bad_quantity_and_checkpoint_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);db=LeadDatabase(root/'crm.db'); path=root/'INBOX'
            html=enquiry('201','<variant@example.test>')
            html.clear_content();html.set_content('<table><tr><td>DATE :</td><td>14-Oct-2026</td></tr><tr><td>customer name</td><td>Variant Buyer</td></tr><tr><td>mobile no:</td><td>9876543211</td></tr><tr><td>Quantity</td><td>3</td></tr></table>',subtype='html')
            plain=enquiry('202','<plain@example.test>');plain.clear_content();plain.set_content('Date: 14/10/2026\nName: Plain Buyer\nPhone: 9876543212\nModel No: HX220')
            bad=enquiry('203','<bad@example.test>');bad.clear_content();bad.set_content('<table><tr><td>Date</td><td>2026-10-14</td></tr><tr><td>Name</td><td>Bad Quantity</td></tr><tr><td>Quantity</td><td>many</td></tr></table>',subtype='html')
            box=mailbox.mbox(path)
            for msg in (html,bad,plain):box.add(msg)
            box.close();os.utime(path,(1,1))
            result=sync_mailboxes(db,[path],'leads@example.test','sales@example.test',settle_seconds=0)
            self.assertEqual(result.errors,[])
            self.assertEqual((result.new_leads,result.unparsed),(2,1))
            self.assertIn('Quantity',result.issues[0]['reason'])
            self.assertEqual(db.find_by_call_id('201')['quantity'],3)
            self.assertEqual(db.find_by_call_id('202')['customer_name'],'Plain Buyer')
            key=db.connection.execute("SELECT key FROM settings WHERE key LIKE 'mailbox_v2:%'").fetchone()[0]
            db.set_setting(key,'[invalid JSON')
            retry=sync_mailboxes(db,[path],'leads@example.test','sales@example.test',settle_seconds=0)
            self.assertEqual(retry.new_leads,0)
            self.assertEqual(db.counts()['total'],2)
            db.close()


if __name__ == '__main__':
    unittest.main()

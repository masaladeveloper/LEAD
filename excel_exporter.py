"""Compatibility adapter for scripts using the original extractor API."""
from report_generator import generate_weekly_report

MAPPING = {'Lead ID':'lead_id', 'Date':'enquiry_date', 'Name':'customer_name',
    'Contact No.':'contact_no', 'Email Id':'email_id', 'Alt No.':'alt_no',
    'Model No.':'model', 'Category':'category', 'City':'city', 'Voice of Customer':'voice_of_customer'}


def export_excel(leads, filename='output/Leads_Report.xlsx'):
    return generate_weekly_report(({MAPPING.get(k, k):v for k,v in lead.items()} for lead in leads), filename)

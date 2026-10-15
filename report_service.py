"""Exports share the CRM master and include email activity in the Remark column."""
from crm_database import as_iso_date
from report_generator import generate_weekly_report


def lead_remarks(database, lead):
    """Use the same dated paragraphs for the app, cards and the Excel Remark column."""
    events = [f"{a['occurred_at']} · {a['kind'].title()}" +
              (f" · {a['sender']}" if a['sender'] else '') + f"\n{a['body']}"
              for a in reversed(database.activities(lead['id']))
              if a['kind'] in ('sent', 'received', 'email', 'note')]
    return '\n\n'.join(filter(None, [lead.get('remark'), *events]))


def export_report(database, destination, from_date='', to_date=''):
    start, end = as_iso_date(from_date), as_iso_date(to_date)
    if start and end and start > end:
        raise ValueError('The start date must be before the end date.')
    leads = database.all_leads(start, end)
    for lead in leads:
        lead['remark'] = lead_remarks(database, lead)
    generate_weekly_report(leads, destination)
    return len(leads)

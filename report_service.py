"""Exports share the CRM master and include email activity in the Remark column."""
from crm_database import as_iso_date
from report_generator import generate_weekly_report


def export_report(database, destination, from_date='', to_date=''):
    start, end = as_iso_date(from_date), as_iso_date(to_date)
    if start and end and start > end:
        raise ValueError('The start date must be before the end date.')
    leads = database.all_leads(start, end)
    for lead in leads:
        emails = [f"{a['occurred_at']} · {a['sender']}\n{a['body']}" for a in reversed(database.activities(lead['id'])) if a['kind'] in ('sent', 'received', 'email', 'note')]
        lead['remark'] = '\n\n'.join(filter(None, [lead.get('remark'), *emails]))
    generate_weekly_report(leads, destination)
    return len(leads)

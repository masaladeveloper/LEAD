from datetime import datetime

from config import MBOX_FILE
from mailbox_reader import read_mailbox
from email_filter import (
    parse_email_date,
    sender_matches,
)
from html_parser import parse_html
from excel_exporter import export_excel


def main():

    sender = input("Sender email: ").strip()

    from_date = datetime.strptime(
        input("From Date (YYYY-MM-DD): ").strip(),
        "%Y-%m-%d",
    ).date()

    to_date = datetime.strptime(
        input("To Date (YYYY-MM-DD): ").strip(),
        "%Y-%m-%d",
    ).date()

    print("\nSearching...\n")

    count = 0
    leads = []
    duplicates = set()

    for mail in read_mailbox(MBOX_FILE):

        # Filter by sender
        if not sender_matches(mail.sender, sender):
            continue

        # Parse Hyundai HTML + Subject
        lead = parse_html(
            mail.html,
            mail.subject
        )

        if not lead:
            continue

        # Filter using Hyundai enquiry date
        lead_date_str = lead.get("Date", "").strip()

        if not lead_date_str:
            continue

        try:
            lead_date = datetime.strptime(
                lead_date_str,
                "%Y-%m-%d"
            ).date()
        except Exception:
            continue

        if not (from_date <= lead_date <= to_date):
            continue

        count += 1

        # Remove duplicate leads using Lead ID
        lead_id = lead.get("Lead ID", "").strip()

        if lead_id:
            key = lead_id
        else:
            key = (
                lead.get("Contact No.", "").strip(),
                lead_date_str,
            )

        if key in duplicates:
            continue

        duplicates.add(key)
        leads.append(lead)

        print("=" * 70)
        print(f"Match : {count}")
        print(f"From      : {mail.sender}")
        print(f"Email Date: {parse_email_date(mail.date)}")
        print(f"Lead Date : {lead_date}")
        print(f"Subject   : {mail.subject}")
        print("-" * 70)

        for k, v in lead.items():
            print(f"{k:20} : {v}")

        print("=" * 70)
        print()

    print()
    print(f"Total matching leads : {count}")
    print(f"Unique leads         : {len(leads)}")

    export_excel(leads)


if __name__ == "__main__":
    main()
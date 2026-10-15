"""
Extract Hyundai lead information from HTML
"""

import re
from bs4 import BeautifulSoup


FIELD_MAP = {
    "Date": "Date",
    "Name": "Name",
    "Contact No.": "Contact No.",
    "Contact No": "Contact No.",
    "Email Id": "Email Id",
    "Alt No.": "Alt No.",
    "Alt No": "Alt No.",
    "Model No.": "Model No.",
    "Model No": "Model No.",
    "Category": "Category",
    "City": "City",
    "Voice of Customer": "Voice of Customer",
    "Customer Name": "Name",
    "Phone": "Contact No.",
    "Mobile No": "Contact No.",
    "Email": "Email Id",
    "Email ID": "Email Id",
    "Quantity": "Quantity",
    "Dealer": "Dealer",
}


def field_name(value):
    """Accept punctuation/case variations while keeping the known enquiry schema."""
    return re.sub(r'[^a-z0-9]', '', value.casefold())


NORMALISED_FIELDS = {field_name(key): value for key, value in FIELD_MAP.items()}


def clean(text: str) -> str:
    if not text:
        return ""

    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def extract_lead_id(subject: str) -> str:
    """
    Extract Lead ID from subject.

    Examples:
        HIGH Priority Sales Inquiry - Regular - 131017
        Re: Sales Inquiry - Regular - 126304
    """

    if not subject:
        return ""

    match = re.search(r"(\d+)\s*$", subject)

    if match:
        return match.group(1)

    return ""


def parse_html(html, subject=""):

    soup = BeautifulSoup(html, "lxml")

    lead = {}

    # Lead ID comes from the subject, not the HTML
    lead["Lead ID"] = extract_lead_id(subject)

    rows = soup.find_all("tr")

    for row in rows:

        cols = row.find_all(["td", "th"], recursive=False)

        if len(cols) < 2:
            continue

        key = clean(cols[0].get_text(" ", strip=True))
        value = clean(cols[1].get_text(" ", strip=True))

        key = key.rstrip(":").strip()

        if field_name(key) in NORMALISED_FIELDS:

            field = NORMALISED_FIELDS[field_name(key)]

            if field == "Category":
                value = value.upper().replace(" LEAD", "").title()

            lead[field] = value

    return lead


def parse_plain_text(text, subject=''):
    """Support label: value messages from the same supplier when HTML is absent."""
    lead = {'Lead ID': extract_lead_id(subject)}
    for line in text.splitlines():
        key, separator, value = line.partition(':')
        field = NORMALISED_FIELDS.get(field_name(key))
        if separator and field and clean(value):
            lead[field] = clean(value)
    return lead

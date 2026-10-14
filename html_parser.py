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
}


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

        cols = row.find_all(["td", "th"])

        if len(cols) < 2:
            continue

        key = clean(cols[0].get_text(" ", strip=True))
        value = clean(cols[1].get_text(" ", strip=True))

        key = key.rstrip(":").strip()

        if key in FIELD_MAP:

            field = FIELD_MAP[key]

            if field == "Category":
                value = value.upper().replace(" LEAD", "").title()

            lead[field] = value

    return lead
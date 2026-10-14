"""
Filter emails by sender and date
"""
from datetime import datetime
from email.utils import parsedate_to_datetime


def parse_email_date(date_string):
    """
    Convert an email Date header into a datetime.date object.
    """
    try:
        return parsedate_to_datetime(date_string).date()
    except Exception:
        return None


def sender_matches(sender, search_sender):
    """
    Case-insensitive sender match.
    """
    return search_sender.lower() in sender.lower()


def date_in_range(email_date, from_date, to_date):
    """
    Check whether email_date falls within the selected range.
    """
    if email_date is None:
        return False

    return from_date <= email_date <= to_date 
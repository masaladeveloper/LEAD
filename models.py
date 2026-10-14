"""
Dataclasses used by the application
"""

from dataclasses import dataclass


@dataclass
class EmailMessage:
    sender: str
    subject: str
    date: str

    message_id: str
    in_reply_to: str
    references: str

    html: str
    text: str
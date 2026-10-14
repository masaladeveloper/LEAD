"""
Read Thunderbird mbox mailbox
"""

import mailbox
from email.header import decode_header

from models import EmailMessage


def decode(value):
    if not value:
        return ""

    parts = decode_header(value)
    result = ""

    for text, enc in parts:

        if isinstance(text, bytes):
            result += text.decode(enc or "utf-8", errors="ignore")

        else:
            result += text

    return result


def get_body(msg):

    html = ""
    text = ""

    if msg.is_multipart():

        for part in msg.walk():

            ctype = part.get_content_type()

            try:

                payload = part.get_payload(decode=True)

                if not payload:
                    continue

                charset = part.get_content_charset() or "utf-8"

                body = payload.decode(charset, errors="ignore")

                if ctype == "text/html":
                    html = body

                elif ctype == "text/plain":
                    text = body

            except Exception:
                pass

    else:

        payload = msg.get_payload(decode=True)

        if payload:

            charset = msg.get_content_charset() or "utf-8"

            body = payload.decode(charset, errors="ignore")

            if msg.get_content_type() == "text/html":
                html = body

            else:
                text = body

    return html, text


def read_mailbox(path):

    box = mailbox.mbox(path)

    for msg in box:

        sender = decode(msg.get("From"))
        subject = decode(msg.get("Subject"))
        date = decode(msg.get("Date"))

        message_id = decode(msg.get("Message-ID"))
        in_reply_to = decode(msg.get("In-Reply-To"))
        references = decode(msg.get("References"))

        html, text = get_body(msg)

        yield EmailMessage(
            sender=sender,
            subject=subject,
            date=date,
            message_id=message_id,
            in_reply_to=in_reply_to,
            references=references,
            html=html,
            text=text,
        )
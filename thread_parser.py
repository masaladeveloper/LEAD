"""
Thread parser.

Collects all replies belonging to a Hyundai lead.
"""

import re

MY_EMAIL = "sales.mhe@munergroup.co.in"


def clean_reply(text):

    if not text:
        return ""

    text = text.replace("\r", "")

    # Stop when Outlook starts quoting previous mail
    stop_words = [
        "From:",
        "Sent:",
        "Subject:",
        "Original Message",
        "-----Original Message-----",
        "Get Outlook for",
        "This email",
    ]

    lines = []

    for line in text.split("\n"):

        line = line.rstrip()

        stop = False

        for word in stop_words:

            if line.lstrip().lower().startswith(word.lower()) or re.match(r"^On .+wrote:$", line.strip(), re.I) or line.lstrip().startswith(">"):
                stop = True
                break

        if stop:
            break

        lines.append(line)

    text = "\n".join(lines)

    text = re.sub(r"\n\s*\n+", "\n\n", text)

    return text.strip()


def collect_replies(parent_mail, thread_index):

    replies = []

    stack = thread_index.get_replies(parent_mail.message_id)

    while stack:

        mail = stack.pop(0)

        replies.append(mail)

        children = thread_index.get_replies(mail.message_id)

        if children:
            stack.extend(children)

    return replies


def build_remarks(parent_mail, thread_index):

    replies = collect_replies(parent_mail, thread_index)

    remarks = []

    for mail in replies:

        sender = mail.sender.lower()

        if MY_EMAIL not in sender:
            continue

        body = mail.text if mail.text else mail.html

        body = clean_reply(body)

        if not body:
            continue

        remarks.append(
            f"{mail.date}\n{body}"
        )

    return "\n\n------------------------------\n\n".join(remarks)
"""
Thread index for storing all mailbox emails.

This class builds indexes while the mailbox is scanned once.
"""

from collections import defaultdict


class ThreadIndex:

    def __init__(self):

        # Message-ID -> EmailMessage
        self.message_index = {}

        # In-Reply-To -> list of replies
        self.reply_index = defaultdict(list)

        # Subject -> list of emails
        self.subject_index = defaultdict(list)

        # All emails
        self.all_emails = []

    def add(self, mail):

        self.all_emails.append(mail)

        # Message-ID
        if mail.message_id:
            self.message_index[
                mail.message_id.strip().lower()
            ] = mail

        # In-Reply-To
        if mail.in_reply_to:
            self.reply_index[
                mail.in_reply_to.strip().lower()
            ].append(mail)

        # Subject
        subject = (mail.subject or "").strip().lower()

        if subject:
            self.subject_index[subject].append(mail)

    def get_replies(self, message_id):

        if not message_id:
            return []

        return self.reply_index.get(
            message_id.strip().lower(),
            []
        )

    def get_message(self, message_id):

        if not message_id:
            return None

        return self.message_index.get(
            message_id.strip().lower()
        )

    def get_subject(self, subject):

        if not subject:
            return []

        return self.subject_index.get(
            subject.strip().lower(),
            []
        )
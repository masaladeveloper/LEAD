"""Remove quoted history from the current plain-text reply."""
import re

QUOTE_PREFIXES = (
    'from:', 'sent:', 'subject:', 'original message',
    '-----original message-----', 'get outlook for', 'this email', '>',
)


def clean_reply(text):
    if not text:
        return ''
    lines = []
    for line in text.replace('\r', '').split('\n'):
        line = line.rstrip()
        stripped = line.strip()
        if stripped.casefold().startswith(QUOTE_PREFIXES) or re.match(r'^On .+wrote:$', stripped, re.I):
            break
        lines.append(line)
    return re.sub(r'\n\s*\n+', '\n\n', '\n'.join(lines)).strip()

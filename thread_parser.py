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


def clean_update(text):
    """Render the useful outgoing update without changing the saved email."""
    lines = clean_reply(text).splitlines()
    while lines:
        first = lines[0].strip()
        if not first or re.fullmatch(r'(?:greetings(?: of the day)?|good (?:morning|afternoon|evening))[!. ,]*', first, re.I):
            lines.pop(0)
            continue
        greeting = re.match(r'^(?:dear|hi|hello)\s+[^,!:\n]{1,60}[,!:]\s*(.*)$', first, re.I)
        if greeting:
            lines[0] = greeting.group(1)
            continue
        if re.fullmatch(r'(?i:dear|hi|hello)(?:\s+(?:(?i:sir|madam|mam|ma\'am|team|all)|[A-Z][a-z]+)){0,3}[. ]*', first):
            lines.pop(0)
            continue
        break
    useful = []
    for line in lines:
        if re.match(r'^(?:--|(?:best\s+|kind\s+|warm\s+)?regards|thanks\s*(?:&|and)\s*regards|sincerely|yours (?:faithfully|sincerely)|thanks|thank you)(?:[,!].*|[. ]*)$', line.strip(), re.I):
            break
        if re.match(r'^Sent from (?:my |Mail for |Outlook)', line.strip(), re.I):
            break
        useful.append(line)
    return '\n'.join(useful).strip()

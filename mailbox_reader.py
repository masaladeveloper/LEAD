"""Decode mail headers and body parts without reading attached messages."""
from email.header import decode_header


def _decode_bytes(value, charset):
    try:
        return value.decode(charset or 'utf-8', errors='replace')
    except LookupError:
        return value.decode('utf-8', errors='replace')


def decode(value):
    if not value:
        return ''
    return ''.join(_decode_bytes(text, charset) if isinstance(text, bytes) else text
                   for text, charset in decode_header(value))


def _body_parts(message):
    # walk() visits the children of attachments too, including forwarded .eml
    # files. Skip the entire attachment tree so it cannot replace the body.
    if message.get_content_disposition() == 'attachment':
        return
    if message.is_multipart():
        for part in message.get_payload():
            yield from _body_parts(part)
    else:
        yield message


def get_body(message):
    bodies = {'text/html': '', 'text/plain': ''}
    for part in _body_parts(message):
        content_type = part.get_content_type()
        if content_type not in bodies:
            continue
        payload = part.get_payload(decode=True)
        if payload:
            bodies[content_type] = _decode_bytes(payload, part.get_content_charset())
    return bodies['text/html'], bodies['text/plain']

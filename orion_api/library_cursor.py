"""Opaque continuation for immutable paper IDs; no SQL is encoded in the cursor."""
import base64
import binascii
import json
from fastapi import HTTPException


def encode_cursor(paper_id):
    return base64.urlsafe_b64encode(json.dumps([1, paper_id], separators=(",", ":")).encode()).decode().rstrip("=")


def decode_cursor(value):
    if value == "start":
        return None
    try:
        data = json.loads(base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True))
        if not isinstance(data, list) or len(data) != 2 or data[0] != 1 or not isinstance(data[1], str) or not 1 <= len(data[1]) <= 1000:
            raise ValueError()
        return data[1]
    except (ValueError, TypeError, binascii.Error, UnicodeDecodeError):
        raise HTTPException(status_code=400, detail="Invalid library cursor") from None

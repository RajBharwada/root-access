"""Small cipher helpers used by the in-game 'decode' command."""
import base64
import binascii


def b64_decode(text):
    try:
        return base64.b64decode(text, validate=True).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError, ValueError):
        return None


def caesar(text, shift):
    """Shift letters by `shift` positions (negative shifts decode)."""
    out = []
    for ch in text:
        if ch.isalpha():
            base = ord("A") if ch.isupper() else ord("a")
            out.append(chr((ord(ch) - base + shift) % 26 + base))
        else:
            out.append(ch)
    return "".join(out)
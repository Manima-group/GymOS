import re
import secrets
import string


def normalize_phone(phone: str) -> str:
    """Store Indian mobiles as the last 10 digits."""
    digits = "".join(c for c in phone if c.isdigit())
    return digits[-10:] if len(digits) >= 10 else digits


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60] or "gym"


def short_code(n: int = 6) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet.replace("O", "").replace("0", "")) for _ in range(n))

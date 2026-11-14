import hashlib
import json
import unicodedata


def normalize_identity(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).split()).casefold()


def invoice_duplicate_key(supplier: str, number: str | None) -> str | None:
    if not number:
        return None
    identity = [normalize_identity(supplier), normalize_identity(number)]
    return hashlib.sha256(json.dumps(identity, ensure_ascii=False).encode()).hexdigest()

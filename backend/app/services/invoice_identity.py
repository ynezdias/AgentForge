import hashlib
import json
import unicodedata


def normalize_identity(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).split()).casefold()


def invoice_duplicate_key(supplier: str, number: str | None, company_id=None) -> str | None:
    """Duplicate identity is per company: two tenants may hold the same supplier invoice.

    Without a company the key matches the original format, for unassigned legacy rows.
    """
    if not number:
        return None
    identity = [normalize_identity(supplier), normalize_identity(number)]
    if company_id is not None:
        identity.insert(0, str(company_id))
    return hashlib.sha256(json.dumps(identity, ensure_ascii=False).encode()).hexdigest()

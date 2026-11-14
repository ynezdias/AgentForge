"""Local text extraction; uploaded documents are never persisted or sent to AI."""
import base64
import binascii
import io
import re
from datetime import datetime

from fastapi import HTTPException
from pypdf import PdfReader


def extract_date(text: str, label: str) -> str | None:
    # Numeric day/month ordering is ambiguous, so only suggest ISO or named months.
    match = re.search(label + r"\s*:?\s*(\d{4}[-/]\d{2}[-/]\d{2}|[A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4}|\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4})", text, re.I)
    if not match:
        return None
    value = match.group(1).replace(",", "")
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%B %d %Y", "%b %d %Y", "%d %B %Y", "%d %b %Y"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            pass
    return None


def extract_invoice_pdf(content: str) -> dict:
    try:
        raw = base64.b64decode(content, validate=True)
    except (ValueError, binascii.Error):
        raise HTTPException(422, "Invalid PDF upload")
    if len(raw) > 5 * 1024 * 1024:
        raise HTTPException(413, "PDF must be 5 MB or smaller")
    if not raw.startswith(b"%PDF-"):
        raise HTTPException(422, "Upload a valid PDF file")
    try:
        reader = PdfReader(io.BytesIO(raw))
        if reader.is_encrypted:
            raise HTTPException(422, "Use an unencrypted PDF, or enter the invoice manually")
        if len(reader.pages) > 20:
            raise HTTPException(422, "Upload an invoice with 20 pages or fewer")
        text = "\n".join(page.extract_text()[:20_000] for page in reader.pages)[:100_000]
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(422, "Could not read this PDF. Try another file or enter the invoice manually")
    if not text.strip():
        raise HTTPException(422, "This PDF has no readable text. Scanned invoices need manual entry")
    amount = re.search(r"(?:grand\s+total|amount\s+due|total\s+due|invoice\s+total|total)\s*:?\s*(?:USD|EUR|GBP|\$|€|£)?\s*([0-9][0-9,]*\.\d{2})\b", text, re.I)
    supplier = re.search(r"(?:supplier|vendor|from)\s*:\s*([^\n]{1,200})", text, re.I)
    currency = re.search(r"\b(USD|EUR|GBP|CAD|AUD|INR)\b", text)
    number = re.search(r"\binvoice\s*(?:number|no\.?|#)\s*[:#]?\s*([A-Za-z0-9][A-Za-z0-9._/\-]{0,99})(?![A-Za-z0-9._/\-])", text, re.I)
    return {"amount": amount.group(1).replace(",", "") if amount else None,
            "supplier_name": supplier.group(1).strip() if supplier else None,
            "currency": currency.group(1) if currency else None,
            "invoice_number": number.group(1) if number else None,
            "invoice_date": extract_date(text, r"\binvoice\s+date"),
            "due_date": extract_date(text, r"\b(?:due\s+date|payment\s+due)"),
            "text_preview": text[:4000],
            "notice": "Review all fields before saving. Select the matching purchase order; its amount is not extracted from the invoice."}

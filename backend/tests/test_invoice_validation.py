from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from app.services.invoice_validation import (
    calculate_discrepancy,
    validate_invoice,
)


def test_discrepancy_calculation():
    result = calculate_discrepancy(
        Decimal("1050"),
        Decimal("1000"),
    )
    assert result == Decimal("5.00")


def test_amount_discrepancy_detected():
    vendor_id = uuid4()
    invoice = SimpleNamespace(
        vendor_id=vendor_id,
        currency="USD",
        amount=Decimal("1100"),
    )
    po = SimpleNamespace(
        vendor_id=vendor_id,
        currency="USD",
        total_amount=Decimal("1000"),
    )
    result = validate_invoice(invoice, po)
    assert result["valid"] is False
    assert "AMOUNT_DISCREPANCY" in result["issues"]

from decimal import Decimal


def calculate_discrepancy(invoice_amount: Decimal, po_amount: Decimal):
    if po_amount <= 0:
        raise ValueError("Purchase order amount must be positive")

    return (
        abs(invoice_amount - po_amount)
        / po_amount
        * Decimal("100")
    ).quantize(Decimal("0.01"))


def validate_invoice(invoice, purchase_order, threshold=Decimal("5")):
    issues = []

    if invoice.vendor_id != purchase_order.vendor_id:
        issues.append("VENDOR_MISMATCH")

    if invoice.currency != purchase_order.currency:
        issues.append("CURRENCY_MISMATCH")

    discrepancy = calculate_discrepancy(
        invoice.amount,
        purchase_order.total_amount,
    )

    if discrepancy > threshold:
        issues.append("AMOUNT_DISCREPANCY")

    return {
        "valid": len(issues) == 0,
        "discrepancy_percentage": discrepancy,
        "issues": issues,
    }
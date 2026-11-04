
from decimal import Decimal

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.business import Vendor, PurchaseOrder, Invoice


def seed_database():
    with SessionLocal() as db:
        existing = db.scalar(
            select(Vendor).where(Vendor.external_ref == "VENDOR-001")
        )

        if existing:
            print("Sample data already exists. Skipping.")
            return

        vendor1 = Vendor(
            name="Acme Supplies",
            external_ref="VENDOR-001",
        )

        vendor2 = Vendor(
            name="Global Tech Solutions",
            external_ref="VENDOR-002",
        )

        db.add_all([vendor1, vendor2])
        db.flush()

        po1 = PurchaseOrder(
            vendor_id=vendor1.id,
            total_amount=Decimal("1000.00"),
            currency="USD",
        )

        po2 = PurchaseOrder(
            vendor_id=vendor2.id,
            total_amount=Decimal("2500.00"),
            currency="USD",
        )

        db.add_all([po1, po2])
        db.flush()

        invoices = [
            Invoice(
                vendor_id=vendor1.id,
                purchase_order_id=po1.id,
                amount=Decimal("1000.00"),
                currency="USD",
                status="pending",
            ),
            Invoice(
                vendor_id=vendor1.id,
                purchase_order_id=po1.id,
                amount=Decimal("1150.00"),
                currency="USD",
                status="pending",
            ),
            Invoice(
                vendor_id=vendor2.id,
                purchase_order_id=po2.id,
                amount=Decimal("2500.00"),
                currency="USD",
                status="pending",
            ),
            Invoice(
                vendor_id=vendor1.id,
                purchase_order_id=po2.id,
                amount=Decimal("2500.00"),
                currency="USD",
                status="pending",
            ),
        ]

        db.add_all(invoices)
        db.commit()

        print("Database seeded successfully!")
        print("Created 2 vendors, 2 purchase orders, 4 invoices.")


if __name__ == "__main__":
    seed_database()

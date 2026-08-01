from sqlalchemy import select
from sqlalchemy.orm import Session

from models.invoice import Invoice


def list_invoices(db: Session, *, limit: int = 100, offset: int = 0) -> list[Invoice]:
    stmt = select(Invoice).order_by(Invoice.id.desc()).limit(limit).offset(offset)
    return list(db.scalars(stmt))


def get_invoice(db: Session, invoice_id: int) -> Invoice | None:
    return db.get(Invoice, invoice_id)


def get_invoice_for_order(db: Session, sales_order_id: int) -> Invoice | None:
    return db.scalar(select(Invoice).where(Invoice.sales_order_id == sales_order_id))

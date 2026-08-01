from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models.invoice import Invoice
from models.payment import Payment
from schemas.payment import PaymentCreate


def list_payments(db: Session, invoice_id: int) -> list[Payment]:
    stmt = select(Payment).where(Payment.invoice_id == invoice_id).order_by(Payment.paid_at.desc())
    return list(db.scalars(stmt))


def _total_paid(db: Session, invoice_id: int) -> float:
    stmt = select(func.coalesce(func.sum(Payment.amount), 0)).where(
        Payment.invoice_id == invoice_id
    )
    return float(db.execute(stmt).scalar_one())


def record_payment(db: Session, invoice: Invoice, data: PaymentCreate) -> Payment:
    payment = Payment(invoice_id=invoice.id, amount=data.amount, method=data.method)
    db.add(payment)
    db.flush()
    total_paid = _total_paid(db, invoice.id)
    if total_paid >= float(invoice.total_amount):
        invoice.status = "paid"
    elif total_paid > 0:
        invoice.status = "partially_paid"
    db.commit()
    db.refresh(payment)
    return payment

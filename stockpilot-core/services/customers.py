from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models.customer import Customer
from schemas.customer import CustomerCreate, CustomerUpdate


def get_customer(db: Session, customer_id: int) -> Customer | None:
    return db.get(Customer, customer_id)


def list_customers(
    db: Session, *, search: str | None = None, limit: int = 100, offset: int = 0
) -> list[Customer]:
    stmt = select(Customer).order_by(Customer.name)
    if search is not None:
        pattern = f"%{search.lower()}%"
        stmt = stmt.where(
            func.lower(Customer.name).like(pattern) | func.lower(Customer.email).like(pattern)
        )
    stmt = stmt.limit(limit).offset(offset)
    return list(db.scalars(stmt))


def create_customer(db: Session, data: CustomerCreate) -> Customer:
    customer = Customer(**data.model_dump())
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


def update_customer(db: Session, customer: Customer, data: CustomerUpdate) -> Customer:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(customer, field, value)
    db.commit()
    db.refresh(customer)
    return customer


def delete_customer(db: Session, customer: Customer) -> None:
    db.delete(customer)
    db.commit()

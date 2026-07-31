from sqlalchemy import select
from sqlalchemy.orm import Session

from models.supplier_contact import SupplierContact
from schemas.supplier_contact import SupplierContactCreate, SupplierContactUpdate


def list_contacts(db: Session, supplier_id: int) -> list[SupplierContact]:
    stmt = (
        select(SupplierContact)
        .where(SupplierContact.supplier_id == supplier_id)
        .order_by(SupplierContact.name)
    )
    return list(db.scalars(stmt))


def get_contact(db: Session, supplier_id: int, contact_id: int) -> SupplierContact | None:
    contact = db.get(SupplierContact, contact_id)
    if contact is None or contact.supplier_id != supplier_id:
        return None
    return contact


def create_contact(db: Session, supplier_id: int, data: SupplierContactCreate) -> SupplierContact:
    contact = SupplierContact(supplier_id=supplier_id, **data.model_dump())
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return contact


def update_contact(
    db: Session, contact: SupplierContact, data: SupplierContactUpdate
) -> SupplierContact:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(contact, field, value)
    db.commit()
    db.refresh(contact)
    return contact


def delete_contact(db: Session, contact: SupplierContact) -> None:
    db.delete(contact)
    db.commit()

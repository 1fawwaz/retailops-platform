from sqlalchemy import select
from sqlalchemy.orm import Session

from models.product import Product
from models.supplier import Supplier
from schemas.supplier import SupplierCreate, SupplierUpdate


def get_supplier(db: Session, supplier_id: int) -> Supplier | None:
    return db.get(Supplier, supplier_id)


def get_supplier_skus(db: Session, supplier_id: int) -> list[str]:
    stmt = select(Product.sku).where(Product.supplier_id == supplier_id).order_by(Product.sku)
    return list(db.scalars(stmt))


def list_suppliers(db: Session, *, limit: int = 100, offset: int = 0) -> list[Supplier]:
    stmt = select(Supplier).order_by(Supplier.id).limit(limit).offset(offset)
    return list(db.scalars(stmt))


def create_supplier(db: Session, data: SupplierCreate) -> Supplier:
    supplier = Supplier(**data.model_dump())
    db.add(supplier)
    db.commit()
    db.refresh(supplier)
    return supplier


def update_supplier(db: Session, supplier: Supplier, data: SupplierUpdate) -> Supplier:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(supplier, field, value)
    db.commit()
    db.refresh(supplier)
    return supplier


def delete_supplier(db: Session, supplier: Supplier) -> None:
    db.delete(supplier)
    db.commit()

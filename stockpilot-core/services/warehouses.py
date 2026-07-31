from sqlalchemy import select
from sqlalchemy.orm import Session

from models.warehouse import Warehouse

MAIN_WAREHOUSE_NAME = "Main Warehouse"


def list_warehouses(db: Session) -> list[Warehouse]:
    return list(db.scalars(select(Warehouse).order_by(Warehouse.name)))


def get_warehouse(db: Session, warehouse_id: int) -> Warehouse | None:
    return db.get(Warehouse, warehouse_id)


def get_warehouse_by_name(db: Session, name: str) -> Warehouse | None:
    return db.scalar(select(Warehouse).where(Warehouse.name == name))


def create_warehouse(db: Session, *, name: str) -> Warehouse:
    warehouse = Warehouse(name=name)
    db.add(warehouse)
    db.commit()
    db.refresh(warehouse)
    return warehouse


def get_or_create_main_warehouse(db: Session) -> Warehouse:
    """Used by tests and any code path that needs a real warehouse to
    attach stock to without the caller having to create one first --
    mirrors the migration's own backfill default (docs/BUILD.md Backend
    Module 4).
    """
    existing = get_warehouse_by_name(db, MAIN_WAREHOUSE_NAME)
    if existing is not None:
        return existing
    return create_warehouse(db, name=MAIN_WAREHOUSE_NAME)

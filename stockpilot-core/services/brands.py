from sqlalchemy import select
from sqlalchemy.orm import Session

from models.brand import Brand


def list_brands(db: Session) -> list[Brand]:
    return list(db.scalars(select(Brand).order_by(Brand.name)))


def get_brand_by_name(db: Session, name: str) -> Brand | None:
    return db.scalar(select(Brand).where(Brand.name == name))


def create_brand(db: Session, *, name: str) -> Brand:
    brand = Brand(name=name)
    db.add(brand)
    db.commit()
    db.refresh(brand)
    return brand

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.product import Product
from schemas.product import ProductCreate, ProductUpdate


def get_product(db: Session, sku: str) -> Product | None:
    return db.get(Product, sku)


def list_products(db: Session, *, limit: int = 100, offset: int = 0) -> list[Product]:
    stmt = select(Product).order_by(Product.sku).limit(limit).offset(offset)
    return list(db.scalars(stmt))


def create_product(db: Session, data: ProductCreate) -> Product:
    product = Product(**data.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


def update_product(db: Session, product: Product, data: ProductUpdate) -> Product:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(product, field, value)
    db.commit()
    db.refresh(product)
    return product


def delete_product(db: Session, product: Product) -> None:
    db.delete(product)
    db.commit()

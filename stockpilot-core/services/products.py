from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.product import Product
from models.product_history import ProductHistory
from models.stock_movement import StockMovement
from schemas.product import ProductCreate, ProductUpdate


def _history_value(value: object) -> str | None:
    """Numeric(10, 2) columns come back from the DB as Decimal while
    incoming update values are plain float -- normalize both to the same
    string form so old_value/new_value are comparable and consistent
    regardless of which side produced them.
    """
    if value is None:
        return None
    if isinstance(value, Decimal):
        return str(float(value))
    return str(value)


def get_product(db: Session, sku: str) -> Product | None:
    return db.get(Product, sku)


def get_product_history(db: Session, sku: str) -> list[ProductHistory]:
    stmt = (
        select(ProductHistory)
        .where(ProductHistory.sku == sku)
        .order_by(ProductHistory.changed_at.desc())
    )
    return list(db.scalars(stmt))


def list_products(db: Session, *, limit: int = 100, offset: int = 0) -> list[Product]:
    stmt = select(Product).order_by(Product.sku).limit(limit).offset(offset)
    return list(db.scalars(stmt))


def get_movement_history(db: Session, sku: str, *, days: int = 90) -> list[StockMovement]:
    cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=days)
    stmt = (
        select(StockMovement)
        .where(StockMovement.sku == sku, StockMovement.movement_date >= cutoff)
        .order_by(StockMovement.movement_date.desc())
    )
    return list(db.scalars(stmt))


def create_product(db: Session, data: ProductCreate) -> Product:
    product = Product(**data.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


def update_product(
    db: Session, product: Product, data: ProductUpdate, *, changed_by_user_id: int | None = None
) -> Product:
    for field, value in data.model_dump(exclude_unset=True).items():
        old_value = getattr(product, field)
        old_str, new_str = _history_value(old_value), _history_value(value)
        # Compare normalized strings, not raw values: Numeric(10, 2)
        # columns come back as Decimal, and Decimal('2.15') == 2.15 is
        # False (binary float imprecision) even though nothing changed.
        if old_str == new_str:
            setattr(product, field, value)
            continue
        db.add(
            ProductHistory(
                sku=product.sku,
                field_name=field,
                old_value=old_str,
                new_value=new_str,
                changed_by_user_id=changed_by_user_id,
            )
        )
        setattr(product, field, value)
    db.commit()
    db.refresh(product)
    return product


def delete_product(db: Session, product: Product) -> None:
    db.delete(product)
    db.commit()

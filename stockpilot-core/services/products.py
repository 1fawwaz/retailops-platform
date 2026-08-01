from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models.category import Category
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


def list_products(
    db: Session,
    *,
    search: str | None = None,
    category: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[Product]:
    """search/category/limit/offset -- previously this had no filter
    params at all and silently capped at 100 rows with no way to reach
    anything past that, which docs/PRODUCT-SPEC.md's own "searchable/
    filterable list" requirement for the Products page can't be built
    against. Found and fixed while building that page's frontend
    counterpart, matching CLAUDE.md §18: extend the backend first, then
    connect the frontend, don't approximate a missing capability
    client-side.
    """
    stmt = select(Product).order_by(Product.sku)
    if search is not None:
        pattern = f"%{search.lower()}%"
        stmt = stmt.where(
            func.lower(Product.sku).like(pattern) | func.lower(Product.description).like(pattern)
        )
    if category is not None:
        stmt = stmt.join(Category, Category.id == Product.category_id).where(
            func.lower(Category.name) == category.lower()
        )
    stmt = stmt.limit(limit).offset(offset)
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

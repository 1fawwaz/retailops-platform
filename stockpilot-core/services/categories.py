from sqlalchemy import select
from sqlalchemy.orm import Session

from models.category import Category


def list_categories(db: Session) -> list[Category]:
    return list(db.scalars(select(Category).order_by(Category.name)))


def get_category_by_name(db: Session, name: str) -> Category | None:
    return db.scalar(select(Category).where(Category.name == name))


def create_category(db: Session, *, name: str) -> Category:
    category = Category(name=name)
    db.add(category)
    db.commit()
    db.refresh(category)
    return category

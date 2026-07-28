from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class Category(Base):
    """Product categories. Derived by TF-IDF + KMeans clustering over
    product descriptions, then hand-labelled. See
    data-derivation.md#category-clustering.
    """

    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(
        unique=True,
        comment="derived: data-derivation.md#category-clustering",
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

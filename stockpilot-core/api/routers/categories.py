from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.deps import get_current_user, require_permission
from database import get_db
from models.user import User
from schemas.category import CategoryCreate, CategoryRead
from services.categories import create_category, get_category_by_name, list_categories

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", response_model=list[CategoryRead])
def list_categories_route(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[CategoryRead]:
    return [CategoryRead.model_validate(c) for c in list_categories(db)]


@router.post("", response_model=CategoryRead, status_code=status.HTTP_201_CREATED)
def create_category_route(
    data: CategoryCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("products:create")),
) -> CategoryRead:
    if get_category_by_name(db, data.name) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Category '{data.name}' already exists",
        )
    return CategoryRead.model_validate(create_category(db, name=data.name))

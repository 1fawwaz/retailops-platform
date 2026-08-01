from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.deps import get_current_user, require_permission
from database import get_db
from models.user import User
from schemas.brand import BrandCreate, BrandRead
from services.brands import create_brand, get_brand_by_name, list_brands

router = APIRouter(prefix="/brands", tags=["brands"])


@router.get("", response_model=list[BrandRead])
def list_brands_route(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[BrandRead]:
    return [BrandRead.model_validate(b) for b in list_brands(db)]


@router.post("", response_model=BrandRead, status_code=status.HTTP_201_CREATED)
def create_brand_route(
    data: BrandCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("products:create")),
) -> BrandRead:
    if get_brand_by_name(db, data.name) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Brand '{data.name}' already exists",
        )
    return BrandRead.model_validate(create_brand(db, name=data.name))

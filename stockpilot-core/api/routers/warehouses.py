from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.deps import get_current_user, require_write_access
from database import get_db
from models.user import User
from schemas.warehouse import WarehouseCreate, WarehouseRead
from services.warehouses import create_warehouse, get_warehouse_by_name, list_warehouses

router = APIRouter(prefix="/warehouses", tags=["warehouses"])


@router.get("", response_model=list[WarehouseRead])
def list_warehouses_route(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[WarehouseRead]:
    return [WarehouseRead.model_validate(w) for w in list_warehouses(db)]


@router.post("", response_model=WarehouseRead, status_code=status.HTTP_201_CREATED)
def create_warehouse_route(
    data: WarehouseCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_write_access),
) -> WarehouseRead:
    if get_warehouse_by_name(db, data.name) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Warehouse '{data.name}' already exists",
        )
    return WarehouseRead.model_validate(create_warehouse(db, name=data.name))

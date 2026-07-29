from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from api.deps import get_current_user
from database import get_db
from models.user import User
from schemas.inventory import (
    DEAD_STOCK_ITEM_DERIVATION_REF,
    DEAD_STOCK_ITEM_PROVENANCE,
    INVENTORY_VALUATION_PROVENANCE,
    SLOW_MOVER_ITEM_DERIVATION_REF,
    SLOW_MOVER_ITEM_PROVENANCE,
    STOCK_DERIVATION_REF,
    STOCK_ITEM_PROVENANCE,
    VALUATION_ROW_DERIVATION_REF,
    VALUATION_ROW_PROVENANCE,
    DeadStockItem,
    InventoryValuation,
    SlowMoverItem,
    StockItem,
    ValuationRow,
)
from services.inventory import (
    DeadStockRow,
    SlowMoverRow,
    StockRow,
    Valuation,
    get_valuation,
    list_dead_stock,
    list_slow_movers,
    list_stock,
)
from services.inventory import (
    ValuationRow as ValuationRowData,
)

router = APIRouter(prefix="/inventory", tags=["inventory"])


def _to_stock_item(row: StockRow) -> StockItem:
    return StockItem(
        sku=row.sku,
        description=row.description,
        category=row.category,
        quantity_on_hand=row.quantity_on_hand,
        reorder_point=row.reorder_point,
        safety_stock=row.safety_stock,
        as_of_date=row.as_of_date,
        is_low_stock=row.is_low_stock,
        provenance=STOCK_ITEM_PROVENANCE,
        derivation_ref=STOCK_DERIVATION_REF,
    )


def _to_dead_stock_item(row: DeadStockRow) -> DeadStockItem:
    return DeadStockItem(
        sku=row.sku,
        description=row.description,
        quantity_on_hand=row.quantity_on_hand,
        last_movement_date=row.last_movement_date,
        days_since_movement=row.days_since_movement,
        provenance=DEAD_STOCK_ITEM_PROVENANCE,
        derivation_ref=DEAD_STOCK_ITEM_DERIVATION_REF,
    )


def _to_slow_mover_item(row: SlowMoverRow) -> SlowMoverItem:
    return SlowMoverItem(
        sku=row.sku,
        description=row.description,
        quantity_on_hand=row.quantity_on_hand,
        units_sold=row.units_sold,
        avg_daily_demand=row.avg_daily_demand,
        provenance=SLOW_MOVER_ITEM_PROVENANCE,
        derivation_ref=SLOW_MOVER_ITEM_DERIVATION_REF,
    )


def _to_valuation_row(row: ValuationRowData) -> ValuationRow:
    return ValuationRow(
        category=row.category,
        quantity_on_hand=row.quantity_on_hand,
        inventory_value=row.inventory_value,
        provenance=VALUATION_ROW_PROVENANCE,
        derivation_ref=VALUATION_ROW_DERIVATION_REF,
    )


def _to_valuation(valuation: Valuation) -> InventoryValuation:
    return InventoryValuation(
        by_category=[_to_valuation_row(row) for row in valuation.by_category],
        total_quantity_on_hand=valuation.total_quantity_on_hand,
        total_inventory_value=valuation.total_inventory_value,
        provenance=INVENTORY_VALUATION_PROVENANCE,
    )


@router.get("/stock", response_model=list[StockItem])
def get_stock(
    category: str | None = Query(default=None),
    low_stock: bool | None = Query(default=None),
    search: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[StockItem]:
    rows = list_stock(
        db, category=category, low_stock=low_stock, search=search, limit=limit, offset=offset
    )
    return [_to_stock_item(row) for row in rows]


@router.get("/low-stock", response_model=list[StockItem])
def get_low_stock(
    category: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[StockItem]:
    rows = list_stock(db, category=category, low_stock=True, limit=limit, offset=offset)
    return [_to_stock_item(row) for row in rows]


@router.get("/dead-stock", response_model=list[DeadStockItem])
def get_dead_stock(
    days: int = Query(default=90, ge=1),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[DeadStockItem]:
    rows = list_dead_stock(db, days=days, limit=limit, offset=offset)
    return [_to_dead_stock_item(row) for row in rows]


@router.get("/slow-movers", response_model=list[SlowMoverItem])
def get_slow_movers(
    window_days: int = Query(default=90, ge=1),
    velocity_threshold: float = Query(default=0.2, gt=0),
    limit: int = Query(default=50, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[SlowMoverItem]:
    rows = list_slow_movers(
        db,
        window_days=window_days,
        velocity_threshold=velocity_threshold,
        limit=limit,
        offset=offset,
    )
    return [_to_slow_mover_item(row) for row in rows]


@router.get("/valuation", response_model=InventoryValuation)
def get_inventory_valuation(
    category: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> InventoryValuation:
    return _to_valuation(get_valuation(db, category=category))

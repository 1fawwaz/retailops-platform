from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.deps import get_current_user, require_permission
from database import get_db
from models.product import Product
from models.stock_movement import StockMovement
from models.user import User
from schemas.product import (
    PRODUCT_DERIVATION_REF,
    PRODUCT_DETAIL_DERIVATION_REF,
    PRODUCT_DETAIL_PROVENANCE,
    PRODUCT_PROVENANCE,
    MovementHistoryEntry,
    ProductCreate,
    ProductDetail,
    ProductHistoryEntry,
    ProductRead,
    ProductUpdate,
)
from services.inventory import get_current_stock
from services.products import (
    create_product,
    delete_product,
    get_movement_history,
    get_product,
    get_product_history,
    list_products,
    update_product,
)
from services.purchase_orders import product_has_open_purchase_order_lines

router = APIRouter(prefix="/products", tags=["products"])


def _to_read_model(product: Product) -> ProductRead:
    return ProductRead(
        sku=product.sku,
        description=product.description,
        category_id=product.category_id,
        supplier_id=product.supplier_id,
        brand_id=product.brand_id,
        unit_cost=float(product.unit_cost) if product.unit_cost is not None else None,
        sale_price=float(product.sale_price) if product.sale_price is not None else None,
        reorder_point=product.reorder_point,
        safety_stock=product.safety_stock,
        created_at=product.created_at,
        provenance=PRODUCT_PROVENANCE,
        derivation_ref=PRODUCT_DERIVATION_REF,
    )


def _to_movement_entry(movement: StockMovement) -> MovementHistoryEntry:
    return MovementHistoryEntry(
        movement_date=movement.movement_date,
        quantity_delta=movement.quantity_delta,
        movement_type=movement.movement_type,
        provenance=movement.provenance,
    )


def _to_detail_model(
    product: Product,
    quantity_on_hand: int | None,
    movements: list[StockMovement],
) -> ProductDetail:
    return ProductDetail(
        sku=product.sku,
        description=product.description,
        category_id=product.category_id,
        supplier_id=product.supplier_id,
        brand_id=product.brand_id,
        unit_cost=float(product.unit_cost) if product.unit_cost is not None else None,
        sale_price=float(product.sale_price) if product.sale_price is not None else None,
        reorder_point=product.reorder_point,
        safety_stock=product.safety_stock,
        created_at=product.created_at,
        quantity_on_hand=quantity_on_hand,
        movement_history=[_to_movement_entry(m) for m in movements],
        provenance=PRODUCT_DETAIL_PROVENANCE,
        derivation_ref=PRODUCT_DETAIL_DERIVATION_REF,
    )


def _get_product_or_404(db: Session, sku: str) -> Product:
    product = get_product(db, sku)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return product


@router.get("", response_model=list[ProductRead])
def list_products_route(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[ProductRead]:
    return [_to_read_model(p) for p in list_products(db)]


@router.get("/{sku}", response_model=ProductDetail)
def get_product_route(
    sku: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> ProductDetail:
    product = _get_product_or_404(db, sku)
    quantity_on_hand = get_current_stock(db, sku)
    movements = get_movement_history(db, sku)
    return _to_detail_model(product, quantity_on_hand, movements)


@router.post("", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
def create_product_route(
    data: ProductCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("products:create")),
) -> ProductRead:
    if get_product(db, data.sku) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Product '{data.sku}' already exists",
        )
    return _to_read_model(create_product(db, data))


@router.put("/{sku}", response_model=ProductRead)
def update_product_route(
    sku: str,
    data: ProductUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("products:update")),
) -> ProductRead:
    product = _get_product_or_404(db, sku)
    return _to_read_model(update_product(db, product, data, changed_by_user_id=user.id))


@router.delete("/{sku}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product_route(
    sku: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("products:delete")),
) -> None:
    product = _get_product_or_404(db, sku)
    if product_has_open_purchase_order_lines(db, sku):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete a product with open purchase order lines "
            "(docs/PRODUCT-SPEC.md §12)",
        )
    delete_product(db, product)


@router.get("/{sku}/history", response_model=list[ProductHistoryEntry])
def get_product_history_route(
    sku: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[ProductHistoryEntry]:
    _get_product_or_404(db, sku)
    return [ProductHistoryEntry.model_validate(h) for h in get_product_history(db, sku)]

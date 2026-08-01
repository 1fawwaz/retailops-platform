from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from api.deps import get_current_user, require_write_access
from api.routers.sales_orders import to_sales_order_read_model
from database import get_db
from models.customer import Customer
from models.user import User
from schemas.customer import CustomerCreate, CustomerRead, CustomerUpdate
from schemas.sales_order import SalesOrderRead
from services.customers import (
    create_customer,
    delete_customer,
    get_customer,
    list_customers,
    update_customer,
)
from services.sales_orders import list_sales_orders

router = APIRouter(prefix="/customers", tags=["customers"])


def _get_customer_or_404(db: Session, customer_id: int) -> Customer:
    customer = get_customer(db, customer_id)
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    return customer


@router.get("", response_model=list[CustomerRead])
def list_customers_route(
    search: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[CustomerRead]:
    return [
        CustomerRead.model_validate(c)
        for c in list_customers(db, search=search, limit=limit, offset=offset)
    ]


@router.get("/{customer_id}", response_model=CustomerRead)
def get_customer_route(
    customer_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> CustomerRead:
    return CustomerRead.model_validate(_get_customer_or_404(db, customer_id))


@router.post("", response_model=CustomerRead, status_code=status.HTTP_201_CREATED)
def create_customer_route(
    data: CustomerCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_write_access),
) -> CustomerRead:
    return CustomerRead.model_validate(create_customer(db, data))


@router.put("/{customer_id}", response_model=CustomerRead)
def update_customer_route(
    customer_id: int,
    data: CustomerUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_write_access),
) -> CustomerRead:
    customer = _get_customer_or_404(db, customer_id)
    return CustomerRead.model_validate(update_customer(db, customer, data))


@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_customer_route(
    customer_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_write_access),
) -> None:
    customer = _get_customer_or_404(db, customer_id)
    delete_customer(db, customer)


@router.get("/{customer_id}/orders", response_model=list[SalesOrderRead])
def list_customer_orders_route(
    customer_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[SalesOrderRead]:
    # Deferred in Backend Module 6, now buildable per docs/BUILD.md
    # Backend Module 7.
    _get_customer_or_404(db, customer_id)
    orders = list_sales_orders(db, customer_id=customer_id)
    return [to_sales_order_read_model(o, db) for o in orders]

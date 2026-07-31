from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.deps import get_current_user, require_write_access
from database import get_db
from models.supplier import Supplier
from models.supplier_contact import SupplierContact
from models.user import User
from schemas.supplier import (
    SUPPLIER_DERIVATION_REF,
    SUPPLIER_PROVENANCE,
    SupplierCreate,
    SupplierDetail,
    SupplierRead,
    SupplierUpdate,
)
from schemas.supplier_contact import (
    SupplierContactCreate,
    SupplierContactRead,
    SupplierContactUpdate,
)
from services.supplier_contacts import (
    create_contact,
    delete_contact,
    get_contact,
    list_contacts,
    update_contact,
)
from services.suppliers import (
    create_supplier,
    delete_supplier,
    get_supplier,
    get_supplier_skus,
    list_suppliers,
    update_supplier,
)

router = APIRouter(prefix="/suppliers", tags=["suppliers"])


def _to_read_model(supplier: Supplier) -> SupplierRead:
    return SupplierRead(
        id=supplier.id,
        name=supplier.name,
        lead_time_days=supplier.lead_time_days,
        reliability_score=supplier.reliability_score,
        created_at=supplier.created_at,
        provenance=SUPPLIER_PROVENANCE,
        derivation_ref=SUPPLIER_DERIVATION_REF,
    )


def _to_detail_model(supplier: Supplier, skus: list[str]) -> SupplierDetail:
    return SupplierDetail(
        id=supplier.id,
        name=supplier.name,
        lead_time_days=supplier.lead_time_days,
        reliability_score=supplier.reliability_score,
        created_at=supplier.created_at,
        skus=skus,
        provenance=SUPPLIER_PROVENANCE,
        derivation_ref=SUPPLIER_DERIVATION_REF,
    )


def _get_supplier_or_404(db: Session, supplier_id: int) -> Supplier:
    supplier = get_supplier(db, supplier_id)
    if supplier is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")
    return supplier


@router.get("", response_model=list[SupplierRead])
def list_suppliers_route(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[SupplierRead]:
    return [_to_read_model(s) for s in list_suppliers(db)]


@router.get("/{supplier_id}", response_model=SupplierDetail)
def get_supplier_route(
    supplier_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> SupplierDetail:
    supplier = _get_supplier_or_404(db, supplier_id)
    skus = get_supplier_skus(db, supplier_id)
    return _to_detail_model(supplier, skus)


@router.post("", response_model=SupplierRead, status_code=status.HTTP_201_CREATED)
def create_supplier_route(
    data: SupplierCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_write_access),
) -> SupplierRead:
    return _to_read_model(create_supplier(db, data))


@router.put("/{supplier_id}", response_model=SupplierRead)
def update_supplier_route(
    supplier_id: int,
    data: SupplierUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_write_access),
) -> SupplierRead:
    supplier = _get_supplier_or_404(db, supplier_id)
    return _to_read_model(update_supplier(db, supplier, data))


@router.delete("/{supplier_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_supplier_route(
    supplier_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_write_access),
) -> None:
    supplier = _get_supplier_or_404(db, supplier_id)
    delete_supplier(db, supplier)


@router.get("/{supplier_id}/contacts", response_model=list[SupplierContactRead])
def list_contacts_route(
    supplier_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[SupplierContactRead]:
    _get_supplier_or_404(db, supplier_id)
    return [SupplierContactRead.model_validate(c) for c in list_contacts(db, supplier_id)]


@router.post(
    "/{supplier_id}/contacts",
    response_model=SupplierContactRead,
    status_code=status.HTTP_201_CREATED,
)
def create_contact_route(
    supplier_id: int,
    data: SupplierContactCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_write_access),
) -> SupplierContactRead:
    _get_supplier_or_404(db, supplier_id)
    return SupplierContactRead.model_validate(create_contact(db, supplier_id, data))


def _get_contact_or_404(db: Session, supplier_id: int, contact_id: int) -> SupplierContact:
    contact = get_contact(db, supplier_id, contact_id)
    if contact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found")
    return contact


@router.put("/{supplier_id}/contacts/{contact_id}", response_model=SupplierContactRead)
def update_contact_route(
    supplier_id: int,
    contact_id: int,
    data: SupplierContactUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_write_access),
) -> SupplierContactRead:
    _get_supplier_or_404(db, supplier_id)
    contact = _get_contact_or_404(db, supplier_id, contact_id)
    return SupplierContactRead.model_validate(update_contact(db, contact, data))


@router.delete("/{supplier_id}/contacts/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_contact_route(
    supplier_id: int,
    contact_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_write_access),
) -> None:
    _get_supplier_or_404(db, supplier_id)
    contact = _get_contact_or_404(db, supplier_id, contact_id)
    delete_contact(db, contact)

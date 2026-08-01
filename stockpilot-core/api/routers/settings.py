from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.deps import require_permission
from database import get_db
from models.user import User
from schemas.setting import SettingsRead, SettingsUpdate
from services.settings_service import get_settings, update_settings

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=SettingsRead)
def get_settings_route(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("settings:read")),
) -> SettingsRead:
    return SettingsRead.model_validate(get_settings(db))


@router.put("", response_model=SettingsRead)
def update_settings_route(
    data: SettingsUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("settings:update")),
) -> SettingsRead:
    return SettingsRead.model_validate(update_settings(db, get_settings(db), data))

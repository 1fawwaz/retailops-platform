"""Named settings_service, not settings, to avoid colliding with the
project-root settings.py (app config: DATABASE_URL, JWT_SECRET, ...) --
a completely different thing from the tenant-level business settings
this module manages.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.setting import Setting
from schemas.setting import SettingsUpdate


def get_settings(db: Session) -> Setting:
    """Singleton row -- creates it with defaults on first access rather
    than requiring a migration-time seed, since defaults alone are
    already a complete, valid settings row.
    """
    setting = db.scalar(select(Setting).limit(1))
    if setting is None:
        setting = Setting()
        db.add(setting)
        db.commit()
        db.refresh(setting)
    return setting


def update_settings(db: Session, setting: Setting, data: SettingsUpdate) -> Setting:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(setting, field, value)
    db.commit()
    db.refresh(setting)
    return setting

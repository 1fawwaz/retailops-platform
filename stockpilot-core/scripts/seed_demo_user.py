"""Seed the one read-only demo account used for the public demo login."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database import get_session_factory  # noqa: E402
from services.users import create_user, get_user_by_email  # noqa: E402
from settings import get_settings  # noqa: E402


def main() -> None:
    settings = get_settings()
    db = get_session_factory()()
    try:
        if get_user_by_email(db, settings.demo_user_email) is not None:
            print(f"Demo user already exists: {settings.demo_user_email}")
            return
        create_user(
            db,
            email=settings.demo_user_email,
            password=settings.demo_user_password,
            is_read_only=True,
        )
        print(f"Created read-only demo user: {settings.demo_user_email}")
    finally:
        db.close()


if __name__ == "__main__":
    main()

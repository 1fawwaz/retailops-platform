import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, text

from services.security import hash_password
from settings import get_settings


def main() -> None:
    settings = get_settings()
    engine = create_engine(settings.database_url)
    with engine.begin() as conn:
        users = conn.execute(text("SELECT id, email, is_active FROM users")).fetchall()
        print("Existing Users:", users)

        # Ensure demo user exists with known password
        demo_email = settings.demo_user_email
        demo_password = settings.demo_user_password
        hashed = hash_password(demo_password)

        existing = conn.execute(
            text("SELECT id FROM users WHERE email = :email"), {"email": demo_email}
        ).fetchone()

        if existing:
            conn.execute(
                text(
                    "UPDATE users SET hashed_password = :h, is_active = true WHERE email = :email"
                ),
                {"h": hashed, "email": demo_email},
            )
            print(f"Updated password for {demo_email}")
        else:
            conn.execute(
                text(
                    "INSERT INTO users (email, hashed_password, is_active) VALUES (:email, :h, true)"
                ),
                {"email": demo_email, "h": hashed},
            )
            print(f"Created demo user {demo_email}")

        # Also ensure test@test.com exists
        test_hashed = hash_password("testpassword123")
        test_existing = conn.execute(
            text("SELECT id FROM users WHERE email = 'test@test.com'")
        ).fetchone()
        if test_existing:
            conn.execute(
                text(
                    "UPDATE users SET hashed_password = :h, is_active = true WHERE email = 'test@test.com'"
                ),
                {"h": test_hashed},
            )
            print("Updated password for test@test.com")
        else:
            conn.execute(
                text(
                    "INSERT INTO users (email, hashed_password, is_active) VALUES ('test@test.com', :h, true)"
                ),
                {"h": test_hashed},
            )
            print("Created test@test.com user")


if __name__ == "__main__":
    main()

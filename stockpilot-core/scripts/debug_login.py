import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import traceback

from database import get_db
from services.users import authenticate_user

try:
    db = next(get_db())
    print("Testing authenticate_user...")
    user = authenticate_user(db, email="demo@retailops.local", password="_awv1jRthdu2YNJzao9CyA")
    print("USER AUTHENTICATED:", user.email if user else None)

    user2 = authenticate_user(db, email="test@test.com", password="testpassword123")
    print("TEST USER AUTHENTICATED:", user2.email if user2 else None)
except Exception:
    print("EXCEPTION DURING AUTH:")
    traceback.print_exc()

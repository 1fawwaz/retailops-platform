import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)

print("Testing POST /auth/login via TestClient...")
resp = client.post(
    "/auth/login", data={"username": "demo@retailops.local", "password": "_awv1jRthdu2YNJzao9CyA"}
)
print("STATUS CODE:", resp.status_code)
print("RESPONSE BODY:", resp.text)

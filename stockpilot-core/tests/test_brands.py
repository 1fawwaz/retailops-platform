from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from services.security import create_access_token
from services.users import create_user


def _auth_headers(client: TestClient, email: str = "writer@example.com") -> dict[str, str]:
    client.post("/auth/register", json={"email": email, "password": "hunter22!!"})
    response = client.post("/auth/login", data={"username": email, "password": "hunter22!!"})
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_create_and_list_brands(client: TestClient) -> None:
    headers = _auth_headers(client)

    create_response = client.post("/brands", json={"name": "Acme Housewares"}, headers=headers)
    assert create_response.status_code == 201, create_response.text
    assert create_response.json()["name"] == "Acme Housewares"

    list_response = client.get("/brands", headers=headers)
    assert list_response.status_code == 200
    names = [b["name"] for b in list_response.json()]
    assert "Acme Housewares" in names


def test_create_duplicate_brand_name_is_rejected(client: TestClient) -> None:
    headers = _auth_headers(client)
    client.post("/brands", json={"name": "Acme Housewares"}, headers=headers)

    response = client.post("/brands", json={"name": "Acme Housewares"}, headers=headers)

    assert response.status_code == 409


def test_read_only_user_can_list_but_not_create_brands(
    client: TestClient, db_session: Session
) -> None:
    create_user(db_session, email="demo@example.com", password="hunter22!!", is_read_only=True)
    token = create_access_token(subject="demo@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    list_response = client.get("/brands", headers=headers)
    assert list_response.status_code == 200

    create_response = client.post("/brands", json={"name": "Acme Housewares"}, headers=headers)
    assert create_response.status_code == 403

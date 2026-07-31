from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from services.security import create_access_token
from services.users import create_user


def _auth_headers(client: TestClient, email: str = "writer@example.com") -> dict[str, str]:
    client.post("/auth/register", json={"email": email, "password": "hunter22!!"})
    response = client.post("/auth/login", data={"username": email, "password": "hunter22!!"})
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_create_and_read_customer(client: TestClient) -> None:
    headers = _auth_headers(client)

    create_response = client.post(
        "/customers",
        json={"name": "Priya Shah", "email": "priya@example.com", "country": "United Kingdom"},
        headers=headers,
    )
    assert create_response.status_code == 201, create_response.text
    customer_id = create_response.json()["id"]

    get_response = client.get(f"/customers/{customer_id}", headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()["name"] == "Priya Shah"
    assert get_response.json()["country"] == "United Kingdom"


def test_list_customers_search_matches_name_or_email(client: TestClient) -> None:
    headers = _auth_headers(client)
    client.post("/customers", json={"name": "Priya Shah", "email": "priya@x.com"}, headers=headers)
    client.post("/customers", json={"name": "Sam Lee", "email": "sam@x.com"}, headers=headers)

    by_name = client.get("/customers", params={"search": "priya"}, headers=headers)
    assert [c["name"] for c in by_name.json()] == ["Priya Shah"]

    by_email = client.get("/customers", params={"search": "sam@x.com"}, headers=headers)
    assert [c["name"] for c in by_email.json()] == ["Sam Lee"]


def test_update_and_delete_customer(client: TestClient) -> None:
    headers = _auth_headers(client)
    create_response = client.post("/customers", json={"name": "Priya Shah"}, headers=headers)
    customer_id = create_response.json()["id"]

    update_response = client.put(
        f"/customers/{customer_id}", json={"phone": "+44 20 7946 0000"}, headers=headers
    )
    assert update_response.status_code == 200
    assert update_response.json()["phone"] == "+44 20 7946 0000"

    delete_response = client.delete(f"/customers/{customer_id}", headers=headers)
    assert delete_response.status_code == 204

    get_response = client.get(f"/customers/{customer_id}", headers=headers)
    assert get_response.status_code == 404


def test_get_nonexistent_customer_is_404(client: TestClient) -> None:
    headers = _auth_headers(client)

    response = client.get("/customers/999", headers=headers)

    assert response.status_code == 404


def test_read_only_user_can_read_but_not_write(client: TestClient, db_session: Session) -> None:
    writer_headers = _auth_headers(client)
    client.post("/customers", json={"name": "Priya Shah"}, headers=writer_headers)

    create_user(db_session, email="demo@example.com", password="hunter22!!", is_read_only=True)
    token = create_access_token(subject="demo@example.com")
    reader_headers = {"Authorization": f"Bearer {token}"}

    list_response = client.get("/customers", headers=reader_headers)
    assert list_response.status_code == 200

    create_response = client.post(
        "/customers", json={"name": "Someone Else"}, headers=reader_headers
    )
    assert create_response.status_code == 403

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

DEMO_USER = "demo@atelier.dev"
DEMO_PASSWORD = "demo1234"


@pytest.fixture
def client() -> TestClient:
    app = create_app(Settings(test_user=DEMO_USER, test_password=DEMO_PASSWORD))
    with TestClient(app) as test_client:
        yield test_client


def login(client: TestClient) -> None:
    response = client.post(
        "/login",
        data={"email": DEMO_USER, "password": DEMO_PASSWORD},
        follow_redirects=False,
    )
    assert response.status_code == 303


def test_notes_page_redirects_when_unauthenticated(client: TestClient) -> None:
    response = client.get("/notes", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_notes_api_rejects_unauthenticated_requests(client: TestClient) -> None:
    response = client.get("/api/notes")

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required."}


def test_invalid_login_does_not_create_session(client: TestClient) -> None:
    response = client.post(
        "/login",
        data={"email": DEMO_USER, "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert "Invalid email or password." in response.text
    assert "atelier_demo_session" not in client.cookies


def test_successful_login_sets_session_and_returns_empty_notes(client: TestClient) -> None:
    login(client)

    assert "atelier_demo_session" in client.cookies

    response = client.get("/api/notes")
    assert response.status_code == 200
    assert response.json() == []


def test_authenticated_user_can_create_and_delete_notes(client: TestClient) -> None:
    login(client)

    create_response = client.post("/api/notes", json={"text": "Review the demo flow"})
    assert create_response.status_code == 201
    created_note = create_response.json()
    assert created_note["text"] == "Review the demo flow"

    list_response = client.get("/api/notes")
    assert list_response.status_code == 200
    assert list_response.json() == [created_note]

    delete_response = client.delete(f"/api/notes/{created_note['id']}")
    assert delete_response.status_code == 204

    final_list = client.get("/api/notes")
    assert final_list.status_code == 200
    assert final_list.json() == []

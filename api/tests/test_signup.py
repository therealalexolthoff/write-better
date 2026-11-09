"""Teacher sign-up requests (api/app/signup.py)."""

import pytest
from fastapi.testclient import TestClient

from api.app import signup
from api.app.main import app

client = TestClient(app)
AUTH = {"Authorization": "Bearer t"}


def _signed_in(monkeypatch, uid="new-1", email="new@example.com", role=None, verified=False):
    claims = {"uid": uid, "email": email, "email_verified": verified, "firebase": {"sign_in_provider": "password"}}
    if role:
        claims["role"] = role
        claims["firebase"]["sign_in_second_factor"] = "totp"
    monkeypatch.setattr("api.app.identity.verify_id_token", lambda token: claims)


@pytest.fixture
def deleted(monkeypatch):
    logins: list[str] = []
    monkeypatch.setattr("api.app.identity.delete_user", logins.append)
    return logins


def test_request_then_status(monkeypatch, fake_db, deleted):
    _signed_in(monkeypatch)
    assert client.get("/signup/me", headers=AUTH).status_code == 404  # nothing yet

    response = client.post("/signup", json={"name": "  Rosa Diaz ", "email": "spoofed@example.com"}, headers=AUTH)
    assert response.status_code == 422  # no email field: it comes from the token only
    response = client.post("/signup", json={"name": "  Rosa Diaz "}, headers=AUTH)
    assert response.json() == {"status": "pending"}
    stored = fake_db.collection("signup_requests").document("new-1").get().to_dict()
    assert stored["name"] == "Rosa Diaz" and stored["email"] == "new@example.com" and stored["status"] == "pending"
    assert "password" not in str(stored)

    assert client.get("/signup/me", headers=AUTH).json() == {"status": "pending", "email_verified": False}
    # Asking again changes nothing.
    assert client.post("/signup", json={"name": "Someone else"}, headers=AUTH).json() == {"status": "pending"}
    assert fake_db.collection("signup_requests").document("new-1").get().get("name") == "Rosa Diaz"
    assert deleted == []


def test_bots_filling_the_hidden_field_get_nothing(monkeypatch, fake_db, deleted):
    _signed_in(monkeypatch, uid="bot-1")
    response = client.post("/signup", json={"name": "Bot", "website": "http://spam.example"}, headers=AUTH)
    assert response.json() == {"status": "pending"}  # the same reply as a real request
    assert fake_db.collection("signup_requests").stream() == []
    assert deleted == ["bot-1"]  # its login is removed


def test_daily_limit(monkeypatch, fake_db, deleted):
    today = signup._today()
    for i in range(signup.MAX_SIGNUPS_PER_DAY):
        fake_db.collection("signup_requests").document(f"u{i}").set({"name": "x", "email": "x", "status": "pending", "day": today})
    _signed_in(monkeypatch)
    assert client.post("/signup", json={"name": "Late"}, headers=AUTH).status_code == 429
    assert not fake_db.collection("signup_requests").document("new-1").get().exists


def test_accounts_with_a_role_cant_sign_up(monkeypatch, fake_db, deleted):
    for role in ("teacher", "admin"):
        _signed_in(monkeypatch, uid=f"{role}-1", role=role)
        assert client.post("/signup", json={"name": "Me"}, headers=AUTH).status_code == 409
    assert fake_db.collection("signup_requests").stream() == []


def test_sign_up_needs_a_signed_in_account(fake_db):
    assert client.post("/signup", json={"name": "Anyone"}).status_code == 401
    assert client.get("/signup/me").status_code == 401

"""The admin's routes (api/app/admin.py): sign-ups and teacher accounts.
Who may reach them is in test_teacher_isolation.py."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from api.app.main import app

from .conftest import become_admin

client = TestClient(app)
AUTH = {"Authorization": "Bearer t"}


@pytest.fixture
def idp(monkeypatch):
    """Stands in for Identity Platform: records each call."""

    class Fake:
        calls: list = []
        taken: set = set()

        def __init__(self):
            self.calls = []

        def record(self, name):
            return lambda *args: self.calls.append((name, *args))

    fake = Fake()
    monkeypatch.setattr("api.app.identity.set_role", fake.record("set_role"))
    monkeypatch.setattr("api.app.identity.delete_user", fake.record("delete_user"))
    monkeypatch.setattr("api.app.identity.disable_user", fake.record("disable_user"))
    monkeypatch.setattr("api.app.identity.enable_user", fake.record("enable_user"))
    monkeypatch.setattr("api.app.identity.clear_authenticator", fake.record("clear_authenticator"))
    monkeypatch.setattr("api.app.identity.email_verified", lambda uid: uid == "verified-1")
    monkeypatch.setattr("api.app.identity.password_setup_link", lambda email: f"https://setup.example/{email}")

    def create(email, name):
        if email == "taken@example.com":
            from api.app.identity import EmailTaken

            raise EmailTaken(email)
        fake.calls.append(("create_teacher_user", email, name))
        return "new-teacher"

    monkeypatch.setattr("api.app.identity.create_teacher_user", create)
    return fake


@pytest.fixture
def as_admin(monkeypatch):
    become_admin(monkeypatch)


def _audit(fake_db):
    return [entry.get("action") for entry in fake_db.collection("audit").stream()]


def _request(fake_db, uid, name="Rosa Diaz", days_old=1):
    created = datetime.now(timezone.utc) - timedelta(days=days_old)
    fake_db.collection("signup_requests").document(uid).set(
        {"name": name, "email": f"{uid}@example.com", "status": "pending", "created_at": created, "day": "x"}
    )


def _teacher(fake_db, uid, name, active=True):
    fake_db.collection("teachers").document(uid).set({"name": name, "email": f"{uid}@example.com", "active": active})


# ---- sign-ups ----


def test_list_approve_and_reject(fake_db, as_admin, idp):
    _request(fake_db, "verified-1", "Rosa", days_old=2)
    _request(fake_db, "pending-2", "Ben", days_old=1)
    listed = client.get("/admin/signups", headers=AUTH).json()
    assert [(r["uid"], r["email_verified"]) for r in listed] == [("verified-1", True), ("pending-2", False)]

    assert client.post("/admin/signups/verified-1/approve", headers=AUTH).json() == {"status": "approved"}
    assert ("set_role", "verified-1", "teacher") in idp.calls
    teacher = fake_db.collection("teachers").document("verified-1").get().to_dict()
    assert teacher["name"] == "Rosa" and teacher["active"] is True and teacher["source"] == "signup"
    assert not fake_db.collection("signup_requests").document("verified-1").get().exists

    assert client.post("/admin/signups/pending-2/reject", headers=AUTH).json() == {"status": "rejected"}
    assert ("delete_user", "pending-2") in idp.calls
    assert not fake_db.collection("teachers").document("pending-2").get().exists
    assert fake_db.collection("signup_requests").stream() == []

    assert client.post("/admin/signups/nobody/approve", headers=AUTH).status_code == 404
    assert _audit(fake_db) == ["approve_signup", "reject_signup"]


def test_old_sign_ups_expire(fake_db, as_admin, idp):
    _request(fake_db, "old-1", days_old=31)
    _request(fake_db, "new-1", days_old=29)
    assert [r["uid"] for r in client.get("/admin/signups", headers=AUTH).json()] == ["new-1"]
    assert ("delete_user", "old-1") in idp.calls
    assert not fake_db.collection("signup_requests").document("old-1").get().exists
    assert _audit(fake_db) == ["expire_signup"]


# ---- teachers ----


def test_create_teacher_returns_a_setup_link(fake_db, as_admin, idp):
    response = client.post("/admin/teachers", json={"name": "Ana Lee", "email": "ana@example.com"}, headers=AUTH)
    assert response.json() == {"uid": "new-teacher", "setup_link": "https://setup.example/ana@example.com"}
    assert ("set_role", "new-teacher", "teacher") in idp.calls
    assert fake_db.collection("teachers").document("new-teacher").get().get("source") == "admin"
    assert client.post("/admin/teachers", json={"name": "X", "email": "taken@example.com"}, headers=AUTH).status_code == 409
    assert client.post("/admin/teachers", json={"name": "X", "email": "not-an-email"}, headers=AUTH).status_code == 422
    assert _audit(fake_db) == ["create_teacher"]


def test_list_shows_counts_not_student_work(fake_db, as_admin, idp):
    _teacher(fake_db, "t1", "Bea")
    _teacher(fake_db, "t2", "ana")
    for sid in ("s1", "s2"):
        fake_db.collection("students").document(sid).set({"username": sid, "teacher_id": "t1", "teacher_notes": "private"})
    teachers = client.get("/admin/teachers", headers=AUTH).json()
    assert [(t["name"], t["student_count"]) for t in teachers] == [("ana", 0), ("Bea", 2)]
    assert "private" not in str(teachers) and "s1" not in str(teachers)


def test_deactivate_reactivate_links_and_authenticator(fake_db, as_admin, idp):
    _teacher(fake_db, "t1", "Bea")
    client.post("/admin/teachers/t1/deactivate", headers=AUTH)
    assert fake_db.collection("teachers").document("t1").get().get("active") is False
    client.post("/admin/teachers/t1/reactivate", headers=AUTH)
    assert fake_db.collection("teachers").document("t1").get().get("active") is True
    assert client.post("/admin/teachers/t1/password-link", headers=AUTH).json() == {"link": "https://setup.example/t1@example.com"}
    client.post("/admin/teachers/t1/reset-authenticator", headers=AUTH)
    assert [c for c in idp.calls if c[0] != "set_role"] == [("disable_user", "t1"), ("enable_user", "t1"), ("clear_authenticator", "t1")]
    assert client.post("/admin/teachers/nobody/deactivate", headers=AUTH).status_code == 404
    assert _audit(fake_db) == ["deactivate_teacher", "reactivate_teacher", "teacher_password_link", "reset_teacher_authenticator"]


def test_transfer_moves_every_record(fake_db, as_admin, idp):
    _teacher(fake_db, "t1", "Leaving")
    _teacher(fake_db, "t2", "Staying")
    _teacher(fake_db, "t3", "Gone", active=False)
    for collection in ("students", "exercises", "submissions", "jobs"):
        fake_db.collection(collection).document(f"{collection}-1").set({"teacher_id": "t1"})
        fake_db.collection(collection).document(f"{collection}-other").set({"teacher_id": "t9"})

    assert client.post("/admin/teachers/t1/transfer", json={"to_teacher_id": "t1"}, headers=AUTH).status_code == 422
    assert client.post("/admin/teachers/t1/transfer", json={"to_teacher_id": "t3"}, headers=AUTH).status_code == 409
    assert client.post("/admin/teachers/t1/transfer", json={"to_teacher_id": "nobody"}, headers=AUTH).status_code == 404

    moved = client.post("/admin/teachers/t1/transfer", json={"to_teacher_id": "t2"}, headers=AUTH).json()["moved"]
    assert moved == {"exercises": 1, "submissions": 1, "jobs": 1, "students": 1}
    for collection in ("students", "exercises", "submissions", "jobs"):
        assert fake_db.collection(collection).document(f"{collection}-1").get().get("teacher_id") == "t2"
        assert fake_db.collection(collection).document(f"{collection}-other").get().get("teacher_id") == "t9"
    # Running it again finds nothing left to move.
    again = client.post("/admin/teachers/t1/transfer", json={"to_teacher_id": "t2"}, headers=AUTH).json()["moved"]
    assert set(again.values()) == {0}
    assert _audit(fake_db).count("transfer_students") == 2

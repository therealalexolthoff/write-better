"""A teacher's classes (api/app/classes.py), and students in them.
Who may reach them is in test_teacher_isolation.py."""

import pytest
from fastapi.testclient import TestClient

from api.app.main import app

from .test_exercises import AUTH, student  # noqa: F401 (fixture)

client = TestClient(app)


@pytest.fixture
def idp(monkeypatch):
    monkeypatch.setattr("api.app.identity.create_student_user", lambda username, password: f"uid-{username}")
    monkeypatch.setattr("api.app.identity.set_student_claims", lambda uid, student_id: None)


def _audit(fake_db):
    return [entry.get("action") for entry in fake_db.collection("audit").stream()]


def test_create_list_rename_archive(fake_db, as_teacher, student):  # noqa: F811
    created = client.post("/classes", json={"name": "  Tuesday morning "}, headers=AUTH).json()
    assert created["name"] == "Tuesday morning" and created["archived"] is False and created["student_count"] == 0
    tuesday = created["class_id"]

    client.put(f"/classes/{tuesday}", json={"name": "Tuesday advanced"}, headers=AUTH)
    client.post("/classes/c1/archive", headers=AUTH)
    listed = client.get("/classes", headers=AUTH).json()
    # Open classes first, then archived; counts of students in each.
    assert [(c["name"], c["archived"], c["student_count"]) for c in listed] == [
        ("Tuesday advanced", False, 0),
        ("Monday evening", True, 2),
    ]
    client.post("/classes/c1/reopen", headers=AUTH)
    assert not fake_db.collection("classes").document("c1").get().get("archived")
    assert client.post("/classes", json={"name": ""}, headers=AUTH).status_code == 422
    assert _audit(fake_db) == ["create_class", "archive_class", "reopen_class"]


def test_new_students_go_into_an_open_class(fake_db, as_teacher, student, idp):  # noqa: F811
    body = {"username": "maria.k", "password": "longenough"}
    assert client.post("/students", json=body, headers=AUTH).status_code == 422  # a class is required
    assert client.post("/students", json={**body, "class_id": "nope"}, headers=AUTH).status_code == 404
    client.post("/classes/c1/archive", headers=AUTH)
    assert client.post("/students", json={**body, "class_id": "c1"}, headers=AUTH).status_code == 409
    client.post("/classes/c1/reopen", headers=AUTH)
    created = client.post("/students", json={**body, "class_id": "c1"}, headers=AUTH).json()
    assert fake_db.collection("students").document(created["student_id"]).get().get("class_id") == "c1"


def test_lists_and_overview_filter_by_class(fake_db, as_teacher, student, idp):  # noqa: F811
    other = client.post("/classes", json={"name": "Saturday"}, headers=AUTH).json()["class_id"]
    client.post("/students", json={"username": "kim.p", "password": "longenough", "class_id": other}, headers=AUTH)
    assert sorted(s["username"] for s in client.get("/students", headers=AUTH).json()) == ["Alex", "Sam", "kim.p"]
    assert [s["username"] for s in client.get(f"/students?class_id={other}", headers=AUTH).json()] == ["kim.p"]
    assert [r["username"] for r in client.get("/overview?class_id=c1", headers=AUTH).json()] == ["Alex", "Sam"]
    assert [r["username"] for r in client.get(f"/overview?class_id={other}", headers=AUTH).json()] == ["kim.p"]


def test_move_a_student_keeps_their_work(fake_db, as_teacher, student):  # noqa: F811
    other = client.post("/classes", json={"name": "Saturday"}, headers=AUTH).json()["class_id"]
    client.put("/students/s1/notes", json={"teacher_notes": "Keeps a diary."}, headers=AUTH)
    moved = client.put("/students/s1/class", json={"class_id": other}, headers=AUTH)
    assert moved.json()["class_id"] == other
    assert client.get("/students/s1/profile", headers=AUTH).json()["teacher_notes"] == "Keeps a diary."
    client.post(f"/classes/{other}/archive", headers=AUTH)
    assert client.put("/students/s2/class", json={"class_id": other}, headers=AUTH).status_code == 409
    assert "move_student" in _audit(fake_db)

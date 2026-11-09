"""AI spending: the atomic total, the cap, the teacher's "paused" notice,
and the admin's spending screen (api/app/spend.py, admin.py)."""

import pytest
from fastapi.testclient import TestClient

from api.app import jobs, spend
from api.app.main import app

from .conftest import as_student, become_admin, become_teacher
from .test_review import _evaluate, _scrub, _submitted
from .test_exercises import AUTH, harness, student  # noqa: F401 (fixtures)

client = TestClient(app)


def test_spend_and_calls_add_up(fake_db):
    for cost in (0.01, 0.02, 0.03):
        spend.record_spend(cost, cap_usd=15.0)
    doc = fake_db.collection("spend").document(spend.month_key()).get().to_dict()
    assert doc["total_usd"] == pytest.approx(0.06) and doc["calls"] == 3
    assert spend.recent_months() == [{"month": spend.month_key(), "total_usd": pytest.approx(0.06), "calls": 3}]


def test_at_the_cap_teachers_see_it_paused(monkeypatch, fake_db, as_teacher, harness, student):  # noqa: F811
    assert client.get("/ai-status", headers=AUTH).json() == {"paused": False, "message": ""}
    exercise_id = _submitted(monkeypatch, harness)
    _scrub(exercise_id)
    fake_db.collection("spend").document(spend.month_key()).set({"total_usd": 14.99})

    status = client.get("/ai-status", headers=AUTH).json()
    assert status["paused"] is True and "paused" in status["message"]
    assert "14.99" not in str(status)  # amounts are the admin's
    response = _evaluate(exercise_id, harness)
    assert response.status_code == 409 and response.json()["detail"] == status["message"]
    assert harness.calls == []
    # Existing work can still be read and edited.
    assert client.get(f"/exercises/{exercise_id}", headers=AUTH).status_code == 200
    assert _scrub(exercise_id, "On saturday I go to the market.").status_code == 200

    as_student(monkeypatch, student_id="s1")
    assert client.get("/ai-status", headers=AUTH).status_code == 403


def test_admin_sees_this_months_spend(monkeypatch, fake_db, as_teacher, harness, student):  # noqa: F811
    fake_db.collection("teachers").document("teacher-1").set({"name": "Ana Lee", "email": "a@example.com", "active": True})
    exercise_id = _submitted(monkeypatch, harness)
    _scrub(exercise_id)
    _evaluate(exercise_id, harness)  # one AI call (mock model: free)
    failed = jobs.create_job("transcribe", "s1", "teacher-1", "v7")
    jobs.fail_job(failed, "boom")
    spend.record_spend(0.04, cap_usd=15.0)

    become_admin(monkeypatch)
    data = client.get("/admin/spending", headers=AUTH).json()
    assert data["month"] == spend.month_key()
    assert data["total_usd"] == pytest.approx(0.04) and data["cap_usd"] == 15.0 and data["max_cap_usd"] == 20.0
    assert data["paused"] is False and data["calls"] == 2 and data["failed_calls"] == 1
    assert {row["operation"]: row["calls"] for row in data["by_operation"]} == {"evaluate_writing": 1, "transcribe": 1}
    assert [(row["name"], row["calls"]) for row in data["by_teacher"]] == [("Ana Lee", 2)]
    assert "Alex" not in str(data) and "s1" not in str(data)  # nothing about students

    become_teacher(monkeypatch)
    assert client.get("/admin/spending", headers=AUTH).status_code == 403


def test_admin_sets_the_cap_up_to_20(monkeypatch, fake_db):
    become_admin(monkeypatch)
    for too_much in (20.01, 100, -1):
        assert client.put("/admin/spending/cap", json={"monthly_cap_usd": too_much}, headers=AUTH).status_code == 422
    assert client.put("/admin/spending/cap", json={"monthly_cap_usd": 8.5}, headers=AUTH).json() == {"cap_usd": 8.5}
    assert client.get("/admin/spending", headers=AUTH).json()["cap_usd"] == 8.5
    client.put("/admin/spending/cap", json={"monthly_cap_usd": 0}, headers=AUTH)  # pauses AI entirely
    assert client.get("/admin/spending", headers=AUTH).json()["paused"] is True
    actions = [entry.get("action") for entry in fake_db.collection("audit").stream()]
    assert actions == ["set_spend_cap", "set_spend_cap"]

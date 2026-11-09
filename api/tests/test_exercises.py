"""Writing exercises: assign -> autosave -> submit, plus who may see what
along the way, reopening, and the shared fixtures other test files use."""

import pytest
from fastapi.testclient import TestClient

from api.app.main import app

from .conftest import as_student, become_teacher

client = TestClient(app)
AUTH = {"Authorization": "Bearer t"}

WRITING = {"kind": "writing", "title": "My weekend", "prompt": "Describe your weekend.", "min_words": 50, "max_words": 150}
TYPED = "On saturday I go to the market with my sister Maria."


def _envelope(result):
    return {"result": result, "model": "mock", "tokens_in": 10, "tokens_out": 10, "latency_ms": 1.0}


@pytest.fixture
def harness(monkeypatch):
    """Stands in for the harness service. Set `harness.result` to change
    what it returns; records each request body it receives."""

    class Fake:
        result: dict = {}
        calls: list = []

        def __call__(self, path, body):
            self.calls.append(body)
            return _envelope(self.result)

    fake = Fake()
    fake.calls = []
    monkeypatch.setattr("api.app.harness_ops.post_to_harness", fake)
    return fake


@pytest.fixture
def student(fake_db):
    """Two students of teacher-1, the teacher the as_teacher fixture signs in as."""
    for student_id, name in (("s1", "Alex"), ("s2", "Sam")):
        fake_db.collection("students").document(student_id).set(
            {"username": name, "auth_uid": f"u{student_id[1:]}", "active": True, "teacher_id": "teacher-1"}
        )


def _assign(student_id="s1", draft=WRITING):
    """A writing exercise assigned to one student, as the teacher."""
    response = client.post(
        "/exercises/writing-for-students", json={"draft": draft, "student_ids": [student_id]}, headers=AUTH
    )
    assert response.status_code == 200, response.text
    return response.json()["exercise_ids"][0]


def _submission(fake_db, exercise_id):
    return fake_db.collection("submissions").document(exercise_id).get().to_dict()


# ---- what students can see ----


def test_student_cannot_see_other_students_work(monkeypatch, fake_db, as_teacher, harness, student):
    other_id = _assign("s2")

    as_student(monkeypatch, student_id="s1")
    assert client.get(f"/exercises/{other_id}", headers=AUTH).status_code == 404
    assert client.put(f"/exercises/{other_id}/answers", json={"answers": {}}, headers=AUTH).status_code == 404
    assert client.post(f"/exercises/{other_id}/submit", json={"answers": {}}, headers=AUTH).status_code == 404
    assert client.get("/me/exercises", headers=AUTH).json() == []


def test_student_view_shows_the_prompt_but_no_teacher_fields(monkeypatch, fake_db, as_teacher, harness, student):
    exercise_id = _assign()
    as_student(monkeypatch, student_id="s1")
    view = client.get(f"/exercises/{exercise_id}", headers=AUTH).json()
    assert view["prompt"] == WRITING["prompt"] and view["max_words"] == 150 and view["state"] == "assigned"
    for hidden in ("teacher_request", "scrubbed_answers", "evaluation", "student_id", "photo_count"):
        assert hidden not in view, hidden


# ---- writing and submitting ----


def test_autosave_then_submit_locks_the_response(monkeypatch, fake_db, as_teacher, harness, student):
    exercise_id = _assign()

    as_student(monkeypatch, student_id="s1")
    assert client.get("/me/exercises", headers=AUTH).json()[0]["state"] == "assigned"
    assert client.put(f"/exercises/{exercise_id}/answers", json={"answers": {"text": "On sat"}}, headers=AUTH).status_code == 200
    resumed = client.get(f"/exercises/{exercise_id}", headers=AUTH).json()
    assert resumed["state"] == "in_progress" and resumed["answers"] == {"text": "On sat"}

    submit = {"answers": {"text": TYPED}}
    assert client.post(f"/exercises/{exercise_id}/submit", json=submit, headers=AUTH).status_code == 200
    # Locked after submit, and still no results before release.
    assert client.put(f"/exercises/{exercise_id}/answers", json=submit, headers=AUTH).status_code == 409
    assert client.post(f"/exercises/{exercise_id}/submit", json=submit, headers=AUTH).status_code == 409
    view = client.get(f"/exercises/{exercise_id}", headers=AUTH).json()
    assert "spans" not in view and "comment" not in view

    become_teacher(monkeypatch)
    view = client.get(f"/exercises/{exercise_id}", headers=AUTH).json()
    assert view["state"] == "scrub_review" and view["final_source"] == "typed"
    assert view["answers"] == {"text": TYPED}
    assert view["scrubbed_answers"] == {"text": TYPED}  # the editable copy starts as the original
    assert client.post(f"/exercises/{exercise_id}/release", headers=AUTH).status_code == 409  # not evaluated


def test_answers_must_be_just_the_text(monkeypatch, fake_db, as_teacher, harness, student):
    exercise_id = _assign()
    as_student(monkeypatch, student_id="s1")
    for bad in ({"i1": "x"}, {"text": "x", "extra": "y"}, {"text": ["x"]}, {"text": "x" * 10_001}):
        response = client.put(f"/exercises/{exercise_id}/answers", json={"answers": bad}, headers=AUTH)
        assert response.status_code == 422, bad


def test_late_autosave_cannot_undo_a_submit(monkeypatch, fake_db, as_teacher, harness, student):
    """An autosave already on its way when the student taps Submit reads
    "in_progress"; the submit lands before the autosave writes. The
    autosave must then fail rather than unlock the submitted work."""
    exercise_id = _assign()
    as_student(monkeypatch, student_id="s1")

    def submit_lands_meanwhile(answers):
        fake_db.collection("submissions").document(exercise_id).update({"state": "scrub_review"})

    monkeypatch.setattr("api.app.exercises._check_answer_shapes", submit_lands_meanwhile)
    response = client.put(f"/exercises/{exercise_id}/answers", json={"answers": {"text": "x"}}, headers=AUTH)
    assert response.status_code == 409
    assert _submission(fake_db, exercise_id)["state"] == "scrub_review"


def test_teacher_cannot_answer_for_a_student(fake_db, as_teacher, harness, student):
    exercise_id = _assign()
    response = client.put(f"/exercises/{exercise_id}/answers", json={"answers": {"text": "x"}}, headers=AUTH)
    assert response.status_code == 403
    assert client.get("/me/exercises", headers=AUTH).status_code == 403


# ---- reopening ----


def test_reopen_is_audited_and_not_allowed_after_release(monkeypatch, fake_db, as_teacher, harness, student):
    exercise_id = _assign()
    as_student(monkeypatch, student_id="s1")
    client.post(f"/exercises/{exercise_id}/submit", json={"answers": {"text": TYPED}}, headers=AUTH)

    become_teacher(monkeypatch)
    assert client.post(f"/exercises/{exercise_id}/reopen", headers=AUTH).status_code == 200
    submission = _submission(fake_db, exercise_id)
    assert submission["state"] == "in_progress"
    assert submission["answers"] == {"text": TYPED}  # kept so the student can continue
    assert any(e.get("action") == "reopen_submission" for e in fake_db.collection("audit").stream())

    # Evaluated with nothing flagged and released: no longer reopenable.
    as_student(monkeypatch, student_id="s1")
    client.post(f"/exercises/{exercise_id}/submit", json={"answers": {"text": TYPED}}, headers=AUTH)
    become_teacher(monkeypatch)
    harness.result = {"annotations": [], "comment": "No errors."}
    assert client.post(f"/exercises/{exercise_id}/evaluate", json={"note": ""}, headers=AUTH).status_code == 200
    client.post(f"/exercises/{exercise_id}/approve", headers=AUTH)
    assert client.post(f"/exercises/{exercise_id}/release", headers=AUTH).json()["state"] == "released"
    assert client.post(f"/exercises/{exercise_id}/reopen", headers=AUTH).status_code == 409


def test_taxonomy_comes_from_the_shared_list(fake_db, as_teacher):
    codes = [c["code"] for c in client.get("/taxonomy", headers=AUTH).json()]
    assert len(codes) == 14 and "VT" in codes


def test_cut_features_are_gone(fake_db, as_teacher, harness, student):
    """Write Better has no AI-generated exercises, grammar items or lessons."""
    for method, path in (
        ("POST", "/exercises/generate"),
        ("POST", "/exercises/x/regenerate"),
        ("POST", "/exercises/x/assign"),
        ("POST", "/lessons/generate"),
        ("GET", "/me/lessons"),
    ):
        assert client.request(method, path, json={}, headers=AUTH).status_code in (404, 405), path
    grammar = {"kind": "grammar", "title": "x", "items": [{"id": "i1", "type": "short_answer", "prompt": "Why?"}]}
    response = client.post("/exercises/writing-for-students", json={"draft": grammar, "student_ids": ["s1"]}, headers=AUTH)
    assert response.status_code == 422
    assert harness.calls == []

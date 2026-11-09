"""The learner profile, teacher notes, and the class overview."""

from fastapi.testclient import TestClient

from api.app.main import app
from api.app.profile import compute_profile

from .conftest import as_student, become_teacher
from .test_exercises import AUTH, _assign, harness, student  # noqa: F401 (fixtures)
from .test_review import _evaluate, _scrub, _submitted
from .test_writing import _released

client = TestClient(app)


# ---- profile: plain counting over approved data ----


def _writing_pair(codes, outcomes=None, text="aa bb cc dd ee"):
    annotations = [{"code": c, "start": 3 * i, "end": 3 * i + 2} for i, c in enumerate(codes)]
    submission = {
        "state": "revision_submitted",
        "scrubbed_answers": {"text": text},
        "evaluation": {"annotations": annotations, "comment": ""},
        "revision": {"edits": {k: "x" for k in (outcomes or {})}, "outcomes": outcomes or {}},
    }
    return {"kind": "writing"}, submission


def test_profile_counts_annotations_and_outcomes():
    first = _writing_pair(["VT", "ART", "VT"], outcomes={"0": "fixed", "2": "changed_wrongly"})
    second = _writing_pair(["SP"])
    rows = {row["code"]: row for row in compute_profile([first, second])}
    assert rows["VT"]["errors"] == 2
    assert (rows["VT"]["fixed"], rows["VT"]["changed_wrongly"], rows["VT"]["unfixed"]) == (1, 1, 0)
    assert rows["ART"]["errors"] == 1 and rows["SP"]["errors"] == 1
    assert "WO" not in rows  # never flagged
    assert [row["code"] for row in compute_profile([first, second])][0] == "VT"  # most frequent first


def test_profile_endpoint_uses_only_approved_work(monkeypatch, fake_db, as_teacher, harness, student):  # noqa: F811
    _released(monkeypatch, harness)  # one VT annotation, approved and released
    unapproved = _submitted(monkeypatch, harness)  # evaluated, but not approved yet
    _scrub(unapproved)
    _evaluate(unapproved, harness)
    _assign()  # assigned, not started

    data = client.get("/students/s1/profile", headers=AUTH).json()
    assert {row["code"]: row["errors"] for row in data["profile"]["codes"]} == {"VT": 1}
    assert data["profile"]["submissions_counted"] == 1

    # Once approved, it counts; the window setting limits how many do.
    client.post(f"/exercises/{unapproved}/approve", headers=AUTH)
    assert client.get("/students/s1/profile", headers=AUTH).json()["profile"]["submissions_counted"] == 2
    fake_db.collection("settings").document("global").set({"profile_window": 1})
    assert client.get("/students/s1/profile", headers=AUTH).json()["profile"]["submissions_counted"] == 1

    as_student(monkeypatch, student_id="s1")
    assert client.get("/students/s1/profile", headers=AUTH).status_code == 403


# ---- teacher notes ----


def test_notes_are_teacher_only_and_never_reach_the_ai(monkeypatch, fake_db, as_teacher, harness, student):  # noqa: F811
    assert client.put("/students/s1/notes", json={"teacher_notes": "Works as a nurse."}, headers=AUTH).status_code == 200
    assert client.get("/students/s1/profile", headers=AUTH).json()["teacher_notes"] == "Works as a nurse."
    as_student(monkeypatch, student_id="s1")
    assert client.put("/students/s1/notes", json={"teacher_notes": "x"}, headers=AUTH).status_code == 403
    become_teacher(monkeypatch)

    exercise_id = _submitted(monkeypatch, harness)
    _scrub(exercise_id)
    assert _evaluate(exercise_id, harness).status_code == 200
    assert "nurse" not in str(harness.calls)

    as_student(monkeypatch, student_id="s1")
    assert "nurse" not in str(client.get(f"/exercises/{exercise_id}", headers=AUTH).json())


# ---- class overview ----


def test_overview_lists_unfinished_work(monkeypatch, fake_db, as_teacher, harness, student):  # noqa: F811
    released = _released(monkeypatch, harness)  # revision open: unfinished
    fresh = _assign()  # assigned, not started

    rows = {row["username"]: row for row in client.get("/overview", headers=AUTH).json()}
    assert [(w["exercise_id"], w["state"]) for w in rows["Alex"]["work"]] == [
        (fresh, "assigned"),
        (released, "revision_open"),
    ]
    assert rows["Sam"] == {"student_id": "s2", "username": "Sam", "work": []}

    # A revision counts as finished once the marks are sent to the student.
    as_student(monkeypatch, student_id="s1")
    client.post(f"/exercises/{released}/revision/submit", json={"edits": {"0": "went"}}, headers=AUTH)
    become_teacher(monkeypatch)
    work = client.get("/overview", headers=AUTH).json()[0]["work"]
    assert [w["state"] for w in work] == ["assigned", "revision_submitted"]
    client.put(f"/exercises/{released}/revision/outcomes", json={"outcomes": {"0": "fixed"}}, headers=AUTH)
    client.post(f"/exercises/{released}/revision/send", headers=AUTH)
    assert [w["state"] for w in client.get("/overview", headers=AUTH).json()[0]["work"]] == ["assigned"]

    as_student(monkeypatch, student_id="s1")
    assert client.get("/overview", headers=AUTH).status_code == 403

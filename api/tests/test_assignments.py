"""Writing assignments for a class (api/app/assignments.py). Who may reach
them is in test_teacher_isolation.py."""

from fastapi.testclient import TestClient

from api.app.main import app

from .conftest import as_student, become_teacher
from .test_exercises import AUTH, TYPED, WRITING, harness, student  # noqa: F401 (fixtures)

client = TestClient(app)


def _add_student(fake_db, student_id, name, class_id="c1", active=True):
    fake_db.collection("students").document(student_id).set(
        {"username": name, "auth_uid": f"u-{student_id}", "active": active, "teacher_id": "teacher-1", "class_id": class_id}
    )


def _create(**body):
    return client.post("/assignments", json={"class_id": "c1", "draft": WRITING, **body}, headers=AUTH)


def test_whole_class_gets_a_copy_each(monkeypatch, fake_db, as_teacher, harness, student):  # noqa: F811
    _add_student(fake_db, "s3", "Kim", active=False)  # inactive: left out
    fake_db.collection("classes").document("c2").set({"teacher_id": "teacher-1", "name": "Other", "archived": False})
    _add_student(fake_db, "s4", "Lee", class_id="c2")  # another class: left out

    created = _create().json()
    copies = [fake_db.collection("exercises").document(e).get().to_dict() for e in created["exercise_ids"]]
    assert sorted(c["student_id"] for c in copies) == ["s1", "s2"]
    assert all(c["assignment_id"] == created["assignment_id"] and c["class_id"] == "c1" for c in copies)
    assert all(c["prompt"] == WRITING["prompt"] and c["status"] == "assigned" for c in copies)
    assert harness.calls == []  # no AI involved

    # Each copy is an ordinary exercise for its own student.
    as_student(monkeypatch, student_id="s2", uid="u2")
    mine = client.get("/me/exercises", headers=AUTH).json()
    assert len(mine) == 1 and mine[0]["title"] == WRITING["title"]
    other = next(e for e, c in zip(created["exercise_ids"], copies) if c["student_id"] == "s1")
    assert client.get(f"/exercises/{other}", headers=AUTH).status_code == 404


def test_chosen_students_must_be_active_and_in_the_class(fake_db, as_teacher, harness, student):  # noqa: F811
    _add_student(fake_db, "s3", "Kim", active=False)
    fake_db.collection("classes").document("c2").set({"teacher_id": "teacher-1", "name": "Other", "archived": False})
    _add_student(fake_db, "s4", "Lee", class_id="c2")
    for bad in (["s1", "s3"], ["s4"], ["nobody"]):
        assert _create(student_ids=bad).status_code == 404, bad
    assert _create(student_ids=[]).status_code == 422
    assert fake_db.collection("assignments").stream() == [] and fake_db.collection("exercises").stream() == []

    created = _create(student_ids=["s2", "s2"]).json()  # picked twice, one copy
    assert len(created["exercise_ids"]) == 1


def test_drafts_are_checked(fake_db, as_teacher, harness, student):  # noqa: F811
    assert _create(draft={**WRITING, "prompt": " "}).status_code == 422
    assert _create(draft={**WRITING, "min_words": 90, "max_words": 50}).status_code == 422
    assert fake_db.collection("assignments").stream() == []


def test_archived_or_empty_classes_take_no_assignment(fake_db, as_teacher, harness, student):  # noqa: F811
    fake_db.collection("classes").document("empty").set({"teacher_id": "teacher-1", "name": "New", "archived": False})
    assert client.post("/assignments", json={"class_id": "empty", "draft": WRITING}, headers=AUTH).status_code == 409
    client.post("/classes/c1/archive", headers=AUTH)
    assert _create().status_code == 409


def test_progress_list_and_detail(monkeypatch, fake_db, as_teacher, harness, student):  # noqa: F811
    first = _create().json()
    second = _create(draft={**WRITING, "title": "A letter"}, student_ids=["s1"]).json()
    # s1 submits the first assignment: it's now the teacher's turn.
    s1_copy = next(e for e in first["exercise_ids"] if fake_db.collection("exercises").document(e).get().get("student_id") == "s1")
    as_student(monkeypatch, student_id="s1")
    client.put(f"/exercises/{s1_copy}/answers", json={"answers": {"text": "On sat"}}, headers=AUTH)
    client.post(f"/exercises/{s1_copy}/submit", json={"answers": {"text": TYPED}}, headers=AUTH)
    become_teacher(monkeypatch)

    listed = client.get("/assignments?class_id=c1", headers=AUTH).json()
    assert {row["assignment_id"] for row in listed} == {first["assignment_id"], second["assignment_id"]}
    row = next(r for r in listed if r["assignment_id"] == first["assignment_id"])
    assert row["students"] == 2
    assert row["progress"] == {"not_started": 1, "writing": 0, "needs_you": 1, "with_student": 0, "done": 0}

    detail = client.get(f"/assignments/{first['assignment_id']}", headers=AUTH).json()
    assert detail["prompt"] == WRITING["prompt"] and detail["class_id"] == "c1"
    assert [(s["username"], s["state"]) for s in detail["students"]] == [("Alex", "scrub_review"), ("Sam", "assigned")]
    assert detail["not_assigned"] == []
    assert "Maria" not in str(detail)  # no student writing on the overview


def test_add_students_who_join_later(fake_db, as_teacher, harness, student):  # noqa: F811
    created = _create(student_ids=["s1"]).json()
    url = f"/assignments/{created['assignment_id']}"
    _add_student(fake_db, "s5", "Noor")  # joins the class later
    assert [s["username"] for s in client.get(url, headers=AUTH).json()["not_assigned"]] == ["Noor", "Sam"]

    added = client.post(f"{url}/students", json={"student_ids": ["s5", "s1"]}, headers=AUTH).json()  # s1 already has it
    assert len(added["exercise_ids"]) == 1
    detail = client.get(url, headers=AUTH).json()
    assert [s["username"] for s in detail["students"]] == ["Alex", "Noor"]
    assert [s["username"] for s in detail["not_assigned"]] == ["Sam"]
    actions = [entry.get("action") for entry in fake_db.collection("audit").stream()]
    assert actions == ["create_assignment", "add_assignment_students"]


def test_students_cant_use_assignments(monkeypatch, fake_db, as_teacher, harness, student):  # noqa: F811
    created = _create().json()
    as_student(monkeypatch, student_id="s1")
    assert _create().status_code == 403
    assert client.get("/assignments", headers=AUTH).status_code == 403
    assert client.get(f"/assignments/{created['assignment_id']}", headers=AUTH).status_code == 403

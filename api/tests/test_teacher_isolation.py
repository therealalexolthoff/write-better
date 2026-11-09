"""Teachers are kept separate (CLAUDE.md), the admin never reaches student
work, students only reach their own, only the admin reaches the admin
routes, and an account with no role reaches only its own sign-up.

Walks every endpoint the app publishes (its OpenAPI listing), like
test_every_route_needs_login.py, so a new endpoint that forgets its
ownership check fails here. Every call is made against real records that
belong to teacher-1 ("teacher A"), by callers who must be refused:
teacher-2 ("teacher B"), the admin, teacher B's student, and teacher A's
other student. A refusal must come before anything else - no 422 for a
bad body, no change to any stored data.
"""

import copy
import re

import pytest
from fastapi.testclient import TestClient

from api.app.main import app

from .conftest import as_student, become_admin, become_teacher
from .test_exercises import AUTH, harness, student  # noqa: F401 (fixtures)
from .test_review import _evaluation
from .test_writing import PHOTO, TYPED, bucket  # noqa: F401 (fixture)

client = TestClient(app)

PUBLIC = {"/health", "/health/harness", "/config"}
# Endpoints with no student or exercise id in the path. The walk below
# can't aim these at teacher A's records, so each is checked by hand in
# this file. A new one must be added here (and checked), or
# test_every_endpoint_is_covered fails.
NO_ID_ENDPOINTS = {
    ("GET", "/students"),
    ("POST", "/students"),
    ("GET", "/exercises"),  # student_id is a query parameter
    ("POST", "/exercises/writing-for-students"),
    ("GET", "/me/exercises"),
    ("GET", "/overview"),
    ("GET", "/taxonomy"),
    ("GET", "/classes"),
    ("POST", "/classes"),
    ("GET", "/me/errors"),
}
# The sign-up routes: the only ones a role-less account reaches, and they
# only ever touch the caller's own request (api/tests/test_signup.py).
SIGNUP_ENDPOINTS = {("POST", "/signup"), ("GET", "/signup/me")}


def _is_admin(path):
    return path.startswith("/admin/") or path == "/admin"


def _endpoints():
    return [
        (method.upper(), path)
        for path, methods in app.openapi()["paths"].items()
        if path not in PUBLIC
        for method in methods
    ]


IDS = ("{student_id}", "{exercise_id}", "{class_id}")


def _has_id(path):
    return any(name in path for name in IDS)


def _id_endpoints():
    """Endpoints aimed at a class's, a student's or an exercise's records."""
    return [(m, p) for m, p in _endpoints() if _has_id(p)]


def _admin_endpoints():
    return [(m, p) for m, p in _endpoints() if _is_admin(p)]


def _sign_in(monkeypatch, caller):
    if caller == "teacher B":
        become_teacher(monkeypatch, uid="teacher-2")
    elif caller == "admin":
        become_admin(monkeypatch)
    elif caller == "teacher B's student":
        as_student(monkeypatch, student_id="b1", uid="ub1")
    elif caller == "teacher A's other student":
        as_student(monkeypatch, student_id="s2", uid="u2")


@pytest.fixture
def world(monkeypatch, fake_db, harness, student, bucket):  # noqa: F811
    """Teacher A's student s1 with one exercise that has gone all the way
    to an open revision (photos, scrub, evaluation, release), and teacher
    B's own student b1. Leaves the test signed in as teacher A."""
    fake_db.collection("classes").document("cb").set({"teacher_id": "teacher-2", "name": "B's class", "archived": False})
    fake_db.collection("students").document("b1").set(
        {"username": "Bea", "auth_uid": "ub1", "active": True, "teacher_id": "teacher-2", "class_id": "cb"}
    )
    become_teacher(monkeypatch)
    draft = {"kind": "writing", "title": "My weekend", "prompt": "Describe your weekend."}
    exercise_id = client.post(
        "/exercises/writing-for-students", json={"draft": draft, "student_ids": ["s1"]}, headers=AUTH
    ).json()["exercise_ids"][0]
    client.post(f"/exercises/{exercise_id}/photos", content=PHOTO, headers={"Content-Type": "image/jpeg", **AUTH})
    as_student(monkeypatch, student_id="s1")
    assert client.post(f"/exercises/{exercise_id}/submit", json={"answers": {"text": TYPED}}, headers=AUTH).status_code == 200
    become_teacher(monkeypatch)
    harness.result = _evaluation()
    assert client.post(f"/exercises/{exercise_id}/evaluate", json={"note": ""}, headers=AUTH).status_code == 200
    client.post(f"/exercises/{exercise_id}/approve", headers=AUTH)
    assert client.post(f"/exercises/{exercise_id}/release", headers=AUTH).json()["state"] == "revision_open"
    return {"student_id": "s1", "exercise_id": exercise_id, "class_id": "c1"}


def _url(path, world):
    return re.sub(r"{(student_id|exercise_id|class_id)}", lambda m: world[m.group(1)], path)


def test_every_endpoint_is_covered():
    """Each endpoint is exactly one of: walked for student/exercise records,
    walked as an admin route, a sign-up route, or checked by hand below."""
    for method, path in _endpoints():
        kinds = [
            _has_id(path),
            _is_admin(path),
            (method, path) in SIGNUP_ENDPOINTS,
            (method, path) in NO_ID_ENDPOINTS,
        ]
        assert sum(kinds) == 1, (
            f"{method} {path}: check its access by hand in this file and add it to NO_ID_ENDPOINTS "
            "(or SIGNUP_ENDPOINTS), or give it a class/student/exercise id or the /admin prefix"
        )


@pytest.mark.parametrize("caller", ["teacher B", "admin", "teacher B's student", "teacher A's other student"])
def test_nobody_else_reaches_teacher_a_records(monkeypatch, fake_db, world, caller):
    endpoints = _id_endpoints()
    assert len(endpoints) >= 25  # sanity: the walk really found the app's endpoints
    _sign_in(monkeypatch, caller)
    for method, path in endpoints:
        before = copy.deepcopy(fake_db._store)
        # An empty body: if the refusal didn't come first, this would be a 422.
        response = client.request(method, _url(path, world), json={}, headers=AUTH)
        assert response.status_code in (403, 404), f"{caller}: {method} {path} answered {response.status_code}"
        assert fake_db._store == before, f"{caller}: {method} {path} changed stored data"
        for secret in ("Alex", TYPED, "went"):
            assert secret not in response.text, f"{caller}: {method} {path} leaked {secret!r}"


def test_teacher_a_still_reaches_their_own(monkeypatch, fake_db, world):
    """The walk above only means something if these ids are right."""
    for path in ("/students/{student_id}", "/students/{student_id}/profile", "/exercises/{exercise_id}", "/exercises/{exercise_id}/photos"):
        assert client.get(_url(path, world), headers=AUTH).status_code == 200, path
    for path in ("/students?class_id={class_id}", "/overview?class_id={class_id}"):
        assert client.get(_url(path, world), headers=AUTH).status_code == 200, path


# ---- the endpoints without an id in the path ----


def test_lists_only_show_the_teachers_own(monkeypatch, fake_db, world):
    assert [s["student_id"] for s in client.get("/students", headers=AUTH).json()] == ["s1", "s2"]
    assert [r["student_id"] for r in client.get("/overview", headers=AUTH).json()] == ["s1", "s2"]
    assert client.get("/exercises?student_id=s1", headers=AUTH).status_code == 200

    become_teacher(monkeypatch, uid="teacher-2")
    assert [s["student_id"] for s in client.get("/students", headers=AUTH).json()] == ["b1"]
    rows = client.get("/overview", headers=AUTH).json()
    assert [r["student_id"] for r in rows] == ["b1"] and rows[0]["work"] == []
    response = client.get("/exercises?student_id=s1", headers=AUTH)
    assert response.status_code == 404 and "Alex" not in response.text
    assert client.get("/exercises?student_id=b1", headers=AUTH).json() == []


def test_classes_and_class_filters_only_reach_the_teachers_own(monkeypatch, fake_db, world):
    assert [c["class_id"] for c in client.get("/classes", headers=AUTH).json()] == ["c1"]
    become_teacher(monkeypatch, uid="teacher-2")
    assert [c["class_id"] for c in client.get("/classes", headers=AUTH).json()] == ["cb"]
    # Teacher A's class, as a filter or a destination, is "not found" to teacher B.
    assert client.get("/students?class_id=c1", headers=AUTH).status_code == 404
    assert client.get("/overview?class_id=c1", headers=AUTH).status_code == 404
    response = client.post("/students", json={"username": "Bo", "password": "longenough", "class_id": "c1"}, headers=AUTH)
    assert response.status_code == 404
    assert client.put("/students/b1/class", json={"class_id": "c1"}, headers=AUTH).status_code == 404
    assert fake_db.collection("students").document("b1").get().get("class_id") == "cb"
    created = client.post("/classes", json={"name": "Mine"}, headers=AUTH).json()
    assert fake_db.collection("classes").document(created["class_id"]).get().get("teacher_id") == "teacher-2"


def test_my_errors_only_shows_the_students_own(monkeypatch, fake_db, world):
    as_student(monkeypatch, student_id="s1")
    assert client.get("/me/errors", headers=AUTH).json()["pieces"] == 1  # the released exercise
    for other in (("s2", "u2"), ("b1", "ub1")):
        as_student(monkeypatch, student_id=other[0], uid=other[1])
        view = client.get("/me/errors", headers=AUTH).json()
        assert view["pieces"] == 0 and view["all"] == [] and "Alex" not in str(view) and TYPED not in str(view)


def test_assigning_only_reaches_the_teachers_own_students(monkeypatch, fake_db, world):
    become_teacher(monkeypatch, uid="teacher-2")
    url = "/exercises/writing-for-students"
    draft = {"kind": "writing", "title": "Mine", "prompt": "Describe your town."}
    exercises_before = len(fake_db.collection("exercises").stream())
    for chosen in (["s1"], ["b1", "s1"]):
        assert client.post(url, json={"draft": draft, "student_ids": chosen}, headers=AUTH).status_code == 404
    assert len(fake_db.collection("exercises").stream()) == exercises_before  # nothing created

    exercise_id = client.post(url, json={"draft": draft, "student_ids": ["b1"]}, headers=AUTH).json()["exercise_ids"][0]
    assert fake_db.collection("exercises").document(exercise_id).get().get("teacher_id") == "teacher-2"
    assert fake_db.collection("submissions").document(exercise_id).get().get("teacher_id") == "teacher-2"


def test_new_students_belong_to_their_creator(monkeypatch, fake_db, world):
    monkeypatch.setattr("api.app.identity.create_student_user", lambda username, password: "ub2")
    monkeypatch.setattr("api.app.identity.set_student_claims", lambda uid, student_id: None)
    become_teacher(monkeypatch, uid="teacher-2")
    created = client.post("/students", json={"username": "Bo", "password": "longenough", "class_id": "cb"}, headers=AUTH).json()
    assert fake_db.collection("students").document(created["student_id"]).get().get("teacher_id") == "teacher-2"
    become_teacher(monkeypatch)
    assert created["student_id"] not in str(client.get("/students", headers=AUTH).json())


def test_every_record_carries_its_teacher(fake_db, world):
    exercise_id = world["exercise_id"]
    assert fake_db.collection("exercises").document(exercise_id).get().get("teacher_id") == "teacher-1"
    assert fake_db.collection("submissions").document(exercise_id).get().get("teacher_id") == "teacher-1"
    jobs = fake_db.collection("jobs").stream()
    assert jobs and all(job.get("teacher_id") == "teacher-1" for job in jobs)


def test_admin_reaches_no_student_endpoint(monkeypatch, fake_db, world):
    become_admin(monkeypatch)
    for method, path in NO_ID_ENDPOINTS:
        response = client.request(method, path, params={"student_id": "s1"}, json={}, headers=AUTH)
        assert response.status_code == 403, f"admin: {method} {path} answered {response.status_code}"


def test_students_reach_no_teacher_list(monkeypatch, fake_db, world):
    as_student(monkeypatch, student_id="s1")
    for method, path in NO_ID_ENDPOINTS - {("GET", "/me/exercises"), ("GET", "/me/errors")}:
        response = client.request(method, path, params={"student_id": "s1"}, json={}, headers=AUTH)
        assert response.status_code == 403, f"student: {method} {path} answered {response.status_code}"
    # Their own list holds only their own work.
    assert [e["exercise_id"] for e in client.get("/me/exercises", headers=AUTH).json()] == [world["exercise_id"]]
    as_student(monkeypatch, student_id="b1", uid="ub1")
    assert client.get("/me/exercises", headers=AUTH).json() == []


# ---- roles and sign-in ----


def test_admin_and_teacher_need_the_authenticator_code(monkeypatch, fake_db):
    for role in ("admin", "teacher"):
        monkeypatch.setattr(
            "api.app.identity.verify_id_token",
            lambda token, role=role: {"uid": "x", "role": role, "firebase": {"sign_in_provider": "password"}},
        )
        assert client.get("/students", headers=AUTH).status_code == 401, role


def test_an_account_with_no_role_reaches_only_its_sign_up(monkeypatch, fake_db):
    """A teacher sign-up the admin hasn't approved yet has no role."""
    monkeypatch.setattr(
        "api.app.identity.verify_id_token",
        lambda token: {"uid": "pending-1", "email": "new@example.com", "firebase": {"sign_in_provider": "password"}},
    )
    for method, path in _endpoints():
        if (method, path) in SIGNUP_ENDPOINTS:
            continue
        response = client.request(method, re.sub(r"{[^}]+}", "x", path), json={}, headers=AUTH)
        assert response.status_code == 401, f"{method} {path} answered {response.status_code} for a role-less account"


# ---- admin routes ----


@pytest.mark.parametrize("caller", ["teacher A", "teacher B", "teacher A's student"])
def test_only_the_admin_reaches_admin_routes(monkeypatch, fake_db, world, caller):
    fake_db.collection("teachers").document("teacher-1").set({"name": "A", "email": "a@example.com", "active": True})
    fake_db.collection("signup_requests").document("pending-1").set({"name": "P", "email": "p@example.com", "status": "pending"})
    if caller == "teacher A":
        become_teacher(monkeypatch)
    elif caller == "teacher B":
        become_teacher(monkeypatch, uid="teacher-2")
    else:
        as_student(monkeypatch, student_id="s1")
    endpoints = _admin_endpoints()
    assert len(endpoints) >= 10  # sanity: the walk found the admin routes
    for method, path in endpoints:
        before = copy.deepcopy(fake_db._store)
        url = re.sub(r"{uid}", "teacher-1" if "teachers" in path else "pending-1", path)
        response = client.request(method, url, json={}, headers=AUTH)
        assert response.status_code == 403, f"{caller}: {method} {path} answered {response.status_code}"
        assert fake_db._store == before, f"{caller}: {method} {path} changed stored data"

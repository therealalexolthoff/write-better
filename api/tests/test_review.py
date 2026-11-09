"""Scrubbing and evaluating a writing response: scrub -> evaluate ->
teacher edits -> approve, plus what each side may do along the way. The
full typed path through to the student's revision is in test_writing.py."""

from fastapi.testclient import TestClient

from api.app.main import app

from .conftest import as_student, become_teacher
from .test_exercises import AUTH, _assign, _submission, harness, student  # noqa: F401 (fixtures)

client = TestClient(app)

ORIGINAL = "On saturday I go to the market with my sister Maria Lopez."
SCRUBBED = "On saturday I go to the market with my sister [name]."


def _evaluation(span="go", comment="Watch your past tense."):
    return {
        "annotations": [
            {"code": "VT", "span_text": span, "occurrence": 1, "correction": "went", "explanation": "Past."},
        ],
        "comment": comment,
    }


def _submitted(monkeypatch, harness):  # noqa: F811
    """A writing exercise submitted by student s1. Leaves the test signed in
    as the teacher."""
    exercise_id = _assign()
    as_student(monkeypatch, student_id="s1")
    response = client.post(f"/exercises/{exercise_id}/submit", json={"answers": {"text": ORIGINAL}}, headers=AUTH)
    assert response.status_code == 200, response.text
    become_teacher(monkeypatch)
    return exercise_id


def _scrub(exercise_id, text=SCRUBBED):
    return client.put(f"/exercises/{exercise_id}/scrubbed", json={"scrubbed_answers": {"text": text}}, headers=AUTH)


def _evaluate(exercise_id, harness, note="", result=None):  # noqa: F811
    harness.result = result or _evaluation()
    return client.post(f"/exercises/{exercise_id}/evaluate", json={"note": note}, headers=AUTH)


def _job(fake_db, job_id):
    return fake_db.collection("jobs").document(job_id).get().to_dict()


def test_only_the_scrubbed_copy_reaches_the_ai(monkeypatch, fake_db, as_teacher, harness, student):  # noqa: F811
    exercise_id = _submitted(monkeypatch, harness)
    assert _scrub(exercise_id).status_code == 200
    response = _evaluate(exercise_id, harness)
    assert response.status_code == 200, response.text
    view = response.json()
    assert view["state"] == "draft_ready"
    annotation = view["evaluation"]["annotations"][0]
    assert (annotation["start"], annotation["end"]) == (14, 16)  # offsets computed by the API

    sent = harness.calls[-1]
    assert sent["text"] == SCRUBBED and sent["student_id"] == "s1"
    assert "Maria" not in str(sent) and "Alex" not in str(sent)  # no original, no username
    assert _submission(fake_db, exercise_id)["answers"]["text"] == ORIGINAL  # untouched

    # Nothing visible to the student before release.
    as_student(monkeypatch, student_id="s1")
    view = client.get(f"/exercises/{exercise_id}", headers=AUTH).json()
    assert "spans" not in view and "comment" not in view and "went" not in str(view)

    become_teacher(monkeypatch)
    assert client.post(f"/exercises/{exercise_id}/release", headers=AUTH).status_code == 409  # not approved yet
    assert client.post(f"/exercises/{exercise_id}/approve", headers=AUTH).status_code == 200
    assert _job(fake_db, _submission(fake_db, exercise_id)["evaluation_job_id"])["teacher_action"] == "accepted"


def test_editing_scrubbed_text_invalidates_the_evaluation(monkeypatch, fake_db, as_teacher, harness, student):  # noqa: F811
    exercise_id = _submitted(monkeypatch, harness)
    _scrub(exercise_id)
    _evaluate(exercise_id, harness)

    view = _scrub(exercise_id, "On saturday I go to the market.").json()
    assert view["state"] == "scrub_review"
    assert view["evaluation"] is None and view["evaluation_valid"] is False
    assert client.post(f"/exercises/{exercise_id}/approve", headers=AUTH).status_code == 409

    # Saving the same text again does not throw an evaluation away.
    _evaluate(exercise_id, harness)
    assert _scrub(exercise_id, "On saturday I go to the market.").json()["state"] == "draft_ready"


def test_scrubbed_copy_must_be_just_the_text(monkeypatch, fake_db, as_teacher, harness, student):  # noqa: F811
    exercise_id = _submitted(monkeypatch, harness)
    for bad in ({"text": "x", "i1": "y"}, {"i3": "x"}, {}):
        response = client.put(f"/exercises/{exercise_id}/scrubbed", json={"scrubbed_answers": bad}, headers=AUTH)
        assert response.status_code == 422, bad


def test_teacher_edits_are_validated(monkeypatch, fake_db, as_teacher, harness, student):  # noqa: F811
    exercise_id = _submitted(monkeypatch, harness)
    _scrub(exercise_id)
    _evaluate(exercise_id, harness)
    url = f"/exercises/{exercise_id}/evaluation"

    # A span that isn't in the scrubbed text is refused.
    assert client.put(url, json=_evaluation(span="goes"), headers=AUTH).status_code == 422
    # An unknown code is refused by the shared schema.
    bad_code = _evaluation()
    bad_code["annotations"][0]["code"] = "ZZ"
    assert client.put(url, json=bad_code, headers=AUTH).status_code == 422
    # The old short-answer shape doesn't fit.
    short_answer = {"items": [{"item_id": "text", "mark": "correct", "annotations": [], "feedback": "x"}]}
    assert client.put(url, json=short_answer, headers=AUTH).status_code == 422

    # Recoding and a new comment are fine, and count as an edit.
    edited = _evaluation(comment="Good work; check your verbs.")
    edited["annotations"][0]["code"] = "VF"
    assert client.put(url, json=edited, headers=AUTH).status_code == 200
    client.post(f"/exercises/{exercise_id}/approve", headers=AUTH)
    assert _job(fake_db, _submission(fake_db, exercise_id)["evaluation_job_id"])["teacher_action"] == "edited"


def test_regenerate_with_note(monkeypatch, fake_db, as_teacher, harness, student):  # noqa: F811
    exercise_id = _submitted(monkeypatch, harness)
    _scrub(exercise_id)
    _evaluate(exercise_id, harness)
    first_job = _submission(fake_db, exercise_id)["evaluation_job_id"]

    response = _evaluate(exercise_id, harness, note="'go' is fine", result={"annotations": [], "comment": "Fine."})
    assert response.status_code == 200
    assert response.json()["evaluation"] == {"annotations": [], "comment": "Fine."}
    assert harness.calls[-1]["regenerate_note"] == "'go' is fine"
    assert _job(fake_db, first_job)["teacher_action"] == "regenerated"


def test_failed_evaluation_loses_nothing(monkeypatch, fake_db, as_teacher, harness, student):  # noqa: F811
    exercise_id = _submitted(monkeypatch, harness)
    _scrub(exercise_id)
    _evaluate(exercise_id, harness)

    # The AI flags words that aren't in the text: rejected by the API's own check.
    assert _evaluate(exercise_id, harness, result=_evaluation(span="went")).status_code == 502
    view = client.get(f"/exercises/{exercise_id}", headers=AUTH).json()
    assert view["state"] == "draft_ready"  # back where it was
    assert view["evaluation"]["annotations"][0]["span_text"] == "go"  # previous draft kept


def test_spend_cap_blocks_evaluation(monkeypatch, fake_db, as_teacher, harness, student):  # noqa: F811
    exercise_id = _submitted(monkeypatch, harness)
    fake_db.collection("settings").document("global").set({"monthly_cap_usd": 0.0})
    response = _evaluate(exercise_id, harness)
    assert response.status_code == 409 and "paused" in response.json()["detail"]
    assert harness.calls == []
    assert client.get(f"/exercises/{exercise_id}", headers=AUTH).json()["state"] == "scrub_review"


def test_students_cannot_use_review_endpoints(monkeypatch, fake_db, as_teacher, harness, student):  # noqa: F811
    exercise_id = _submitted(monkeypatch, harness)
    as_student(monkeypatch, student_id="s1")
    assert _scrub(exercise_id).status_code == 403
    assert _evaluate(exercise_id, harness).status_code == 403
    assert client.put(f"/exercises/{exercise_id}/evaluation", json=_evaluation(), headers=AUTH).status_code == 403
    assert client.post(f"/exercises/{exercise_id}/approve", headers=AUTH).status_code == 403
    assert client.post(f"/exercises/{exercise_id}/release", headers=AUTH).status_code == 403
    assert client.post(f"/exercises/{exercise_id}/reopen", headers=AUTH).status_code == 403


def test_reopen_clears_scrub_and_evaluation(monkeypatch, fake_db, as_teacher, harness, student):  # noqa: F811
    exercise_id = _submitted(monkeypatch, harness)
    _scrub(exercise_id)
    _evaluate(exercise_id, harness)
    assert client.post(f"/exercises/{exercise_id}/reopen", headers=AUTH).status_code == 200
    view = client.get(f"/exercises/{exercise_id}", headers=AUTH).json()
    assert view["state"] == "in_progress"
    assert view["scrubbed_answers"] == {} and view["evaluation"] is None
    assert view["answers"]["text"] == ORIGINAL  # the student's response is kept

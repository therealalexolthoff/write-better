"""Writing exercises, end to end.

Teacher: list a student's exercises, release results, reopen a submission.
(Exercises are created by assigning writing: assignments.py.)
Student: list assigned work, open it, autosave the response, submit.
Who may reach which exercise is checked in access.py, before each route
runs; every exercise and submission records its teacher as teacher_id.

The teacher always writes the exercise; the AI never does. Scrubbing and
evaluation are in review.py; handwriting and revision in writing.py.

Firestore layout (docs/ARCHITECTURE.md section 4):
- exercises/{id}:   one student's copy of a writing exercise. Its status is
                    always "assigned": there are no drafts.
- submissions/{id}: the student's response, created with the exercise.
                    Same id as its exercise - every exercise belongs to
                    exactly one student, so there is one submission each.

Submission states (docs/ARCHITECTURE.md section 5):
    assigned -> in_progress -> scrub_review -> evaluating -> draft_ready
        -> ready_to_release -> released            (nothing flagged)
                           \\-> revision_open -> revision_submitted -> revision_reviewed
Handwritten work adds, before scrub_review (writing.py):
    ... -> transcribing -> transcript_review -> scrub_review

A submission's "answers" hold the student's original response, under the
single key WRITING_KEY, and are never changed after submit. The separate
"scrubbed_answers" copy, which the teacher edits, is the only student text
ever sent to the harness (docs/REQUIREMENTS.md FR-18).
"""

from collections.abc import Callable
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from google.api_core.exceptions import FailedPrecondition
from google.cloud.firestore_v1.base_query import FieldFilter

from shared.taxonomy import CODE_DESCRIPTIONS, ErrorCode

from .access import exercise_for_caller, owned_exercise, owned_student, students_exercise
from .audit import record as record_audit
from .auth import CurrentUser, get_current_user, require_student, require_teacher
from .firestore_client import get_db
from .harness_ops import HarnessValidationFailed, SpendCapReached, ai_paused, call_harness
from .models import (
    WRITING_KEY,
    AnswersBody,
    SpanView,
    StudentExerciseSummary,
    StudentExerciseView,
)
from .revision import revision_view

router = APIRouter(tags=["exercises"])

AI_PAUSED_MESSAGE = (
    "AI feedback is paused. This month's AI budget has been used. Nothing was lost, and you can still read and "
    "edit your students' work. It starts again next month, or ask the Write Better administrator."
)

# States in which the student may still change their response.
OPEN_STATES = ("assigned", "in_progress")
# States the teacher may reopen from. Not "released": once the student has
# seen results, reopening would let them rewrite with the feedback in view.
# Not "evaluating" or "transcribing": an AI call is in progress.
_REOPENABLE_STATES = ("transcript_review", "scrub_review", "draft_ready", "ready_to_release")
# States in which the student sees results.
RESULTS_STATES = ("released", "revision_open", "revision_submitted", "revision_reviewed")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _exercise_ref(exercise_id: str):
    return get_db().collection("exercises").document(exercise_id)


def _submission_ref(exercise_id: str):
    return get_db().collection("submissions").document(exercise_id)


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="exercise not found")


def _load_exercise(exercise_id: str) -> dict:
    doc = _exercise_ref(exercise_id).get()
    if not doc.exists:
        raise _not_found()
    return doc.to_dict()


def _load_submission(exercise_id: str) -> dict | None:
    doc = _submission_ref(exercise_id).get()
    return doc.to_dict() if doc.exists else None


def update_open_submission(exercise_id: str, check, changes: dict | Callable[[dict], dict], open_states=OPEN_STATES) -> None:
    """Applies `changes` to a submission the student can still edit (one
    of `open_states`).

    Read, check and write would race otherwise: an autosave already on its
    way when the student taps Submit could read "in_progress", lose the
    race, and then write "in_progress" back over the submit - unlocking
    work that must stay locked (FR-15). So the write only goes through if
    the document is unchanged since it was read; if something else wrote
    in between, read again and re-check. `check` runs between the read
    and the write (answer-shape validation). `changes` may also be a
    function of the submission just read, for changes that build on it
    (e.g. adding a photo page to the list).
    """
    ref = _submission_ref(exercise_id)
    for _ in range(3):
        snapshot = ref.get()
        if not snapshot.exists or snapshot.get("state") not in open_states:
            raise HTTPException(status_code=409, detail="This exercise has already been submitted.")
        check()
        new = changes(snapshot.to_dict()) if callable(changes) else changes
        try:
            ref.update(new, option=get_db().write_option(last_update_time=snapshot.update_time))
            return
        except FailedPrecondition:
            continue  # someone else wrote first; look again
    raise HTTPException(status_code=409, detail="Your answers could not be saved. Please try again.")


def load_for_student(exercise_id: str, user: CurrentUser) -> dict:
    """The student may only see their own exercises. Anything else looks
    like "not found" so a student can't probe which exercise ids exist."""
    exercise = _load_exercise(exercise_id)
    if exercise["student_id"] != user.student_id or exercise["status"] != "assigned":
        raise _not_found()
    return exercise


def call_ai(operation: str, req, teacher_id: str) -> tuple[object, str]:
    """One harness call, with failures turned into teacher-readable errors.
    Invalid output is never returned (FR-8). Returns (result, job id)."""
    try:
        return call_harness(operation, req, teacher_id)
    except SpendCapReached as exc:
        raise HTTPException(status_code=409, detail=AI_PAUSED_MESSAGE) from exc
    except HarnessValidationFailed as exc:
        raise HTTPException(
            status_code=502, detail="The AI result could not be used. Nothing was changed - please try again."
        ) from exc


def _teacher_view(exercise_id: str, exercise: dict) -> dict:
    """Everything the teacher sees, including the student's original
    response. Photos themselves come from GET /exercises/{id}/photos as
    short-lived links."""
    submission = _load_submission(exercise_id) or {}
    return {
        "exercise_id": exercise_id,
        "student_id": exercise["student_id"],
        "kind": exercise["kind"],
        "status": exercise["status"],
        "title": exercise["title"],
        "teacher_request": exercise["teacher_request"],
        "prompt": exercise["prompt"],
        "min_words": exercise["min_words"],
        "max_words": exercise["max_words"],
        "state": submission.get("state", "assigned"),
        "answers": submission.get("answers", {}),
        # Scrubbing and evaluation: see review.py.
        "scrubbed_answers": submission.get("scrubbed_answers", {}),
        "evaluation": submission.get("evaluation"),
        "evaluation_valid": submission.get("evaluation_valid", False),
        # Handwriting and revision: see writing.py.
        "photo_count": len(submission.get("photos", [])),
        "transcription": submission.get("transcription"),
        "final_source": submission.get("final_source"),
        "revision": revision_view(submission),
    }


def _student_spans(annotations: list[dict]) -> list[SpanView]:
    """Error spans as a student may see them: position and code only,
    never the correction or explanation (FR-21). Kept in annotation order,
    which is how revision edits refer to them."""
    return [
        SpanView(start=a["start"], end=a["end"], code=a["code"], meaning=CODE_DESCRIPTIONS[ErrorCode(a["code"])])
        for a in annotations
    ]


def _student_view(exercise_id: str, exercise: dict, submission: dict) -> StudentExerciseView:
    """A writing exercise for its student: the prompt and word limits, and
    once released, their evaluated text with coded spans, the overall
    comment (FR-21), and their revision (FR-26). Never the photos, the
    transcription, corrections or explanations (FR-25) - except that once
    the teacher sends back the checked revision, each changed span's
    outcome, and the correction for each one not fixed (FR-27)."""
    state = submission.get("state", "assigned")
    view = StudentExerciseView(
        exercise_id=exercise_id,
        title=exercise["title"],
        state=state,
        answers=submission.get("answers", {}),
        prompt=exercise["prompt"],
        min_words=exercise["min_words"],
        max_words=exercise["max_words"],
    )
    if state in RESULTS_STATES:
        evaluation = submission["evaluation"]
        # The evaluated (scrubbed) text, which the spans point into.
        view.answer_text = submission["scrubbed_answers"][WRITING_KEY]
        view.spans = _student_spans(evaluation["annotations"])
        view.comment = evaluation["comment"]
        revision = revision_view(submission)
        if revision is not None:
            view.revision_edits = revision["edits"]
            view.revised_text = revision["revised_text"]
            if state == "revision_reviewed":
                view.outcomes = revision["outcomes"]
                view.corrections = {
                    index: evaluation["annotations"][int(index)]["correction"]
                    for index, outcome in revision["outcomes"].items()
                    if outcome != "fixed"
                }
    return view


def _check_answer_shapes(answers: dict) -> None:
    """A writing exercise has one answer: the response text."""
    if set(answers) - {WRITING_KEY} or not isinstance(answers.get(WRITING_KEY, ""), str):
        raise HTTPException(status_code=422, detail=f"a writing answer is just {{{WRITING_KEY!r}: text}}")


def _new_submission(exercise_id: str, student_id: str, teacher_id: str) -> dict:
    """The student's empty submission, created with their exercise."""
    return {
        "exercise_id": exercise_id,
        "student_id": student_id,
        "teacher_id": teacher_id,
        "state": "assigned",
        "answers": {},
        "updated_at": _now(),
    }


# ---- teacher ----


@router.get("/ai-status")
def ai_status(user: CurrentUser = Depends(require_teacher)) -> dict:
    """Whether AI feedback is paused by the monthly cap, so the review
    screen can say so before the teacher tries. No amounts: those are the
    admin's (admin.py)."""
    paused = ai_paused()
    return {"paused": paused, "message": AI_PAUSED_MESSAGE if paused else ""}


@router.get("/taxonomy")
def taxonomy(user: CurrentUser = Depends(require_teacher)) -> list[dict]:
    """The 14 codes for the evaluation editor's code picker, served from
    the one shared list rather than copied into the frontend."""
    return [{"code": code.value, "description": desc} for code, desc in CODE_DESCRIPTIONS.items()]


@router.get("/exercises", dependencies=[Depends(owned_student)])
def list_exercises(student_id: str, user: CurrentUser = Depends(require_teacher)) -> list[dict]:
    docs = (
        get_db()
        .collection("exercises")
        .where(filter=FieldFilter("student_id", "==", student_id))
        .where(filter=FieldFilter("teacher_id", "==", user.uid))
        .stream()
    )
    summaries = []
    for doc in docs:
        submission = _load_submission(doc.id) or {}
        summaries.append(
            {
                "exercise_id": doc.id,
                "title": doc.get("title"),
                "status": doc.get("status"),
                "state": submission.get("state", "assigned"),
            }
        )
    return summaries


@router.post("/exercises/{exercise_id}/release", dependencies=[Depends(owned_exercise)])
def release_results(exercise_id: str, user: CurrentUser = Depends(require_teacher)) -> dict:
    exercise = _load_exercise(exercise_id)
    submission = _load_submission(exercise_id)
    if submission is None or submission["state"] != "ready_to_release":
        raise HTTPException(status_code=409, detail="not ready to release")
    # Flagged errors open the student's one revision round straight away
    # (FR-26). Nothing flagged means nothing to revise.
    state = "revision_open" if submission["evaluation"]["annotations"] else "released"
    _submission_ref(exercise_id).update({"state": state, "released_at": _now()})
    return _teacher_view(exercise_id, exercise)


@router.post("/exercises/{exercise_id}/reopen", dependencies=[Depends(owned_exercise)])
def reopen_submission(exercise_id: str, user: CurrentUser = Depends(require_teacher)) -> dict:
    """Sends a submitted exercise back to the student (FR-15). Audit-logged."""
    exercise = _load_exercise(exercise_id)
    submission = _load_submission(exercise_id)
    if submission is None or submission["state"] not in _REOPENABLE_STATES:
        raise HTTPException(status_code=409, detail="only submitted, unreleased work can be reopened")
    # The response is kept so the student continues where they left off.
    # The scrubbed copy and any evaluation are rebuilt after the next
    # submit. Handwriting photos and their transcription are the teacher's
    # work and are kept too; the final source is chosen again.
    _submission_ref(exercise_id).update(
        {
            "state": "in_progress",
            "scrubbed_answers": {},
            "final_source": None,
            "evaluation": None,
            "evaluation_ai": None,
            "evaluation_valid": False,
            "updated_at": _now(),
        }
    )
    record_audit(user.uid, "reopen_submission", target=exercise_id)
    return _teacher_view(exercise_id, exercise)


# ---- student (and teacher, for GET) ----


@router.get("/me/exercises", response_model=list[StudentExerciseSummary])
def my_exercises(user: CurrentUser = Depends(require_student)) -> list[StudentExerciseSummary]:
    docs = (
        get_db()
        .collection("exercises")
        .where(filter=FieldFilter("student_id", "==", user.student_id))
        .where(filter=FieldFilter("status", "==", "assigned"))
        .stream()
    )
    return [
        StudentExerciseSummary(
            exercise_id=doc.id,
            title=doc.get("title"),
            state=(_load_submission(doc.id) or {}).get("state", "assigned"),
        )
        for doc in docs
    ]


@router.get("/exercises/{exercise_id}", dependencies=[Depends(exercise_for_caller)])
def get_exercise(exercise_id: str, user: CurrentUser = Depends(get_current_user)) -> dict:
    if user.role == "teacher":
        return _teacher_view(exercise_id, _load_exercise(exercise_id))
    exercise = load_for_student(exercise_id, user)
    view = _student_view(exercise_id, exercise, _load_submission(exercise_id) or {})
    # Serialized through the model, so only the fields it declares go out.
    return view.model_dump(mode="json", exclude_none=True)


@router.put("/exercises/{exercise_id}/answers", dependencies=[Depends(students_exercise)])
def save_answers(exercise_id: str, body: AnswersBody, user: CurrentUser = Depends(require_student)) -> dict:
    """Autosave (FR-13). Replaces the saved response with the one sent."""
    update_open_submission(
        exercise_id,
        check=lambda: _check_answer_shapes(body.answers),
        changes={"answers": body.answers, "state": "in_progress", "updated_at": _now()},
    )
    return {"status": "saved"}


@router.post("/exercises/{exercise_id}/submit", dependencies=[Depends(students_exercise)])
def submit_answers(exercise_id: str, body: AnswersBody, user: CurrentUser = Depends(require_student)) -> dict:
    """Final submit (FR-15/FR-16). Takes the response once more so nothing
    typed after the last autosave is lost, then locks it for scrubbing."""
    update_open_submission(
        exercise_id,
        check=lambda: _check_answer_shapes(body.answers),
        changes={
            "answers": body.answers,
            # The teacher's editable copy starts as the original (FR-18).
            "scrubbed_answers": {WRITING_KEY: body.answers.get(WRITING_KEY, "")},
            "final_source": "typed",
            "state": "scrub_review",
            "submitted_at": _now(),
            "updated_at": _now(),
        },
    )
    return {"status": "submitted"}

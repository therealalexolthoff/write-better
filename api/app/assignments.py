"""Writing assignments: one piece of writing the teacher sets for a class.

The teacher writes the prompt (the AI never does) and assigns it to the
whole class, or to chosen students in it. Each student gets their own copy
(an exercise and its submission, exercises.py), so everything after that -
writing, scrubbing, evaluation, release, revision - works exactly as for a
single exercise. The assignment ties the copies together, so the teacher
can see everyone's progress in one place and add students who join the
class later.

Firestore: assignments/{id}: teacher_id, class_id, kind, title, prompt,
min_words, max_words, created_at. Each copy's exercise records its
assignment_id and class_id. Only the assignment's own teacher reaches it
(access.py).
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from google.cloud.firestore_v1.base_query import FieldFilter
from pydantic import BaseModel, Field

from shared.schemas import WritingExerciseDraft

from .access import check_class, owned_assignment, teacher_owns
from .audit import record as record_audit
from .auth import CurrentUser, require_teacher
from .exercises import _new_submission, _submission_ref
from .firestore_client import get_db

router = APIRouter(prefix="/assignments", tags=["assignments"])

MAX_STUDENTS = 100

# How each submission state is counted on the teacher's screens.
PROGRESS_GROUPS = {
    "not_started": ("assigned",),
    "writing": ("in_progress",),
    "needs_you": (
        "transcribing", "transcript_review", "scrub_review", "evaluating", "draft_ready", "ready_to_release",
        "revision_submitted",
    ),
    "with_student": ("revision_open",),
    "done": ("released", "revision_reviewed"),
}
_GROUP_OF = {state: group for group, states in PROGRESS_GROUPS.items() for state in states}


class NewAssignmentBody(BaseModel):
    class_id: str
    draft: WritingExerciseDraft
    # None: every active student in the class. Otherwise these students of it.
    student_ids: list[str] | None = Field(default=None, min_length=1, max_length=MAX_STUDENTS)


class AddStudentsBody(BaseModel):
    student_ids: list[str] = Field(min_length=1, max_length=MAX_STUDENTS)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _class_students(class_id: str, user: CurrentUser) -> dict[str, dict]:
    """The class's active students, by id."""
    docs = (
        get_db()
        .collection("students")
        .where(filter=FieldFilter("teacher_id", "==", user.uid))
        .where(filter=FieldFilter("class_id", "==", class_id))
        .stream()
    )
    return {doc.id: doc.to_dict() for doc in docs if doc.get("active")}


def _chosen(student_ids: list[str], class_id: str, user: CurrentUser) -> list[str]:
    """Each chosen student, once, in the order picked. Every one must be an
    active student of the teacher in this class: another teacher's student
    looks the same as one that doesn't exist."""
    chosen = list(dict.fromkeys(student_ids))
    for student_id in chosen:
        student = get_db().collection("students").document(student_id).get().to_dict()
        if not teacher_owns(student, user) or not student.get("active") or student.get("class_id") != class_id:
            raise HTTPException(status_code=404, detail="A chosen student was not found, is inactive, or isn't in this class.")
    return chosen


def _add_copies(assignment_id: str, assignment: dict, student_ids: list[str], user: CurrentUser) -> list[str]:
    """One exercise and empty submission per student, all or none."""
    batch = get_db().batch()
    exercise_ids = []
    for student_id in student_ids:
        ref = get_db().collection("exercises").document()
        exercise = {
            "student_id": student_id,
            "teacher_id": user.uid,
            "class_id": assignment["class_id"],
            "assignment_id": assignment_id,
            "status": "assigned",
            "kind": assignment["kind"],
            "title": assignment["title"],
            "prompt": assignment["prompt"],
            "min_words": assignment["min_words"],
            "max_words": assignment["max_words"],
            "teacher_request": "Written by you.",
            "created_at": _now(),
            "assigned_at": _now(),
        }
        batch.set(ref, exercise)
        batch.set(_submission_ref(ref.id), _new_submission(ref.id, student_id, user.uid))
        exercise_ids.append(ref.id)
    batch.commit()
    return exercise_ids


def _copies(assignment_id: str) -> list[tuple[str, dict]]:
    docs = get_db().collection("exercises").where(filter=FieldFilter("assignment_id", "==", assignment_id)).stream()
    return [(doc.id, doc.to_dict()) for doc in docs]


def _state(exercise_id: str) -> str:
    doc = _submission_ref(exercise_id).get()
    return doc.get("state") if doc.exists else "assigned"


def _progress(states: list[str]) -> dict[str, int]:
    counts = {group: 0 for group in PROGRESS_GROUPS}
    for state in states:
        counts[_GROUP_OF.get(state, "needs_you")] += 1
    return counts


# ---- routes ----


@router.post("")
def create_assignment(body: NewAssignmentBody, user: CurrentUser = Depends(require_teacher)) -> dict:
    """A writing exercise for a class: every active student in it, or the
    chosen ones. Each gets their own copy straight away."""
    draft = body.draft
    if not draft.title.strip() or not draft.prompt.strip():
        raise HTTPException(status_code=422, detail="Give the assignment a title and a prompt.")
    check_class(body.class_id, user, open_only=True)
    if body.student_ids is None:
        student_ids = sorted(_class_students(body.class_id, user))
        if not student_ids:
            raise HTTPException(status_code=409, detail="This class has no active students yet.")
    else:
        student_ids = _chosen(body.student_ids, body.class_id, user)

    ref = get_db().collection("assignments").document()
    assignment = {
        "teacher_id": user.uid,
        "class_id": body.class_id,
        **draft.model_dump(mode="json"),  # kind, title, prompt, word limits
        "created_at": _now(),
    }
    ref.set(assignment)
    exercise_ids = _add_copies(ref.id, assignment, student_ids, user)
    record_audit(user.uid, "create_assignment", target=ref.id)
    return {"assignment_id": ref.id, "exercise_ids": exercise_ids}


@router.get("")
def list_assignments(class_id: str | None = None, user: CurrentUser = Depends(require_teacher)) -> list[dict]:
    """The teacher's assignments, newest first, with how far along everyone is."""
    query = get_db().collection("assignments").where(filter=FieldFilter("teacher_id", "==", user.uid))
    if class_id is not None:
        check_class(class_id, user)
        query = query.where(filter=FieldFilter("class_id", "==", class_id))
    rows = []
    for doc in query.stream():
        copies = _copies(doc.id)
        rows.append(
            {
                "assignment_id": doc.id,
                "class_id": doc.get("class_id"),
                "title": doc.get("title"),
                "created_at": doc.get("created_at"),
                "students": len(copies),
                "progress": _progress([_state(exercise_id) for exercise_id, _ in copies]),
            }
        )
    return sorted(rows, key=lambda row: row["created_at"], reverse=True)


@router.get("/{assignment_id}", dependencies=[Depends(owned_assignment)])
def get_assignment(assignment_id: str, user: CurrentUser = Depends(require_teacher)) -> dict:
    """The assignment, each student's copy and stage, and the class's
    active students who don't have it yet (for example, who joined later)."""
    assignment = get_db().collection("assignments").document(assignment_id).get().to_dict()
    copies = _copies(assignment_id)
    students = {doc.id: doc.to_dict() for doc in get_db().collection("students").where(filter=FieldFilter("teacher_id", "==", user.uid)).stream()}
    rows = [
        {
            "exercise_id": exercise_id,
            "student_id": exercise["student_id"],
            "username": students.get(exercise["student_id"], {}).get("username", "(deleted student)"),
            "state": _state(exercise_id),
        }
        for exercise_id, exercise in copies
    ]
    have = {row["student_id"] for row in rows}
    not_assigned = [
        {"student_id": student_id, "username": student["username"]}
        for student_id, student in _class_students(assignment["class_id"], user).items()
        if student_id not in have
    ]
    return {
        "assignment_id": assignment_id,
        "class_id": assignment["class_id"],
        "title": assignment["title"],
        "prompt": assignment["prompt"],
        "min_words": assignment["min_words"],
        "max_words": assignment["max_words"],
        "created_at": assignment["created_at"],
        "progress": _progress([row["state"] for row in rows]),
        "students": sorted(rows, key=lambda row: row["username"].lower()),
        "not_assigned": sorted(not_assigned, key=lambda row: row["username"].lower()),
    }


@router.post("/{assignment_id}/students", dependencies=[Depends(owned_assignment)])
def add_students(assignment_id: str, body: AddStudentsBody, user: CurrentUser = Depends(require_teacher)) -> dict:
    """Gives the assignment to more students of its class, for example ones
    who joined after it was set. Students who already have it are skipped."""
    assignment = get_db().collection("assignments").document(assignment_id).get().to_dict()
    check_class(assignment["class_id"], user, open_only=True)
    have = {exercise["student_id"] for _, exercise in _copies(assignment_id)}
    new = [student_id for student_id in _chosen(body.student_ids, assignment["class_id"], user) if student_id not in have]
    exercise_ids = _add_copies(assignment_id, assignment, new, user) if new else []
    if new:
        record_audit(user.uid, "add_assignment_students", target=assignment_id)
    return {"exercise_ids": exercise_ids}

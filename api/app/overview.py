"""The class overview (docs/REQUIREMENTS.md FR-32): one screen listing
each student with their unfinished work and the stage each piece is at.
Teacher only, and only their own students and work.

Work counts as finished once released with nothing left to do: released
writing with nothing to revise, or a checked revision sent back to the
student.
"""

from fastapi import APIRouter, Depends
from google.cloud.firestore_v1.base_query import FieldFilter

from .access import check_class
from .auth import CurrentUser, require_teacher
from .firestore_client import get_db

router = APIRouter(tags=["overview"])

# The pipeline stages in order (docs/ARCHITECTURE.md section 5), so each
# student's work is listed from earliest to latest stage.
PIPELINE = [
    "assigned",
    "in_progress",
    "transcribing",
    "transcript_review",
    "scrub_review",
    "evaluating",
    "draft_ready",
    "ready_to_release",
    "revision_open",
    "revision_submitted",
    "revision_reviewed",
]


def is_finished(submission: dict) -> bool:
    return submission.get("state") in ("released", "revision_reviewed")


@router.get("/overview")
def class_overview(class_id: str | None = None, user: CurrentUser = Depends(require_teacher)) -> list[dict]:
    """Every student of the teacher, or one class's, with unfinished work."""
    if class_id is not None:
        check_class(class_id, user)
    db = get_db()

    def mine(collection: str):
        return db.collection(collection).where(filter=FieldFilter("teacher_id", "==", user.uid)).stream()

    titles = {doc.id: doc.get("title") for doc in mine("exercises")}
    rows = {
        doc.id: {"student_id": doc.id, "username": doc.get("username"), "work": []}
        for doc in mine("students")
        if doc.get("active") and (class_id is None or doc.get("class_id") == class_id)
    }

    for doc in mine("submissions"):
        submission = doc.to_dict()
        row = rows.get(submission["student_id"])
        if row is None or is_finished(submission):
            continue
        row["work"].append({"exercise_id": doc.id, "title": titles.get(doc.id, ""), "state": submission["state"]})

    for row in rows.values():
        row["work"].sort(key=lambda w: PIPELINE.index(w["state"]))
    return sorted(rows.values(), key=lambda row: row["username"].lower())

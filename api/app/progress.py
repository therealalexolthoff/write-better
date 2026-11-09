"""The student's own error view: which kinds of mistake they make across
all their returned work, and examples from their own writing.

Built from the same counting as the teacher's learner profile (profile.py),
with two differences that keep it to what the student has already seen:
- only work released to the student counts. The teacher's profile also
  counts approved work that hasn't been released yet ("ready_to_release");
- revision outcomes count only once the teacher has sent them back
  ("revision_reviewed"). Outcomes the teacher has marked but not sent yet
  are left out.
Never the teacher's notes, corrections or explanations. Plain counts only:
no scores or percentages (CLAUDE.md).
"""

import re

from fastapi import APIRouter, Depends
from google.cloud.firestore_v1.base_query import FieldFilter

from .auth import CurrentUser, require_student
from .firestore_client import get_db
from .profile import annotated_spans, compute_profile
from .settings import get_settings

router = APIRouter(tags=["progress"])

# States in which the student has seen their results (exercises.RESULTS_STATES).
RELEASED_STATES = ("released", "revision_open", "revision_submitted", "revision_reviewed")
EXAMPLES_PER_CODE = 3
MAX_EXCERPT = 220

# Where a sentence ends: . ! or ? followed by a space, or a line break.
_SENTENCE_END = re.compile(r"[.!?](?=\s)|\n")


def released_work(student_id: str) -> list[tuple[dict, dict]]:
    """The student's released work, newest first, as (exercise, submission)
    pairs. Revision outcomes the student hasn't been sent are removed."""
    db = get_db()
    docs = db.collection("submissions").where(filter=FieldFilter("student_id", "==", student_id)).stream()
    released = [(doc.id, doc.to_dict()) for doc in docs if doc.get("state") in RELEASED_STATES]
    released.sort(key=lambda pair: pair[1].get("released_at") or pair[1]["updated_at"], reverse=True)
    pairs = []
    for exercise_id, submission in released:
        if submission["state"] != "revision_reviewed" and submission.get("revision"):
            submission = {**submission, "revision": {**submission["revision"], "outcomes": {}}}
        exercise = db.collection("exercises").document(exercise_id).get().to_dict() or {}
        pairs.append((exercise, submission))
    return pairs


def excerpt(text: str, start: int, end: int) -> dict:
    """The sentence around an error, with the error's position in it.
    A very long sentence is cut to about MAX_EXCERPT characters around the
    error; cut_start / cut_end say where, so the screen can show "…"."""
    ends_before = [m.end() for m in _SENTENCE_END.finditer(text, 0, start)]
    sentence_start = ends_before[-1] if ends_before else 0
    after = _SENTENCE_END.search(text, end)
    sentence_end = after.end() if after else len(text)
    # Split the room left around the error evenly before and after it.
    room = max(0, MAX_EXCERPT - (end - start))
    from_ = max(sentence_start, start - room // 2)
    to = min(sentence_end, from_ + max(MAX_EXCERPT, end - from_))
    piece = text[from_:to]
    lead = len(piece) - len(piece.lstrip())
    return {
        "text": piece.strip(),
        "start": start - from_ - lead,
        "end": end - from_ - lead,
        "cut_start": from_ > sentence_start,
        "cut_end": to < sentence_end,
    }


def examples_by_code(pairs: list[tuple[dict, dict]]) -> dict[str, list[dict]]:
    """Up to EXAMPLES_PER_CODE examples of each code, newest work first."""
    examples: dict[str, list[dict]] = {}
    for exercise, submission in pairs:
        for span in annotated_spans(submission):
            found = examples.setdefault(span["code"], [])
            if len(found) < EXAMPLES_PER_CODE:
                found.append({"title": exercise.get("title", ""), **excerpt(span["text"], span["start"], span["end"])})
    return examples


@router.get("/me/errors")
def my_errors(user: CurrentUser = Depends(require_student)) -> dict:
    """The signed-in student's own errors: across all returned work, across
    their most recent pieces, and examples of each kind."""
    pairs = released_work(user.student_id)
    recent_count = min(get_settings().profile_window, len(pairs))
    return {
        "pieces": len(pairs),
        "recent_pieces": recent_count,
        "all": compute_profile(pairs),
        "recent": compute_profile(pairs[:recent_count]),
        "examples": examples_by_code(pairs),
    }

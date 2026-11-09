"""Pydantic request/response schemas for the API."""

from typing import Annotated, Literal

from pydantic import BaseModel, Field

class StudentCreateRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=8)
    class_id: str  # one of the teacher's own open classes


class MoveStudentRequest(BaseModel):
    class_id: str


class ResetPasswordRequest(BaseModel):
    password: str = Field(min_length=8)


class DeleteStudentRequest(BaseModel):
    confirm_username: str


class StudentPublic(BaseModel):
    student_id: str
    username: str
    active: bool
    class_id: str | None = None


# ---- writing exercises ----

# Generous limits that still stop runaway input from reaching Firestore or
# the harness (the harness bills per token).
_MAX_DESCRIPTION = 2000
_MAX_ANSWER = 10_000  # a long writing response is ~1,500 words
_MAX_SPAN_EDIT = 500

AnswerText = Annotated[str, Field(max_length=_MAX_ANSWER)]

# The student's response, its scrubbed copy and so on are all stored under
# this one key: {"text": ...}.
WRITING_KEY = "text"


class AnswersBody(BaseModel):
    answers: dict[str, AnswerText]


class SpanView(BaseModel):
    """An error span as a student sees it: where it is, its code, and what
    the code means - never the correction or explanation (FR-21)."""

    start: int
    end: int
    code: str
    meaning: str


class ScrubbedBody(BaseModel):
    # {"text": the teacher's scrubbed copy of the response}
    scrubbed_answers: dict[str, AnswerText]


class EvaluateBody(BaseModel):
    note: str = Field(default="", max_length=_MAX_DESCRIPTION)  # regenerate note (FR-20)


class StudentExerciseView(BaseModel):
    exercise_id: str
    kind: str = "writing"
    title: str
    state: str
    answers: dict[str, AnswerText]
    prompt: str
    min_words: int | None = None
    max_words: int | None = None
    # Only after release:
    answer_text: str | None = None  # the evaluated (scrubbed) text the spans point into
    spans: list[SpanView] | None = None
    comment: str | None = None
    revision_edits: dict[str, str] | None = None  # {span index: the student's new words}
    revised_text: str | None = None
    # Once the teacher sends back the checked revision:
    outcomes: dict[str, str] | None = None  # {span index: outcome} for each span the student changed
    corrections: dict[str, str] | None = None  # {span index: suggested correction}, only spans not fixed


# ---- handwriting and revision ----


class TranscriptionBody(BaseModel):
    text: str = Field(max_length=_MAX_ANSWER)


class FinalSourceBody(BaseModel):
    # Which version of the response is evaluated (FR-24).
    source: Literal["typed", "photo"]


class RevisionBody(BaseModel):
    # {span index (its position in the annotation list): the new words}
    edits: dict[str, Annotated[str, Field(max_length=_MAX_SPAN_EDIT)]]


Outcome = Literal["fixed", "unfixed", "changed_wrongly"]


class OutcomesBody(BaseModel):
    # {span index: outcome} for every span the student changed (FR-27)
    outcomes: dict[str, Outcome]


class StudentExerciseSummary(BaseModel):
    exercise_id: str
    title: str
    state: str


# ---- learner profile and notes ----

_MAX_NOTES = 5000


class NotesBody(BaseModel):
    teacher_notes: str = Field(max_length=_MAX_NOTES)

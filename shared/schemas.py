"""Pydantic schemas for the two harness operations (transcribe and
evaluate_writing), and for the writing exercises the teacher writes.

Single source of truth for both services - the harness builds these, the
API re-validates them independently (docs/HARNESS_SPEC.md: "the API
re-validates independently"). Most of the structural rules from
HARNESS_SPEC.md section 4 are enforced right here as field/model
validators; the one check that needs text living outside the annotation
itself (span resolution) is in shared/validation.py instead.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .taxonomy import ErrorCode

# The prompt template version, recorded on every job (docs/HARNESS_SPEC.md
# section 8). Lives here, not in the harness, because the API sends it on
# every request - one definition means the two services can't disagree.
# Bump it whenever any prompt in harness/app/prompts.py changes.
# v7 removed the generation, short-answer and lesson prompts; the prompts
# still sent are unchanged from v6.
PROMPT_VERSION = "v7"


class StrictModel(BaseModel):
    """No extra properties, anywhere - part of forcing Claude's output into
    the schema exactly (docs/HARNESS_SPEC.md section 8: "Output is forced
    into a JSON schema ... for format only")."""

    model_config = ConfigDict(extra="forbid")


class BaseHarnessRequest(StrictModel):
    student_id: str
    request_id: str
    prompt_version: str


# ---- writing exercises (written by the teacher, never by the AI) ----


class WritingExerciseDraft(StrictModel):
    kind: Literal["writing"] = "writing"
    title: str
    prompt: str
    min_words: int | None = Field(default=None, ge=1)
    max_words: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def check_word_range(self) -> "WritingExerciseDraft":
        if self.min_words and self.max_words and self.min_words > self.max_words:
            raise ValueError(f"min_words ({self.min_words}) is more than max_words ({self.max_words})")
        return self


# ---- transcribe ----


class TranscriptionPage(StrictModel):
    page: int = Field(ge=1)
    text: str


class TranscribeResult(StrictModel):
    pages: list[TranscriptionPage] = Field(min_length=1)


class TranscribeRequest(BaseHarnessRequest):
    pages: list[str] = Field(min_length=1)  # base64 image data, in page order


# ---- evaluate_writing ----


class Annotation(StrictModel):
    code: ErrorCode
    span_text: str
    occurrence: int = Field(ge=1)
    correction: str
    explanation: str


class EvaluateWritingRequest(BaseHarnessRequest):
    prompt: str
    text: str
    # The teacher's optional note when regenerating an evaluation (FR-20).
    regenerate_note: str | None = None


class EvaluateWritingResult(StrictModel):
    annotations: list[Annotation] = Field(default_factory=list)
    comment: str


# ---- response envelope ----


class HarnessMeta(StrictModel):
    """Every harness response carries these - docs/HARNESS_SPEC.md section 1."""

    model: str
    tokens_in: int = Field(ge=0)
    tokens_out: int = Field(ge=0)
    tokens_cached: int = Field(ge=0, default=0)
    latency_ms: float = Field(ge=0)


class TranscribeResponse(HarnessMeta):
    result: TranscribeResult


class EvaluateWritingResponse(HarnessMeta):
    result: EvaluateWritingResult

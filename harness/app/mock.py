"""Canned, schema-valid mock responses for the two operations.

Used when HARNESS_MOCK_MODE is on (see app/main.py), so the rest of the
app can be built and tested without calling Claude - docs/HARNESS_SPEC.md
section 8. Still built from the real request where it's easy to (e.g.
annotation spans reference actual substrings of the input text), so the
validation pipeline is genuinely exercised rather than trivially passed.
"""

from shared.schemas import (
    Annotation,
    EvaluateWritingRequest,
    EvaluateWritingResult,
    TranscribeRequest,
    TranscribeResult,
    TranscriptionPage,
)

MOCK_MODEL = "mock"


def mock_transcribe(req: TranscribeRequest) -> TranscribeResult:
    pages = [
        TranscriptionPage(page=i, text=f"(mock transcription of page {i})")
        for i in range(1, len(req.pages) + 1)
    ]
    return TranscribeResult(pages=pages)


def mock_evaluate_writing(req: EvaluateWritingRequest) -> EvaluateWritingResult:
    words = req.text.split()
    annotations = (
        [Annotation(code="SP", span_text=words[0], occurrence=1, correction=words[0], explanation="(mock)")]
        if words
        else []
    )
    return EvaluateWritingResult(annotations=annotations, comment="(mock overall comment)")

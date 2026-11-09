"""Harness service entry point.

The two operations, transcribe and evaluate_writing - see
docs/HARNESS_SPEC.md and app/operations.py.

Reminder for every future change to this service: no database or storage
access, ever, and never log student text or images.
"""

from fastapi import FastAPI

from shared.logs import catch_unexpected_errors
from shared.schemas import (
    EvaluateWritingRequest,
    EvaluateWritingResponse,
    TranscribeRequest,
    TranscribeResponse,
)

from . import operations

app = FastAPI(title="Write Better Harness")
catch_unexpected_errors(app)  # no tracebacks in the logs: they can quote student text


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/transcribe", response_model=TranscribeResponse)
def transcribe(req: TranscribeRequest) -> TranscribeResponse:
    return operations.transcribe(req)


@app.post("/evaluate_writing", response_model=EvaluateWritingResponse)
def evaluate_writing(req: EvaluateWritingRequest) -> EvaluateWritingResponse:
    return operations.evaluate_writing(req)

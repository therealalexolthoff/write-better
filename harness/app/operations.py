"""The two harness operations: transcribe and evaluate_writing.

Mock mode (HARNESS_MOCK_MODE) builds canned, schema-valid output locally;
real mode calls Claude via claude_ops.call_claude, falling back to Gemini
(gemini_ops.call_gemini) when Claude is unavailable. Either way, each
operation re-runs the one semantic check that needs the source text
(annotation spans - docs/HARNESS_SPEC.md section 3) and wraps the result
in the response envelope with token/latency metadata.
"""

import logging
import time
from collections.abc import Callable

import anthropic
from fastapi import HTTPException
from pydantic import BaseModel

from shared.schemas import (
    EvaluateWritingRequest,
    EvaluateWritingResponse,
    EvaluateWritingResult,
    TranscribeRequest,
    TranscribeResponse,
    TranscribeResult,
)
from shared.validation import check_page_numbers, resolve_annotations

from . import mock, prompts
from .claude_ops import call_claude
from .config import settings
from .gemini_ops import call_gemini

MOCK_MODEL = "mock"

logger = logging.getLogger(__name__)

# Claude errors that mean "Claude can't serve this right now" rather than
# "this request is wrong": no quota (429), no access (403), model not
# found (404), or a server-side failure. A 400 is our own bug and is not
# hidden by falling back.
_CLAUDE_UNAVAILABLE_STATUS = {403, 404, 408, 429, 500, 502, 503, 504, 529}


def _call_model(
    *,
    system: str,
    user_content: str | list[dict],
    output_model: type[BaseModel],
    validate: Callable[[BaseModel], None] | None = None,
    gemini_thinking: str = "low",
) -> tuple[BaseModel, dict]:
    """Claude first; Gemini with the same prompt if Claude is unavailable
    (teacher decision 2026-10-08, while the Claude quota is pending). The
    usage dict names the model that actually answered, so the API prices
    the call correctly and the job record shows which one was used."""
    try:
        return call_claude(system=system, user_content=user_content, output_model=output_model, validate=validate)
    except anthropic.APIStatusError as exc:
        if exc.status_code not in _CLAUDE_UNAVAILABLE_STATUS:
            raise
        reason = f"HTTP {exc.status_code}"
    except (anthropic.APIConnectionError, anthropic.APITimeoutError) as exc:
        reason = type(exc).__name__
    # Only the status/error type is logged - never prompt or student text.
    logger.warning("Claude unavailable (%s); falling back to Gemini", reason)
    return call_gemini(
        system=system,
        user_content=user_content,
        output_model=output_model,
        validate=validate,
        thinking=gemini_thinking,
    )


def _tokens_for(obj: BaseModel) -> int:
    """Rough chars/4 estimate, mock mode only - real mode uses the actual
    counts Claude reports."""
    return max(1, len(obj.model_dump_json()) // 4)


def _mock_response(req: BaseModel, result: BaseModel, response_cls: type[BaseModel], start: float):
    return response_cls(
        result=result,
        model=MOCK_MODEL,
        tokens_in=_tokens_for(req),
        tokens_out=_tokens_for(result),
        latency_ms=(time.monotonic() - start) * 1000,
    )


def _invalid_spans(exc: Exception) -> HTTPException:
    return HTTPException(status_code=500, detail=f"invalid annotation spans: {exc}")


def transcribe(req: TranscribeRequest) -> TranscribeResponse:
    start = time.monotonic()
    if settings.mock_mode:
        result = mock.mock_transcribe(req)
        return _mock_response(req, result, TranscribeResponse, start)

    def check(result: TranscribeResult) -> None:
        check_page_numbers([p.page for p in result.pages], len(req.pages))

    result, usage = _call_model(
        system=prompts.TRANSCRIBE_SYSTEM,
        user_content=prompts.transcribe_user_content(req),
        output_model=TranscribeResult,
        gemini_thinking="medium",  # accuracy matters more than speed here
        validate=check,
    )
    return TranscribeResponse(result=result, **usage)


def evaluate_writing(req: EvaluateWritingRequest) -> EvaluateWritingResponse:
    start = time.monotonic()

    def check(result: EvaluateWritingResult) -> None:
        resolve_annotations(result.annotations, req.text)

    if settings.mock_mode:
        result = mock.mock_evaluate_writing(req)
        try:
            check(result)
        except Exception as exc:
            raise _invalid_spans(exc) from exc
        return _mock_response(req, result, EvaluateWritingResponse, start)

    result, usage = _call_model(
        system=prompts.EVALUATE_WRITING_SYSTEM,
        user_content=prompts.evaluate_writing_user_content(req),
        output_model=EvaluateWritingResult,
        gemini_thinking="medium",  # accuracy matters more than speed here
        validate=check,
    )
    return EvaluateWritingResponse(result=result, **usage)

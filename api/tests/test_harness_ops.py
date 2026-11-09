import pytest

from api.app import harness_ops, spend
from shared.schemas import EvaluateWritingRequest, TranscribeRequest

BASE = dict(student_id="s1", request_id="r1", prompt_version="v1")
EVALUATE_REQ = dict(**BASE, prompt="Describe your weekend.", text="I go park.")


def _envelope(result):
    return {
        "model": "mock",
        "tokens_in": 10,
        "tokens_out": 20,
        "tokens_cached": 0,
        "latency_ms": 1.0,
        "result": result,
    }


def test_call_harness_happy_path_records_job(monkeypatch, fake_db):
    result_payload = {
        "annotations": [{"code": "VT", "span_text": "go", "occurrence": 1, "correction": "went", "explanation": ""}],
        "comment": "c",
    }
    monkeypatch.setattr("api.app.harness_ops.post_to_harness", lambda op, body: _envelope(result_payload))

    result, job_id = harness_ops.call_harness("evaluate_writing", EvaluateWritingRequest(**EVALUATE_REQ), "teacher-1")

    assert result.annotations[0].span_text == "go"
    assert spend.current_month_spend() == 0.0  # mock model is free
    job = fake_db.collection("jobs").document(job_id).get().to_dict()
    assert job["status"] == "done" and job["operation"] == "evaluate_writing" and job["teacher_id"] == "teacher-1"


def test_call_harness_rejects_invalid_annotation_span(monkeypatch, fake_db):
    # "went" never appears in "I go park." - an unresolvable span.
    bad_result = {
        "annotations": [{"code": "VT", "span_text": "went", "occurrence": 1, "correction": "went", "explanation": ""}],
        "comment": "c",
    }
    monkeypatch.setattr("api.app.harness_ops.post_to_harness", lambda op, body: _envelope(bad_result))

    with pytest.raises(harness_ops.HarnessValidationFailed):
        harness_ops.call_harness("evaluate_writing", EvaluateWritingRequest(**EVALUATE_REQ), "teacher-1")

    assert any(d.get("status") == "error" for d in fake_db.collection("jobs").stream())


def test_call_harness_rejects_a_transcription_missing_a_page(monkeypatch, fake_db):
    monkeypatch.setattr(
        "api.app.harness_ops.post_to_harness", lambda op, body: _envelope({"pages": [{"page": 1, "text": "a"}]})
    )
    with pytest.raises(harness_ops.HarnessValidationFailed):
        harness_ops.call_harness("transcribe", TranscribeRequest(**BASE, pages=["p1", "p2"]), "teacher-1")


def test_call_harness_respects_spend_cap(monkeypatch, fake_db):
    fake_db.collection("settings").document("global").set(
        {"monthly_cap_usd": 0.01, "estimated_cost_per_call_usd": 0.05}
    )

    called = []
    monkeypatch.setattr("api.app.harness_ops.post_to_harness", lambda op, body: called.append(1))

    with pytest.raises(harness_ops.SpendCapReached):
        harness_ops.call_harness("evaluate_writing", EvaluateWritingRequest(**EVALUATE_REQ), "teacher-1")

    assert called == []  # never actually called the harness


def test_cut_operations_are_unknown(fake_db):
    for operation in ("generate_exercise", "evaluate_exercise", "generate_lesson"):
        with pytest.raises(ValueError):
            harness_ops.call_harness(operation, EvaluateWritingRequest(**EVALUATE_REQ), "teacher-1")

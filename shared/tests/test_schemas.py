import pytest
from pydantic import ValidationError

from shared.schemas import Annotation, EvaluateWritingResult, WritingExerciseDraft


def test_writing_draft_word_limits_are_optional():
    draft = WritingExerciseDraft(title="t", prompt="p")
    assert (draft.kind, draft.min_words, draft.max_words) == ("writing", None, None)


def test_writing_draft_rejects_min_above_max():
    with pytest.raises(ValidationError):
        WritingExerciseDraft(title="t", prompt="p", min_words=200, max_words=100)


def test_writing_draft_rejects_another_kind_and_extra_fields():
    with pytest.raises(ValidationError):
        WritingExerciseDraft(kind="grammar", title="t", prompt="p")
    with pytest.raises(ValidationError):
        WritingExerciseDraft(title="t", prompt="p", items=[])


def test_annotation_rejects_unknown_code():
    with pytest.raises(ValidationError):
        Annotation(code="ZZ", span_text="x", occurrence=1, correction="y", explanation="z")


def test_evaluation_needs_a_comment():
    with pytest.raises(ValidationError):
        EvaluateWritingResult(annotations=[])

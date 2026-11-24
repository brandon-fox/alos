"""RED-first unit tests for Ring 1 frozen action, context, and memory domain models."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest
from pydantic import BaseModel, TypeAdapter, ValidationError

import alos.domain.models as dm
import alos.schemas as legacy_schemas
import alos.schemas.actions as legacy_actions
from alos.core.evaluator import EvaluatorNode, RiskLevel

_MAIL = {"to_email": "a@b.c", "subject": "Q", "body": "B"}
_CAL = dict(action_type="google_calendar_create_event", title="S", start_time="1", end_time="2")
_DOC = {"file_name": "a.md", "file_path": "/a.md", "content": "x"}

ACTION_CASES: list[tuple[Mapping[str, Any], type[dm.BaseAction]]] = [
    ({"action_type": "todoist_create_task", "title": "Sealant"}, dm.TodoistTaskCreate),
    (_CAL, dm.GoogleCalendarEvent),
    ({"action_type": "email_create_draft", **_MAIL}, dm.EmailDraft),
    ({"action_type": "email_send", **_MAIL}, dm.EmailSend),
    ({"action_type": "vault_update_note", "filename": "n.md", "content": "x"}, dm.VaultNoteUpdate),
    ({"action_type": "web_search", "query": "local rag"}, dm.WebSearchQuery),
]

FROZEN_CASES: list[tuple[type[BaseModel], dict[str, Any], str, Any]] = [
    (dm.BaseAction, {"action_type": "custom", "description": "d"}, "description", "m"),
    (dm.TodoistTaskCreate, {"title": "Task"}, "title", "m"),
    (dm.EmailSend, _MAIL, "subject", "m"),
    (dm.ActionPlan, {"plan_id": "p1", "goal": "Goal"}, "goal", "m"),
    (dm.UserProfile, {"username": "alex"}, "username", "bob"),
    (dm.RAGDocument, _DOC, "score", 1.0),
    (dm.ContextPayload, {}, "preferences", ["x"]),
    (dm.ObsidianNote, _DOC, "content", "z"),
    (dm.GraphNeighborhood, {"center_note": "NoteA"}, "center_note", "NoteB"),
    (dm.SpecChunk, {**_DOC, "header": "H", "source_type": "spec"}, "header", "H2"),
]


@pytest.mark.parametrize(("payload", "expected_cls"), ACTION_CASES)
def test_action_union_discriminates_action_type(
    payload: Mapping[str, Any], expected_cls: type[dm.BaseAction]
) -> None:
    """ActionUnion validates each concrete action model via its Literal action_type."""
    parsed = TypeAdapter(dm.ActionUnion).validate_python(payload)
    assert isinstance(parsed, expected_cls)
    assert parsed.action_type == payload["action_type"]


@pytest.mark.parametrize(("model_cls", "kwargs", "field_name", "new_val"), FROZEN_CASES)
def test_domain_models_frozen_and_forbid_extra(
    model_cls: type[BaseModel], kwargs: dict[str, Any], field_name: str, new_val: Any
) -> None:
    """Every action, context, and memory model rejects mutation and unknown fields."""
    instance = model_cls.model_validate(kwargs)
    with pytest.raises(ValidationError):
        setattr(instance, field_name, new_val)
    with pytest.raises(ValidationError):
        model_cls.model_validate({**kwargs, "unexpected_extra": "forbid_me"})


def test_union_bounds_safety_matrix_and_schema_shims() -> None:
    """Union rejects unknowns, ActionPlan/RAG bounds hold, emails stay HIGH, shims match."""
    with pytest.raises(ValidationError):
        TypeAdapter(dm.ActionUnion).validate_python({"action_type": "unknown", "description": "x"})
    plan = dm.ActionPlan.model_validate(
        {"plan_id": "p1", "goal": "Send", "actions": [{"action_type": "email_send", **_MAIL}]}
    )
    assert isinstance(plan.actions[0], dm.EmailSend)
    with pytest.raises(ValidationError):
        dm.RAGDocument(**_DOC, score=-0.1)
    ev = EvaluatorNode(context=None)
    assert ev.classify_risk(dm.EmailDraft.model_validate(_MAIL)) == RiskLevel.HIGH
    assert ev.classify_risk(dm.EmailSend.model_validate(_MAIL)) == RiskLevel.HIGH
    assert set(legacy_actions.__all__) == set(legacy_schemas.__all__)
    assert {"ActionUnion", "EmailDraft", "EmailSend"} <= set(legacy_actions.__all__)
    for name in legacy_actions.__all__:
        assert name in dm.__all__
        assert getattr(legacy_actions, name) is getattr(dm, name)
        assert getattr(legacy_schemas, name) is getattr(dm, name)

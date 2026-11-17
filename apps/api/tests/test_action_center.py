from datetime import date
from uuid import UUID

import pytest

from pmc_api import action_center
from pmc_api.action_center import ActionItem, classify_urgency, summarize


def item(*, identifier: str, urgency: str, assigned: bool = True) -> ActionItem:
    return ActionItem.model_validate(
        {
            "id": identifier,
            "source": "capa",
            "source_id": UUID("10000000-0000-4000-8000-000000000001"),
            "unit_id": UUID("20000000-0000-4000-8000-000000000001"),
            "title": "Containment action",
            "context": "CAPA-001 · Supplier escape",
            "state": "open",
            "urgency": urgency,
            "due_date": "2026-11-02",
            "overdue": urgency == "overdue",
            "assigned_to_user_id": (
                UUID("30000000-0000-4000-8000-000000000001") if assigned else None
            ),
            "assignee_name": "Quality lead" if assigned else None,
            "target_workspace": "capa",
            "target_record_id": UUID("40000000-0000-4000-8000-000000000001"),
            "target_subrecord_id": UUID("10000000-0000-4000-8000-000000000001"),
            "target_process_id": UUID("50000000-0000-4000-8000-000000000001"),
            "updated_at": "2026-11-02T12:00:00Z",
        }
    )


def test_urgency_is_deterministic_at_boundaries() -> None:
    today = date(2026, 11, 2)
    assert classify_urgency(date(2026, 11, 1), today=today) == "overdue"
    assert classify_urgency(today, today=today) == "due_soon"
    assert classify_urgency(date(2026, 11, 9), today=today) == "due_soon"
    assert classify_urgency(date(2026, 11, 10), today=today) == "normal"
    assert classify_urgency(None, today=today, waiting_review=True) == "waiting_review"


def test_summary_counts_actionable_states() -> None:
    summary = summarize(
        [
            item(identifier="one", urgency="overdue"),
            item(identifier="two", urgency="due_soon", assigned=False),
            item(identifier="three", urgency="normal"),
        ]
    )
    assert summary.total == 3
    assert summary.overdue == 1
    assert summary.due_soon == 1
    assert summary.unassigned == 1
    assert summary.by_source == {"capa": 3}


def test_evidence_review_action_requires_the_complete_destination_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    granted = {"evidence.review"}
    monkeypatch.setattr(
        action_center,
        "_can",
        lambda _db, capability, _unit_id: capability in granted,
    )
    assert not action_center._can_review_evidence(None, UUID(int=1))  # type: ignore[arg-type]
    granted.update({"controls.read", "control_instances.read", "control_instances.manage"})
    assert action_center._can_review_evidence(None, UUID(int=1))  # type: ignore[arg-type]

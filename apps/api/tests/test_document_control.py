"""Pure domain tests for PMC-05 controlled document revisions."""
from datetime import UTC, datetime
from uuid import UUID

import pytest

from pmc_api.document_control import (
    InvalidRevisionTransition,
    Revision,
    RevisionState,
    transition,
)

TENANT = UUID("10000000-0000-4000-8000-000000000001")
OTHER_TENANT = UUID("10000000-0000-4000-8000-000000000002")
DOCUMENT = UUID("20000000-0000-4000-8000-000000000001")
AUTHOR = UUID("30000000-0000-4000-8000-000000000001")
REVIEWER = UUID("30000000-0000-4000-8000-000000000002")


def change(revision: Revision, target: RevisionState, *, actor: UUID = REVIEWER,
           tenant: UUID = TENANT, timestamp: datetime | None = None) -> Revision:
    return transition(revision, target=target, actor_id=actor,
                      actor_tenant_id=tenant, timestamp=timestamp)


def draft() -> Revision:
    return Revision(tenant_id=TENANT, document_id=DOCUMENT, number=1, author_id=AUTHOR)


def test_controlled_lifecycle_and_immutability() -> None:
    original = draft()
    review = change(original, RevisionState.IN_REVIEW, actor=AUTHOR)
    approved = change(review, RevisionState.APPROVED)
    effective = change(approved, RevisionState.EFFECTIVE,
                       timestamp=datetime(2026, 11, 12, tzinfo=UTC))
    superseded = change(effective, RevisionState.SUPERSEDED)
    assert original.state is RevisionState.DRAFT
    assert approved.approver_id == REVIEWER
    assert effective.effective_at == datetime(2026, 11, 12, tzinfo=UTC)
    assert superseded.state is RevisionState.SUPERSEDED


def test_author_cannot_self_approve() -> None:
    review = change(draft(), RevisionState.IN_REVIEW)
    with pytest.raises(InvalidRevisionTransition):
        change(review, RevisionState.APPROVED, actor=AUTHOR)


def test_cross_tenant_transition_denied() -> None:
    with pytest.raises(InvalidRevisionTransition):
        change(draft(), RevisionState.IN_REVIEW, tenant=OTHER_TENANT)


def test_skip_review_denied() -> None:
    with pytest.raises(InvalidRevisionTransition):
        change(draft(), RevisionState.EFFECTIVE)


def test_naive_effective_time_denied() -> None:
    approved = change(change(draft(), RevisionState.IN_REVIEW), RevisionState.APPROVED)
    with pytest.raises(InvalidRevisionTransition):
        change(approved, RevisionState.EFFECTIVE, timestamp=datetime(2026, 11, 12))


def test_rejection_can_return_to_draft() -> None:
    review = change(draft(), RevisionState.IN_REVIEW)
    rejected = change(review, RevisionState.REJECTED)
    assert change(rejected, RevisionState.DRAFT).state is RevisionState.DRAFT

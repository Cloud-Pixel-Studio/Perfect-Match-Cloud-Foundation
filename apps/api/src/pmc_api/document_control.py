"""PMC-05 document revision lifecycle rules.

This domain component does not itself provide persistence, authorization,
audit events or an HTTP endpoint. Callers must enforce tenant membership.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID


class RevisionState(StrEnum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    EFFECTIVE = "effective"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class InvalidRevisionTransition(ValueError):
    """A document revision cannot make the requested state change."""


@dataclass(frozen=True)
class Revision:
    tenant_id: UUID
    document_id: UUID
    number: int
    author_id: UUID
    state: RevisionState = RevisionState.DRAFT
    approver_id: UUID | None = None
    effective_at: datetime | None = None


_NEXT: dict[RevisionState, frozenset[RevisionState]] = {
    RevisionState.DRAFT: frozenset({RevisionState.IN_REVIEW}),
    RevisionState.IN_REVIEW: frozenset({RevisionState.APPROVED, RevisionState.REJECTED}),
    RevisionState.REJECTED: frozenset({RevisionState.DRAFT}),
    RevisionState.APPROVED: frozenset({RevisionState.EFFECTIVE}),
    RevisionState.EFFECTIVE: frozenset({RevisionState.SUPERSEDED}),
    RevisionState.SUPERSEDED: frozenset(),
}


def transition(
    revision: Revision,
    *,
    target: RevisionState,
    actor_id: UUID,
    actor_tenant_id: UUID,
    timestamp: datetime | None = None,
) -> Revision:
    """Validate and return a new immutable revision state."""

    if actor_tenant_id != revision.tenant_id:
        raise InvalidRevisionTransition("Cross-tenant revision transition denied")
    if revision.number < 1:
        raise InvalidRevisionTransition("Revision number must be positive")
    if target not in _NEXT[revision.state]:
        raise InvalidRevisionTransition("Invalid revision state transition")
    if target is RevisionState.APPROVED:
        if actor_id == revision.author_id:
            raise InvalidRevisionTransition("Authors cannot approve their own revisions")
        return replace(revision, state=target, approver_id=actor_id)
    if target is RevisionState.EFFECTIVE:
        if revision.approver_id is None or revision.approver_id == revision.author_id:
            raise InvalidRevisionTransition("Independent approval required")
        instant = timestamp if timestamp is not None else datetime.now(UTC)
        if instant.tzinfo is None or instant.utcoffset() is None:
            raise InvalidRevisionTransition("Effective timestamp must have a timezone")
        return replace(revision, state=target, effective_at=instant)
    return replace(revision, state=target)

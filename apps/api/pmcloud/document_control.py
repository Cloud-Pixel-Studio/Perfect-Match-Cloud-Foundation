"""PMC-05 domain rules for controlled document revisions.

Pure domain functions; persistence, tenant authorization, and audit writes must
be handled by the API transaction before this can serve requests.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum


class RevisionStatus(StrEnum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    EFFECTIVE = "effective"
    SUPERSEDED = "superseded"
    REJECTED = "rejected"


class DocumentTransitionError(ValueError):
    pass


@dataclass(frozen=True)
class DocumentRevision:
    document_id: str
    tenant_id: str
    revision: int
    status: RevisionStatus
    effective_at: datetime | None = None


_ALLOWED = {
    RevisionStatus.DRAFT: {RevisionStatus.IN_REVIEW},
    RevisionStatus.IN_REVIEW: {RevisionStatus.APPROVED, RevisionStatus.REJECTED},
    RevisionStatus.REJECTED: {RevisionStatus.DRAFT},
    RevisionStatus.APPROVED: {RevisionStatus.EFFECTIVE},
    RevisionStatus.EFFECTIVE: {RevisionStatus.SUPERSEDED},
    RevisionStatus.SUPERSEDED: set(),
}


def transition_revision(
    revision: DocumentRevision,
    target: RevisionStatus,
    *,
    actor_id: str,
    author_id: str,
    approved_by: str | None = None,
    now: datetime | None = None,
) -> DocumentRevision:
    """Return a validated new state; never mutate the original revision."""
    if not actor_id or not author_id:
        raise DocumentTransitionError("Actor and author identities are required")
    if target not in _ALLOWED[revision.status]:
        raise DocumentTransitionError(f"Invalid revision transition: {revision.status} -> {target}")
    if target == RevisionStatus.APPROVED and actor_id == author_id:
        raise DocumentTransitionError("Author cannot approve their own revision")
    if target == RevisionStatus.EFFECTIVE:
        if not approved_by or approved_by == author_id:
            raise DocumentTransitionError("Independent approval is required before effectiveness")
        instant = now or datetime.now(timezone.utc)
        if instant.tzinfo is None or instant.utcoffset() is None:
            raise DocumentTransitionError("Effective timestamp must be timezone-aware")
        return DocumentRevision(
            revision.document_id, revision.tenant_id, revision.revision, target, instant
        )
    return DocumentRevision(
        revision.document_id, revision.tenant_id, revision.revision, target, revision.effective_at
    )

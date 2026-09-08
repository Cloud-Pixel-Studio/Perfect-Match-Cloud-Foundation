from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pmc_api import audit_service
from pmc_api.models import Membership, OrganizationUnit, OrganizationUnitAssignment, User


@dataclass(frozen=True)
class OrganizationActor:
    user_id: UUID
    display_name: str
    role: str
    tenant_id: UUID


def require_context(db: Session, *, user_id: UUID, tenant_id: UUID | None) -> OrganizationActor:
    if tenant_id is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "tenant selection required")
    membership = db.scalar(
        select(Membership).where(
            Membership.tenant_id == tenant_id,
            Membership.user_id == user_id,
            Membership.status == "active",
        )
    )
    user = db.get(User, user_id)
    if membership is None or user is None or user.status != "active":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "tenant access denied")
    return OrganizationActor(user.id, user.display_name, membership.role, tenant_id)


def require_write(actor: OrganizationActor) -> None:
    if actor.role not in {"owner", "admin"}:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "organization mutation requires owner or admin"
        )


def _unit_values(unit: OrganizationUnit) -> dict[str, object]:
    return {
        "unit_id": str(unit.id),
        "code": unit.code,
        "name": unit.name,
        "unit_type": unit.unit_type,
        "parent_id": str(unit.parent_id) if unit.parent_id else None,
        "status": unit.status,
    }


def _assignment_values(assignment: OrganizationUnitAssignment) -> dict[str, object]:
    return {
        "assignment_id": str(assignment.id),
        "unit_id": str(assignment.unit_id),
        "user_id": str(assignment.user_id),
        "assignment_role": assignment.assignment_role,
        "is_primary": assignment.is_primary,
        "status": assignment.status,
    }


def _audit(
    db: Session,
    *,
    writer: object,
    actor: OrganizationActor,
    request_id: UUID,
    resource_id: UUID,
    old: dict[str, object] | None,
    new: dict[str, object] | None,
) -> None:
    writer(
        db,
        tenant_id=actor.tenant_id,
        actor_user_id=actor.user_id,
        actor_display_name=actor.display_name,
        actor_role=actor.role,
        resource_id=resource_id,
        request_id=request_id,
        old_values=old,
        new_values=new,
    )  # type: ignore[operator]


def create_unit(
    db: Session, *, actor: OrganizationActor, request_id: UUID, values: dict[str, object]
) -> OrganizationUnit:
    require_write(actor)
    now = datetime.now(UTC)
    unit = OrganizationUnit(
        id=uuid4(),
        tenant_id=actor.tenant_id,
        created_at=now,
        updated_at=now,
        status="active",
        **values,
    )
    db.add(unit)
    db.flush()
    _audit(
        db,
        writer=audit_service.record_organization_unit_created,
        actor=actor,
        request_id=request_id,
        resource_id=unit.id,
        old=None,
        new=_unit_values(unit),
    )
    db.commit()
    return unit


def update_unit(
    db: Session,
    *,
    actor: OrganizationActor,
    request_id: UUID,
    unit: OrganizationUnit,
    changes: dict[str, object],
) -> OrganizationUnit:
    require_write(actor)
    before = _unit_values(unit)
    for key, value in changes.items():
        setattr(unit, key, value)
    unit.updated_at = datetime.now(UTC)
    db.flush()
    _audit(
        db,
        writer=audit_service.record_organization_unit_updated,
        actor=actor,
        request_id=request_id,
        resource_id=unit.id,
        old=before,
        new=_unit_values(unit),
    )
    db.commit()
    return unit


def move_unit(
    db: Session,
    *,
    actor: OrganizationActor,
    request_id: UUID,
    unit: OrganizationUnit,
    parent_id: UUID | None,
) -> OrganizationUnit:
    require_write(actor)
    before = _unit_values(unit)
    unit.parent_id = parent_id
    unit.updated_at = datetime.now(UTC)
    db.flush()
    _audit(
        db,
        writer=audit_service.record_organization_unit_moved,
        actor=actor,
        request_id=request_id,
        resource_id=unit.id,
        old=before,
        new=_unit_values(unit),
    )
    db.commit()
    return unit


def archive_unit(
    db: Session, *, actor: OrganizationActor, request_id: UUID, unit: OrganizationUnit
) -> OrganizationUnit:
    require_write(actor)
    blocked = db.scalar(
        select(OrganizationUnit.id).where(
            OrganizationUnit.parent_id == unit.id, OrganizationUnit.status == "active"
        )
    ) or db.scalar(
        select(OrganizationUnitAssignment.id).where(
            OrganizationUnitAssignment.unit_id == unit.id,
            OrganizationUnitAssignment.status == "active",
        )
    )
    if blocked:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "archive blocked by active organization dependencies"
        )
    before = _unit_values(unit)
    unit.status = "archived"
    unit.updated_at = datetime.now(UTC)
    db.flush()
    _audit(
        db,
        writer=audit_service.record_organization_unit_archived,
        actor=actor,
        request_id=request_id,
        resource_id=unit.id,
        old=before,
        new=_unit_values(unit),
    )
    db.commit()
    return unit


def restore_unit(
    db: Session, *, actor: OrganizationActor, request_id: UUID, unit: OrganizationUnit
) -> OrganizationUnit:
    require_write(actor)
    before = _unit_values(unit)
    unit.status = "active"
    unit.updated_at = datetime.now(UTC)
    db.flush()
    _audit(
        db,
        writer=audit_service.record_organization_unit_restored,
        actor=actor,
        request_id=request_id,
        resource_id=unit.id,
        old=before,
        new=_unit_values(unit),
    )
    db.commit()
    return unit


def create_assignment(
    db: Session, *, actor: OrganizationActor, request_id: UUID, values: dict[str, object]
) -> OrganizationUnitAssignment:
    require_write(actor)
    now = datetime.now(UTC)
    assignment = OrganizationUnitAssignment(
        id=uuid4(),
        tenant_id=actor.tenant_id,
        created_at=now,
        updated_at=now,
        status="active",
        **values,
    )
    db.add(assignment)
    db.flush()
    _audit(
        db,
        writer=audit_service.record_organization_assignment_created,
        actor=actor,
        request_id=request_id,
        resource_id=assignment.id,
        old=None,
        new=_assignment_values(assignment),
    )
    db.commit()
    return assignment


def update_assignment(
    db: Session,
    *,
    actor: OrganizationActor,
    request_id: UUID,
    assignment: OrganizationUnitAssignment,
    changes: dict[str, object],
) -> OrganizationUnitAssignment:
    require_write(actor)
    before = _assignment_values(assignment)
    old_status = assignment.status
    for key, value in changes.items():
        setattr(assignment, key, value)
    assignment.updated_at = datetime.now(UTC)
    db.flush()
    action = (
        "reactivated"
        if old_status == "inactive" and assignment.status == "active"
        else "deactivated"
        if old_status == "active" and assignment.status == "inactive"
        else "updated"
    )
    writer = getattr(audit_service, f"record_organization_assignment_{action}")
    _audit(
        db,
        writer=writer,
        actor=actor,
        request_id=request_id,
        resource_id=assignment.id,
        old=before,
        new=_assignment_values(assignment),
    )
    db.commit()
    return assignment


def list_units(
    db: Session, actor: OrganizationActor, *, limit: int, offset: int
) -> list[OrganizationUnit]:
    return list(
        db.scalars(
            select(OrganizationUnit)
            .where(OrganizationUnit.tenant_id == actor.tenant_id)
            .order_by(func.lower(OrganizationUnit.name), OrganizationUnit.id)
            .offset(offset)
            .limit(limit)
        )
    )


def list_assignments(
    db: Session, actor: OrganizationActor, *, limit: int, offset: int, unit_id: UUID | None
) -> list[OrganizationUnitAssignment]:
    statement = select(OrganizationUnitAssignment).where(
        OrganizationUnitAssignment.tenant_id == actor.tenant_id
    )
    if unit_id:
        statement = statement.where(OrganizationUnitAssignment.unit_id == unit_id)
    return list(
        db.scalars(statement.order_by(OrganizationUnitAssignment.id).offset(offset).limit(limit))
    )

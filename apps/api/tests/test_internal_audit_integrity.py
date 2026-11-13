# ruff: noqa: E501
from __future__ import annotations

import os
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from starlette.requests import Request

from pmc_api.database import set_request_context
from pmc_api.internal_audits import (
    InternalAuditInput,
    InternalAuditPatch,
    InternalAuditTransition,
    ProgramInput,
    ProgramPatch,
    ProgramTransition,
    create_audit,
    create_program,
    get_audit,
    get_program,
    list_audits,
    list_programs,
    transition_audit,
    transition_program,
    update_audit,
    update_program,
)
from pmc_api.models import QMSAccessGrant, QMSAuditProgram, QMSInternalAudit
from pmc_api.organization_service import OrganizationActor
from pmc_api.qms_access import GrantInput, create_grant, require_capability, revoke_grant

pytestmark = [
    pytest.mark.internal_audit_integrity,
    pytest.mark.skipif(
        "PMC_TEST_RUNTIME_DATABASE_URL" not in os.environ,
        reason="internal-audit suite requires disposable PostgreSQL",
    ),
]

TENANT_A = UUID("a0000000-0000-4000-8000-000000000001")
TENANT_B = UUID("a0000000-0000-4000-8000-000000000002")
OWNER = UUID("a1000000-0000-4000-8000-000000000001")
MANAGER = UUID("a1000000-0000-4000-8000-000000000002")
REVIEWER = UUID("a1000000-0000-4000-8000-000000000003")
AUDITOR = UUID("a1000000-0000-4000-8000-000000000004")
UNIT_A = UUID("a2000000-0000-4000-8000-000000000001")
UNIT_A_OTHER = UUID("a2000000-0000-4000-8000-000000000002")
UNIT_B = UUID("a2000000-0000-4000-8000-000000000003")


def _engine(name: str) -> Engine:
    return create_engine(os.environ[name])


def _actor(user_id: UUID, role: str) -> OrganizationActor:
    return OrganizationActor(user_id, str(user_id), role, TENANT_A)


def _authenticated(user_id: UUID, tenant_id: UUID = TENANT_A) -> Any:
    return SimpleNamespace(
        user=SimpleNamespace(id=user_id),
        record=SimpleNamespace(current_tenant_id=tenant_id),
    )


def _request() -> Request:
    request = Request({"type": "http", "method": "POST", "path": "/", "headers": []})
    request.state.request_id = uuid4()
    return request


def _grant(db: Session, user_id: UUID, capability: str, unit_id: UUID = UNIT_A) -> QMSAccessGrant:
    set_request_context(db, user_id=OWNER, tenant_id=TENANT_A)
    return create_grant(
        db,
        _actor(OWNER, "owner"),
        uuid4(),
        GrantInput(user_id=user_id, unit_id=unit_id, capability=capability),
    )


@pytest.fixture(scope="module", autouse=True)
def seed_identity() -> None:
    now = datetime.now(UTC)
    with _engine("PMC_TEST_ADMIN_DATABASE_URL").begin() as connection:
        connection.execute(
            text(
                "TRUNCATE qms_processes, qms_internal_audits, qms_audit_programs, qms_access_grants, "
                "audit_events CASCADE"
            )
        )
        connection.execute(
            text("DELETE FROM organization_unit_assignments WHERE tenant_id IN (:a,:b)"),
            {"a": TENANT_A, "b": TENANT_B},
        )
        connection.execute(
            text("DELETE FROM organization_units WHERE tenant_id IN (:a,:b)"),
            {"a": TENANT_A, "b": TENANT_B},
        )
        connection.execute(
            text("DELETE FROM memberships WHERE tenant_id IN (:a,:b)"),
            {"a": TENANT_A, "b": TENANT_B},
        )
        connection.execute(
            text("DELETE FROM users WHERE id IN (:owner,:manager,:reviewer,:auditor)"),
            {
                "owner": OWNER,
                "manager": MANAGER,
                "reviewer": REVIEWER,
                "auditor": AUDITOR,
            },
        )
        connection.execute(
            text("DELETE FROM tenants WHERE id IN (:a,:b)"),
            {"a": TENANT_A, "b": TENANT_B},
        )
        for tenant_id, slug in ((TENANT_A, "audit-a"), (TENANT_B, "audit-b")):
            connection.execute(
                text(
                    "INSERT INTO tenants (id,name,slug,status,created_at,updated_at) "
                    "VALUES (:id,:name,:slug,'active',:now,:now)"
                ),
                {"id": tenant_id, "name": slug, "slug": slug, "now": now},
            )
        for user_id in (OWNER, MANAGER, REVIEWER, AUDITOR):
            connection.execute(
                text(
                    "INSERT INTO users (id,display_name,status,created_at) "
                    "VALUES (:id,:name,'active',:now)"
                ),
                {"id": user_id, "name": str(user_id), "now": now},
            )
        for user_id, role in (
            (OWNER, "owner"),
            (MANAGER, "member"),
            (REVIEWER, "admin"),
            (AUDITOR, "auditor"),
        ):
            connection.execute(
                text(
                    "INSERT INTO memberships (id,tenant_id,user_id,role,status,created_at) "
                    "VALUES (:id,:tenant,:user,:role,'active',:now)"
                ),
                {
                    "id": uuid4(),
                    "tenant": TENANT_A,
                    "user": user_id,
                    "role": role,
                    "now": now,
                },
            )
        connection.execute(
            text(
                "INSERT INTO memberships (id,tenant_id,user_id,role,status,created_at) "
                "VALUES (:id,:tenant,:user,'member','active',:now)"
            ),
            {"id": uuid4(), "tenant": TENANT_B, "user": MANAGER, "now": now},
        )
        for unit_id, tenant_id, code in (
            (UNIT_A, TENANT_A, "AUD-A"),
            (UNIT_A_OTHER, TENANT_A, "AUD-A2"),
            (UNIT_B, TENANT_B, "AUD-B"),
        ):
            connection.execute(
                text(
                    "INSERT INTO organization_units "
                    "(id,tenant_id,unit_type,code,name,status,created_at,updated_at) "
                    "VALUES (:id,:tenant,'team',:code,:name,'active',:now,:now)"
                ),
                {
                    "id": unit_id,
                    "tenant": tenant_id,
                    "code": code,
                    "name": code,
                    "now": now,
                },
            )
        for user_id in (MANAGER, REVIEWER, AUDITOR):
            connection.execute(
                text(
                    "INSERT INTO organization_unit_assignments "
                    "(id,tenant_id,unit_id,user_id,assignment_role,is_primary,status,created_at,updated_at) "
                    "VALUES (:id,:tenant,:unit,:user,'member',true,'active',:now,:now)"
                ),
                {
                    "id": uuid4(),
                    "tenant": TENANT_A,
                    "unit": UNIT_A,
                    "user": user_id,
                    "now": now,
                },
            )


def test_planning_slice_is_explicitly_authorized_isolated_and_audited() -> None:
    runtime = _engine("PMC_TEST_RUNTIME_DATABASE_URL")
    with Session(runtime, expire_on_commit=False) as db:
        _grant(db, MANAGER, "audits.manage")
        with pytest.raises(HTTPException) as denied_without_read:
            create_program(
                _request(),
                ProgramInput(
                    unit_id=UNIT_A,
                    code="AP-2027",
                    name="2027 audit program",
                    objective="Verify the management system",
                    description="Risk-based annual program",
                    date_start=date(2027, 1, 1),
                    date_end=date(2027, 12, 31),
                    owner_user_id=MANAGER,
                ),
                db,
                _authenticated(MANAGER),
            )
        assert denied_without_read.value.status_code == 403

        manager_read = _grant(db, MANAGER, "audits.read")
        manager_read_id = manager_read.id
        _grant(db, REVIEWER, "audits.read")
        _grant(db, REVIEWER, "audits.review")
        for capability in ("audits.read", "audits.manage"):
            _grant(db, MANAGER, capability, UNIT_A_OTHER)

        program = create_program(
            _request(),
            ProgramInput(
                unit_id=UNIT_A,
                code="AP-2027",
                name="2027 audit program",
                objective="Verify the management system",
                description="Risk-based annual program",
                date_start=date(2027, 1, 1),
                date_end=date(2027, 12, 31),
                owner_user_id=MANAGER,
            ),
            db,
            _authenticated(MANAGER),
        )
        assert program.state == "draft" and program.row_version == 1
        program_id = program.id

        with pytest.raises(HTTPException) as duplicate:
            create_program(
                _request(),
                ProgramInput(
                    unit_id=UNIT_A,
                    code="ap-2027",
                    name="Duplicate",
                    date_start=date(2027, 1, 1),
                    date_end=date(2027, 1, 2),
                ),
                db,
                _authenticated(MANAGER),
            )
        assert duplicate.value.status_code == 409

        with pytest.raises(HTTPException) as stale:
            update_program(
                _request(),
                program_id,
                ProgramPatch(expected_version=99, name="Stale edit"),
                db,
                _authenticated(MANAGER),
            )
        assert stale.value.status_code == 409

        program = update_program(
            _request(),
            program_id,
            ProgramPatch(expected_version=1, name="2027 risk-based audit program"),
            db,
            _authenticated(MANAGER),
        )
        assert program.row_version == 2

        set_request_context(db, user_id=MANAGER, tenant_id=TENANT_A)
        with pytest.raises(DBAPIError):
            db.execute(
                text(
                    "UPDATE qms_audit_programs SET state='approved',row_version=row_version+1,"
                    "updated_at=now() WHERE id=:id"
                ),
                {"id": program_id},
            )
        db.rollback()

        audit = create_audit(
            _request(),
            InternalAuditInput(
                unit_id=UNIT_A,
                program_id=program_id,
                code="IA-2027-001",
                name="Document control audit",
                audit_type="process",
                planned_start=date(2027, 2, 8),
                planned_end=date(2027, 2, 10),
                objective="Confirm controlled-document effectiveness",
                scope_summary="Document lifecycle and retained evidence",
                lead_auditor_user_id=AUDITOR,
            ),
            db,
            _authenticated(MANAGER),
        )
        assert audit.state == "draft" and audit.independence_status == "pending"
        audit_id = audit.id

        with pytest.raises(HTTPException) as mismatched_program_scope:
            create_audit(
                _request(),
                InternalAuditInput(
                    unit_id=UNIT_A_OTHER,
                    program_id=program_id,
                    code="IA-2027-002",
                    name="Wrong scope",
                    planned_start=date(2027, 3, 1),
                    planned_end=date(2027, 3, 2),
                    objective="Must fail closed",
                ),
                db,
                _authenticated(MANAGER),
            )
        assert mismatched_program_scope.value.status_code == 409

        audit = transition_audit(
            _request(),
            audit_id,
            InternalAuditTransition(
                expected_version=1,
                target_state="planned",
                decision="Plan reviewed and scheduled",
            ),
            db,
            _authenticated(MANAGER),
        )
        assert audit.state == "planned" and audit.row_version == 2

        audit = transition_audit(
            _request(),
            audit_id,
            InternalAuditTransition(
                expected_version=2,
                target_state="cancelled",
                decision="Scope replaced by a consolidated audit",
            ),
            db,
            _authenticated(REVIEWER),
        )
        assert audit.state == "cancelled" and audit.cancelled_by_user_id == REVIEWER
        with pytest.raises(HTTPException) as terminated_audit:
            update_audit(
                _request(),
                audit_id,
                InternalAuditPatch(expected_version=3, name="Forbidden edit"),
                db,
                _authenticated(MANAGER),
            )
        assert terminated_audit.value.status_code == 409

        for target, expected in (("approved", 3), ("active", 4), ("completed", 5)):
            program = transition_program(
                _request(),
                program_id,
                ProgramTransition(
                    expected_version=program.row_version,
                    target_state=target,
                    decision=f"Controlled decision: {target}",
                ),
                db,
                _authenticated(REVIEWER),
            )
            assert program.state == target and program.row_version == expected
        with pytest.raises(HTTPException) as terminated_program:
            update_program(
                _request(),
                program_id,
                ProgramPatch(expected_version=5, name="Forbidden edit"),
                db,
                _authenticated(MANAGER),
            )
        assert terminated_program.value.status_code == 409

        set_request_context(db, user_id=MANAGER, tenant_id=TENANT_B)
        assert db.scalar(text("SELECT count(*) FROM qms_audit_programs")) == 0
        assert db.scalar(text("SELECT count(*) FROM qms_internal_audits")) == 0
        set_request_context(db, user_id=MANAGER, tenant_id=TENANT_A)
        assert (
            db.scalar(
                text("SELECT count(*) FROM qms_audit_programs WHERE unit_id=:unit"),
                {"unit": UNIT_A_OTHER},
            )
            == 0
        )

        set_request_context(db, user_id=OWNER, tenant_id=TENANT_A)
        revoke_grant(db, _actor(OWNER, "owner"), uuid4(), manager_read_id)
        with pytest.raises(HTTPException) as revoked_immediately:
            get_program(program_id, db, _authenticated(MANAGER))
        assert revoked_immediately.value.status_code in {403, 404}
        with pytest.raises(HTTPException):
            get_audit(audit_id, db, _authenticated(MANAGER))

    with _engine("PMC_TEST_ADMIN_DATABASE_URL").connect() as connection:
        actions = connection.execute(
            text(
                "SELECT action,count(*) FROM audit_events "
                "WHERE resource_id IN (:program,:audit) GROUP BY action ORDER BY action"
            ),
            {"program": program_id, "audit": audit_id},
        ).all()
    action_counts = {row[0]: row[1] for row in actions}
    assert action_counts == {
        "audit_program.created": 1,
        "audit_program.transitioned": 3,
        "audit_program.updated": 1,
        "internal_audit.created": 1,
        "internal_audit.transitioned": 2,
    }


def test_auditor_role_is_limited_to_read_and_execution_capabilities() -> None:
    with Session(_engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        for capability in ("audits.read", "audits.execute"):
            grant = _grant(db, AUDITOR, capability)
            assert grant.capability == capability
        for forbidden in ("audits.manage", "audits.review"):
            with pytest.raises(HTTPException) as denied:
                _grant(db, AUDITOR, forbidden)
            assert denied.value.status_code == 409
        set_request_context(db, user_id=AUDITOR, tenant_id=TENANT_A)
        require_capability(db, "audits.read", UNIT_A)
        require_capability(db, "audits.execute", UNIT_A)
        with pytest.raises(HTTPException):
            require_capability(db, "audits.manage", UNIT_A)


@dataclass
class PlanningRecords:
    db: Session
    programs: dict[UUID, list[QMSAuditProgram]]
    audits: dict[UUID, list[QMSInternalAudit]]
    read_grant_id: UUID


@pytest.fixture
def planning_records(seed_identity: None) -> Iterator[PlanningRecords]:
    """Populate actual API records in three scopes, only in the disposable DB."""
    membership_id = uuid4()
    with _engine("PMC_TEST_ADMIN_DATABASE_URL").begin() as connection:
        connection.execute(
            text(
                "TRUNCATE qms_internal_audits, qms_audit_programs, qms_access_grants, "
                "audit_events CASCADE"
            )
        )
        # Grant tenant B's reader through the real service with an authorized
        # owner, rather than manufacturing a grant or changing RLS policies.
        connection.execute(
            text(
                "INSERT INTO memberships(id,tenant_id,user_id,role,status,created_at) "
                "VALUES(:id,:tenant,:user,'owner','active',CURRENT_TIMESTAMP)"
            ),
            {"id": membership_id, "tenant": TENANT_B, "user": OWNER},
        )
    try:
        with Session(_engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
            primary_read = _grant(db, MANAGER, "audits.read")
            _grant(db, MANAGER, "audits.manage")
            for capability in ("audits.read", "audits.manage"):
                _grant(db, MANAGER, capability, UNIT_A_OTHER)
                set_request_context(db, user_id=OWNER, tenant_id=TENANT_B)
                create_grant(
                    db,
                    OrganizationActor(OWNER, str(OWNER), "owner", TENANT_B),
                    uuid4(),
                    GrantInput(user_id=MANAGER, unit_id=UNIT_B, capability=capability),
                )
            _grant(db, AUDITOR, "audits.read")
            programs: dict[UUID, list[QMSAuditProgram]] = {}
            audits: dict[UUID, list[QMSInternalAudit]] = {}
            for unit, tenant in ((UNIT_A, TENANT_A), (UNIT_A_OTHER, TENANT_A), (UNIT_B, TENANT_B)):
                programs[unit], audits[unit] = [], []
                for index in range(3 if unit == UNIT_A else 1):
                    suffix = f"{unit.hex[-1]}-{index + 1:02d}"
                    program = create_program(
                        _request(),
                        ProgramInput(
                            unit_id=unit,
                            code=f"AP-LIST-{suffix}",
                            name="Literal _%\\ finding" if index == 0 else "Ordinary finding",
                            date_start=date(2027, 3 if index < 2 else 2, 1),
                            date_end=date(2027, 12, 31),
                            owner_user_id=MANAGER,
                        ),
                        db,
                        _authenticated(MANAGER, tenant),
                    )
                    audit = create_audit(
                        _request(),
                        InternalAuditInput(
                            unit_id=unit,
                            program_id=program.id,
                            code=f"IA-LIST-{suffix}",
                            name="Synthetic listed audit",
                            planned_start=date(2027, 4 if index < 2 else 3, 1),
                            planned_end=date(2027, 12, 31),
                            objective="Verify planning navigation and scope isolation",
                        ),
                        db,
                        _authenticated(MANAGER, tenant),
                    )
                    programs[unit].append(program)
                    audits[unit].append(audit)
            yield PlanningRecords(db, programs, audits, primary_read.id)
    finally:
        with _engine("PMC_TEST_ADMIN_DATABASE_URL").begin() as connection:
            connection.execute(text("DELETE FROM memberships WHERE id=:id"), {"id": membership_id})


def _planning_list(
    kind: str,
    db: Session,
    unit_id: UUID = UNIT_A,
    *,
    user_id: UUID = MANAGER,
    tenant_id: UUID = TENANT_A,
    limit: int = 50,
    offset: int = 0,
) -> list[QMSAuditProgram] | list[QMSInternalAudit]:
    authenticated = _authenticated(user_id, tenant_id)
    if kind == "program":
        return list_programs(db, authenticated, unit_id, limit=limit, offset=offset)
    return list_audits(db, authenticated, unit_id, limit=limit, offset=offset)


def _planning_get(
    kind: str,
    db: Session,
    record_id: UUID,
    *,
    user_id: UUID = MANAGER,
    tenant_id: UUID = TENANT_A,
) -> QMSAuditProgram | QMSInternalAudit:
    authenticated = _authenticated(user_id, tenant_id)
    if kind == "program":
        return get_program(record_id, db, authenticated)
    return get_audit(record_id, db, authenticated)


def test_program_search_is_literal_and_cannot_expand_the_unit_scope(
    planning_records: PlanningRecords,
) -> None:
    db, programs = planning_records.db, planning_records.programs
    expected = programs[UNIT_A][0]
    # The same literal name exists in other scopes; wildcard escaping alone
    # must not be mistaken for tenant/unit isolation.
    for query in ("_%", "\\", expected.code.lower()):
        assert [row.id for row in list_programs(db, _authenticated(MANAGER), UNIT_A, q=query)] == [
            expected.id
        ]
    assert {row.id for row in list_programs(db, _authenticated(MANAGER), UNIT_A, q=" ")} == {
        row.id for row in programs[UNIT_A]
    }


@pytest.mark.parametrize("kind", ["program", "audit"])
def test_planning_register_pages_are_stable_and_contain_only_the_requested_unit(
    planning_records: PlanningRecords, kind: str
) -> None:
    db = planning_records.db
    records = planning_records.programs if kind == "program" else planning_records.audits
    field = "date_start" if kind == "program" else "planned_start"
    scoped: list[QMSAuditProgram | QMSInternalAudit] = list(records[UNIT_A])
    expected = sorted(scoped, key=lambda row: (-getattr(row, field).toordinal(), row.id))
    assert [row.id for row in _planning_list(kind, db)] == [row.id for row in expected]
    seen = [
        row.id for offset in range(3) for row in _planning_list(kind, db, limit=1, offset=offset)
    ]
    assert seen == [row.id for row in expected]
    assert len(set(seen)) == 3
    assert _planning_list(kind, db, limit=1, offset=3) == []
    assert {row.id for row in _planning_list(kind, db, UNIT_A_OTHER)} == {
        row.id for row in records[UNIT_A_OTHER]
    }


@pytest.mark.parametrize("kind", ["program", "audit"])
def test_a_valid_reader_in_another_company_cannot_resolve_foreign_planning_ids(
    planning_records: PlanningRecords, kind: str
) -> None:
    db = planning_records.db
    records = planning_records.programs if kind == "program" else planning_records.audits
    assert {row.id for row in _planning_list(kind, db, UNIT_B, tenant_id=TENANT_B)} == {
        row.id for row in records[UNIT_B]
    }
    with pytest.raises(HTTPException) as hidden_in_b:
        _planning_get(kind, db, records[UNIT_A][0].id, tenant_id=TENANT_B)
    assert hidden_in_b.value.status_code == 404
    with pytest.raises(HTTPException) as hidden_in_a:
        _planning_get(kind, db, records[UNIT_B][0].id)
    assert hidden_in_a.value.status_code == 404


@pytest.mark.parametrize("kind", ["program", "audit"])
def test_read_revocation_clears_previously_visible_planning_history(
    planning_records: PlanningRecords, kind: str
) -> None:
    db = planning_records.db
    records = planning_records.programs if kind == "program" else planning_records.audits
    assert len(_planning_list(kind, db)) == 3
    set_request_context(db, user_id=OWNER, tenant_id=TENANT_A)
    revoke_grant(db, _actor(OWNER, "owner"), uuid4(), planning_records.read_grant_id)
    # MANAGER keeps audits.manage. That must not imply read authority.
    with pytest.raises(HTTPException) as denied:
        _planning_list(kind, db)
    assert denied.value.status_code == 403
    with pytest.raises(HTTPException) as hidden:
        _planning_get(kind, db, records[UNIT_A][0].id)
    assert hidden.value.status_code == 404


@pytest.mark.parametrize("kind", ["program", "audit"])
def test_read_grant_in_one_unit_does_not_authorize_another_planning_scope(
    planning_records: PlanningRecords, kind: str
) -> None:
    db = planning_records.db
    records = planning_records.programs if kind == "program" else planning_records.audits
    assert len(_planning_list(kind, db, user_id=AUDITOR)) == 3
    with pytest.raises(HTTPException) as denied:
        _planning_list(kind, db, UNIT_A_OTHER, user_id=AUDITOR)
    assert denied.value.status_code == 403
    with pytest.raises(HTTPException) as hidden:
        _planning_get(kind, db, records[UNIT_A_OTHER][0].id, user_id=AUDITOR)
    assert hidden.value.status_code == 404

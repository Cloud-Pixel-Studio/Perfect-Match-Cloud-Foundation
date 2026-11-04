from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
import test_process_integrity as process_fixtures
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from test_process_integrity import SITE, actor
from test_process_integrity import create as create_process
from test_workflow_integrity import MEMBER, OTHER, OWNER, TENANT_A, TENANT_B, UNIT, context, engine

from pmc_api import audit_service, risks
from pmc_api.auth import AuthenticatedSession
from pmc_api.database import set_request_context
from pmc_api.models import QMSAccessGrant, QMSProcess, QMSRisk
from pmc_api.processes import VersionCommand, change_status
from pmc_api.qms_access import GrantInput, create_grant, revoke_grant

pytestmark = [
    pytest.mark.process_integrity,
    pytest.mark.skipif(
        "PMC_TEST_RUNTIME_DATABASE_URL" not in os.environ,
        reason="risk suite requires disposable PostgreSQL",
    ),
]


@pytest.fixture(scope="module", autouse=True)
def seed_risks() -> None:
    # The combined runner executes process tests first. Reuse their identities instead
    # of attempting to delete tenants that already have immutable audit history.
    with engine("PMC_TEST_ADMIN_DATABASE_URL").connect() as connection:
        seeded = connection.scalar(
            text(
                "SELECT EXISTS(SELECT 1 FROM organization_units "
                "WHERE id=:unit AND tenant_id=:tenant)"
            ),
            {"unit": UNIT, "tenant": TENANT_A},
        )
    if not seeded:
        process_fixtures.seed_process_identity()


@pytest.fixture(autouse=True)
def clean_risks(seed_risks: None) -> None:
    process_fixtures.reset_process_records()


def authenticated(user: UUID = MEMBER, tenant: UUID = TENANT_A) -> AuthenticatedSession:
    return cast(
        AuthenticatedSession,
        SimpleNamespace(
            user=SimpleNamespace(id=user),
            record=SimpleNamespace(current_tenant_id=tenant),
        ),
    )


def current(db: Session, user: UUID = MEMBER, tenant: UUID = TENANT_A) -> None:
    set_request_context(db, user_id=user, tenant_id=tenant)


def grant(
    db: Session,
    user: UUID = MEMBER,
    capabilities: tuple[str, ...] = (
        "risks.read",
        "risks.manage",
        "risks.review",
        "processes.read",
    ),
    unit: UUID = UNIT,
) -> list[QMSAccessGrant]:
    result = []
    for capability in capabilities:
        current(db, OWNER)
        result.append(
            create_grant(
                db,
                actor(OWNER, "owner"),
                uuid4(),
                GrantInput(user_id=user, unit_id=unit, capability=capability),
            )
        )
    current(db)
    return result


def create(db: Session, process: QMSProcess, **values: Any) -> QMSRisk:
    current(db)
    body = {
        "unit_id": UNIT,
        "process_id": process.id,
        "code": "R-" + uuid4().hex[:8],
        "name": "Incoming lot mismatch",
        "description": "The receiving check may fail to identify a mismatch.",
        "owner_user_id": MEMBER,
        **values,
    }
    return risks.create_risk(db, actor(), uuid4(), risks.RiskInput(**body))


def transition(
    db: Session,
    row: QMSRisk,
    target: str,
    **values: Any,
) -> QMSRisk:
    current(db)
    return risks.transition_risk(
        db,
        actor(),
        uuid4(),
        row.id,
        risks.RiskTransition(
            expected_version=row.row_version,
            target_state=target,
            decision="Reviewed against the receiving process.",
            **values,
        ),
    )


def response(row: QMSRisk) -> risks.RiskResponse:
    return risks.RiskResponse.model_validate(row)


def listed(db: Session, **filters: Any) -> list[QMSRisk]:
    return risks.list_risks(
        db,
        authenticated(),
        UNIT,
        **{"q": None, "state": None, "risk_type": None, "limit": 50, "offset": 0, **filters},
    )


def test_risk_lifecycle_scores_review_and_audit_preserve_the_record() -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        process = create_process(db)
        grant(db)
        yesterday = datetime.now(UTC).date() - timedelta(days=1)
        row = create(
            db,
            process,
            likelihood=4,
            impact=4,
            residual_likelihood=2,
            residual_impact=2,
            target_date=yesterday,
            cause="Distribution check has no backup owner.",
        )
        view = response(row)
        assert (view.initial_score, view.initial_level) == (16, "critical")
        assert (view.residual_score, view.residual_level) == (4, "low")
        assert view.scoring_model == "PMC-RISK-5X5-v1"
        assert view.is_overdue and view.days_overdue == 1
        row = transition(db, row, "assessed")
        assert row.assessed_by_user_id == MEMBER and row.assessed_at is not None
        row = transition(db, row, "action_required")
        row = transition(db, row, "monitoring")
        row = transition(db, row, "monitoring")
        assert row.reviewed_by_user_id == MEMBER and row.reviewed_at is not None
        row = transition(db, row, "closed", closure_notes="Control effectiveness was verified.")
        assert row.closed_by_user_id == MEMBER and row.closed_at is not None
        assert not response(row).is_overdue
        current(db, OWNER)
        history = list(
            db.execute(
                text(
                    "SELECT action,new_values FROM audit_events "
                    "WHERE resource_id=:id ORDER BY occurred_at,id"
                ),
                {"id": row.id},
            )
        )
        assert [event.action for event in history].count("risk.created") == 1
        assert [event.action for event in history].count("risk.reviewed") == 1
        payload = str([event.new_values for event in history])
        assert "description_hash" in payload
        assert "The receiving check may fail" not in payload
        assert "Distribution check has no backup owner" not in payload


def test_owner_without_explicit_grants_and_reader_cannot_mutate_risks() -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        process = create_process(db)
        current(db, OWNER)
        with pytest.raises(HTTPException) as denied:
            risks.create_risk(
                db,
                actor(OWNER, "owner"),
                uuid4(),
                risks.RiskInput(
                    unit_id=UNIT,
                    process_id=process.id,
                    code="OWNER-NO-GRANT",
                    name="Owner attempt",
                    description="Owner alone grants no QMS authority.",
                ),
            )
        assert denied.value.status_code == 403
        db.rollback()
        grant(db)
        row = create(db, process)
        grant(db, OTHER, ("risks.read",))
        viewed = risks.get_risk(db, authenticated(OTHER), row.id)
        assert viewed.id == row.id
        current(db, OTHER)
        with pytest.raises(HTTPException) as denied:
            risks.update_risk(
                db,
                actor(OTHER),
                uuid4(),
                row.id,
                risks.RiskPatch(expected_version=1, name="Reader rewrite"),
            )
        assert denied.value.status_code in {403, 404}
        current(db, OTHER)
        with pytest.raises(HTTPException) as denied:
            risks.transition_risk(
                db,
                actor(OTHER),
                uuid4(),
                row.id,
                risks.RiskTransition(
                    expected_version=1, target_state="assessed", decision="Denied"
                ),
            )
        assert denied.value.status_code in {403, 404}


def test_risk_rls_denies_absent_context_and_foreign_tenant() -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        process = create_process(db)
        grant(db)
        row = create(db, process)
        risk_id = row.id
    with engine("PMC_TEST_RUNTIME_DATABASE_URL").connect() as connection:
        assert connection.scalar(
            text(
                "SELECT relrowsecurity AND relforcerowsecurity FROM pg_class "
                "WHERE relname='qms_risks'"
            )
        )
        assert connection.scalar(text("SELECT count(*) FROM qms_risks")) == 0
        context(connection, OTHER, TENANT_B)
        assert (
            connection.scalar(text("SELECT count(*) FROM qms_risks WHERE id=:id"), {"id": risk_id})
            == 0
        )
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL")) as db:
        with pytest.raises(HTTPException) as missing:
            risks.get_risk(db, authenticated(OTHER, TENANT_B), risk_id)
        assert missing.value.status_code == 404


@pytest.mark.parametrize("tamper", ["state", "version", "timestamp", "scope", "scoring_model"])
def test_direct_writes_cannot_bypass_risk_identity_or_workflow(tamper: str) -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        process = create_process(db)
        grant(db)
        row = create(db, process)
        risk_id = row.id
    clause = {
        "state": "state='assessed',assessed_by_user_id=:user,"
        "assessed_at=CURRENT_TIMESTAMP,row_version=2",
        "version": "name='Skipped version',row_version=3",
        "timestamp": "closed_by_user_id=:user,closed_at=CURRENT_TIMESTAMP,row_version=2",
        "scope": "unit_id=:unit,row_version=2",
        "scoring_model": "scoring_model='unsafe-global-policy',row_version=2",
    }[tamper]
    with engine("PMC_TEST_RUNTIME_DATABASE_URL").connect() as connection:
        context(connection, MEMBER, TENANT_A)
        with pytest.raises(DBAPIError):
            connection.execute(
                text(f"UPDATE qms_risks SET {clause} WHERE id=:id"),  # noqa: S608
                {"id": risk_id, "user": MEMBER, "unit": SITE},
            )


def test_risk_rejects_wrong_process_scope_and_unknown_owner() -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        process = create_process(db)
        grant(db)
        grant(db, capabilities=("risks.manage", "risks.read", "processes.read"), unit=SITE)
        with pytest.raises(HTTPException) as conflict:
            create(db, process, unit_id=SITE)
        assert conflict.value.status_code == 409
        current(db)
        with pytest.raises(HTTPException) as conflict:
            create(db, process, owner_user_id=uuid4())
        assert conflict.value.status_code == 409


def test_risk_edit_conflict_review_gate_and_closed_immutability() -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        process = create_process(db)
        grant(db)
        row = create(db, process)
        current(db)
        row = risks.update_risk(
            db, actor(), uuid4(), row.id, risks.RiskPatch(expected_version=1, impact=5)
        )
        assert response(row).initial_score == row.likelihood * 5
        current(db)
        with pytest.raises(HTTPException) as stale:
            risks.update_risk(
                db, actor(), uuid4(), row.id, risks.RiskPatch(expected_version=1, impact=1)
            )
        assert stale.value.status_code == 409
        current(db)
        with pytest.raises(HTTPException) as skip:
            transition(db, row, "closed", closure_notes="Skipped review")
        assert skip.value.status_code == 409
        row = transition(db, row, "assessed")
        row = transition(db, row, "monitoring")
        with pytest.raises(HTTPException) as notes:
            transition(db, row, "closed")
        assert notes.value.status_code in {409, 422}
        row = transition(db, row, "closed", closure_notes="Monitoring confirmed acceptance.")
        current(db)
        with pytest.raises(HTTPException) as closed:
            risks.update_risk(
                db,
                actor(),
                uuid4(),
                row.id,
                risks.RiskPatch(expected_version=row.row_version, name="Rewrite closed"),
            )
        assert closed.value.status_code == 409


def test_failed_audit_does_not_leave_an_untracked_risk(monkeypatch: pytest.MonkeyPatch) -> None:
    def unavailable(*args: object, **kwargs: object) -> None:
        raise RuntimeError("audit unavailable")

    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        process = create_process(db)
        grant(db)
        monkeypatch.setattr(audit_service, "record_risk", unavailable)
        with pytest.raises(RuntimeError, match="audit unavailable"):
            create(db, process)
    with engine("PMC_TEST_ADMIN_DATABASE_URL").connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM qms_risks")) == 0


def test_risk_search_is_literal_and_pages_do_not_overlap() -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        process = create_process(db)
        grant(db)
        literal = create(db, process, name="Rare 100%_risk marker")
        other = create(db, process, name="Ordinary opportunity", risk_type="opportunity")
        assert [r.id for r in listed(db, q="100%_")] == [literal.id]
        assert [r.id for r in listed(db, risk_type="opportunity")] == [other.id]
        first = listed(db, limit=1, offset=0)
        second = listed(db, limit=1, offset=1)
        assert len(first) == len(second) == 1 and first[0].id != second[0].id
        assert {first[0].id, second[0].id} == {literal.id, other.id}


def test_revoked_risk_grant_removes_read_and_mutation_authority() -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        process = create_process(db)
        grants = grant(db)
        row = create(db, process)
        current(db, OWNER)
        read_grant = next(g for g in grants if g.capability == "risks.read")
        revoke_grant(db, actor(OWNER, "owner"), uuid4(), read_grant.id)
        with pytest.raises(HTTPException) as revoked:
            risks.get_risk(db, authenticated(), row.id)
        assert revoked.value.status_code == 403
        current(db)
        with pytest.raises(HTTPException) as revoked:
            risks.update_risk(
                db,
                actor(),
                uuid4(),
                row.id,
                risks.RiskPatch(expected_version=1, name="After read revocation"),
            )
        assert revoked.value.status_code == 403


@pytest.mark.parametrize(
    "body",
    [
        {"likelihood": 0},
        {"impact": 6},
        {"residual_likelihood": None},
        {"risk_type": "undefined"},
        {"name": "   "},
        {"description": ""},
        {"state": "closed"},
    ],
)
def test_invalid_risk_input_is_rejected_before_database(body: dict[str, Any]) -> None:
    values = {
        "unit_id": UNIT,
        "process_id": uuid4(),
        "code": "R-INPUT",
        "name": "Risk",
        "description": "An assessed process exposure.",
        **body,
    }
    with pytest.raises(ValidationError):
        risks.RiskInput(**values)


def test_null_patch_cannot_erase_required_risk_fields() -> None:
    with pytest.raises(ValidationError):
        risks.RiskPatch(expected_version=1, name=None)


def test_auditor_can_receive_risk_read_but_not_management_or_review() -> None:
    with engine("PMC_TEST_ADMIN_DATABASE_URL").begin() as connection:
        connection.execute(
            text("UPDATE memberships SET role='auditor' WHERE tenant_id=:tenant AND user_id=:user"),
            {"tenant": TENANT_A, "user": OTHER},
        )
    try:
        with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
            process = create_process(db)
            grant(db)
            row = create(db, process)
            grant(db, user=OTHER, capabilities=("risks.read",))
            current(db, OTHER)
            assert risks.get_risk(db, authenticated(OTHER), row.id).id == row.id
            for capability in ("risks.manage", "risks.review"):
                current(db, OWNER)
                with pytest.raises(HTTPException) as denied:
                    create_grant(
                        db,
                        actor(OWNER, "owner"),
                        uuid4(),
                        GrantInput(user_id=OTHER, unit_id=UNIT, capability=capability),
                    )
                assert denied.value.status_code == 409
    finally:
        with engine("PMC_TEST_ADMIN_DATABASE_URL").begin() as connection:
            connection.execute(
                text(
                    "UPDATE memberships SET role='member' WHERE tenant_id=:tenant AND user_id=:user"
                ),
                {"tenant": TENANT_A, "user": OTHER},
            )


def test_archived_process_keeps_risk_followup_and_closure_available() -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        process = create_process(db)
        grant(db)
        row = create(db, process)
        current(db)
        change_status(
            db,
            actor(),
            uuid4(),
            process.id,
            VersionCommand(expected_version=process.row_version),
            "archived",
        )
        row = transition(db, row, "assessed")
        row = transition(db, row, "monitoring")
        row = transition(db, row, "closed", closure_notes="Archived process exposure resolved.")
        assert row.state == "closed"
        with pytest.raises(HTTPException) as denied:
            create(db, process)
        assert denied.value.status_code == 409

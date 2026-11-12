from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from test_process_integrity import SITE, actor
from test_process_integrity import create as create_process
from test_risk_integrity import authenticated, current, grant
from test_risk_integrity import clean_risks as clean_risks
from test_risk_integrity import seed_risks as seed_risks
from test_workflow_integrity import MEMBER, OTHER, OWNER, TENANT_A, TENANT_B, UNIT, context, engine

from pmc_api import audit_service, nonconformities
from pmc_api.models import QMSAccessGrant, QMSNonconformity, QMSProcess
from pmc_api.processes import VersionCommand, change_status
from pmc_api.qms_access import GrantInput, create_grant, revoke_grant

pytestmark = [
    pytest.mark.process_integrity,
    pytest.mark.skipif(
        "PMC_TEST_RUNTIME_DATABASE_URL" not in os.environ,
        reason="NCR suite requires disposable PostgreSQL",
    ),
]


def access(
    db: Session,
    user: UUID = MEMBER,
    capabilities: tuple[str, ...] = ("ncr.read", "ncr.manage", "ncr.review", "processes.read"),
    unit: UUID = UNIT,
) -> list[QMSAccessGrant]:
    return grant(db, user=user, capabilities=capabilities, unit=unit)


def create(db: Session, process: QMSProcess, **values: Any) -> QMSNonconformity:
    current(db)
    body = {
        "unit_id": UNIT,
        "process_id": process.id,
        "code": "NCR-" + uuid4().hex[:10],
        "name": "Superseded instruction in use",
        "description": "A fictional workstation held a superseded receiving instruction.",
        "detected_date": datetime.now(UTC).date(),
        "owner_user_id": MEMBER,
        **values,
    }
    return nonconformities.create_ncr(db, actor(), uuid4(), nonconformities.NCRInput(**body))


def transition(
    db: Session,
    row: QMSNonconformity,
    target: str,
    *,
    user: UUID = MEMBER,
    decision: str = "Reviewed the NCR response against the recorded condition.",
    **values: Any,
) -> QMSNonconformity:
    current(db, user)
    return nonconformities.transition_ncr(
        db,
        actor(user),
        uuid4(),
        row.id,
        nonconformities.NCRTransition(
            expected_version=row.row_version, target_state=target, decision=decision, **values
        ),
    )


def listed(db: Session, **filters: Any) -> list[QMSNonconformity]:
    return nonconformities.list_ncrs(
        db,
        authenticated(),
        UNIT,
        **{
            "q": None,
            "state": None,
            "source_type": None,
            "severity": None,
            "limit": 50,
            "offset": 0,
            **filters,
        },
    )


def test_ncr_containment_investigation_closure_and_audit_history() -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        process = create_process(db)
        access(db)
        yesterday = datetime.now(UTC).date() - timedelta(days=1)
        row = create(
            db,
            process,
            source_type="document",
            severity="major",
            containment_required=True,
            target_date=yesterday,
        )
        response = nonconformities.NCRResponse.model_validate(row)
        assert response.is_overdue and response.days_overdue == 1
        assert row.detected_by_user_id == MEMBER and row.state == "draft"
        row = transition(db, row, "open")
        assert row.opened_by_user_id == MEMBER and row.opened_at is not None
        row = transition(db, row, "containment")
        with pytest.raises(HTTPException) as blocked:
            transition(db, row, "investigation")
        assert blocked.value.status_code in {409, 422}
        current(db)
        with pytest.raises(HTTPException) as bypass:
            nonconformities.update_ncr(
                db,
                actor(),
                uuid4(),
                row.id,
                nonconformities.NCRPatch(
                    expected_version=row.row_version, containment_required=False
                ),
            )
        assert bypass.value.status_code in {409, 422}
        current(db)
        row = nonconformities.update_ncr(
            db,
            actor(),
            uuid4(),
            row.id,
            nonconformities.NCRPatch(
                expected_version=row.row_version,
                containment_action="Withdraw the superseded copy from the fictional workstation.",
                containment_date=datetime.now(UTC).date(),
                containment_completed=True,
                containment_owner_user_id=MEMBER,
                root_cause_summary="Distribution check lacked ownership.",
                disposition="rework",
                disposition_notes="Reissue the correct controlled instruction.",
            ),
        )
        row = transition(db, row, "investigation")
        assert row.reviewed_by_user_id == MEMBER and row.reviewed_at is not None
        row = transition(db, row, "action_required")
        row = transition(db, row, "verification")
        row = transition(
            db, row, "closed", closure_notes="Fictional correction verified at all workstations."
        )
        assert row.closed_by_user_id == MEMBER and row.closed_at is not None
        assert not nonconformities.NCRResponse.model_validate(row).is_overdue
        current(db, OWNER)
        events = list(
            db.execute(
                text(
                    "SELECT action,new_values FROM audit_events "
                    "WHERE resource_id=:id ORDER BY occurred_at,id"
                ),
                {"id": row.id},
            )
        )
        assert [event.action for event in events].count("ncr.created") == 1
        assert [event.action for event in events].count("ncr.transitioned") == 6
        payload = str([event.new_values for event in events])
        assert "description_hash" in payload and "containment_action_hash" in payload
        assert "fictional workstation held" not in payload
        assert "Distribution check lacked" not in payload


def test_ncr_author_and_reviewer_have_separate_authority() -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        process = create_process(db)
        access(db, capabilities=("ncr.read", "ncr.manage", "processes.read"))
        access(db, user=OTHER, capabilities=("ncr.read", "ncr.review"))
        row = create(db, process)
        row = transition(db, row, "open")
        with pytest.raises(HTTPException) as denied:
            transition(db, row, "investigation")
        assert denied.value.status_code == 403
        row = transition(db, row, "investigation", user=OTHER)
        assert row.reviewed_by_user_id == OTHER
        current(db, OTHER)
        with pytest.raises(HTTPException) as denied:
            nonconformities.update_ncr(
                db,
                actor(OTHER),
                uuid4(),
                row.id,
                nonconformities.NCRPatch(expected_version=row.row_version, name="Reviewer rewrite"),
            )
        assert denied.value.status_code == 403
        row = transition(db, row, "action_required", user=OTHER)
        row = transition(
            db,
            row,
            "closed",
            user=OTHER,
            closure_notes="Reviewer supplied closure atomically without edit authority.",
        )
        assert row.closed_by_user_id == OTHER and row.opened_by_user_id == MEMBER


def test_owner_without_ncr_grant_and_read_only_member_cannot_mutate() -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        process = create_process(db)
        current(db, OWNER)
        with pytest.raises(HTTPException) as implicit:
            nonconformities.create_ncr(
                db,
                actor(OWNER, "owner"),
                uuid4(),
                nonconformities.NCRInput(
                    unit_id=UNIT,
                    process_id=process.id,
                    code="OWNER-NCR",
                    name="Owner attempt",
                    description="The platform owner has no QMS grant.",
                ),
            )
        assert implicit.value.status_code == 403
        db.rollback()
        access(db)
        row = create(db, process)
        access(db, OTHER, capabilities=("ncr.read",))
        assert nonconformities.get_ncr(db, authenticated(OTHER), row.id).id == row.id
        current(db, OTHER)
        with pytest.raises(HTTPException) as denied:
            nonconformities.update_ncr(
                db,
                actor(OTHER),
                uuid4(),
                row.id,
                nonconformities.NCRPatch(expected_version=1, severity="critical"),
            )
        assert denied.value.status_code in {403, 404}
        with pytest.raises(HTTPException) as denied:
            transition(db, row, "open", user=OTHER)
        assert denied.value.status_code in {403, 404}


def test_ncr_rls_hides_records_without_context_and_from_other_tenant() -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        process = create_process(db)
        access(db)
        ncr_id = create(db, process).id
    with engine("PMC_TEST_RUNTIME_DATABASE_URL").connect() as connection:
        assert connection.scalar(
            text(
                "SELECT relrowsecurity AND relforcerowsecurity "
                "FROM pg_class WHERE relname='qms_nonconformities'"
            )
        )
        assert connection.scalar(text("SELECT count(*) FROM qms_nonconformities")) == 0
        context(connection, OTHER, TENANT_B)
        assert (
            connection.scalar(
                text("SELECT count(*) FROM qms_nonconformities WHERE id=:id"), {"id": ncr_id}
            )
            == 0
        )
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL")) as db:
        with pytest.raises(HTTPException) as hidden:
            nonconformities.get_ncr(db, authenticated(OTHER, TENANT_B), ncr_id)
        assert hidden.value.status_code == 404


@pytest.mark.parametrize("tamper", ["state", "version", "code", "scope", "detector", "stamp"])
def test_direct_ncr_writes_cannot_bypass_identity_or_workflow(tamper: str) -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        process = create_process(db)
        access(db)
        ncr_id = create(db, process).id
    clause = {
        "state": "state='open',opened_by_user_id=:user,opened_at=CURRENT_TIMESTAMP,row_version=2",
        "version": "name='Skipped version',row_version=3",
        "code": "code='RENUMBERED',row_version=2",
        "scope": "unit_id=:unit,row_version=2",
        "detector": "detected_by_user_id=:other,row_version=2",
        "stamp": "closed_by_user_id=:user,closed_at=CURRENT_TIMESTAMP,row_version=2",
    }[tamper]
    with engine("PMC_TEST_RUNTIME_DATABASE_URL").connect() as connection:
        context(connection, MEMBER, TENANT_A)
        with pytest.raises(DBAPIError):
            connection.execute(
                text(f"UPDATE qms_nonconformities SET {clause} WHERE id=:id"),  # noqa: S608
                {"id": ncr_id, "user": MEMBER, "other": OTHER, "unit": SITE},
            )


def test_ncr_rejects_wrong_process_scope_and_foreign_tenant_owner() -> None:
    foreign_user = uuid4()
    with engine("PMC_TEST_ADMIN_DATABASE_URL").begin() as connection:
        connection.execute(
            text(
                "INSERT INTO users(id,display_name,status,created_at) "
                "VALUES(:id,'Foreign NCR owner','active',CURRENT_TIMESTAMP)"
            ),
            {"id": foreign_user},
        )
        connection.execute(
            text(
                "INSERT INTO memberships(id,tenant_id,user_id,role,status,created_at) "
                "VALUES(:id,:tenant,:user,'member','active',CURRENT_TIMESTAMP)"
            ),
            {"id": uuid4(), "tenant": TENANT_B, "user": foreign_user},
        )
    try:
        with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
            process = create_process(db)
            access(db)
            access(db, capabilities=("ncr.read", "ncr.manage", "processes.read"), unit=SITE)
            with pytest.raises(HTTPException) as scope:
                create(db, process, unit_id=SITE)
            assert scope.value.status_code == 409
            for field in ("owner_user_id", "containment_owner_user_id"):
                with pytest.raises(HTTPException) as owner:
                    create(db, process, **{field: foreign_user})
                assert owner.value.status_code == 409
    finally:
        with engine("PMC_TEST_ADMIN_DATABASE_URL").begin() as connection:
            connection.execute(
                text("DELETE FROM memberships WHERE user_id=:id"), {"id": foreign_user}
            )
            connection.execute(text("DELETE FROM users WHERE id=:id"), {"id": foreign_user})


@pytest.mark.parametrize("terminal", ["closed", "cancelled"])
def test_ncr_terminal_state_is_immutable_and_stale_edits_are_rejected(terminal: str) -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        process = create_process(db)
        access(db)
        row = create(db, process)
        current(db)
        row = nonconformities.update_ncr(
            db,
            actor(),
            uuid4(),
            row.id,
            nonconformities.NCRPatch(expected_version=1, severity="critical"),
        )
        current(db)
        with pytest.raises(HTTPException) as stale:
            nonconformities.update_ncr(
                db,
                actor(),
                uuid4(),
                row.id,
                nonconformities.NCRPatch(expected_version=1, severity="minor"),
            )
        assert stale.value.status_code == 409
        if terminal == "closed":
            with pytest.raises(HTTPException) as skip:
                transition(db, row, "closed", closure_notes="Premature closure")
            assert skip.value.status_code == 409
            row = transition(db, row, "open")
            row = transition(db, row, "investigation")
            row = transition(db, row, "action_required")
            with pytest.raises(HTTPException) as no_notes:
                transition(db, row, "closed")
            assert no_notes.value.status_code in {409, 422}
            row = transition(db, row, "closed", closure_notes="The correction was verified.")
        else:
            row = transition(
                db, row, "cancelled", decision="Duplicate report superseded by the original NCR."
            )
            assert row.cancellation_reason == "Duplicate report superseded by the original NCR."
            assert row.cancelled_by_user_id == MEMBER and row.cancelled_at is not None
        assert not nonconformities.NCRResponse.model_validate(row).is_overdue
        current(db)
        with pytest.raises(HTTPException) as immutable:
            nonconformities.update_ncr(
                db,
                actor(),
                uuid4(),
                row.id,
                nonconformities.NCRPatch(
                    expected_version=row.row_version, name="Rewrite terminal record"
                ),
            )
        assert immutable.value.status_code == 409
        ncr_id = row.id
        db.rollback()
        with engine("PMC_TEST_RUNTIME_DATABASE_URL").connect() as connection:
            context(connection, MEMBER, TENANT_A)
            with pytest.raises(DBAPIError):
                connection.execute(
                    text(
                        "UPDATE qms_nonconformities SET name='Direct rewrite',"
                        "row_version=row_version+1 WHERE id=:id"
                    ),
                    {"id": ncr_id},
                )


def test_audit_failure_rolls_back_ncr_creation_and_transition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unavailable(*args: object, **kwargs: object) -> None:
        raise RuntimeError("NCR audit unavailable")

    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        process = create_process(db)
        access(db)
        with monkeypatch.context() as patch:
            patch.setattr(audit_service, "record_ncr", unavailable)
            with pytest.raises(RuntimeError, match="NCR audit unavailable"):
                create(db, process)
        current(db)
        assert db.scalar(text("SELECT count(*) FROM qms_nonconformities")) == 0
        row = create(db, process)
        ncr_id = row.id
        with monkeypatch.context() as patch:
            patch.setattr(audit_service, "record_ncr", unavailable)
            with pytest.raises(RuntimeError, match="NCR audit unavailable"):
                transition(db, row, "open")
        current(db)
        stored = db.get(QMSNonconformity, ncr_id, populate_existing=True)
        assert stored is not None and stored.state == "draft" and stored.row_version == 1
        assert stored.opened_at is None


def test_ncr_search_filters_are_literal_and_pages_do_not_overlap() -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        process = create_process(db)
        access(db)
        first = create(
            db, process, name="Instruction 100%_mismatch", source_type="document", severity="major"
        )
        second = create(
            db, process, name="Supplier return", source_type="supplier", severity="critical"
        )
        assert [row.id for row in listed(db, q="100%_")] == [first.id]
        assert [row.id for row in listed(db, source_type="supplier", severity="critical")] == [
            second.id
        ]
        page_one, page_two = listed(db, limit=1, offset=0), listed(db, limit=1, offset=1)
        assert len(page_one) == len(page_two) == 1
        assert {page_one[0].id, page_two[0].id} == {first.id, second.id}
        with pytest.raises(HTTPException) as duplicate:
            create(db, process, code=first.code.lower())
        assert duplicate.value.status_code == 409


def test_revoked_ncr_read_removes_api_visibility_and_edit_authority() -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        process = create_process(db)
        grants = access(db)
        row = create(db, process)
        current(db, OWNER)
        read_grant = next(item for item in grants if item.capability == "ncr.read")
        revoke_grant(db, actor(OWNER, "owner"), uuid4(), read_grant.id)
        with pytest.raises(HTTPException) as revoked:
            nonconformities.get_ncr(db, authenticated(), row.id)
        assert revoked.value.status_code == 403
        current(db)
        with pytest.raises(HTTPException) as denied:
            nonconformities.update_ncr(
                db,
                actor(),
                uuid4(),
                row.id,
                nonconformities.NCRPatch(expected_version=1, name="Revoked access edit"),
            )
        assert denied.value.status_code == 403


def test_auditor_can_read_ncr_but_cannot_receive_manage_or_review() -> None:
    with engine("PMC_TEST_ADMIN_DATABASE_URL").begin() as connection:
        connection.execute(
            text("UPDATE memberships SET role='auditor' WHERE tenant_id=:tenant AND user_id=:user"),
            {"tenant": TENANT_A, "user": OTHER},
        )
    try:
        with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
            process = create_process(db)
            access(db)
            row = create(db, process)
            access(db, OTHER, capabilities=("ncr.read",))
            assert nonconformities.get_ncr(db, authenticated(OTHER), row.id).id == row.id
            for capability in ("ncr.manage", "ncr.review"):
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


def test_existing_ncr_can_close_after_process_archive_but_new_intake_is_blocked() -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        process = create_process(db)
        access(db)
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
        row = transition(db, row, "open")
        row = transition(db, row, "investigation")
        row = transition(db, row, "action_required")
        row = transition(db, row, "closed", closure_notes="Archived process deviation resolved.")
        assert row.state == "closed"
        with pytest.raises(HTTPException) as intake:
            create(db, process)
        assert intake.value.status_code == 409


@pytest.mark.parametrize(
    "values",
    [
        {"name": "   "},
        {"description": ""},
        {"severity": "undefined"},
        {"source_type": "unknown"},
        {"detected_date": "not-a-date"},
        {"state": "closed"},
        {"detected_by_user_id": str(OTHER)},
    ],
)
def test_ncr_input_rejects_invalid_fields_or_injected_state(values: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        nonconformities.NCRInput(
            unit_id=UNIT,
            process_id=uuid4(),
            code="NCR-INPUT",
            **{"name": "Issue", "description": "Deviation detected.", **values},
        )


def test_ncr_patch_cannot_erase_required_data() -> None:
    with pytest.raises(ValidationError):
        nonconformities.NCRPatch(expected_version=1, description=None)
    with pytest.raises(ValidationError):
        nonconformities.NCRPatch(expected_version=1)


@pytest.mark.parametrize(
    "values",
    [
        {"containment_action": "", "containment_date": datetime.now(UTC).date()},
        {"containment_action": "Withdraw outdated copy", "containment_date": None},
    ],
)
def test_completed_containment_requires_action_and_date(values: dict[str, Any]) -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        process = create_process(db)
        access(db)
        with pytest.raises((ValidationError, HTTPException)):
            create(db, process, containment_required=True, containment_completed=True, **values)

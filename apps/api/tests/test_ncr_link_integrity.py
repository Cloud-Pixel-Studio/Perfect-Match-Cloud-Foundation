from __future__ import annotations

import os
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from test_nonconformity_integrity import access
from test_nonconformity_integrity import create as create_ncr
from test_nonconformity_integrity import transition as transition_ncr
from test_process_integrity import SITE, actor
from test_process_integrity import create as create_process
from test_risk_integrity import authenticated, current, grant
from test_risk_integrity import clean_risks as clean_risks
from test_risk_integrity import create as create_risk
from test_risk_integrity import seed_risks as seed_risks
from test_risk_integrity import transition as transition_risk
from test_risk_link_integrity import DocumentTarget, control_target, document_target
from test_workflow_integrity import MEMBER, OTHER, OWNER, TENANT_A, TENANT_B, UNIT, context, engine

from pmc_api import audit_service, controls, ncr_links, risks
from pmc_api.models import QMSControlInstance, QMSNonconformity, QMSProcess, QMSRisk
from pmc_api.qms_access import revoke_grant

pytestmark = [
    pytest.mark.process_integrity,
    pytest.mark.skipif(
        "PMC_TEST_RUNTIME_DATABASE_URL" not in os.environ,
        reason="NCR links require disposable PostgreSQL",
    ),
]

KINDS = ("risk", "control", "document")
TABLES = {kind: f"qms_ncr_{kind}_links" for kind in KINDS}
TARGET_READ = {
    "risk": "risks.read",
    "control": "control_instances.read",
    "document": "documents.read",
}
TARGET_CAPABILITIES = (
    "risks.read",
    "risks.manage",
    "risks.review",
    "controls.read",
    "controls.manage",
    "control_instances.read",
    "control_instances.manage",
    "documents.read",
)
Target = QMSRisk | QMSControlInstance | DocumentTarget


def setup_ncr(db: Session) -> tuple[QMSNonconformity, QMSProcess]:
    process = create_process(db)
    access(db)
    grant(db, capabilities=TARGET_CAPABILITIES)
    return create_ncr(db, process), process


def target(db: Session, process: QMSProcess, kind: str) -> Target:
    if kind == "risk":
        return create_risk(db, process, unit_id=process.unit_id)
    if kind == "control":
        return control_target(db, process)
    return document_target(process)


def version(db: Session, row: QMSNonconformity) -> int:
    current(db)
    db.refresh(row)
    return row.row_version


def link(
    db: Session,
    row: QMSNonconformity,
    related: Target,
    kind: str,
    *,
    expected_version: int | None = None,
    user: UUID = MEMBER,
) -> Any:
    expected = version(db, row) if expected_version is None else expected_version
    current(db, user)
    if kind == "risk":
        body = ncr_links.RiskLinkInput(expected_version=expected, risk_id=related.id)
        return ncr_links.create_risk_link(db, actor(user), uuid4(), row.id, body)
    if kind == "control":
        control_body = ncr_links.ControlLinkInput(
            expected_version=expected, control_instance_id=related.id
        )
        return ncr_links.create_control_link(db, actor(user), uuid4(), row.id, control_body)
    assert isinstance(related, DocumentTarget)
    document_body = ncr_links.DocumentLinkInput(
        expected_version=expected, document_id=related.id, document_revision_id=related.revision_id
    )
    return ncr_links.create_document_link(db, actor(user), uuid4(), row.id, document_body)


def listed(
    db: Session,
    row: QMSNonconformity,
    kind: str,
    *,
    user: UUID = MEMBER,
    tenant: UUID = TENANT_A,
    limit: int = 50,
    offset: int = 0,
) -> list[Any]:
    current(db, user, tenant)
    return list(
        getattr(ncr_links, f"list_{kind}_links")(
            db, authenticated(user, tenant), row.id, limit=limit, offset=offset
        )
    )


def remove(
    db: Session,
    row: QMSNonconformity,
    item: Any,
    kind: str,
    *,
    expected_version: int | None = None,
    expected_link_version: int | None = None,
    user: UUID = MEMBER,
) -> Any:
    expected = version(db, row) if expected_version is None else expected_version
    current(db, user)
    return getattr(ncr_links, f"remove_{kind}_link")(
        db,
        actor(user),
        uuid4(),
        row.id,
        item.id,
        ncr_links.LinkRemoveInput(
            expected_version=expected,
            expected_link_version=(
                item.row_version if expected_link_version is None else expected_link_version
            ),
            reason="Replaced by a more suitable traceable reference.",
        ),
    )


def revoke(db: Session, capability: str, user: UUID = MEMBER) -> None:
    current(db, OWNER)
    grant_id = db.scalar(
        text(
            "SELECT id FROM qms_access_grants WHERE tenant_id=:tenant AND user_id=:user "
            "AND unit_id=:unit AND capability=:capability AND status='active'"
        ),
        {"tenant": TENANT_A, "user": user, "unit": UNIT, "capability": capability},
    )
    assert grant_id is not None
    revoke_grant(db, actor(OWNER, "owner"), uuid4(), grant_id)
    current(db)


@pytest.mark.parametrize("kind", KINDS)
def test_link_snapshots_and_advances_only_ncr_version(kind: str) -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        row, process = setup_ncr(db)
        related = target(db, process, kind)
        item = link(db, row, related, kind)
        assert item.nonconformity_id == row.id and item.unit_id == UNIT
        assert item.target_process_id == process.id and item.linked_target_version == 1
        assert item.status == "active" and item.row_version == 1
        assert item.ncr_row_version == 2 == version(db, row)
        assert item.created_by_user_id == MEMBER and item.created_at is not None
        if kind == "risk":
            assert isinstance(related, QMSRisk)
            assert item.snapshot_code == related.code and item.snapshot_name == related.name
            current(db)
            risks.update_risk(
                db,
                actor(),
                uuid4(),
                related.id,
                risks.RiskPatch(expected_version=1, name="Renamed risk after NCR linkage"),
            )
            assert listed(db, row, kind)[0].snapshot_name == "Incoming lot mismatch"
        elif kind == "control":
            assert isinstance(related, QMSControlInstance)
            assert item.snapshot_code == related.code and item.snapshot_name == related.name
            current(db)
            controls.update_instance(
                db,
                actor(),
                uuid4(),
                related.id,
                controls.InstancePatch(expected_version=1, name="Renamed response control"),
            )
            assert listed(db, row, kind)[0].snapshot_name == "Receiving inspection"
        else:
            assert item.snapshot_name == "Receiving procedure" and item.snapshot_revision == "A"
            assert item.file_sha256 == "a" * 64
        assert listed(db, row, kind)[0].linked_target_version == 1
        assert version(db, row) == 2


@pytest.mark.parametrize("kind", KINDS)
def test_links_allow_another_process_in_same_unit_and_target_read_only(kind: str) -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        row, process = setup_ncr(db)
        other_process = create_process(db, name="Related warehousing process")
        related = target(db, other_process, kind)
        if kind in {"risk", "control"}:
            revoke(db, "risks.manage" if kind == "risk" else "control_instances.manage")
        item = link(db, row, related, kind)
        assert item.target_process_id == other_process.id != process.id
        current(db)
        db.refresh(row)
        assert row.process_id == process.id


def test_closed_risk_is_valid_historical_context_without_reopening_it() -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        row, process = setup_ncr(db)
        related = create_risk(db, process)
        related = transition_risk(db, related, "assessed")
        related = transition_risk(db, related, "monitoring")
        related = transition_risk(db, related, "closed", closure_notes="Prior response verified.")
        previous = related.row_version
        item = link(db, row, related, "risk")
        assert item.target_state == "closed" and item.linked_target_version == previous
        current(db)
        db.refresh(related)
        assert related.state == "closed" and related.row_version == previous


@pytest.mark.parametrize("kind", KINDS)
def test_cross_unit_target_is_rejected_without_bumping_ncr(kind: str) -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        row, _ = setup_ncr(db)
        grant(
            db, unit=SITE, capabilities=("processes.read", "processes.manage", *TARGET_CAPABILITIES)
        )
        other_process = create_process(db, unit_id=SITE)
        related = target(db, other_process, kind)
        with pytest.raises(HTTPException) as denied:
            link(db, row, related, kind)
        assert denied.value.status_code in {404, 409}
        assert version(db, row) == 1


@pytest.mark.parametrize("kind", KINDS)
def test_foreign_tenant_and_missing_context_hide_relationships(kind: str) -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        row, process = setup_ncr(db)
        related = target(db, process, kind)
        item = link(db, row, related, kind)
        with engine("PMC_TEST_RUNTIME_DATABASE_URL").connect() as connection:
            assert connection.scalar(
                text(
                    "SELECT relrowsecurity AND relforcerowsecurity FROM pg_class "
                    "WHERE relname=:table"
                ),
                {"table": TABLES[kind]},
            )
            assert connection.scalar(text(f"SELECT count(*) FROM {TABLES[kind]}")) == 0  # noqa: S608
            context(connection, OTHER, TENANT_B)
            assert connection.scalar(text(f"SELECT count(*) FROM {TABLES[kind]}")) == 0  # noqa: S608
        with pytest.raises(HTTPException) as denied:
            listed(db, row, kind, user=OTHER, tenant=TENANT_B)
        assert denied.value.status_code == 404
        current(db, OTHER, TENANT_B)
        with pytest.raises(HTTPException) as denied:
            getattr(ncr_links, f"remove_{kind}_link")(
                db,
                actor(OTHER),
                uuid4(),
                row.id,
                item.id,
                ncr_links.LinkRemoveInput(
                    expected_version=2, expected_link_version=1, reason="Foreign context"
                ),
            )
        assert denied.value.status_code == 404


@pytest.mark.parametrize("kind", KINDS)
def test_target_read_revocation_hides_snapshots_and_denies_writes(kind: str) -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        row, process = setup_ncr(db)
        related = target(db, process, kind)
        item = link(db, row, related, kind)
        revoke(db, TARGET_READ[kind])
        with pytest.raises(HTTPException) as denied:
            listed(db, row, kind)
        assert denied.value.status_code == 403
        current(db)
        assert db.scalar(text(f"SELECT count(*) FROM {TABLES[kind]}")) == 0  # noqa: S608
        operations: tuple[Callable[[], object], ...] = (
            lambda: link(db, row, related, kind),
            lambda: remove(db, row, item, kind),
        )
        for operation in operations:
            with pytest.raises(HTTPException) as denied:
                operation()
            assert denied.value.status_code == 403


def test_ncr_read_is_required_even_when_manage_and_target_read_remain() -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        row, process = setup_ncr(db)
        related = target(db, process, "risk")
        item = link(db, row, related, "risk")
        revoke(db, "ncr.read")
        with pytest.raises(HTTPException) as denied:
            listed(db, row, "risk")
        assert denied.value.status_code == 403
        current(db)
        assert db.scalar(text("SELECT count(*) FROM qms_ncr_risk_links")) == 0
        with pytest.raises(HTTPException) as denied:
            remove(db, row, item, "risk")
        assert denied.value.status_code == 403


@pytest.mark.parametrize("role", ["member", "auditor"])
def test_read_only_users_and_ungranted_owner_cannot_link_or_remove(role: str) -> None:
    if role == "auditor":
        with engine("PMC_TEST_ADMIN_DATABASE_URL").begin() as connection:
            connection.execute(
                text(
                    "UPDATE memberships SET role='auditor' "
                    "WHERE tenant_id=:tenant AND user_id=:user"
                ),
                {"tenant": TENANT_A, "user": OTHER},
            )
    try:
        with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
            row, process = setup_ncr(db)
            related = target(db, process, "risk")
            item = link(db, row, related, "risk")
            grant(db, user=OTHER, capabilities=("ncr.read", "risks.read"))
            assert listed(db, row, "risk", user=OTHER)[0].id == item.id
            for operation in (
                lambda: link(db, row, related, "risk", user=OTHER),
                lambda: remove(db, row, item, "risk", user=OTHER),
                lambda: listed(db, row, "risk", user=OWNER),
            ):
                with pytest.raises(HTTPException) as denied:
                    operation()
                assert denied.value.status_code in {403, 404}
    finally:
        if role == "auditor":
            with engine("PMC_TEST_ADMIN_DATABASE_URL").begin() as connection:
                connection.execute(
                    text(
                        "UPDATE memberships SET role='member' "
                        "WHERE tenant_id=:tenant AND user_id=:user"
                    ),
                    {"tenant": TENANT_A, "user": OTHER},
                )


@pytest.mark.parametrize("kind", KINDS)
def test_duplicate_and_stale_commands_preserve_parent_and_link_history(kind: str) -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        row, process = setup_ncr(db)
        related = target(db, process, kind)
        item = link(db, row, related, kind)
        with pytest.raises(HTTPException) as denied:
            link(db, row, related, kind, expected_version=1)
        assert denied.value.status_code == 409
        with pytest.raises(HTTPException) as denied:
            link(db, row, related, kind)
        assert denied.value.status_code == 409
        with pytest.raises(HTTPException) as denied:
            remove(db, row, item, kind, expected_link_version=2)
        assert denied.value.status_code == 409
        assert version(db, row) == 2 and listed(db, row, kind)[0].status == "active"


@pytest.mark.parametrize("kind", KINDS)
def test_soft_removal_retains_history_and_hashes_private_reason(kind: str) -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        row, process = setup_ncr(db)
        related = target(db, process, kind)
        item = link(db, row, related, kind)
        removed = remove(db, row, item, kind)
        assert removed.status == "removed" and removed.row_version == 2
        assert removed.removed_by_user_id == MEMBER and removed.removed_at is not None
        assert removed.ncr_row_version == 3 == version(db, row)
        new = link(db, row, related, kind)
        assert new.id != removed.id and new.status == "active"
        assert {entry.status for entry in listed(db, row, kind)} == {"active", "removed"}
        current(db, OWNER)
        events = list(
            db.execute(
                text("SELECT action,new_values FROM audit_events WHERE resource_id=:id"),
                {"id": item.id},
            )
        )
        assert {entry.action for entry in events} == {f"ncr.{kind}_linked", f"ncr.{kind}_unlinked"}
        assert all("removal_reason_hash" in entry.new_values for entry in events)
        assert all("removal_reason" not in entry.new_values for entry in events)


@pytest.mark.parametrize("kind", KINDS)
def test_snapshots_delete_and_removed_history_are_protected_in_database(kind: str) -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        row, process = setup_ncr(db)
        item = link(db, row, target(db, process, kind), kind)
        current(db)
        with pytest.raises(DBAPIError):
            db.execute(
                text(
                    f"UPDATE {TABLES[kind]} SET "  # noqa: S608
                    "snapshot_name='Rewritten',row_version=row_version+1 WHERE id=:id"
                ),
                {"id": item.id},
            )  # noqa: S608
            db.commit()
        db.rollback()
        current(db)
        with pytest.raises(DBAPIError):
            db.execute(text(f"DELETE FROM {TABLES[kind]} WHERE id=:id"), {"id": item.id})  # noqa: S608
            db.commit()
        db.rollback()
        item = remove(db, row, item, kind)
        current(db)
        with pytest.raises(DBAPIError):
            db.execute(
                text(
                    f"UPDATE {TABLES[kind]} SET "  # noqa: S608
                    "removal_reason='Rewritten',row_version=row_version+1 WHERE id=:id"
                ),
                {"id": item.id},
            )  # noqa: S608
            db.commit()
        db.rollback()
        assert version(db, row) == 3


@pytest.mark.parametrize("terminal", ["closed", "cancelled"])
def test_terminal_ncr_blocks_new_links_and_removal_but_keeps_reads(terminal: str) -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        row, process = setup_ncr(db)
        related = target(db, process, "risk")
        item = link(db, row, related, "risk")
        version(db, row)
        if terminal == "closed":
            row = transition_ncr(db, row, "open")
            row = transition_ncr(db, row, "investigation")
            row = transition_ncr(db, row, "action_required")
            row = transition_ncr(
                db, row, "closed", closure_notes="Correction and traceable context verified."
            )
        else:
            row = transition_ncr(
                db, row, "cancelled", decision="Duplicate NCR superseded by original report."
            )
        assert listed(db, row, "risk")[0].id == item.id
        operations: tuple[Callable[[], object], ...] = (
            lambda: link(db, row, related, "risk"),
            lambda: remove(db, row, item, "risk"),
        )
        for operation in operations:
            with pytest.raises(HTTPException) as denied:
                operation()
            assert denied.value.status_code == 409


def test_archived_control_and_superseded_revision_keep_prior_links_only() -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        row, process = setup_ncr(db)
        control = control_target(db, process)
        document = document_target(process)
        control_link = link(db, row, control, "control")
        document_link = link(db, row, document, "document")
        with engine("PMC_TEST_ADMIN_DATABASE_URL").begin() as connection:
            connection.execute(
                text(
                    "UPDATE qms_control_instances SET status='archived',"
                    "row_version=row_version+1 WHERE id=:id"
                ),
                {"id": control.id},
            )
            connection.execute(
                text(
                    "UPDATE qms_document_revisions SET status='superseded',"
                    "row_version=row_version+1 WHERE id=:id"
                ),
                {"id": document.revision_id},
            )
        assert listed(db, row, "control")[0].target_state == "archived"
        assert listed(db, row, "document")[0].target_state == "superseded"
        remove(db, row, control_link, "control")
        remove(db, row, document_link, "document")
        for related, kind in ((control, "control"), (document, "document")):
            with pytest.raises(HTTPException) as denied:
                link(db, row, related, kind)
            assert denied.value.status_code in {404, 409}


@pytest.mark.parametrize(
    "document_status,revision_status,file_state",
    [
        ("draft", "active", "clean"),
        ("active", "draft", "clean"),
        ("active", "approved", "clean"),
        ("active", "under_review", "quarantined"),
        ("active", "rejected", "rejected"),
    ],
)
def test_document_references_reject_unreleased_and_unsafe_files(
    document_status: str, revision_status: str, file_state: str
) -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        row, process = setup_ncr(db)
        related = document_target(
            process,
            document_status=document_status,
            revision_status=revision_status,
            file_state=file_state,
        )
        with pytest.raises(HTTPException) as denied:
            link(db, row, related, "document")
        assert denied.value.status_code in {404, 409}
        assert version(db, row) == 1


@pytest.mark.parametrize("kind", KINDS)
def test_audit_failure_rolls_back_addition_and_removal(
    kind: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    def unavailable(*args: object, **kwargs: object) -> None:
        raise RuntimeError("NCR link audit unavailable")

    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        row, process = setup_ncr(db)
        related = target(db, process, kind)
        with monkeypatch.context() as patch:
            patch.setattr(audit_service, "record_ncr_link", unavailable)
            with pytest.raises(RuntimeError, match="NCR link audit unavailable"):
                link(db, row, related, kind)
        assert version(db, row) == 1 and listed(db, row, kind) == []
        item = link(db, row, related, kind)
        with monkeypatch.context() as patch:
            patch.setattr(audit_service, "record_ncr_link", unavailable)
            with pytest.raises(RuntimeError, match="NCR link audit unavailable"):
                remove(db, row, item, kind)
        assert version(db, row) == 2
        assert listed(db, row, kind)[0].status == "active"


def test_link_pages_are_disjoint_and_include_removed_history() -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        row, process = setup_ncr(db)
        entries = [link(db, row, target(db, process, "risk"), "risk") for _ in range(3)]
        remove(db, row, entries[0], "risk")
        first, second = listed(db, row, "risk", limit=2), listed(db, row, "risk", limit=2, offset=2)
        assert len(first) == 2 and len(second) == 1
        assert {item.id for item in first}.isdisjoint(item.id for item in second)
        assert {item.id for item in first + second} == {item.id for item in entries}
        assert {item.status for item in first + second} == {"active", "removed"}


def test_closure_serializes_with_concurrent_link_creation() -> None:
    started = Event()
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        row, process = setup_ncr(db)
        related = target(db, process, "risk")
        row = transition_ncr(db, row, "open")
        row = transition_ncr(db, row, "investigation")
        row = transition_ncr(db, row, "action_required")
        old_version, ncr_id, target_id = row.row_version, row.id, related.id
        current(db)
        db.execute(
            text("SELECT id FROM qms_nonconformities WHERE id=:id FOR UPDATE"), {"id": ncr_id}
        )

        def concurrent_link() -> int:
            with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL")) as writer:
                current(writer)
                started.set()
                try:
                    ncr_links.create_risk_link(
                        writer,
                        actor(),
                        uuid4(),
                        ncr_id,
                        ncr_links.RiskLinkInput(expected_version=old_version, risk_id=target_id),
                    )
                except HTTPException as conflict:
                    return conflict.status_code
                return 201

        with ThreadPoolExecutor(max_workers=1) as pool:
            result = pool.submit(concurrent_link)
            assert started.wait(timeout=5)
            transition_ncr(db, row, "closed", closure_notes="Correction verified before linking.")
            assert result.result(timeout=10) == 409
        assert listed(db, row, "risk") == []


@pytest.mark.parametrize("reason", ["", "   ", "x" * 501])
def test_removal_requires_bounded_nonblank_explanation(reason: str) -> None:
    with pytest.raises(ValidationError):
        ncr_links.LinkRemoveInput(expected_version=1, expected_link_version=1, reason=reason)

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import Event
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from test_process_integrity import SITE, actor
from test_process_integrity import create as create_process
from test_risk_integrity import authenticated, current, grant
from test_risk_integrity import clean_risks as clean_risks
from test_risk_integrity import create as create_risk
from test_risk_integrity import seed_risks as seed_risks
from test_risk_integrity import transition as transition_risk
from test_workflow_integrity import MEMBER, OTHER, OWNER, TENANT_A, TENANT_B, UNIT, engine

from pmc_api import audit_service, controls, risk_links
from pmc_api.models import QMSControlInstance, QMSProcess, QMSRisk
from pmc_api.qms_access import revoke_grant

pytestmark = [
    pytest.mark.process_integrity,
    pytest.mark.skipif(
        "PMC_TEST_RUNTIME_DATABASE_URL" not in os.environ,
        reason="risk links require disposable PostgreSQL",
    ),
]


@dataclass(frozen=True)
class DocumentTarget:
    id: UUID
    revision_id: UUID


def setup_risk(db: Session) -> tuple[QMSRisk, QMSProcess]:
    process = create_process(db)
    grant(db)
    grant(
        db,
        capabilities=(
            "controls.read",
            "controls.manage",
            "control_instances.read",
            "control_instances.manage",
            "documents.read",
        ),
    )
    return create_risk(db, process), process


def control_target(db: Session, process: QMSProcess, **values: Any) -> QMSControlInstance:
    current(db)
    control = controls.create_control(
        db,
        actor(),
        uuid4(),
        controls.ControlInput(
            unit_id=process.unit_id,
            process_id=process.id,
            code="CTL-" + uuid4().hex[:10],
            name="Incoming material identity",
            objective="Check receiving before release",
        ),
    )
    current(db)
    control = controls.change_control_state(db, actor(), uuid4(), control.id, 1, "active")
    current(db)
    return controls.create_instance(
        db,
        actor(),
        uuid4(),
        process.unit_id,
        process.id,
        controls.InstanceInput(
            control_id=control.id,
            code="IMP-" + uuid4().hex[:10],
            name="Receiving inspection",
            **values,
        ),
    )


def document_target(
    process: QMSProcess,
    *,
    document_status: str = "active",
    revision_status: str = "active",
    file_state: str = "clean",
) -> DocumentTarget:
    # The DB suite isolates scope/state validation from AV/S3. The runtime E2E covers
    # actual scanning, storage and independent document release separately.
    document_id, revision_id = uuid4(), uuid4()
    now = datetime.now(UTC)
    with engine("PMC_TEST_ADMIN_DATABASE_URL").begin() as connection:
        connection.execute(
            text("""
            INSERT INTO qms_documents(id,tenant_id,unit_id,process_id,code,title,document_type,
             owner_user_id,status,current_revision_id,row_version,created_by_user_id,created_at,updated_at)
            VALUES(:id,:tenant,:unit,:process,:code,'Receiving procedure','procedure',NULL,
             :status,NULL,1,:actor,:now,:now)
        """),
            {
                "id": document_id,
                "tenant": TENANT_A,
                "unit": process.unit_id,
                "process": process.id,
                "code": "D-" + uuid4().hex[:10],
                "status": document_status,
                "actor": MEMBER,
                "now": now,
            },
        )
        connection.execute(
            text("""
            INSERT INTO qms_document_revisions(id,tenant_id,document_id,revision,status,
             prepared_by_user_id,reviewed_by_user_id,approved_by_user_id,change_summary,
             revision_date,effective_date,review_date,file_state,file_object_key,file_sha256,
             file_size,file_media_type,row_version,created_at)
            VALUES(:id,:tenant,:document,'A',:status,:actor,:reviewer,:reviewer,'Initial release',
             :date,:date,NULL,:file_state,'private/synthetic-validation.pdf',:hash,100,
             'application/pdf',1,:now)
        """),
            {
                "id": revision_id,
                "tenant": TENANT_A,
                "document": document_id,
                "status": revision_status,
                "actor": MEMBER,
                "reviewer": OWNER,
                "date": now.date(),
                "file_state": file_state,
                "hash": "a" * 64,
                "now": now,
            },
        )
    return DocumentTarget(document_id, revision_id)


def version(db: Session, row: QMSRisk) -> int:
    current(db)
    db.refresh(row)
    return row.row_version


def link_control(
    db: Session, risk: QMSRisk, target: QMSControlInstance, expected_version: int | None = None
) -> risk_links.ControlLinkResponse:
    expected = version(db, risk) if expected_version is None else expected_version
    current(db)
    return risk_links.create_control_link(
        db,
        actor(),
        uuid4(),
        risk.id,
        risk_links.ControlLinkInput(expected_version=expected, control_instance_id=target.id),
    )


def link_document(
    db: Session, risk: QMSRisk, target: DocumentTarget, expected_version: int | None = None
) -> risk_links.DocumentLinkResponse:
    expected = version(db, risk) if expected_version is None else expected_version
    current(db)
    return risk_links.create_document_link(
        db,
        actor(),
        uuid4(),
        risk.id,
        risk_links.DocumentLinkInput(
            expected_version=expected,
            document_id=target.id,
            document_revision_id=target.revision_id,
        ),
    )


def test_control_link_snapshots_target_and_advances_parent_once() -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        risk, process = setup_risk(db)
        target = control_target(db, process)
        before = version(db, risk)
        link = link_control(db, risk, target)
        assert link.snapshot_code == target.code and link.snapshot_name == target.name
        assert link.target_process_id == process.id and link.linked_target_version == 1
        assert link.status == "active" and link.row_version == 1
        assert link.risk_row_version == before + 1 == version(db, risk)
        current(db)
        controls.update_instance(
            db,
            actor(),
            uuid4(),
            target.id,
            controls.InstancePatch(expected_version=1, name="Updated label"),
        )
        current(db)
        links = risk_links.list_control_links(db, authenticated(), risk.id, limit=50, offset=0)
        assert links[0].snapshot_name == "Receiving inspection"
        assert links[0].linked_target_version == 1


def test_same_unit_cross_process_link_is_allowed_without_changing_risk_scope() -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        risk, process = setup_risk(db)
        other_process = create_process(db, name="Related warehouse process")
        target = control_target(db, other_process)
        link = link_control(db, risk, target)
        assert link.target_process_id == other_process.id != process.id
        current(db)
        db.refresh(risk)
        assert risk.process_id == process.id


def test_risk_writer_needs_only_read_authority_on_target_implementation() -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        risk, process = setup_risk(db)
        target = control_target(db, process)
        current(db, OWNER)
        grant_id = db.scalar(
            text(
                "SELECT id FROM qms_access_grants WHERE tenant_id=:tenant "
                "AND user_id=:user AND capability='control_instances.manage' AND status='active'"
            ),
            {"tenant": TENANT_A, "user": MEMBER},
        )
        assert grant_id is not None
        revoke_grant(db, actor(OWNER, "owner"), uuid4(), grant_id)
        assert link_control(db, risk, target).control_instance_id == target.id


def test_closure_serializes_with_concurrent_link_creation() -> None:
    started = Event()
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        risk, process = setup_risk(db)
        target = control_target(db, process)
        risk = transition_risk(db, risk, "assessed")
        risk = transition_risk(db, risk, "monitoring")
        old_version, risk_id, target_id = risk.row_version, risk.id, target.id
        current(db)
        db.execute(text("SELECT id FROM qms_risks WHERE id=:id FOR UPDATE"), {"id": risk_id})

        def concurrent_link() -> int:
            with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL")) as writer:
                current(writer)
                started.set()
                try:
                    risk_links.create_control_link(
                        writer,
                        actor(),
                        uuid4(),
                        risk_id,
                        risk_links.ControlLinkInput(
                            expected_version=old_version, control_instance_id=target_id
                        ),
                    )
                except HTTPException as conflict:
                    return conflict.status_code
                return 201

        with ThreadPoolExecutor(max_workers=1) as pool:
            result = pool.submit(concurrent_link)
            assert started.wait(timeout=5)
            transition_risk(db, risk, "closed", closure_notes="Exposure resolved before linking.")
            assert result.result(timeout=10) == 409
        current(db)
        assert (
            db.scalar(
                text("SELECT count(*) FROM qms_risk_control_links WHERE risk_id=:id"),
                {"id": risk_id},
            )
            == 0
        )


def test_document_link_snapshots_released_revision_and_preserves_historical_reference() -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        risk, process = setup_risk(db)
        target = document_target(process)
        link = link_document(db, risk, target)
        assert link.snapshot_name == "Receiving procedure" and link.snapshot_revision == "A"
        assert link.file_sha256 == "a" * 64 and link.linked_target_version == 1
        with engine("PMC_TEST_ADMIN_DATABASE_URL").begin() as connection:
            connection.execute(
                text(
                    "UPDATE qms_document_revisions SET status='superseded',"
                    "row_version=row_version+1 WHERE id=:id"
                ),
                {"id": target.revision_id},
            )
        current(db)
        links = risk_links.list_document_links(db, authenticated(), risk.id, limit=50, offset=0)
        assert len(links) == 1 and links[0].snapshot_revision == "A"
        assert links[0].target_state == "superseded"


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
def test_document_link_rejects_unreleased_or_unsafe_revision(
    document_status: str, revision_status: str, file_state: str
) -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        risk, process = setup_risk(db)
        target = document_target(
            process,
            document_status=document_status,
            revision_status=revision_status,
            file_state=file_state,
        )
        with pytest.raises(HTTPException) as rejected:
            link_document(db, risk, target)
        assert rejected.value.status_code in {404, 409}
        assert version(db, risk) == 1


def test_duplicate_active_link_and_stale_parent_version_are_rejected() -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        risk, process = setup_risk(db)
        first, second = control_target(db, process), control_target(db, process)
        link_control(db, risk, first)
        with pytest.raises(HTTPException) as stale:
            link_control(db, risk, second, expected_version=1)
        assert stale.value.status_code == 409
        with pytest.raises(HTTPException) as duplicate:
            link_control(db, risk, first)
        assert duplicate.value.status_code == 409
        assert version(db, risk) == 2


def test_soft_removal_retains_history_hashes_reason_and_allows_new_link() -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        risk, process = setup_risk(db)
        target = control_target(db, process)
        link = link_control(db, risk, target)
        current(db)
        removed = risk_links.remove_control_link(
            db,
            actor(),
            uuid4(),
            risk.id,
            link.id,
            risk_links.LinkRemoveInput(
                expected_version=link.risk_row_version,
                expected_link_version=link.row_version,
                reason="Replaced by a more suitable response control.",
            ),
        )
        assert removed.status == "removed" and removed.row_version == 2
        assert removed.removed_by_user_id == MEMBER and removed.removed_at is not None
        assert removed.risk_row_version == 3 == version(db, risk)
        new = link_control(db, risk, target)
        assert new.id != removed.id and new.status == "active"
        current(db, OWNER)
        events = list(
            db.execute(
                text("SELECT action,new_values FROM audit_events WHERE resource_id=:id"),
                {"id": removed.id},
            )
        )
        assert {row.action for row in events} == {"risk.control_linked", "risk.control_unlinked"}
        assert "removal_reason_hash" in str(events)
        assert "Replaced by a more suitable" not in str(events)


def test_removed_link_and_snapshot_cannot_be_rewritten_directly() -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        risk, process = setup_risk(db)
        link = link_control(db, risk, control_target(db, process))
        current(db)
        with pytest.raises(DBAPIError):
            db.execute(
                text(
                    "UPDATE qms_risk_control_links SET snapshot_name='Changed',"
                    "row_version=row_version+1 WHERE id=:id"
                ),
                {"id": link.id},
            )
            db.commit()
        db.rollback()
        current(db)
        removed = risk_links.remove_control_link(
            db,
            actor(),
            uuid4(),
            risk.id,
            link.id,
            risk_links.LinkRemoveInput(
                expected_version=version(db, risk),
                expected_link_version=1,
                reason="Response superseded.",
            ),
        )
        current(db)
        with pytest.raises(DBAPIError):
            db.execute(
                text(
                    "UPDATE qms_risk_control_links SET removal_reason='Replacement',"
                    "row_version=row_version+1 WHERE id=:id"
                ),
                {"id": removed.id},
            )
            db.commit()
        db.rollback()


def test_closed_risk_blocks_link_and_removal() -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        risk, process = setup_risk(db)
        target = control_target(db, process)
        link = link_control(db, risk, target)
        version(db, risk)
        risk = transition_risk(db, risk, "assessed")
        risk = transition_risk(db, risk, "monitoring")
        risk = transition_risk(db, risk, "closed", closure_notes="Risk resolved.")
        with pytest.raises(HTTPException) as closed:
            link_control(db, risk, target)
        assert closed.value.status_code == 409
        current(db)
        with pytest.raises(HTTPException) as immutable:
            risk_links.remove_control_link(
                db,
                actor(),
                uuid4(),
                risk.id,
                link.id,
                risk_links.LinkRemoveInput(
                    expected_version=risk.row_version,
                    expected_link_version=1,
                    reason="Cannot rewrite closed risk.",
                ),
            )
        assert immutable.value.status_code == 409


def test_target_read_revocation_hides_link_data_and_blocks_new_links() -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        risk, process = setup_risk(db)
        target = control_target(db, process)
        link = link_control(db, risk, target)
        current(db, OWNER)
        target_grant = db.scalar(
            select(text("id"))
            .select_from(text("qms_access_grants"))
            .where(
                text(
                    "tenant_id=:tenant AND user_id=:user AND unit_id=:unit "
                    "AND capability='control_instances.read' AND status='active'"
                )
            ),
            {"tenant": TENANT_A, "user": MEMBER, "unit": UNIT},
        )
        assert target_grant is not None
        revoke_grant(db, actor(OWNER, "owner"), uuid4(), target_grant)
        current(db)
        with pytest.raises(HTTPException) as denied:
            risk_links.list_control_links(db, authenticated(), risk.id, limit=50, offset=0)
        assert denied.value.status_code == 403
        current(db)
        assert (
            db.scalar(
                text("SELECT count(*) FROM qms_risk_control_links WHERE id=:id"), {"id": link.id}
            )
            == 0
        )
        with pytest.raises(HTTPException) as denied:
            link_control(db, risk, target)
        assert denied.value.status_code == 403


def test_cross_unit_control_reference_is_rejected() -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        risk, _ = setup_risk(db)
        grant(
            db,
            unit=SITE,
            capabilities=(
                "processes.manage",
                "processes.read",
                "controls.read",
                "controls.manage",
                "control_instances.read",
                "control_instances.manage",
            ),
        )
        other_process = create_process(db, unit_id=SITE)
        target = control_target(db, other_process)
        with pytest.raises(HTTPException) as rejected:
            link_control(db, risk, target)
        assert rejected.value.status_code in {404, 409}
        assert version(db, risk) == 1


def test_foreign_tenant_context_cannot_read_or_mutate_link() -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        risk, process = setup_risk(db)
        link = link_control(db, risk, control_target(db, process))
        current(db, OTHER, TENANT_B)
        assert (
            db.scalar(
                text("SELECT count(*) FROM qms_risk_control_links WHERE id=:id"), {"id": link.id}
            )
            == 0
        )
        with pytest.raises(HTTPException) as denied:
            risk_links.list_control_links(
                db, authenticated(OTHER, tenant=TENANT_B), risk.id, limit=50, offset=0
            )
        assert denied.value.status_code == 404


def test_audit_failure_rolls_back_link_and_parent_version(monkeypatch: pytest.MonkeyPatch) -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        risk, process = setup_risk(db)
        target = control_target(db, process)

        def failed(*args: object, **kwargs: object) -> None:
            raise RuntimeError("audit unavailable")

        monkeypatch.setattr(audit_service, "record_risk_link", failed)
        with pytest.raises(RuntimeError, match="audit unavailable"):
            link_control(db, risk, target)
        assert version(db, risk) == 1
        current(db)
        assert (
            db.scalar(
                text("SELECT count(*) FROM qms_risk_control_links WHERE risk_id=:id"),
                {"id": risk.id},
            )
            == 0
        )


def test_control_candidate_search_is_literal_and_pages_are_disjoint() -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        _, process = setup_risk(db)
        targets = [control_target(db, process) for _ in range(3)]
        current(db)
        controls.update_instance(
            db,
            actor(),
            uuid4(),
            targets[0].id,
            controls.InstancePatch(expected_version=1, name="Literal_% marker"),
        )
        current(db)
        literal = controls.list_instances(
            db, authenticated(), UNIT, process_id=None, search="_%", limit=50, offset=0
        )
        assert [row.id for row in literal] == [targets[0].id]
        current(db)
        first = controls.list_instances(
            db, authenticated(), UNIT, process_id=None, search=None, limit=2, offset=0
        )
        current(db)
        second = controls.list_instances(
            db, authenticated(), UNIT, process_id=None, search=None, limit=2, offset=2
        )
        assert len(first) == 2 and len(second) == 1
        assert {row.id for row in first}.isdisjoint(row.id for row in second)


@pytest.mark.parametrize("reason", ["", "   "])
def test_link_removal_requires_nonblank_reason(reason: str) -> None:
    with pytest.raises(ValidationError):
        risk_links.LinkRemoveInput(expected_version=1, expected_link_version=1, reason=reason)

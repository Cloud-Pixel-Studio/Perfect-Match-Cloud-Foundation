"""CAPA direct trace links preserve scoped control and evidence snapshots."""

from __future__ import annotations

import os
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from test_capa_intake_integrity import access, intake, request
from test_ncr_evidence_link_integrity import reviewed_evidence
from test_process_integrity import actor, reset_process_records
from test_process_integrity import create as create_process
from test_risk_integrity import authenticated, current, grant
from test_risk_integrity import seed_risks as seed_risks
from test_risk_link_integrity import control_target
from test_workflow_integrity import OTHER, OWNER, engine

from pmc_api import capa_trace_links, control_instance_evidence
from pmc_api.models import (
    QMSCAPA,
    QMSAccessGrant,
    QMSCAPAControlLink,
    QMSCAPAEvidenceLink,
    QMSProcess,
)
from pmc_api.qms_access import revoke_grant

pytestmark = [
    pytest.mark.process_integrity,
    pytest.mark.skipif(
        "PMC_TEST_RUNTIME_DATABASE_URL" not in os.environ,
        reason="requires disposable PostgreSQL",
    ),
]


@pytest.fixture(autouse=True)
def clean(seed_risks: None) -> None:
    reset_process_records()


def setup(db: Session) -> tuple[QMSCAPA, QMSProcess]:
    process = create_process(db)
    access(db)
    grant(
        db,
        capabilities=(
            "controls.read",
            "controls.manage",
            "control_instances.read",
            "control_instances.manage",
        ),
    )
    return intake(db, process.id), process


def version(db: Session, row: QMSCAPA) -> int:
    current(db)
    db.refresh(row)
    return row.row_version


def test_capa_control_link_snapshot_removal_and_audit() -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        capa, process = setup(db)
        target = control_target(db, process)
        current(db)
        linked = capa_trace_links.add_control_link(
            request(),
            capa.id,
            capa_trace_links.CAPAControlLinkInput(
                expected_version=version(db, capa), control_instance_id=target.id
            ),
            db,
            authenticated(),
        )
        assert linked.snapshot_code == target.code and linked.snapshot_name == target.name
        assert linked.linked_target_version == target.row_version
        assert linked.status == "active" and linked.capa_row_version == 2
        current(db)
        listed = capa_trace_links.list_control_links(capa.id, db, authenticated())
        assert len(listed) == 1 and listed[0].id == linked.id
        with pytest.raises(DBAPIError):
            db.execute(
                text("UPDATE qms_capa_control_links SET snapshot_name='tampered' WHERE id=:id"),
                {"id": linked.id},
            )
            db.flush()
        db.rollback()
        current(db)
        removed = capa_trace_links.remove_control_link(
            request(),
            capa.id,
            linked.id,
            capa_trace_links.CAPATraceLinkRemove(
                expected_version=version(db, capa),
                expected_link_version=1,
                reason="Replaced by a verified implementation.",
            ),
            db,
            authenticated(),
        )
        assert removed.status == "removed" and removed.row_version == 2
        assert removed.snapshot_name == linked.snapshot_name and removed.capa_row_version == 3
        current(db, OWNER)
        events = db.execute(
            text("SELECT action,new_values FROM audit_events WHERE resource_id=:id"),
            {"id": linked.id},
        ).all()
        assert {event.action for event in events} == {
            "capa.control_linked",
            "capa.control_unlinked",
        }
        assert all("removal_reason_hash" in event.new_values for event in events)


def test_capa_evidence_link_requires_independent_acceptance() -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        capa, process = setup(db)
        evidence = reviewed_evidence(db, process.id, process.unit_id)
        current(db)
        with pytest.raises(HTTPException) as draft:
            capa_trace_links.add_evidence_link(
                request(),
                capa.id,
                capa_trace_links.CAPAEvidenceLinkInput(
                    expected_version=version(db, capa), evidence_id=evidence.id
                ),
                db,
                authenticated(),
            )
        assert draft.value.status_code == 409
        db.rollback()
        current(db)
        evidence = control_instance_evidence.update_evidence(
            request(),
            evidence.id,
            control_instance_evidence.EvidencePatch(
                expected_version=evidence.row_version,
                evidence_summary="Receiving evidence reviewed for CAPA effectiveness.",
            ),
            db,
            authenticated(),
        )
        current(db)
        evidence = control_instance_evidence.submit_evidence(
            request(),
            evidence.id,
            control_instance_evidence.EvidenceCommand(expected_version=evidence.row_version),
            db,
            authenticated(),
        )
        grant(db, user=OTHER, capabilities=("control_instances.read", "control_instances.manage"))
        current(db, OTHER)
        evidence = control_instance_evidence.review_evidence(
            request(),
            evidence.id,
            control_instance_evidence.ReviewCommand(
                expected_version=evidence.row_version,
                target_status="accepted",
                decision="Independent reviewer accepted the evidence.",
            ),
            db,
            authenticated(OTHER),
        )
        current(db)
        linked = capa_trace_links.add_evidence_link(
            request(),
            capa.id,
            capa_trace_links.CAPAEvidenceLinkInput(
                expected_version=version(db, capa), evidence_id=evidence.id
            ),
            db,
            authenticated(),
        )
        assert linked.target_state == "accepted"
        assert linked.control_instance_id == evidence.control_instance_id
        assert linked.snapshot_name == evidence.name and linked.capa_row_version == 2
        current(db)
        assert (
            db.scalar(select(QMSCAPAEvidenceLink).where(QMSCAPAEvidenceLink.id == linked.id))
            is not None
        )


def test_direct_sql_cannot_bypass_controlled_capa_link_command() -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        capa, process = setup(db)
        target = control_target(db, process)
        current(db)
        with pytest.raises(DBAPIError):
            db.execute(
                text(
                    "INSERT INTO qms_capa_control_links"
                    "(id,tenant_id,unit_id,capa_id,control_instance_id,target_process_id,"
                    "snapshot_code,snapshot_name,linked_target_version,status,row_version,"
                    "created_by_user_id,created_at,removal_reason) VALUES"
                    "(:id,:tenant,:unit,:capa,:target,:process,'x','x',1,'active',1,:actor,now(),'')"
                ),
                {
                    "id": uuid4(),
                    "tenant": capa.tenant_id,
                    "unit": capa.unit_id,
                    "capa": capa.id,
                    "target": target.id,
                    "process": process.id,
                    "actor": capa.created_by_user_id,
                },
            )
            db.flush()
        db.rollback()
        current(db)
        assert (
            db.scalar(select(QMSCAPAControlLink).where(QMSCAPAControlLink.capa_id == capa.id))
            is None
        )


def test_control_link_rejects_duplicate_foreign_target_and_revoked_read() -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        capa, process = setup(db)
        target = control_target(db, process)
        current(db)
        linked = capa_trace_links.add_control_link(
            request(),
            capa.id,
            capa_trace_links.CAPAControlLinkInput(
                expected_version=version(db, capa), control_instance_id=target.id
            ),
            db,
            authenticated(),
        )
        current(db)
        with pytest.raises(HTTPException) as duplicate:
            capa_trace_links.add_control_link(
                request(),
                capa.id,
                capa_trace_links.CAPAControlLinkInput(
                    expected_version=version(db, capa), control_instance_id=target.id
                ),
                db,
                authenticated(),
            )
        assert duplicate.value.status_code == 409
        current(db)
        with pytest.raises(HTTPException) as foreign_target:
            capa_trace_links.add_control_link(
                request(),
                capa.id,
                capa_trace_links.CAPAControlLinkInput(
                    expected_version=version(db, capa), control_instance_id=uuid4()
                ),
                db,
                authenticated(),
            )
        assert foreign_target.value.status_code == 409
        current(db)
        control_read = db.scalar(
            select(QMSAccessGrant).where(
                QMSAccessGrant.user_id == capa.created_by_user_id,
                QMSAccessGrant.unit_id == capa.unit_id,
                QMSAccessGrant.capability == "control_instances.read",
                QMSAccessGrant.status == "active",
            )
        )
        assert control_read is not None
        current(db, OWNER)
        revoke_grant(db, actor(OWNER, "owner"), uuid4(), control_read.id)
        current(db)
        with pytest.raises(HTTPException) as revoked:
            capa_trace_links.list_control_links(capa.id, db, authenticated())
        assert revoked.value.status_code == 403
        assert linked.id is not None


def test_trace_links_lock_when_effectiveness_review_begins(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        capa, process = setup(db)
        target = control_target(db, process)
        db.expunge(capa)
        capa.state = "effectiveness_review"
        monkeypatch.setattr(capa_trace_links, "_row", lambda *_args, **_kwargs: capa)
        current(db)
        with pytest.raises(HTTPException) as locked:
            capa_trace_links.add_control_link(
                request(),
                capa.id,
                capa_trace_links.CAPAControlLinkInput(
                    expected_version=capa.row_version, control_instance_id=target.id
                ),
                db,
                authenticated(),
            )
        assert locked.value.status_code == 409
        db.rollback()

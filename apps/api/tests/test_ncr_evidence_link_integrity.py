"""Accepted evidence can be cited by an NCR without losing review provenance."""

from __future__ import annotations

import os
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException, Request
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from test_ncr_link_integrity import setup_ncr, version
from test_process_integrity import actor
from test_risk_integrity import authenticated, current, grant
from test_risk_integrity import clean_risks as clean_risks
from test_risk_integrity import seed_risks as seed_risks
from test_workflow_integrity import MEMBER, OTHER, OWNER, engine

from pmc_api import control_definitions, control_instance_evidence, controls, ncr_links
from pmc_api.models import QMSControlInstanceEvidence
from pmc_api.qms_access import revoke_grant

pytestmark = [
    pytest.mark.process_integrity,
    pytest.mark.skipif(
        "PMC_TEST_RUNTIME_DATABASE_URL" not in os.environ,
        reason="requires disposable PostgreSQL",
    ),
]


def request() -> Request:
    return cast(Request, SimpleNamespace(state=SimpleNamespace(request_id=uuid4())))


def reviewed_evidence(db: Session, process_id: UUID, unit_id: UUID) -> QMSControlInstanceEvidence:
    current(db)
    control = controls.create_control(
        db,
        actor(),
        uuid4(),
        controls.ControlInput(
            unit_id=unit_id,
            process_id=process_id,
            code="EVID-" + uuid4().hex[:8],
            name="Review incoming materials",
            objective="Confirm traceable evidence",
        ),
    )
    control_definitions.create_evidence_requirement(
        control.id,
        request(),
        control_definitions.EvidenceRequirementInput(
            name="Reviewed receiving record", evidence_type="record"
        ),
        db,
        authenticated(),
    )
    current(db)
    controls.change_control_state(db, actor(), uuid4(), control.id, control.row_version, "active")
    current(db)
    instance = controls.create_instance(
        db,
        actor(),
        uuid4(),
        unit_id,
        process_id,
        controls.InstanceInput(
            control_id=control.id, code="IMPL-" + uuid4().hex[:8], name="Receiving implementation"
        ),
    )
    current(db)
    row = db.scalar(
        select(QMSControlInstanceEvidence).where(
            QMSControlInstanceEvidence.control_instance_id == instance.id
        )
    )
    assert row is not None and row.status == "draft"
    return row


def test_ncr_evidence_link_requires_independent_acceptance_and_preserves_history() -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        ncr, process = setup_ncr(db)
        evidence = reviewed_evidence(db, process.id, process.unit_id)
        current(db)
        with pytest.raises(HTTPException):
            ncr_links.create_evidence_link(
                db,
                actor(),
                uuid4(),
                ncr.id,
                ncr_links.EvidenceLinkInput(
                    expected_version=version(db, ncr), evidence_id=evidence.id
                ),
            )
        db.rollback()
        current(db)
        evidence = control_instance_evidence.update_evidence(
            request(),
            evidence.id,
            control_instance_evidence.EvidencePatch(
                expected_version=evidence.row_version,
                evidence_summary="Synthetic reviewed receiving outcome.",
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
                decision="Independent synthetic review accepted.",
            ),
            db,
            authenticated(OTHER),
        )
        assert evidence.status == "accepted" and evidence.reviewed_by_user_id == OTHER
        current(db)
        linked = ncr_links.create_evidence_link(
            db,
            actor(),
            uuid4(),
            ncr.id,
            ncr_links.EvidenceLinkInput(expected_version=version(db, ncr), evidence_id=evidence.id),
        )
        assert linked.status == "active" and linked.target_state == "accepted"
        assert linked.snapshot_name == "Reviewed receiving record"
        assert linked.control_instance_id == evidence.control_instance_id
        assert linked.ncr_row_version == version(db, ncr)
        current(db)
        listed = ncr_links.list_evidence_links(db, authenticated(), ncr.id, limit=50, offset=0)
        assert len(listed) == 1 and listed[0].id == linked.id
        with pytest.raises(DBAPIError):
            db.execute(
                text(
                    "UPDATE qms_ncr_evidence_links SET snapshot_name='tampered',"
                    "row_version=2 WHERE id=:id"
                ),
                {"id": linked.id},
            )
            db.flush()
        db.rollback()
        current(db)
        removed = ncr_links.remove_evidence_link(
            db,
            actor(),
            uuid4(),
            ncr.id,
            linked.id,
            ncr_links.LinkRemoveInput(
                expected_version=version(db, ncr),
                expected_link_version=1,
                reason="Replace synthetic evidence reference.",
            ),
        )
        assert removed.status == "removed" and removed.snapshot_name == linked.snapshot_name
        current(db, OWNER)
        audit = list(
            db.execute(
                text("SELECT action,new_values FROM audit_events WHERE resource_id=:id"),
                {"id": linked.id},
            )
        )
        assert {r.action for r in audit} == {"ncr.evidence_linked", "ncr.evidence_unlinked"}
        assert all(
            "removal_reason_hash" in r.new_values and "removal_reason" not in r.new_values
            for r in audit
        )


def test_ncr_evidence_target_read_revocation_blocks_history() -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        ncr, process = setup_ncr(db)
        evidence = reviewed_evidence(db, process.id, process.unit_id)
        # A draft cannot be linked, even when the actor manages the NCR and implementation.
        current(db)
        with pytest.raises(HTTPException):
            ncr_links.create_evidence_link(
                db,
                actor(),
                uuid4(),
                ncr.id,
                ncr_links.EvidenceLinkInput(
                    expected_version=version(db, ncr), evidence_id=evidence.id
                ),
            )
        db.rollback()
        current(db, OWNER)
        grant_id = db.scalar(
            text(
                "SELECT id FROM qms_access_grants WHERE user_id=:user "
                "AND capability='control_instances.read' AND status='active'"
            ),
            {"user": MEMBER},
        )
        assert grant_id is not None
        revoke_grant(db, actor(OWNER, "owner"), uuid4(), grant_id)
        current(db)
        with pytest.raises(HTTPException) as error:
            ncr_links.list_evidence_links(db, authenticated(), ncr.id, limit=50, offset=0)
        assert error.value.status_code in {403, 404}

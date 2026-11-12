"""CAPA document citations retain released snapshots and enforced authority."""

from __future__ import annotations

import os
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from test_capa_intake_integrity import access, intake, request
from test_process_integrity import actor, reset_process_records
from test_process_integrity import create as create_process
from test_risk_integrity import authenticated, current, grant
from test_risk_integrity import seed_risks as seed_risks
from test_risk_link_integrity import document_target
from test_workflow_integrity import OWNER, engine

from pmc_api import capa_links
from pmc_api.models import QMSCAPA, QMSAccessGrant, QMSCAPADocumentLink, QMSProcess
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
    grant(db, capabilities=("documents.read",))
    row = intake(db, process.id)
    return row, process


def test_capa_document_link_snapshot_version_removal_and_audit() -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        row, process = setup(db)
        target = document_target(process)
        current(db)
        linked = capa_links.add_document_link(
            request(),
            row.id,
            capa_links.CAPADocumentLinkInput(
                expected_version=row.row_version,
                document_id=target.id,
                document_revision_id=target.revision_id,
            ),
            db,
            authenticated(),
        )
        assert linked.status == "active" and linked.snapshot_revision == "A"
        assert linked.file_sha256 == "a" * 64 and linked.capa_row_version == 2
        current(db)
        assert [
            item.id for item in capa_links.list_document_links(row.id, db, authenticated())
        ] == [linked.id]
        with pytest.raises(DBAPIError):
            db.execute(
                text("UPDATE qms_capa_document_links SET snapshot_name='tampered' WHERE id=:id"),
                {"id": linked.id},
            )
            db.flush()
        db.rollback()
        current(db)
        with pytest.raises(HTTPException) as stale:
            capa_links.add_document_link(
                request(),
                row.id,
                capa_links.CAPADocumentLinkInput(
                    expected_version=1,
                    document_id=target.id,
                    document_revision_id=target.revision_id,
                ),
                db,
                authenticated(),
            )
        assert stale.value.status_code == 409
        db.rollback()
        current(db)
        removed = capa_links.remove_document_link(
            request(),
            row.id,
            linked.id,
            capa_links.CAPADocumentLinkRemove(
                expected_version=2,
                expected_link_version=1,
                reason="Superseded by the next released procedure.",
            ),
            db,
            authenticated(),
        )
        assert removed.status == "removed" and removed.row_version == 2
        assert removed.capa_row_version == 3 and removed.snapshot_name == linked.snapshot_name
        current(db, OWNER)
        audit = db.execute(
            text("SELECT action,new_values FROM audit_events WHERE resource_id=:id"),
            {"id": linked.id},
        ).all()
        assert {item.action for item in audit} == {
            "capa.document_linked",
            "capa.document_unlinked",
        }
        assert all(
            "removal_reason_hash" in item.new_values and "removal_reason" not in item.new_values
            for item in audit
        )


@pytest.mark.parametrize(
    "revision_status,file_state",
    [
        ("draft", "clean"),
        ("under_review", "quarantined"),
    ],
)
def test_capa_document_link_rejects_unreleased_or_unsafe_revision(
    revision_status: str,
    file_state: str,
) -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        row, process = setup(db)
        target = document_target(process, revision_status=revision_status, file_state=file_state)
        current(db)
        with pytest.raises(HTTPException) as rejected:
            capa_links.add_document_link(
                request(),
                row.id,
                capa_links.CAPADocumentLinkInput(
                    expected_version=1,
                    document_id=target.id,
                    document_revision_id=target.revision_id,
                ),
                db,
                authenticated(),
            )
        assert rejected.value.status_code == 409
        current(db)
        assert (
            db.scalar(select(QMSCAPADocumentLink).where(QMSCAPADocumentLink.capa_id == row.id))
            is None
        )


def test_document_read_revocation_hides_capa_link() -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        row, process = setup(db)
        target = document_target(process)
        current(db)
        linked = capa_links.add_document_link(
            request(),
            row.id,
            capa_links.CAPADocumentLinkInput(
                expected_version=1,
                document_id=target.id,
                document_revision_id=target.revision_id,
            ),
            db,
            authenticated(),
        )
        current(db)
        current(db, OWNER)
        grants = db.scalars(
            select(QMSAccessGrant).where(QMSAccessGrant.capability == "documents.read")
        ).all()
        for item in grants:
            revoke_grant(db, actor(OWNER, "owner"), uuid4(), item.id)
        current(db)
        assert (
            db.scalar(select(QMSCAPADocumentLink).where(QMSCAPADocumentLink.id == linked.id))
            is None
        )

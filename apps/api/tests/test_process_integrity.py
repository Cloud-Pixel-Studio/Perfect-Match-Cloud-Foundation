# ruff: noqa: E501
from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException, Request
from pydantic import ValidationError
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from test_workflow_integrity import MEMBER, OTHER, OWNER, TENANT_A, TENANT_B, UNIT, context, engine

from pmc_api import audit_service
from pmc_api import documents as document_service
from pmc_api.auth import AuthenticatedSession
from pmc_api.control_definitions import (
    ActivityInput,
    ActivityPatch,
    EvidenceRequirementInput,
    EvidenceRequirementPatch,
    create_activity,
    create_evidence_requirement,
    update_activity,
    update_evidence_requirement,
)
from pmc_api.control_instance_activities import (
    ActivityTransition,
    transition_activity,
)
from pmc_api.control_instance_evidence import (
    EvidenceCommand,
    EvidencePatch,
    ReviewCommand,
    review_evidence,
    submit_evidence,
    update_evidence,
)
from pmc_api.controls import (
    ControlInput,
    InstanceInput,
    TransitionInput,
    change_control_state,
    create_control,
    create_instance,
    get_control,
    get_instance,
    transition_instance,
)
from pmc_api.database import set_request_context
from pmc_api.models import (
    AuditEvent,
    QMSControlEvidenceRequirement,
    QMSControlInstance,
    QMSControlInstanceActivity,
    QMSControlInstanceEvidence,
    QMSDocument,
    QMSProcess,
)
from pmc_api.organization_service import OrganizationActor
from pmc_api.processes import (
    ProcessInput,
    ProcessPatch,
    VersionCommand,
    change_status,
    create_process,
    update_process,
)
from pmc_api.qms_access import GrantInput, create_grant, revoke_grant

pytestmark = [
    pytest.mark.process_integrity,
    pytest.mark.skipif(
        "PMC_TEST_RUNTIME_DATABASE_URL" not in os.environ,
        reason="process suite requires disposable PostgreSQL",
    ),
]
SITE = uuid4()
FOREIGN_SITE = uuid4()


@pytest.fixture(scope="module", autouse=True)
def seed_identity() -> None:
    seed_process_identity()


def seed_process_identity() -> None:
    now = datetime.now(UTC)
    with engine("PMC_TEST_ADMIN_DATABASE_URL").begin() as connection:
        connection.execute(
            text(
                "TRUNCATE qms_capa_control_links, qms_capa_evidence_links, qms_capa_document_links, qms_capa_effectiveness_reviews, qms_capa_actions, qms_capas, qms_ncr_evidence_links, qms_ncr_risk_links, qms_ncr_control_links, qms_ncr_document_links, qms_nonconformities, qms_risks, qms_document_revisions, qms_documents, qms_control_instances, qms_controls, qms_processes, qms_process_dependency_projection, qms_access_grants, workflow_instance_events, workflow_instances, workflow_step_assignments, workflow_transitions, workflow_steps, workflow_versions, workflow_definitions CASCADE"
            )
        )
        connection.execute(
            text("DELETE FROM organization_unit_assignments WHERE tenant_id IN (:a,:b)"),
            {"a": TENANT_A, "b": TENANT_B},
        )
        connection.execute(
            text("DELETE FROM memberships WHERE tenant_id IN (:a,:b)"),
            {"a": TENANT_A, "b": TENANT_B},
        )
        connection.execute(
            text("DELETE FROM users WHERE id IN (:owner,:member,:other)"),
            {"owner": OWNER, "member": MEMBER, "other": OTHER},
        )
        connection.execute(
            text("DELETE FROM tenants WHERE id IN (:a,:b)"), {"a": TENANT_A, "b": TENANT_B}
        )
        for tenant in (TENANT_A, TENANT_B):
            connection.execute(
                text(
                    "INSERT INTO tenants (id,name,slug,status,created_at,updated_at) VALUES (:id,:name,:slug,'active',:now,:now)"
                ),
                {"id": tenant, "name": f"Tenant {tenant}", "slug": str(tenant), "now": now},
            )
        for user in (OWNER, MEMBER, OTHER):
            connection.execute(
                text(
                    "INSERT INTO users (id,display_name,status,created_at) VALUES (:id,:name,'active',:now)"
                ),
                {"id": user, "name": str(user), "now": now},
            )
        for user, role in ((OWNER, "owner"), (MEMBER, "member"), (OTHER, "member")):
            connection.execute(
                text(
                    "INSERT INTO memberships (id,tenant_id,user_id,role,status,created_at) VALUES (:id,:tenant,:user,:role,'active',:now)"
                ),
                {"id": uuid4(), "tenant": TENANT_A, "user": user, "role": role, "now": now},
            )
        connection.execute(
            text(
                "INSERT INTO memberships (id,tenant_id,user_id,role,status,created_at) VALUES (:id,:tenant,:user,'member','active',:now)"
            ),
            {"id": uuid4(), "tenant": TENANT_B, "user": OTHER, "now": now},
        )
        connection.execute(
            text(
                "INSERT INTO organization_units (id,tenant_id,unit_type,code,name,status,created_at,updated_at) VALUES (:id,:tenant,'team','WF','Workflow team','active',:now,:now)"
            ),
            {"id": UNIT, "tenant": TENANT_A, "now": now},
        )
        for site_id, tenant_id, code in (
            (SITE, TENANT_A, "SITE-A"),
            (FOREIGN_SITE, TENANT_B, "SITE-B"),
        ):
            connection.execute(
                text(
                    "INSERT INTO organization_units (id,tenant_id,unit_type,code,name,status,created_at,updated_at) VALUES (:id,:tenant,'site',:code,:name,'active',:now,:now)"
                ),
                {"id": site_id, "tenant": tenant_id, "code": code, "name": code, "now": now},
            )
        connection.execute(
            text(
                "INSERT INTO organization_unit_assignments (id,tenant_id,unit_id,user_id,assignment_role,is_primary,status,created_at,updated_at) VALUES (:id,:tenant,:unit,:user,'member',true,'active',:now,:now)"
            ),
            {"id": uuid4(), "tenant": TENANT_A, "unit": UNIT, "user": MEMBER, "now": now},
        )


def actor(user: UUID = MEMBER, role: str = "member") -> OrganizationActor:
    return OrganizationActor(user, str(user), role, TENANT_A)


@pytest.fixture(autouse=True)
def clean_processes(seed_identity: None) -> None:
    reset_process_records()


def reset_process_records() -> None:
    with engine("PMC_TEST_ADMIN_DATABASE_URL").begin() as connection:
        connection.execute(
            text(
                "TRUNCATE qms_capa_control_links, qms_capa_evidence_links, qms_capa_document_links, qms_capa_effectiveness_reviews, qms_capa_actions, qms_capas, qms_ncr_evidence_links, qms_ncr_risk_links, qms_ncr_control_links, qms_ncr_document_links, qms_nonconformities, qms_risk_control_links, qms_risk_document_links, qms_risks, qms_document_revisions, qms_control_instance_evidence, qms_documents, qms_control_instance_activities, qms_control_instances, qms_control_activities, qms_control_evidence_requirements, qms_controls, qms_process_sites, qms_processes, qms_process_dependency_projection, qms_process_site_dependency_projection, qms_access_grants"
            )
        )
        connection.execute(
            text("UPDATE organization_units SET status='active' WHERE id=:site"), {"site": SITE}
        )
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL")) as db:
        set_request_context(db, user_id=OWNER, tenant_id=TENANT_A)
        create_grant(
            db,
            actor(OWNER, "owner"),
            uuid4(),
            GrantInput(user_id=MEMBER, unit_id=UNIT, capability="processes.manage"),
        )


def grant_control_access(db: Session) -> None:
    for capability in (
        "processes.read",
        "controls.read",
        "controls.manage",
        "control_instances.read",
        "control_instances.manage",
    ):
        set_request_context(db, user_id=OWNER, tenant_id=TENANT_A)
        create_grant(
            db,
            actor(OWNER, "owner"),
            uuid4(),
            GrantInput(user_id=MEMBER, unit_id=UNIT, capability=capability),
        )
    set_request_context(db, user_id=MEMBER, tenant_id=TENANT_A)


def revoke_test_control_access() -> None:
    with engine("PMC_TEST_ADMIN_DATABASE_URL").begin() as connection:
        connection.execute(
            text(
                "DELETE FROM qms_access_grants WHERE capability IN ('processes.read','controls.read','controls.manage','control_instances.read','control_instances.manage')"
            )
        )


def create(db: Session, **values: Any) -> QMSProcess:
    set_request_context(db, user_id=MEMBER, tenant_id=TENANT_A)
    body = {
        "unit_id": UNIT,
        "code": "P-" + uuid4().hex[:8],
        "name": "Receiving",
        "owner_user_id": MEMBER,
        "inputs": "Incoming lot",
        "outputs": "Verified lot",
        **values,
    }
    return create_process(db, actor(), uuid4(), ProcessInput(**body))


def _document(
    db: Session, process: QMSProcess, *, owner_user_id: UUID | None = None
) -> QMSDocument:
    now = datetime.now(UTC)
    row = QMSDocument(
        id=uuid4(),
        tenant_id=TENANT_A,
        unit_id=UNIT,
        process_id=process.id,
        code="D-" + uuid4().hex[:8],
        title="Controlled procedure",
        document_type="procedure",
        owner_user_id=owner_user_id,
        status="draft",
        current_revision_id=None,
        row_version=1,
        created_by_user_id=MEMBER,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.flush()
    return row


def test_process_permissions_and_audit_are_scoped() -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        row = create(db)
        set_request_context(db, user_id=MEMBER, tenant_id=TENANT_A)
        assert db.get(QMSProcess, row.id) is not None
        assert db.scalar(
            text(
                "SELECT relrowsecurity AND relforcerowsecurity FROM pg_class WHERE relname='qms_processes'"
            )
        )
        set_request_context(db, user_id=OWNER, tenant_id=TENANT_A)
        assert (
            db.scalar(
                text(
                    "SELECT count(*) FROM audit_events WHERE resource_id=:id AND action='process.created'"
                ),
                {"id": row.id},
            )
            == 1
        )
        set_request_context(db, user_id=OTHER, tenant_id=TENANT_B)
        assert db.scalar(select(QMSProcess.id).where(QMSProcess.id == row.id)) is None
        assert db.scalar(text("SELECT count(*) FROM qms_processes")) == 0


def test_process_sites_are_multi_valued_scoped_and_audited() -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        row = create(db, site_ids=[SITE])
        set_request_context(db, user_id=MEMBER, tenant_id=TENANT_A)
        assert (
            db.scalar(
                text("SELECT site_unit_id FROM qms_process_sites WHERE process_id=:id"),
                {"id": row.id},
            )
            == SITE
        )
        set_request_context(db, user_id=OWNER, tenant_id=TENANT_A)
        created_event = db.scalar(
            text(
                "SELECT new_values FROM audit_events WHERE resource_id=:id AND action='process.created'"
            ),
            {"id": row.id},
        )
        assert created_event["site_ids"] == [str(SITE)]
        with pytest.raises(HTTPException) as error:
            create(db, site_ids=[UNIT])
        assert error.value.status_code == 409

        set_request_context(db, user_id=MEMBER, tenant_id=TENANT_A)
        row = update_process(
            db, actor(), uuid4(), row.id, ProcessPatch(expected_version=1, site_ids=[])
        )
        assert (
            db.scalar(
                text("SELECT count(*) FROM qms_process_sites WHERE process_id=:id"), {"id": row.id}
            )
            == 0
        )
        set_request_context(db, user_id=OWNER, tenant_id=TENANT_A)
        event = db.scalar(
            text(
                "SELECT new_values FROM audit_events WHERE resource_id=:id AND action='process.updated'"
            ),
            {"id": row.id},
        )
        assert event["site_ids"] == []


def test_process_site_rejects_foreign_tenant() -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        with pytest.raises(HTTPException) as error:
            create(db, site_ids=[FOREIGN_SITE])
        assert error.value.status_code == 409


def test_active_process_protects_site_and_restore_requires_active_sites() -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        row = create(db, site_ids=[SITE])
        with pytest.raises(DBAPIError), engine("PMC_TEST_ADMIN_DATABASE_URL").begin() as connection:
            connection.execute(
                text("UPDATE organization_units SET status='archived' WHERE id=:site"),
                {"site": SITE},
            )

        set_request_context(db, user_id=MEMBER, tenant_id=TENANT_A)
        archived = change_status(
            db, actor(), uuid4(), row.id, VersionCommand(expected_version=1), "archived"
        )
        with engine("PMC_TEST_ADMIN_DATABASE_URL").begin() as connection:
            connection.execute(
                text("UPDATE organization_units SET status='archived' WHERE id=:site"),
                {"site": SITE},
            )
        set_request_context(db, user_id=MEMBER, tenant_id=TENANT_A)
        with pytest.raises(HTTPException) as error:
            change_status(
                db,
                actor(),
                uuid4(),
                row.id,
                VersionCommand(expected_version=archived.row_version),
                "active",
            )
        assert error.value.status_code == 409
        with engine("PMC_TEST_ADMIN_DATABASE_URL").begin() as connection:
            connection.execute(
                text("UPDATE organization_units SET status='active' WHERE id=:site"),
                {"site": SITE},
            )
        set_request_context(db, user_id=MEMBER, tenant_id=TENANT_A)
        restored = change_status(
            db,
            actor(),
            uuid4(),
            row.id,
            VersionCommand(expected_version=archived.row_version),
            "active",
        )
        assert restored.status == "active"


def test_owner_and_metadata_responsibility_do_not_grant_access() -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        row = create(db, owner_user_id=OWNER)
        set_request_context(db, user_id=OWNER, tenant_id=TENANT_A)
        assert db.scalar(select(QMSProcess.id).where(QMSProcess.id == row.id)) is None
        with pytest.raises(HTTPException) as error:
            create_process(
                db,
                actor(OWNER, "owner"),
                uuid4(),
                ProcessInput(unit_id=UNIT, code="DENIED", name="Denied"),
            )
        assert error.value.status_code == 403


def test_read_capability_does_not_allow_mutation() -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        row = create(db)
        set_request_context(db, user_id=OWNER, tenant_id=TENANT_A)
        create_grant(
            db,
            actor(OWNER, "owner"),
            uuid4(),
            GrantInput(user_id=OTHER, unit_id=UNIT, capability="processes.read"),
        )
        set_request_context(db, user_id=OTHER, tenant_id=TENANT_A)
        assert db.scalar(select(QMSProcess.id).where(QMSProcess.id == row.id)) == row.id
        with pytest.raises(HTTPException):
            update_process(
                db, actor(OTHER), uuid4(), row.id, ProcessPatch(expected_version=1, name="Denied")
            )


def test_document_rls_requires_explicit_author_capability_and_isolates_tenants() -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        process = create(db)
        set_request_context(db, user_id=OWNER, tenant_id=TENANT_A)
        create_grant(
            db,
            actor(OWNER, "owner"),
            uuid4(),
            GrantInput(user_id=MEMBER, unit_id=UNIT, capability="documents.author"),
        )
        set_request_context(db, user_id=MEMBER, tenant_id=TENANT_A)
        document = _document(db, process)
        db.commit()
        set_request_context(db, user_id=OTHER, tenant_id=TENANT_B)
        assert db.scalar(select(QMSDocument.id).where(QMSDocument.id == document.id)) is None


def test_document_register_requires_explicit_view_responsibility() -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        set_request_context(db, user_id=MEMBER, tenant_id=TENANT_A)
        authenticated = cast(
            AuthenticatedSession,
            SimpleNamespace(
                user=SimpleNamespace(id=MEMBER),
                record=SimpleNamespace(current_tenant_id=TENANT_A),
            ),
        )
        with pytest.raises(HTTPException) as error:
            document_service.list_documents(db, authenticated, UNIT)
        assert error.value.status_code == 403


def test_document_scope_cannot_be_changed_even_by_author() -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        process = create(db)
        other_process = create(db, code="P-" + uuid4().hex[:8])
        set_request_context(db, user_id=OWNER, tenant_id=TENANT_A)
        create_grant(
            db,
            actor(OWNER, "owner"),
            uuid4(),
            GrantInput(user_id=MEMBER, unit_id=UNIT, capability="documents.author"),
        )
        set_request_context(db, user_id=MEMBER, tenant_id=TENANT_A)
        document = _document(db, process)
        document.process_id = other_process.id
        document.row_version += 1
        with pytest.raises(DBAPIError):
            db.flush()
        db.rollback()


def test_owner_without_document_capability_cannot_insert_document() -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        process = create(db)
        set_request_context(db, user_id=OWNER, tenant_id=TENANT_A)
        document = QMSDocument(
            id=uuid4(),
            tenant_id=TENANT_A,
            unit_id=UNIT,
            process_id=process.id,
            code="DENY-" + uuid4().hex[:8],
            title="Denied procedure",
            document_type="procedure",
            owner_user_id=None,
            status="draft",
            current_revision_id=None,
            row_version=1,
            created_by_user_id=OWNER,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        db.add(document)
        with pytest.raises(DBAPIError):
            db.flush()
        db.rollback()


def test_document_owner_must_be_an_active_member_of_the_current_tenant() -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        process = create(db)
        set_request_context(db, user_id=OWNER, tenant_id=TENANT_A)
        create_grant(
            db,
            actor(OWNER, "owner"),
            uuid4(),
            GrantInput(user_id=MEMBER, unit_id=UNIT, capability="documents.author"),
        )
        with engine("PMC_TEST_ADMIN_DATABASE_URL").begin() as connection:
            connection.execute(
                text(
                    "UPDATE memberships SET status='revoked' WHERE tenant_id=:tenant AND user_id=:user"
                ),
                {"tenant": TENANT_A, "user": OTHER},
            )
        try:
            set_request_context(db, user_id=MEMBER, tenant_id=TENANT_A)
            with pytest.raises(DBAPIError):
                _document(db, process, owner_user_id=OTHER)
            db.rollback()
        finally:
            with engine("PMC_TEST_ADMIN_DATABASE_URL").begin() as connection:
                connection.execute(
                    text(
                        "UPDATE memberships SET status='active' WHERE tenant_id=:tenant AND user_id=:user"
                    ),
                    {"tenant": TENANT_A, "user": OTHER},
                )


def test_document_cannot_be_created_against_an_archived_process() -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        process = create(db)
        set_request_context(db, user_id=MEMBER, tenant_id=TENANT_A)
        change_status(
            db, actor(), uuid4(), process.id, VersionCommand(expected_version=1), "archived"
        )
        set_request_context(db, user_id=MEMBER, tenant_id=TENANT_A)
        with pytest.raises(DBAPIError):
            _document(db, process)
        db.rollback()


def test_document_obsolescence_requires_its_own_capability_and_is_audited(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        process = create(db)
        grants = []
        for capability in ("documents.author", "processes.read"):
            set_request_context(db, user_id=OWNER, tenant_id=TENANT_A)
            grants.append(
                create_grant(
                    db,
                    actor(OWNER, "owner"),
                    uuid4(),
                    GrantInput(user_id=MEMBER, unit_id=UNIT, capability=capability),
                )
            )
        set_request_context(db, user_id=MEMBER, tenant_id=TENANT_A)
        document = _document(db, process)
        db.commit()

        def set_actor_context(session: Session, _authenticated: object) -> OrganizationActor:
            set_request_context(session, user_id=MEMBER, tenant_id=TENANT_A)
            return actor()

        monkeypatch.setattr(document_service, "actor_context", set_actor_context)
        request = Request(
            {"type": "http", "method": "POST", "path": "/documents/obsolete", "headers": []}
        )
        request.state.request_id = uuid4()
        with pytest.raises(HTTPException) as denied:
            document_service.obsolete_document(
                document.id,
                request,
                document_service.Command(expected_version=1),
                db,
                cast(AuthenticatedSession, object()),
            )
        assert denied.value.status_code == 403
        db.rollback()

        set_request_context(db, user_id=OWNER, tenant_id=TENANT_A)
        obsolete_grant = create_grant(
            db,
            actor(OWNER, "owner"),
            uuid4(),
            GrantInput(user_id=MEMBER, unit_id=UNIT, capability="documents.obsolete"),
        )
        set_request_context(db, user_id=MEMBER, tenant_id=TENANT_A)
        obsoleted = document_service.obsolete_document(
            document.id,
            request,
            document_service.Command(expected_version=1),
            db,
            cast(AuthenticatedSession, object()),
        )
        assert obsoleted.status == "obsolete"
        assert obsoleted.row_version == 2
        set_request_context(db, user_id=OWNER, tenant_id=TENANT_A)
        assert (
            db.scalar(
                text(
                    "SELECT count(*) FROM audit_events WHERE resource_id=:id AND action='document.obsoleted'"
                ),
                {"id": document.id},
            )
            == 1
        )

        set_request_context(db, user_id=OWNER, tenant_id=TENANT_A)
        revoke_grant(db, actor(OWNER, "owner"), uuid4(), obsolete_grant.id)
        for grant in grants:
            set_request_context(db, user_id=OWNER, tenant_id=TENANT_A)
            revoke_grant(db, actor(OWNER, "owner"), uuid4(), grant.id)


def test_hierarchy_rejects_cycles_and_parent_archival() -> None:
    runtime = engine("PMC_TEST_RUNTIME_DATABASE_URL")
    with Session(runtime, expire_on_commit=False) as db:
        parent = create(db)
        child = create(db, parent_id=parent.id)
        set_request_context(db, user_id=MEMBER, tenant_id=TENANT_A)
        with pytest.raises(HTTPException) as cycle:
            update_process(
                db,
                actor(),
                uuid4(),
                parent.id,
                ProcessPatch(expected_version=1, parent_id=child.id),
            )
        assert cycle.value.status_code == 409
        set_request_context(db, user_id=MEMBER, tenant_id=TENANT_A)
        with pytest.raises(HTTPException) as archive:
            change_status(
                db, actor(), uuid4(), parent.id, VersionCommand(expected_version=1), "archived"
            )
        assert archive.value.status_code == 409


def test_archive_restore_and_stale_edits() -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        row = create(db)
        set_request_context(db, user_id=MEMBER, tenant_id=TENANT_A)
        change_status(db, actor(), uuid4(), row.id, VersionCommand(expected_version=1), "archived")
        set_request_context(db, user_id=MEMBER, tenant_id=TENANT_A)
        with pytest.raises(HTTPException):
            update_process(
                db, actor(), uuid4(), row.id, ProcessPatch(expected_version=2, name="Denied")
            )
        set_request_context(db, user_id=MEMBER, tenant_id=TENANT_A)
        restored = change_status(
            db, actor(), uuid4(), row.id, VersionCommand(expected_version=2), "active"
        )
        assert restored.row_version == 3
        set_request_context(db, user_id=MEMBER, tenant_id=TENANT_A)
        with pytest.raises(HTTPException) as stale:
            update_process(
                db, actor(), uuid4(), row.id, ProcessPatch(expected_version=1, name="Stale")
            )
        assert stale.value.status_code == 409


@pytest.mark.parametrize("invalid", ["parent", "owner", "duplicate"])
def test_invalid_references_and_duplicate_codes(invalid: str) -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        row = create(db)
        values = (
            {"parent_id": uuid4()}
            if invalid == "parent"
            else {"owner_user_id": uuid4()}
            if invalid == "owner"
            else {"code": row.code.lower()}
        )
        with pytest.raises(HTTPException) as error:
            create(db, **values)
        assert error.value.status_code == 409


def test_audit_failure_rolls_back_process_and_dependency_projection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(*args: object, **kwargs: object) -> None:
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(audit_service, "record_process", fail)
    with (
        Session(engine("PMC_TEST_RUNTIME_DATABASE_URL")) as db,
        pytest.raises(RuntimeError, match="audit unavailable"),
    ):
        create(db)
    with engine("PMC_TEST_ADMIN_DATABASE_URL").begin() as connection:
        assert connection.scalar(text("SELECT count(*) FROM qms_processes")) == 0
        assert (
            connection.scalar(text("SELECT count(*) FROM qms_process_dependency_projection")) == 0
        )


def test_invisible_processes_still_block_unit_archival() -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL")) as db:
        create(db)
    with engine("PMC_TEST_ADMIN_DATABASE_URL").begin() as connection:
        connection.execute(
            text("UPDATE organization_unit_assignments SET status='inactive' WHERE unit_id=:id"),
            {"id": UNIT},
        )
    try:
        with engine("PMC_TEST_RUNTIME_DATABASE_URL").connect() as connection:
            context(connection, OWNER, TENANT_A)
            assert connection.scalar(text("SELECT count(*) FROM qms_processes")) == 0
            with pytest.raises(DBAPIError) as error:
                connection.execute(
                    text("UPDATE organization_units SET status='archived' WHERE id=:id"),
                    {"id": UNIT},
                )
            assert error.value.orig is not None
            assert "active process dependencies" in str(error.value.orig)
    finally:
        with engine("PMC_TEST_ADMIN_DATABASE_URL").begin() as connection:
            connection.execute(
                text("UPDATE organization_unit_assignments SET status='active' WHERE unit_id=:id"),
                {"id": UNIT},
            )


@pytest.mark.parametrize("operation", ["delete", "move", "archived_edit"])
def test_direct_sql_cannot_delete_move_or_rewrite_archived_process(operation: str) -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        row = create(db)
        if operation == "archived_edit":
            set_request_context(db, user_id=MEMBER, tenant_id=TENANT_A)
            change_status(
                db, actor(), uuid4(), row.id, VersionCommand(expected_version=1), "archived"
            )
    query = {
        "delete": "DELETE FROM qms_processes WHERE id=:id",
        "move": "UPDATE qms_processes SET unit_id=:unit,row_version=row_version+1 WHERE id=:id",
        "archived_edit": "UPDATE qms_processes SET name='Forbidden',row_version=row_version+1 WHERE id=:id",
    }[operation]
    with engine("PMC_TEST_RUNTIME_DATABASE_URL").connect() as connection:
        context(connection, MEMBER, TENANT_A)
        with pytest.raises(DBAPIError):
            connection.execute(text(query), {"id": row.id, "unit": uuid4()})


def test_concurrent_editors_get_one_conflict() -> None:
    runtime = engine("PMC_TEST_RUNTIME_DATABASE_URL")
    with Session(runtime, expire_on_commit=False) as db:
        row = create(db)

    def attempt(name: str) -> str:
        with Session(runtime, expire_on_commit=False) as db:
            set_request_context(db, user_id=MEMBER, tenant_id=TENANT_A)
            try:
                update_process(
                    db, actor(), uuid4(), row.id, ProcessPatch(expected_version=1, name=name)
                )
                return "saved"
            except HTTPException as error:
                assert error.status_code == 409
                return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(attempt, ["First", "Second"]))
    assert sorted(outcomes) == ["conflict", "saved"]


def test_concurrent_parent_assignments_cannot_form_cycle() -> None:
    from threading import Barrier

    runtime = engine("PMC_TEST_RUNTIME_DATABASE_URL")
    with Session(runtime, expire_on_commit=False) as db:
        first = create(db)
        second = create(db)
    barrier = Barrier(2)

    def attempt(pair: tuple[UUID, UUID]) -> str:
        with Session(runtime, expire_on_commit=False) as db:
            set_request_context(db, user_id=MEMBER, tenant_id=TENANT_A)
            barrier.wait(timeout=10)
            try:
                update_process(
                    db,
                    actor(),
                    uuid4(),
                    pair[0],
                    ProcessPatch(expected_version=1, parent_id=pair[1]),
                )
                return "saved"
            except HTTPException as error:
                assert error.status_code == 409
                return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(attempt, [(first.id, second.id), (second.id, first.id)]))
    assert sorted(outcomes) == ["conflict", "saved"]
    with Session(runtime) as db:
        set_request_context(db, user_id=MEMBER, tenant_id=TENANT_A)
        rows = list(db.scalars(select(QMSProcess)))
        assert sum(row.parent_id is not None for row in rows) == 1


def test_process_pages_keep_scope_order_and_no_overlap() -> None:
    from pmc_api.processes import list_processes

    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        for index in range(55):
            create(db, code=f"PAGE-{index:03d}")
        set_request_context(db, user_id=MEMBER, tenant_id=TENANT_A)
        first = list_processes(db, actor(), UNIT, 50, 0)
        second = list_processes(db, actor(), UNIT, 50, 50)
        assert [row.code for row in first] == [f"PAGE-{index:03d}" for index in range(50)]
        assert [row.code for row in second] == [f"PAGE-{index:03d}" for index in range(50, 55)]
        assert not {row.id for row in first} & {row.id for row in second}
        set_request_context(db, user_id=OTHER, tenant_id=TENANT_B)
        assert list_processes(db, actor(OTHER), UNIT, 50, 50) == []


def test_private_dependency_projection_is_not_readable() -> None:
    with engine("PMC_TEST_RUNTIME_DATABASE_URL").connect() as connection:
        context(connection, MEMBER, TENANT_A)
        with pytest.raises(DBAPIError):
            connection.execute(text("SELECT * FROM qms_process_dependency_projection"))


def test_process_search_is_literal_scoped_and_case_insensitive() -> None:
    from pmc_api.processes import list_processes

    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        first = create(db, code="LITERAL%_!", name="Unique incoming inspection")
        create(db, code="LITERAL-OTHER", name="Control sample")
        set_request_context(db, user_id=MEMBER, tenant_id=TENANT_A)
        assert [row.id for row in list_processes(db, actor(), UNIT, 50, 0, "%_!")] == [first.id]
        assert [row.id for row in list_processes(db, actor(), UNIT, 50, 0, "INCOMING")] == [
            first.id
        ]
        set_request_context(db, user_id=OTHER, tenant_id=TENANT_B)
        assert list_processes(db, actor(OTHER), UNIT, 50, 0, "INCOMING") == []


def test_preloaded_process_cannot_overwrite_a_newer_revision() -> None:
    runtime = engine("PMC_TEST_RUNTIME_DATABASE_URL")
    with Session(runtime, expire_on_commit=False) as db:
        row = create(db)
    with Session(runtime, expire_on_commit=False) as stale:
        set_request_context(stale, user_id=MEMBER, tenant_id=TENANT_A)
        loaded = stale.scalar(select(QMSProcess).where(QMSProcess.id == row.id))
        assert loaded is not None and loaded.row_version == 1
        with Session(runtime, expire_on_commit=False) as fresh:
            set_request_context(fresh, user_id=MEMBER, tenant_id=TENANT_A)
            update_process(
                fresh,
                actor(),
                uuid4(),
                row.id,
                ProcessPatch(expected_version=1, name="Reviewed update"),
            )
        with pytest.raises(HTTPException) as error:
            update_process(
                stale,
                actor(),
                uuid4(),
                row.id,
                ProcessPatch(expected_version=1, name="Stale overwrite"),
            )
        assert error.value.status_code == 409
        stale.rollback()
        set_request_context(stale, user_id=MEMBER, tenant_id=TENANT_A)
        assert (
            stale.scalar(select(QMSProcess.name).where(QMSProcess.id == row.id))
            == "Reviewed update"
        )


def test_revoked_grant_denies_preloaded_process_reads_and_writes() -> None:
    from pmc_api.models import QMSAccessGrant
    from pmc_api.processes import list_processes
    from pmc_api.qms_access import revoke_grant

    runtime = engine("PMC_TEST_RUNTIME_DATABASE_URL")
    with Session(runtime, expire_on_commit=False) as db:
        row = create(db)
    with Session(runtime, expire_on_commit=False) as member:
        set_request_context(member, user_id=MEMBER, tenant_id=TENANT_A)
        assert member.scalar(select(QMSProcess).where(QMSProcess.id == row.id)) is not None
        with Session(runtime, expire_on_commit=False) as owner:
            set_request_context(owner, user_id=OWNER, tenant_id=TENANT_A)
            grant = owner.scalar(
                select(QMSAccessGrant).where(
                    QMSAccessGrant.user_id == MEMBER,
                    QMSAccessGrant.capability == "processes.manage",
                    QMSAccessGrant.status == "active",
                )
            )
            assert grant is not None
            revoke_grant(owner, actor(OWNER, "owner"), uuid4(), grant.id)
        assert list_processes(member, actor(), UNIT, 50, 0) == []
        with pytest.raises(HTTPException) as error:
            update_process(
                member, actor(), uuid4(), row.id, ProcessPatch(expected_version=1, name="Forbidden")
            )
        assert error.value.status_code in {403, 404}


def test_control_catalog_and_instance_workflow_are_scoped_versioned_and_audited() -> None:
    request_id = uuid4()
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        process = create(db)
        grant_control_access(db)
        control = create_control(
            db,
            actor(),
            request_id,
            ControlInput(
                unit_id=UNIT,
                process_id=process.id,
                code="CTL-" + uuid4().hex[:8],
                name="Incoming quality verification",
                objective="Confirm received material meets specifications",
                guidance_purpose="Reusable purpose text must not be copied to audit history",
            ),
        )
        assert control.state == "draft"
        set_request_context(db, user_id=MEMBER, tenant_id=TENANT_A)
        control = change_control_state(db, actor(), uuid4(), control.id, 1, "active")
        set_request_context(db, user_id=MEMBER, tenant_id=TENANT_A)
        instance = create_instance(
            db,
            actor(),
            uuid4(),
            UNIT,
            process.id,
            InstanceInput(
                control_id=control.id,
                code="IMP-" + uuid4().hex[:8],
                name=control.name,
                owner_user_id=MEMBER,
            ),
        )
        assert instance.implementation_status == "not_started"
        set_request_context(db, user_id=MEMBER, tenant_id=TENANT_A)
        instance = transition_instance(
            db,
            actor(),
            uuid4(),
            instance.id,
            TransitionInput(
                expected_version=1, target_status="in_progress", decision="Work started"
            ),
        )
        set_request_context(db, user_id=MEMBER, tenant_id=TENANT_A)
        instance = transition_instance(
            db,
            actor(),
            uuid4(),
            instance.id,
            TransitionInput(
                expected_version=2, target_status="under_review", decision="Evidence submitted"
            ),
        )
        set_request_context(db, user_id=MEMBER, tenant_id=TENANT_A)
        instance = transition_instance(
            db,
            actor(),
            uuid4(),
            instance.id,
            TransitionInput(
                expected_version=3, target_status="implemented", decision="Evidence verified"
            ),
        )
        assert instance.implementation_date is not None
        assert instance.row_version == 4
        authenticated = cast(
            AuthenticatedSession,
            SimpleNamespace(
                user=SimpleNamespace(id=MEMBER),
                record=SimpleNamespace(current_tenant_id=TENANT_A),
            ),
        )
        set_request_context(db, user_id=MEMBER, tenant_id=TENANT_A)
        assert get_control(control.id, db, authenticated).id == control.id
        assert get_instance(instance.id, db, authenticated).id == instance.id
        foreign = cast(
            AuthenticatedSession,
            SimpleNamespace(
                user=SimpleNamespace(id=OTHER),
                record=SimpleNamespace(current_tenant_id=TENANT_B),
            ),
        )
        set_request_context(db, user_id=OTHER, tenant_id=TENANT_B)
        with pytest.raises(HTTPException) as hidden_control:
            get_control(control.id, db, foreign)
        with pytest.raises(HTTPException) as hidden_instance:
            get_instance(instance.id, db, foreign)
        assert hidden_control.value.status_code == 404
        assert hidden_instance.value.status_code == 404
        set_request_context(db, user_id=OWNER, tenant_id=TENANT_A)
        events = list(
            db.scalars(
                select(AuditEvent)
                .where(AuditEvent.tenant_id == TENANT_A)
                .order_by(AuditEvent.occurred_at)
            )
        )
        actions = [event.action for event in events]
        assert "control.created" in actions
        assert "control.activated" in actions
        assert actions.count("control_instance.transitioned") == 3
        created_event = next(event for event in events if event.action == "control.created")
        assert "guidance_purpose" not in (created_event.new_values or {})
        assert "guidance_hashes" in (created_event.new_values or {})
        transition_event = next(
            event for event in events if event.action == "control_instance.transitioned"
        )
        assert (transition_event.new_values or {}).get("decision") == "Work started"
        revoke_test_control_access()


def test_controls_reject_scope_mismatch_and_invalid_direct_instance_transition() -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        process = create(db)
        other_process = create(db, code="P-" + uuid4().hex[:8])
        grant_control_access(db)
        control = create_control(
            db,
            actor(),
            uuid4(),
            ControlInput(
                unit_id=UNIT,
                process_id=process.id,
                code="CTL-" + uuid4().hex[:8],
                name="Scope check",
                objective="Keep control bound to its process",
            ),
        )
        process_id = process.id
        control_id = control.id
        set_request_context(db, user_id=MEMBER, tenant_id=TENANT_A)
        with pytest.raises(DBAPIError):
            db.add(
                QMSControlInstance(
                    id=uuid4(),
                    tenant_id=TENANT_A,
                    unit_id=UNIT,
                    process_id=other_process.id,
                    control_id=control.id,
                    code="BAD-" + uuid4().hex[:8],
                    name="Mismatch",
                    owner_user_id=None,
                    implementation_status="not_started",
                    applicability="applicable",
                    justification="",
                    target_date=None,
                    implementation_date=None,
                    review_date=None,
                    notes="",
                    status="active",
                    row_version=1,
                    created_by_user_id=MEMBER,
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                )
            )
            db.flush()
        db.rollback()
        set_request_context(db, user_id=MEMBER, tenant_id=TENANT_A)
        control = change_control_state(db, actor(), uuid4(), control_id, 1, "active")
        set_request_context(db, user_id=MEMBER, tenant_id=TENANT_A)
        instance = create_instance(
            db,
            actor(),
            uuid4(),
            UNIT,
            process_id,
            InstanceInput(
                control_id=control.id,
                code="IMP-" + uuid4().hex[:8],
                name="Invalid transition check",
            ),
        )
        set_request_context(db, user_id=MEMBER, tenant_id=TENANT_A)
        with pytest.raises(DBAPIError):
            db.execute(
                text(
                    "UPDATE qms_control_instances SET implementation_status='implemented', implementation_date=CURRENT_DATE, row_version=2 WHERE id=:id"
                ),
                {"id": instance.id},
            )
        db.rollback()
        revoke_test_control_access()


def test_not_applicable_implementation_requires_reason_and_can_be_created() -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        process = create(db)
        grant_control_access(db)
        control = create_control(
            db,
            actor(),
            uuid4(),
            ControlInput(
                unit_id=UNIT,
                process_id=process.id,
                code="CTL-" + uuid4().hex[:8],
                name="Conditional control",
                objective="Verify applicability decisions are justified",
            ),
        )
        set_request_context(db, user_id=MEMBER, tenant_id=TENANT_A)
        control = change_control_state(db, actor(), uuid4(), control.id, 1, "active")
        with pytest.raises(ValidationError):
            InstanceInput(
                control_id=control.id,
                code="IMP-" + uuid4().hex[:8],
                name=control.name,
                applicability="not_applicable",
            )
        set_request_context(db, user_id=MEMBER, tenant_id=TENANT_A)
        instance = create_instance(
            db,
            actor(),
            uuid4(),
            UNIT,
            process.id,
            InstanceInput(
                control_id=control.id,
                code="IMP-" + uuid4().hex[:8],
                name=control.name,
                applicability="not_applicable",
                justification="The control does not apply to this process scope.",
            ),
        )
        assert instance.implementation_status == "not_applicable"
        assert instance.justification
        revoke_test_control_access()


def test_control_method_definitions_are_scoped_audited_and_locked_on_activation() -> None:
    def auth() -> AuthenticatedSession:
        return cast(
            AuthenticatedSession,
            SimpleNamespace(
                user=SimpleNamespace(id=MEMBER),
                record=SimpleNamespace(current_tenant_id=TENANT_A),
            ),
        )

    def request() -> Request:
        return cast(Request, SimpleNamespace(state=SimpleNamespace(request_id=uuid4())))

    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        process = create(db)
        grant_control_access(db)
        control = create_control(
            db,
            actor(),
            uuid4(),
            ControlInput(
                unit_id=UNIT,
                process_id=process.id,
                code="CTL-" + uuid4().hex[:8],
                name="Evidence-backed supplier review",
                objective="Review critical suppliers on a recurring basis",
            ),
        )
        activity = create_activity(
            control.id,
            request(),
            ActivityInput(
                name="Review supplier performance",
                objective="Identify sustained quality risk",
                activity_kind="project_administration",
                readiness_required=True,
                expected_output="Approved supplier review record",
            ),
            db,
            auth(),
        )
        requirement = create_evidence_requirement(
            control.id,
            request(),
            EvidenceRequirementInput(
                name="Supplier performance review",
                description="Record the review outcome and follow-up actions.",
                acceptance_criteria="The review is approved and actions have owners.",
                evidence_type="record",
                mandatory=True,
                definition_key="supplier-review-v1",
            ),
            db,
            auth(),
        )
        assert activity.readiness_required is False
        assert requirement.mandatory is True
        set_request_context(db, user_id=MEMBER, tenant_id=TENANT_A)
        activity = update_activity(
            activity.id,
            request(),
            ActivityPatch(expected_version=1, active=False),
            db,
            auth(),
        )
        assert activity.active is False and activity.row_version == 2
        with Session(
            engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False
        ) as other_tenant:
            set_request_context(other_tenant, user_id=MEMBER, tenant_id=TENANT_B)
            assert (
                other_tenant.scalar(
                    select(QMSControlEvidenceRequirement.id).where(
                        QMSControlEvidenceRequirement.id == requirement.id
                    )
                )
                is None
            )
        set_request_context(db, user_id=MEMBER, tenant_id=TENANT_A)
        control = change_control_state(db, actor(), uuid4(), control.id, 1, "active")
        with pytest.raises(HTTPException) as error:
            update_evidence_requirement(
                requirement.id,
                request(),
                EvidenceRequirementPatch(expected_version=1, mandatory=False),
                db,
                auth(),
            )
        assert error.value.status_code == 409
        assert control.state == "active"
        set_request_context(db, user_id=OWNER, tenant_id=TENANT_A)
        events = list(
            db.scalars(
                select(AuditEvent).where(
                    AuditEvent.tenant_id == TENANT_A,
                    AuditEvent.action.in_(
                        [
                            "control.activity_created",
                            "control.activity_deactivated",
                            "control.evidence_requirement_created",
                        ]
                    ),
                )
            )
        )
        assert {event.action for event in events} == {
            "control.activity_created",
            "control.activity_deactivated",
            "control.evidence_requirement_created",
        }
        req_event = next(
            event for event in events if event.action == "control.evidence_requirement_created"
        )
        assert "acceptance_criteria_hash" in (req_event.new_values or {})
        assert "The review is approved" not in str(req_event.new_values)
        revoke_test_control_access()


def test_control_instance_generates_readiness_tasks_and_gates_implementation() -> None:
    def auth() -> AuthenticatedSession:
        return cast(
            AuthenticatedSession,
            SimpleNamespace(
                user=SimpleNamespace(id=MEMBER),
                record=SimpleNamespace(current_tenant_id=TENANT_A),
            ),
        )

    def request() -> Request:
        return cast(Request, SimpleNamespace(state=SimpleNamespace(request_id=uuid4())))

    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        process = create(db)
        grant_control_access(db)
        control = create_control(
            db,
            actor(),
            uuid4(),
            ControlInput(
                unit_id=UNIT,
                process_id=process.id,
                code="CTL-" + uuid4().hex[:8],
                name="Readiness-gated control",
                objective="Complete required work before implementation",
            ),
        )
        definition = create_activity(
            control.id,
            request(),
            ActivityInput(
                name="Train process owners",
                readiness_required=True,
                success_criteria="Owners pass the assessment",
            ),
            db,
            auth(),
        )
        set_request_context(db, user_id=MEMBER, tenant_id=TENANT_A)
        control = change_control_state(
            db, actor(), uuid4(), control.id, control.row_version, "active"
        )
        set_request_context(db, user_id=MEMBER, tenant_id=TENANT_A)
        instance = create_instance(
            db,
            actor(),
            uuid4(),
            UNIT,
            process.id,
            InstanceInput(control_id=control.id, code="IMP-" + uuid4().hex[:8], name=control.name),
        )
        set_request_context(db, user_id=MEMBER, tenant_id=TENANT_A)
        task = db.scalar(
            select(QMSControlInstanceActivity).where(
                QMSControlInstanceActivity.control_instance_id == instance.id
            )
        )
        assert task is not None
        assert task.activity_definition_id == definition.id
        assert task.name == "Train process owners" and task.readiness_required

        with pytest.raises(HTTPException) as error:
            transition_instance(
                db,
                actor(),
                uuid4(),
                instance.id,
                TransitionInput(
                    expected_version=1, target_status="under_review", decision="Request review"
                ),
            )
        assert error.value.status_code == 409

        task = transition_activity(
            request(),
            task.id,
            ActivityTransition(expected_version=1, target_status="in_progress", decision="Started"),
            db,
            auth(),
        )
        task = transition_activity(
            request(),
            task.id,
            ActivityTransition(
                expected_version=2, target_status="under_review", decision="Submitted"
            ),
            db,
            auth(),
        )
        task = transition_activity(
            request(),
            task.id,
            ActivityTransition(
                expected_version=3,
                target_status="completed",
                decision="Verified",
                completion_summary="All owners passed the assessment.",
            ),
            db,
            auth(),
        )
        assert task.status == "completed" and task.completed_by_user_id == MEMBER

        set_request_context(db, user_id=MEMBER, tenant_id=TENANT_A)
        instance = transition_instance(
            db,
            actor(),
            uuid4(),
            instance.id,
            TransitionInput(
                expected_version=1,
                target_status="in_progress",
                decision="Implementation work started",
            ),
        )
        set_request_context(db, user_id=MEMBER, tenant_id=TENANT_A)
        instance = transition_instance(
            db,
            actor(),
            uuid4(),
            instance.id,
            TransitionInput(
                expected_version=2, target_status="under_review", decision="Ready for review"
            ),
        )
        set_request_context(db, user_id=MEMBER, tenant_id=TENANT_A)
        instance = transition_instance(
            db,
            actor(),
            uuid4(),
            instance.id,
            TransitionInput(
                expected_version=3, target_status="implemented", decision="Implementation accepted"
            ),
        )
        assert instance.implementation_status == "implemented"
        set_request_context(db, user_id=OWNER, tenant_id=TENANT_A)
        actions = list(
            db.scalars(
                select(AuditEvent.action).where(
                    AuditEvent.tenant_id == TENANT_A,
                    AuditEvent.action.like("control_instance_activity.%"),
                )
            )
        )
        assert actions.count("control_instance_activity.created") == 1
        assert actions.count("control_instance_activity.transitioned") == 3
        revoke_test_control_access()


def test_control_evidence_requires_independent_review_before_readiness() -> None:
    def auth(user_id: UUID = MEMBER, tenant_id: UUID = TENANT_A) -> AuthenticatedSession:
        return cast(
            AuthenticatedSession,
            SimpleNamespace(
                user=SimpleNamespace(id=user_id),
                record=SimpleNamespace(current_tenant_id=tenant_id),
            ),
        )

    def request() -> Request:
        return cast(Request, SimpleNamespace(state=SimpleNamespace(request_id=uuid4())))

    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        process = create(db)
        grant_control_access(db)
        control = create_control(
            db,
            actor(),
            uuid4(),
            ControlInput(
                unit_id=UNIT,
                process_id=process.id,
                code="CTL-" + uuid4().hex[:8],
                name="Reviewed evidence control",
                objective="Require review of submitted evidence",
            ),
        )
        requirement = create_evidence_requirement(
            control.id,
            request(),
            EvidenceRequirementInput(
                name="Approved procedure",
                mandatory=True,
                evidence_type="document",
                acceptance_criteria="A released controlled procedure is identified.",
            ),
            db,
            auth(),
        )
        set_request_context(db, user_id=MEMBER, tenant_id=TENANT_A)
        control = change_control_state(
            db, actor(), uuid4(), control.id, control.row_version, "active"
        )
        set_request_context(db, user_id=MEMBER, tenant_id=TENANT_A)
        instance = create_instance(
            db,
            actor(),
            uuid4(),
            UNIT,
            process.id,
            InstanceInput(control_id=control.id, code="IMP-" + uuid4().hex[:8], name=control.name),
        )
        set_request_context(db, user_id=MEMBER, tenant_id=TENANT_A)
        evidence = db.scalar(
            select(QMSControlInstanceEvidence).where(
                QMSControlInstanceEvidence.control_instance_id == instance.id
            )
        )
        assert evidence is not None and evidence.requirement_definition_id == requirement.id
        evidence_id = evidence.id
        with pytest.raises(DBAPIError):
            db.execute(
                text(
                    "UPDATE qms_control_instance_evidence SET status='submitted', "
                    "submitted_by_user_id=:user, submitted_at=CURRENT_TIMESTAMP, row_version=2 "
                    "WHERE id=:id"
                ),
                {"user": MEMBER, "id": evidence.id},
            )
        db.rollback()
        set_request_context(db, user_id=MEMBER, tenant_id=TENANT_B)
        assert (
            db.scalar(
                select(QMSControlInstanceEvidence.id).where(
                    QMSControlInstanceEvidence.id == evidence_id
                )
            )
            is None
        )
        set_request_context(db, user_id=MEMBER, tenant_id=TENANT_A)
        evidence = db.scalar(
            select(QMSControlInstanceEvidence).where(QMSControlInstanceEvidence.id == evidence_id)
        )
        assert evidence is not None
        instance = transition_instance(
            db,
            actor(),
            uuid4(),
            instance.id,
            TransitionInput(expected_version=1, target_status="in_progress", decision="Start"),
        )
        set_request_context(db, user_id=MEMBER, tenant_id=TENANT_A)
        with pytest.raises(HTTPException) as error:
            transition_instance(
                db,
                actor(),
                uuid4(),
                instance.id,
                TransitionInput(
                    expected_version=2,
                    target_status="under_review",
                    decision="Review before evidence",
                ),
            )
        assert error.value.status_code == 409
        evidence = update_evidence(
            request(),
            evidence.id,
            EvidencePatch(
                expected_version=1, evidence_summary="Procedure QP-001 revision 4 is released."
            ),
            db,
            auth(),
        )
        evidence = submit_evidence(
            request(),
            evidence.id,
            EvidenceCommand(expected_version=2),
            db,
            auth(),
        )
        with pytest.raises(HTTPException) as error:
            review_evidence(
                request(),
                evidence.id,
                ReviewCommand(
                    expected_version=3,
                    target_status="accepted",
                    decision="The evidence is acceptable.",
                ),
                db,
                auth(),
            )
        assert error.value.status_code == 403

        set_request_context(db, user_id=OWNER, tenant_id=TENANT_A)
        create_grant(
            db,
            actor(OWNER, "owner"),
            uuid4(),
            GrantInput(user_id=OTHER, unit_id=UNIT, capability="control_instances.manage"),
        )
        evidence = review_evidence(
            request(),
            evidence.id,
            ReviewCommand(
                expected_version=3, target_status="accepted", decision="The evidence is acceptable."
            ),
            db,
            auth(OTHER),
        )
        assert evidence.status == "accepted" and evidence.reviewed_by_user_id == OTHER
        # Reset actor context after the review transaction; acceptance satisfies the evidence gate.
        set_request_context(db, user_id=MEMBER, tenant_id=TENANT_A)
        instance = transition_instance(
            db,
            actor(),
            uuid4(),
            instance.id,
            TransitionInput(expected_version=2, target_status="under_review", decision="Review"),
        )
        assert instance.implementation_status == "under_review"
        set_request_context(db, user_id=OWNER, tenant_id=TENANT_A)
        actions = list(
            db.scalars(
                select(AuditEvent.action).where(
                    AuditEvent.tenant_id == TENANT_A,
                    AuditEvent.action.like("control_instance_evidence.%"),
                )
            )
        )
        assert actions.count("control_instance_evidence.created") == 1
        assert actions.count("control_instance_evidence.submitted") == 1
        assert actions.count("control_instance_evidence.accepted") == 1
        revoke_test_control_access()

"""CAPA source navigation must enforce origin access before returning scoped history."""

from __future__ import annotations

import os
from typing import Any
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session
from test_capa_intake_integrity import access, intake
from test_nonconformity_integrity import create as create_ncr
from test_nonconformity_integrity import transition as transition_ncr
from test_process_integrity import FOREIGN_SITE, SITE, actor, reset_process_records
from test_process_integrity import create as create_process
from test_risk_integrity import authenticated, current, grant
from test_risk_integrity import create as create_risk
from test_risk_integrity import seed_risks as seed_risks
from test_workflow_integrity import OTHER, OWNER, TENANT_A, TENANT_B, UNIT, engine

from pmc_api import capa
from pmc_api.models import QMSCAPA
from pmc_api.organization_service import OrganizationActor
from pmc_api.qms_access import GrantInput, create_grant, revoke_grant

pytestmark = [
    pytest.mark.process_integrity,
    pytest.mark.skipif(
        "PMC_TEST_RUNTIME_DATABASE_URL" not in os.environ,
        reason="requires disposable PostgreSQL",
    ),
]


@pytest.fixture(autouse=True)
def clean_sources(seed_risks: None) -> None:
    reset_process_records()


def listed(db: Session, **filters: Any) -> list[QMSCAPA]:
    return capa.list_capas(db, authenticated(), UNIT, **filters)


@pytest.mark.parametrize("kind", ["ncr", "risk"])
def test_source_navigation_excludes_other_origins_and_preserves_paging(kind: str) -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        process = create_process(db)
        access(db)
        make = create_ncr if kind == "ncr" else create_risk
        source = make(db, process)
        unrelated_source = make(db, process)
        reference = {f"source_{kind}_id": source.id}
        first = intake(
            db,
            process.id,
            source_type=kind,
            code="CAPA-01",
            name="Literal _% finding",
            **reference,
        )
        second = intake(db, process.id, source_type=kind, code="CAPA-02", **reference)
        intake(
            db,
            process.id,
            source_type=kind,
            code="CAPA-00",
            name="Literal _% finding",
            **{f"source_{kind}_id": unrelated_source.id},
        )
        intake(db, process.id, code="CAPA-OTHER", name="Literal _% finding")

        assert [row.id for row in listed(db, **reference)] == [first.id, second.id]
        assert [row.id for row in listed(db, limit=1, offset=0, **reference)] == [first.id]
        assert [row.id for row in listed(db, limit=1, offset=1, **reference)] == [second.id]
        assert listed(db, limit=1, offset=2, **reference) == []
        assert [row.id for row in listed(db, q="_%", **reference)] == [first.id]
        assert [row.id for row in listed(db, source_type=kind, **reference)] == [
            first.id,
            second.id,
        ]


def test_conflicting_origin_filters_are_rejected_instead_of_broadening_results() -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        access(db)
        for filters in (
            {"source_ncr_id": uuid4(), "source_risk_id": uuid4()},
            {"source_type": "risk", "source_ncr_id": uuid4()},
            {"source_type": "ncr", "source_risk_id": uuid4()},
            {"source_type": "other", "source_ncr_id": uuid4()},
        ):
            with pytest.raises(HTTPException) as invalid:
                listed(db, **filters)
            assert invalid.value.status_code == 422


@pytest.mark.parametrize("kind", ["ncr", "risk"])
def test_unknown_origin_is_not_an_empty_success_response(kind: str) -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        access(db)
        with pytest.raises(HTTPException) as missing:
            listed(db, **{f"source_{kind}_id": uuid4()})
        assert missing.value.status_code == 404


@pytest.mark.parametrize("kind", ["ncr", "risk"])
def test_read_permission_in_another_unit_does_not_authorize_the_origin(kind: str) -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        process = create_process(db)
        access(db)
        source = (create_ncr if kind == "ncr" else create_risk)(db, process)
        intake(db, process.id, source_type=kind, **{f"source_{kind}_id": source.id})
        read = "ncr.read" if kind == "ncr" else "risks.read"
        grant(db, capabilities=("capa.read", read), unit=SITE)
        source_filters: dict[str, Any] = {f"source_{kind}_id": source.id}
        with pytest.raises(HTTPException) as missing:
            capa.list_capas(db, authenticated(), SITE, **source_filters)
        assert missing.value.status_code == 404


@pytest.mark.parametrize("kind", ["ncr", "risk"])
def test_authorized_reader_in_another_company_cannot_resolve_the_origin(kind: str) -> None:
    # A valid reader in tenant B must receive 404 for tenant A's source, even when
    # the client supplies a real source ID and has both read grants in B's unit.
    membership_id = uuid4()
    with engine("PMC_TEST_ADMIN_DATABASE_URL").begin() as connection:
        connection.execute(
            text(
                "INSERT INTO memberships(id,tenant_id,user_id,role,status,created_at) "
                "VALUES(:id,:tenant,:user,'owner','active',CURRENT_TIMESTAMP)"
            ),
            {"id": membership_id, "tenant": TENANT_B, "user": OWNER},
        )
    try:
        with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
            process = create_process(db)
            access(db)
            source = (create_ncr if kind == "ncr" else create_risk)(db, process)
            intake(db, process.id, source_type=kind, **{f"source_{kind}_id": source.id})
            read = "ncr.read" if kind == "ncr" else "risks.read"
            for capability in ("capa.read", read):
                current(db, OWNER, TENANT_B)
                create_grant(
                    db,
                    OrganizationActor(OWNER, str(OWNER), "owner", TENANT_B),
                    uuid4(),
                    GrantInput(user_id=OTHER, unit_id=FOREIGN_SITE, capability=capability),
                )
            source_filters: dict[str, Any] = {f"source_{kind}_id": source.id}
            with pytest.raises(HTTPException) as missing:
                capa.list_capas(
                    db,
                    authenticated(OTHER, TENANT_B),
                    FOREIGN_SITE,
                    **source_filters,
                )
            assert missing.value.status_code == 404
            assert (
                db.scalar(
                    text("SELECT count(*) FROM qms_capas WHERE tenant_id=:tenant"),
                    {"tenant": TENANT_A},
                )
                == 0
            )
    finally:
        with engine("PMC_TEST_ADMIN_DATABASE_URL").begin() as connection:
            connection.execute(text("DELETE FROM memberships WHERE id=:id"), {"id": membership_id})


@pytest.mark.parametrize("kind", ["ncr", "risk"])
@pytest.mark.parametrize("revoke_origin_read", [False, True])
def test_revoked_read_authority_cannot_return_previously_visible_history(
    kind: str, revoke_origin_read: bool
) -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        process = create_process(db)
        grants = access(db)
        source = (create_ncr if kind == "ncr" else create_risk)(db, process)
        reference = {f"source_{kind}_id": source.id}
        row = intake(db, process.id, source_type=kind, **reference)
        assert [item.id for item in listed(db, **reference)] == [row.id]
        capability = (
            ("ncr.read" if kind == "ncr" else "risks.read") if revoke_origin_read else "capa.read"
        )
        read_grant = next(item for item in grants if item.capability == capability)
        current(db, OWNER)
        revoke_grant(db, actor(OWNER, "owner"), uuid4(), read_grant.id)
        with pytest.raises(HTTPException) as denied:
            listed(db, **reference)
        assert denied.value.status_code == 403


def test_cancelled_ncr_preserves_existing_corrective_action_history() -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        process = create_process(db)
        access(db)
        source = create_ncr(db, process)
        row = intake(db, process.id, source_type="ncr", source_ncr_id=source.id)
        grant(db, capabilities=("ncr.review",))
        source = transition_ncr(
            db, source, "cancelled", decision="Duplicate NCR; preserve linked CAPA history."
        )
        assert source.state == "cancelled"
        assert [item.id for item in listed(db, source_ncr_id=source.id)] == [row.id]
        # Reading history must not weaken the existing prohibition on creating
        # another CAPA from a cancelled source.
        with pytest.raises(HTTPException) as cancelled:
            intake(db, process.id, source_type="ncr", source_ncr_id=source.id)
        assert cancelled.value.status_code == 404

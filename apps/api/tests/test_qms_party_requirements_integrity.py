"""Interested-party assessment and history against disposable PostgreSQL."""

import os
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from test_qms_context_integrity import BODY, grant
from test_tenant_suspension_integrity import SITE, USERS, Boundary, context, migrate, sqlstate
from test_tenant_suspension_integrity import boundary as boundary

pytestmark = pytest.mark.skipif(
    "PMC_TEST_RUNTIME_DATABASE_URL" not in os.environ,
    reason="requires a dedicated disposable PostgreSQL fixture",
)
ENDPOINT = "/context/interested-parties"
PARTY = {**BODY, "classification": "supplier", "category": "", "requirements": "Legacy note."}
REQUIREMENT = {
    "id": "00000000-0000-4000-8000-000000000001",
    "statement": "Trace each received lot to its certificate.",
    "source": "Synthetic customer purchasing specification",
    "disposition": "pending",
    "rationale": "",
}
DECIDED = {
    **REQUIREMENT,
    "disposition": "addressed_by_qms",
    "rationale": "The receiving process will verify certificates against lot records.",
}
DECISION = {"note": "Reviewed with purchasing.", "review_due_on": "2099-06-01"}


def assignment(boundary: Boundary) -> None:
    grant(boundary, "member", "read", "manage")
    grant(boundary, "admin", "read", "review")


def test_individual_decisions_are_required_and_preserved(boundary: Boundary) -> None:
    assignment(boundary)
    draft = boundary.call(
        "POST",
        ENDPOINT,
        {**PARTY, "party_requirements": [REQUIREMENT]},
        role="member",
        expected=201,
    )
    path = f"{ENDPOINT}/{draft['id']}"
    review_path = f"{path}/review?unit_id={SITE}"
    boundary.call(
        "POST", review_path, {**DECISION, "expected_version": 1}, role="admin", expected=409
    )
    edited = {key: value for key, value in PARTY.items() if key != "unit_id"}
    boundary.call(
        "PATCH",
        f"{path}?unit_id={SITE}",
        {
            **edited,
            "expected_version": 1,
            "party_requirements": [
                {**DECIDED, "rationale": "\u0085\ufeff " + DECIDED["rationale"] + "\u001f"},
                {
                    **REQUIREMENT,
                    "id": str(uuid4()),
                    "statement": "Schedule quarterly commercial meetings.",
                    "disposition": "outside_qms",
                    "rationale": "Managed by the commercial contract.",
                },
            ],
        },
        role="member",
    )
    approved = boundary.call("POST", review_path, {**DECISION, "expected_version": 2}, role="admin")
    assert approved["status"] == "active" and approved["row_version"] == 3
    assert approved["party_requirements"][0] == DECIDED
    assert approved["party_requirements"][1]["disposition"] == "outside_qms"
    # A legacy client edits the party summary without sending the new fields.
    saved = boundary.call(
        "PATCH", f"{path}?unit_id={SITE}", {**edited, "expected_version": 3}, role="member"
    )
    assert saved["party_requirements"] == approved["party_requirements"]
    assert saved["status"] == "draft"
    history = boundary.call("GET", f"{path}/history?unit_id={SITE}", role="member")
    assert history[1]["snapshot"]["party_requirements"] == approved["party_requirements"]
    assert history[-1]["snapshot"]["party_requirements"] == [REQUIREMENT]


def test_documented_absence_and_contradictory_assessment(boundary: Boundary) -> None:
    assignment(boundary)
    draft = boundary.call("POST", ENDPOINT, PARTY, role="member", expected=201)
    path = f"{ENDPOINT}/{draft['id']}"
    review = f"{path}/review?unit_id={SITE}"
    boundary.call("POST", review, {**DECISION, "expected_version": 1}, role="admin", expected=409)
    edited = {key: value for key, value in PARTY.items() if key != "unit_id"}
    boundary.call(
        "PATCH",
        f"{path}?unit_id={SITE}",
        {
            **edited,
            "expected_version": 1,
            "relevance": "not_relevant",
            "party_requirements": [DECIDED],
        },
        role="member",
    )
    boundary.call("POST", review, {**DECISION, "expected_version": 2}, role="admin", expected=409)
    reason = "The review of the synthetic agreement found no requirements relevant to this scope."
    boundary.call(
        "PATCH",
        f"{path}?unit_id={SITE}",
        {
            **edited,
            "expected_version": 2,
            "party_requirements": [],
            "no_requirements_reason": reason,
        },
        role="member",
    )
    approved = boundary.call("POST", review, {**DECISION, "expected_version": 3}, role="admin")
    assert approved["no_requirements_reason"] == reason and approved["party_requirements"] == []


@pytest.mark.parametrize(
    "changes",
    [
        {"party_requirements": [REQUIREMENT, REQUIREMENT]},
        {"party_requirements": [{**DECIDED, "rationale": "\ufeff\u0085 "}]},
        {"party_requirements": [{**REQUIREMENT, "source": "before\u0000after"}]},
        {"party_requirements": [{**REQUIREMENT, "disposition": "certified"}]},
        {"party_requirements": [REQUIREMENT], "no_requirements_reason": "Conflicting account."},
    ],
)
def test_invalid_assessments_are_rejected(boundary: Boundary, changes: dict[str, object]) -> None:
    assignment(boundary)
    boundary.call("POST", ENDPOINT, {**PARTY, **changes}, role="member", expected=422)
    boundary.call(
        "POST",
        "/context/issues",
        {**BODY, "party_requirements": [REQUIREMENT]},
        role="member",
        expected=422,
    )
    assert boundary.call("GET", f"{ENDPOINT}?unit_id={SITE}", role="member") == []


def test_database_review_gate_and_downgrade_protect_history(boundary: Boundary) -> None:
    assignment(boundary)
    draft = boundary.call(
        "POST",
        ENDPOINT,
        {**PARTY, "party_requirements": [REQUIREMENT]},
        role="member",
        expected=201,
    )
    with boundary.runtime.begin() as db:
        context(db, USERS["admin"])
        db.execute(text("SELECT set_config('app.qms_context_command','reviewed',true)"))
        with pytest.raises(DBAPIError) as rejected, db.begin_nested():
            db.execute(
                text(
                    "UPDATE public.qms_context_records "
                    "SET row_version=2,decision_note='Review',review_due_on='2099-06-01' "
                    "WHERE id=:id"
                ),
                {"id": draft["id"]},
            )
        assert sqlstate(rejected.value) == "23514"
    edited = {key: value for key, value in PARTY.items() if key != "unit_id"}
    boundary.call(
        "PATCH",
        f"{ENDPOINT}/{draft['id']}?unit_id={SITE}",
        {**edited, "expected_version": 1, "party_requirements": []},
        role="member",
    )
    with boundary.admin.connect() as db:
        previous_head = db.scalar(text("SELECT version_num FROM alembic_version"))
    downgrade = migrate("0052_qms_context_register", "downgrade")
    assert (
        downgrade.returncode
        and "cannot discard interested party requirement history" in downgrade.stderr
    )
    with boundary.admin.connect() as db:
        assert db.scalar(text("SELECT version_num FROM alembic_version")) == previous_head
        assert db.scalar(text("SELECT count(*) FROM public.qms_context_revisions")) == 2


def test_upgrade_preserves_existing_party_and_snapshot(boundary: Boundary) -> None:
    assignment(boundary)
    revert = migrate("0052_qms_context_register", "downgrade")
    assert revert.returncode == 0, revert.stderr
    legacy_id = uuid4()
    try:
        with boundary.runtime.begin() as db:
            context(db, USERS["member"])
            db.execute(text("SELECT set_config('app.qms_context_command','created',true)"))
            db.execute(
                text("""
INSERT INTO public.qms_context_records(
 id,tenant_id,unit_id,kind,code,name,classification,category,relevance,description,
 requirements,evidence_summary,owner_user_id,review_due_on
) VALUES (
 :id,current_setting('app.tenant_id')::uuid,:unit,'interested-parties','PG-LEGACY',
 'Legacy appointed supplier','supplier','','relevant','Existing expectations',
 'Preserved free-text requirements','Existing notes',:owner,'2099-06-01'
)
"""),
                {"id": legacy_id, "unit": SITE, "owner": USERS["member"]},
            )
        with boundary.runtime.begin() as db:
            context(db, USERS["admin"])
            db.execute(text("SELECT set_config('app.qms_context_command','reviewed',true)"))
            db.execute(
                text(
                    "UPDATE public.qms_context_records "
                    "SET row_version=2, decision_note='Legacy review' WHERE id=:id"
                ),
                {"id": legacy_id},
            )
    finally:
        upgrade = migrate("head", "upgrade")
        assert upgrade.returncode == 0, upgrade.stderr
    detail = f"{ENDPOINT}/{legacy_id}"
    legacy = boundary.call("GET", f"{detail}?unit_id={SITE}", role="member")
    assert legacy["status"] == "active" and legacy["row_version"] == 2
    assert legacy["requirements"] == "Preserved free-text requirements"
    assert legacy["party_requirements"] == [] and legacy["no_requirements_reason"] == ""
    history = boundary.call("GET", f"{detail}/history?unit_id={SITE}", role="member")
    assert [revision["snapshot"]["row_version"] for revision in history] == [2, 1]
    assert all(
        revision["snapshot"]["requirements"] == legacy["requirements"] for revision in history
    )
    boundary.call(
        "POST",
        f"{detail}/review?unit_id={SITE}",
        {**DECISION, "expected_version": 2},
        role="admin",
        expected=409,
    )

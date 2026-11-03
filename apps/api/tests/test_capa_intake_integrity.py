"""CAPA intake provenance and authority in disposable PostgreSQL."""

from __future__ import annotations

import json
import os
from datetime import date
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException, Request
from pydantic import ValidationError
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from test_nonconformity_integrity import create as create_ncr
from test_process_integrity import actor, reset_process_records
from test_process_integrity import create as create_process
from test_risk_integrity import authenticated, current, grant
from test_risk_integrity import create as create_risk
from test_risk_integrity import seed_risks as seed_risks
from test_workflow_integrity import MEMBER, OTHER, OWNER, TENANT_B, UNIT, engine

from pmc_api import audit_service, capa
from pmc_api.models import QMSCAPA, QMSAccessGrant, QMSCAPAAction
from pmc_api.qms_access import revoke_grant

pytestmark = [
    pytest.mark.process_integrity,
    pytest.mark.skipif(
        "PMC_TEST_RUNTIME_DATABASE_URL" not in os.environ,
        reason="requires disposable PostgreSQL",
    ),
]


@pytest.fixture(autouse=True)
def clean_capa(seed_risks: None) -> None:
    reset_process_records()


def request() -> Request:
    return cast(Request, SimpleNamespace(state=SimpleNamespace(request_id=uuid4())))


def access(db: Session) -> list[QMSAccessGrant]:
    return grant(
        db,
        capabilities=(
            "processes.read",
            "ncr.read",
            "ncr.manage",
            "risks.read",
            "risks.manage",
            "capa.read",
            "capa.manage",
        ),
    )


def intake(db: Session, process_id: UUID, **changes: Any) -> QMSCAPA:
    current(db)
    values: dict[str, Any] = {
        "unit_id": UNIT,
        "process_id": process_id,
        "code": "CAPA-" + uuid4().hex[:8],
        "name": "Correct receiving control",
        "source_type": "other",
        "problem_statement": "Synthetic receiving condition requires investigation.",
        "owner_user_id": MEMBER,
        **changes,
    }
    return capa.create_capa(request(), capa.CAPAInput(**values), db, authenticated())


def test_capa_sources_are_exclusive_scoped_and_audited() -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        process = create_process(db)
        access(db)
        ncr = create_ncr(db, process)
        risk = create_risk(db, process)
        row = intake(db, process.id, source_type="ncr", source_ncr_id=ncr.id)
        assert row.state == "draft" and row.source_code == ncr.code
        assert row.source_state == ncr.state and row.source_risk_id is None
        risk_row = intake(db, process.id, source_type="risk", source_risk_id=risk.id)
        assert risk_row.source_code == risk.code and risk_row.source_state == risk.state
        current(db)
        assert db.scalar(select(QMSCAPA).where(QMSCAPA.id == row.id)) is not None
        current(db, OWNER)
        assert (
            db.scalar(
                text(
                    "SELECT count(*) FROM audit_events WHERE resource_id=:id "
                    "AND action='capa.created'"
                ),
                {"id": row.id},
            )
            == 1
        )
        current(db)
        with pytest.raises(ValidationError):
            capa.CAPAInput(
                unit_id=UNIT,
                process_id=process.id,
                code="BAD",
                name="Bad",
                source_type="ncr",
                source_ncr_id=ncr.id,
                source_risk_id=risk.id,
                problem_statement="Invalid double origin",
            )
        with pytest.raises(HTTPException) as wrong_scope:
            intake(db, process.id, source_type="risk", source_risk_id=uuid4())
        assert wrong_scope.value.status_code == 404


def test_capa_version_provenance_and_sql_state_are_guarded() -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        process = create_process(db)
        access(db)
        row = intake(db, process.id)
        capa_id = row.id
        current(db)
        updated = capa.update_capa(
            request(),
            capa_id,
            capa.CAPAPatch(expected_version=1, name="Improved receiving control"),
            db,
            authenticated(),
        )
        assert updated.row_version == 2
        with pytest.raises(HTTPException) as stale:
            capa.update_capa(
                request(),
                capa_id,
                capa.CAPAPatch(expected_version=1, name="Lost update"),
                db,
                authenticated(),
            )
        assert stale.value.status_code == 409
        db.rollback()
        current(db)
        for statement in (
            "UPDATE qms_capas SET state='analysis',row_version=row_version+1,"
            "updated_at=now() WHERE id=:id",
            "UPDATE qms_capas SET source_type='risk',source_risk_id=:other,"
            "row_version=row_version+1,updated_at=now() WHERE id=:id",
        ):
            with pytest.raises(DBAPIError):
                db.execute(text(statement), {"id": capa_id, "other": uuid4()})
                db.commit()
            db.rollback()
            current(db)
        current(db, OWNER)
        assert (
            db.scalar(
                text(
                    "SELECT count(*) FROM audit_events WHERE resource_id=:id "
                    "AND action='capa.updated'"
                ),
                {"id": capa_id},
            )
            == 1
        )


def test_capa_origin_read_revocation_hides_existing_record() -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        process = create_process(db)
        grants = access(db)
        ncr = create_ncr(db, process)
        row = intake(db, process.id, source_type="ncr", source_ncr_id=ncr.id)
        ncr_read = next(item for item in grants if item.capability == "ncr.read")
        current(db, OWNER)
        revoke_grant(db, actor(OWNER, "owner"), uuid4(), ncr_read.id)
        current(db)
        assert db.scalar(select(QMSCAPA).where(QMSCAPA.id == row.id)) is None
        with pytest.raises(HTTPException) as hidden:
            capa.get_capa(db, authenticated(), row.id)
        assert hidden.value.status_code == 404


def test_capa_audit_failure_rolls_back_creation(monkeypatch: pytest.MonkeyPatch) -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        process = create_process(db)
        access(db)
        code = "CAPA-" + uuid4().hex[:8]

        def fail(*args: object, **kwargs: object) -> None:
            raise RuntimeError("audit unavailable")

        monkeypatch.setattr(audit_service, "record_capa", fail)
        with pytest.raises(RuntimeError):
            intake(db, process.id, code=code)
        current(db)
        assert db.scalar(select(QMSCAPA).where(QMSCAPA.code == code)) is None


@pytest.mark.parametrize(
    ("method", "fields"),
    [
        ("5why", {"why1", "why2", "why3", "why4", "why5"}),
        ("fishbone", {"people", "process", "equipment", "materials", "measurement", "environment"}),
        ("is_is_not", {"what", "where", "when", "extent"}),
        ("other", set()),
    ],
)
def test_analysis_starts_with_fixed_method_structure_and_locks_method(
    method: str, fields: set[str]
) -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        process = create_process(db)
        access(db)
        row = intake(db, process.id, root_cause_method=method)
        current(db)
        row = capa.start_analysis(
            request(), row.id, capa.CAPAStartAnalysis(expected_version=1), db, authenticated()
        )
        assert row.state == "analysis" and set(row.analysis_data) == fields
        assert row.analysis_started_by_user_id == MEMBER and row.analysis_started_at is not None
        with pytest.raises(HTTPException) as locked:
            capa.update_capa(
                request(),
                row.id,
                capa.CAPAPatch(expected_version=row.row_version, root_cause_method="other"),
                db,
                authenticated(),
            )
        assert locked.value.status_code == 409
        db.rollback()
        current(db)
        replacement = "5why" if method == "other" else "other"
        with pytest.raises(DBAPIError):
            db.execute(
                text(
                    "UPDATE qms_capas SET root_cause_method=:method,"
                    "row_version=row_version+1,updated_at=now() WHERE id=:id"
                ),
                {"id": row.id, "method": replacement},
            )
            db.commit()
        db.rollback()


def test_analysis_rejects_malformed_structure_and_preserves_hashed_history() -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        process = create_process(db)
        access(db)
        row = intake(db, process.id, root_cause_method="5why")
        current(db)
        row = capa.start_analysis(
            request(), row.id, capa.CAPAStartAnalysis(expected_version=1), db, authenticated()
        )
        capa_id = row.id
        with pytest.raises(HTTPException) as malformed:
            capa.update_analysis(
                request(),
                capa_id,
                capa.CAPAAnalysisInput(expected_version=2, analysis_data={"why1": "Because"}),
                db,
                authenticated(),
            )
        assert malformed.value.status_code == 422
        current(db)
        filled = dict(row.analysis_data)
        filled["why1"] = "Synthetic handoff was unclear."
        filled["why2"] = "A fictional control lacked an owner."
        row = capa.update_analysis(
            request(),
            capa_id,
            capa.CAPAAnalysisInput(
                expected_version=2,
                analysis_data=filled,
                analysis_summary="Synthetic investigation summary.",
                verified_root_cause="Fictional ownership gap.",
            ),
            db,
            authenticated(),
        )
        assert row.row_version == 3 and row.analysis_data["why1"] == filled["why1"]
        with pytest.raises(HTTPException) as stale:
            capa.update_analysis(
                request(),
                capa_id,
                capa.CAPAAnalysisInput(expected_version=2, analysis_data=filled),
                db,
                authenticated(),
            )
        assert stale.value.status_code == 409
        db.rollback()
        current(db)
        with pytest.raises(DBAPIError):
            db.execute(
                text(
                    "UPDATE qms_capas SET analysis_summary='Bypass',"
                    "row_version=row_version+1,updated_at=now() WHERE id=:id"
                ),
                {"id": capa_id},
            )
            db.commit()
        db.rollback()
        current(db, OWNER)
        events = list(
            db.execute(
                text(
                    "SELECT action,new_values FROM audit_events WHERE resource_id=:id "
                    "ORDER BY occurred_at,id"
                ),
                {"id": capa_id},
            )
        )
        assert {event.action for event in events} >= {
            "capa.analysis_started",
            "capa.analysis_updated",
        }
        payload = str([event.new_values for event in events])
        assert "analysis_data_hash" in payload
        assert "Synthetic handoff" not in payload and "Fictional ownership gap" not in payload


def test_analysis_requires_selected_method_and_manage_authority() -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        process = create_process(db)
        grants = access(db)
        row = intake(db, process.id)
        current(db)
        with pytest.raises(HTTPException) as missing:
            capa.start_analysis(
                request(), row.id, capa.CAPAStartAnalysis(expected_version=1), db, authenticated()
            )
        assert missing.value.status_code == 422
        row = capa.update_capa(
            request(),
            row.id,
            capa.CAPAPatch(expected_version=1, root_cause_method="fishbone"),
            db,
            authenticated(),
        )
        manage = next(item for item in grants if item.capability == "capa.manage")
        current(db, OWNER)
        revoke_grant(db, actor(OWNER, "owner"), uuid4(), manage.id)
        current(db)
        with pytest.raises(HTTPException) as denied:
            capa.start_analysis(
                request(),
                row.id,
                capa.CAPAStartAnalysis(expected_version=row.row_version),
                db,
                authenticated(),
            )
        assert denied.value.status_code in {403, 404}


def test_is_is_not_accepts_bounded_multibyte_answers() -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        process = create_process(db)
        access(db)
        row = intake(db, process.id, root_cause_method="is_is_not")
        current(db)
        row = capa.start_analysis(
            request(), row.id, capa.CAPAStartAnalysis(expected_version=1), db, authenticated()
        )
        data: dict[str, object] = {
            dimension: {
                field: "á" * 1000 for field in ("observed", "not_observed", "distinction", "change")
            }
            for dimension in ("what", "where", "when", "extent")
        }
        row = capa.update_analysis(
            request(),
            row.id,
            capa.CAPAAnalysisInput(expected_version=2, analysis_data=data),
            db,
            authenticated(),
        )
        assert row.row_version == 3
        assert row.analysis_data == data


def test_fishbone_supports_multiple_causes_and_requires_evidence_for_confirmation() -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        process = create_process(db)
        access(db)
        row = intake(db, process.id, root_cause_method="fishbone")
        current(db)
        row = capa.start_analysis(
            request(), row.id, capa.CAPAStartAnalysis(expected_version=1), db, authenticated()
        )
        assert row.analysis_data["people"] == []
        data = dict(row.analysis_data)
        people_causes: list[dict[str, object]] = [
            {
                "statement": "Synthetic role handoff was unclear",
                "evidence": "Fictional review log 1",
                "rationale": "The same omission appeared twice",
                "confirmed": True,
            },
            {
                "statement": "Synthetic training gap",
                "evidence": "",
                "rationale": "",
                "confirmed": False,
            },
        ]
        data["people"] = people_causes
        data["process"] = [
            {
                "statement": "Draft procedure was ambiguous",
                "evidence": "",
                "rationale": "",
                "confirmed": False,
            }
        ]
        row = capa.update_analysis(
            request(),
            row.id,
            capa.CAPAAnalysisInput(expected_version=2, analysis_data=data),
            db,
            authenticated(),
        )
        saved_people = cast(list[dict[str, object]], row.analysis_data["people"])
        assert row.row_version == 3 and len(saved_people) == 2
        assert saved_people[0]["confirmed"] is True
        capa_id = row.id
        invalid = dict(data)
        invalid["people"] = [{**people_causes[0], "evidence": ""}]
        with pytest.raises(HTTPException) as missing_evidence:
            capa.update_analysis(
                request(),
                row.id,
                capa.CAPAAnalysisInput(expected_version=3, analysis_data=invalid),
                db,
                authenticated(),
            )
        assert missing_evidence.value.status_code == 422
        db.rollback()
        current(db)
        db.execute(text("SELECT set_config('app.capa_analysis_command','edit',true)"))
        with pytest.raises(DBAPIError):
            db.execute(
                text(
                    "UPDATE qms_capas SET analysis_data=jsonb_set(analysis_data,"
                    "'{people,0,rationale}', '\"\"'::jsonb),row_version=row_version+1,"
                    "updated_at=now()+interval '1 second' WHERE id=:id"
                ),
                {"id": capa_id},
            )
            db.commit()
        db.rollback()
        current(db, OWNER)
        events = list(
            db.execute(
                text(
                    "SELECT new_values FROM audit_events WHERE resource_id=:id "
                    "AND action='capa.analysis_updated'"
                ),
                {"id": capa_id},
            )
        )
        assert len(events) == 1
        assert "Fictional review" not in str(events[0].new_values)


def test_legacy_fishbone_text_can_be_replaced_by_structured_causes() -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        process = create_process(db)
        access(db)
        row = intake(db, process.id, root_cause_method="fishbone")
        current(db)
        row = capa.start_analysis(
            request(), row.id, capa.CAPAStartAnalysis(expected_version=1), db, authenticated()
        )
        legacy = {category: "" for category in row.analysis_data}
        legacy["people"] = "Saved before the structured editor"
        current(db)
        db.execute(text("SELECT set_config('app.capa_analysis_command','edit',true)"))
        updated_id = db.scalar(
            text(
                "UPDATE qms_capas SET analysis_data=CAST(:analysis AS jsonb),"
                "row_version=row_version+1,"
                "updated_at=updated_at+interval '1 microsecond' WHERE id=:id RETURNING id"
            ),
            {"analysis": json.dumps(legacy), "id": row.id},
        )
        assert updated_id == row.id
        db.commit()
        structured: dict[str, object] = {category: [] for category in legacy}
        structured["people"] = [
            {
                "statement": legacy["people"],
                "evidence": "",
                "rationale": "",
                "confirmed": False,
            }
        ]
        current(db)
        updated = capa.update_analysis(
            request(),
            row.id,
            capa.CAPAAnalysisInput(expected_version=3, analysis_data=structured),
            db,
            authenticated(),
        )
        assert updated.row_version == 4 and updated.analysis_data == structured


@pytest.mark.parametrize("method", ["5why", "fishbone", "is_is_not", "other"])
def test_plan_requires_completed_method_and_locks_verified_investigation(method: str) -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        process = create_process(db)
        access(db)
        row = intake(db, process.id, root_cause_method=method)
        current(db)
        row = capa.start_analysis(
            request(), row.id, capa.CAPAStartAnalysis(expected_version=1), db, authenticated()
        )
        data = dict(row.analysis_data)
        if method == "5why":
            data["why2"] = "Synthetic gap after a blank first answer"
        elif method == "fishbone":
            data["people"] = [
                {
                    "statement": "Synthetic handoff gap",
                    "evidence": "",
                    "rationale": "",
                    "confirmed": False,
                }
            ]
        elif method == "is_is_not":
            data = {
                dimension: {
                    field: "Synthetic observation"
                    for field in ("observed", "not_observed", "distinction", "change")
                }
                for dimension in ("what", "where", "when", "extent")
            }
            cast(dict[str, str], data["extent"])["distinction"] = ""
        row = capa.update_analysis(
            request(),
            row.id,
            capa.CAPAAnalysisInput(
                expected_version=2,
                analysis_data=data,
                analysis_summary="Synthetic investigation completed.",
                verified_root_cause="Synthetic root cause verified.",
            ),
            db,
            authenticated(),
        )
        with pytest.raises(HTTPException) as incomplete:
            capa.start_plan(
                request(),
                row.id,
                capa.CAPAStartPlan(
                    expected_version=row.row_version, plan_summary="Correct the control."
                ),
                db,
                authenticated(),
            )
        assert incomplete.value.status_code == 422
        db.rollback()
        if method == "5why":
            data["why1"] = "Synthetic control did not assign responsibility"
        elif method == "fishbone":
            data["people"] = [
                {
                    "statement": "Synthetic handoff gap",
                    "evidence": "Fictional review log",
                    "rationale": "Repeated in two fictional cases",
                    "confirmed": True,
                }
            ]
        elif method == "is_is_not":
            cast(dict[str, str], data["extent"])["distinction"] = "Synthetic distinction"
        current(db)
        row = capa.update_analysis(
            request(),
            row.id,
            capa.CAPAAnalysisInput(
                expected_version=3,
                analysis_data=data,
                analysis_summary="Synthetic investigation completed.",
                verified_root_cause="Synthetic root cause verified.",
                other_method_name="Synthetic alternate method" if method == "other" else "",
            ),
            db,
            authenticated(),
        )
        current(db)
        with pytest.raises(DBAPIError):
            db.execute(
                text(
                    "UPDATE qms_capas SET state='action_planned',plan_summary='Bypass',"
                    "planned_by_user_id=:actor,planned_at=now(),row_version=row_version+1,"
                    "updated_at=updated_at+interval '1 second' WHERE id=:id"
                ),
                {"id": row.id, "actor": MEMBER},
            )
            db.commit()
        db.rollback()
        current(db)
        planned = capa.start_plan(
            request(),
            row.id,
            capa.CAPAStartPlan(expected_version=4, plan_summary="Correct the synthetic control."),
            db,
            authenticated(),
        )
        assert planned.state == "action_planned" and planned.row_version == 5
        assert planned.planned_by_user_id == MEMBER and planned.planned_at is not None
        with pytest.raises(HTTPException) as stale:
            capa.start_plan(
                request(),
                planned.id,
                capa.CAPAStartPlan(expected_version=4, plan_summary="Duplicate"),
                db,
                authenticated(),
            )
        assert stale.value.status_code == 409
        with pytest.raises(HTTPException) as locked:
            capa.update_analysis(
                request(),
                planned.id,
                capa.CAPAAnalysisInput(expected_version=5, analysis_data=data),
                db,
                authenticated(),
            )
        assert locked.value.status_code == 409
        current(db, OWNER)
        event = db.execute(
            text(
                "SELECT new_values FROM audit_events WHERE resource_id=:id "
                "AND action='capa.plan_started' "
                "ORDER BY occurred_at DESC LIMIT 1"
            ),
            {"id": row.id},
        ).one()
        payload = event.new_values
        assert payload["state"] == "action_planned" and "plan_summary_hash" in payload
        assert "Correct the synthetic control" not in str(payload)


def test_capa_action_register_versions_owner_and_audit() -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        process = create_process(db)
        access(db)
        parent = intake(db, process.id, root_cause_method="5why")
        current(db)
        parent = capa.start_analysis(
            request(), parent.id, capa.CAPAStartAnalysis(expected_version=1), db, authenticated()
        )
        data = dict(parent.analysis_data)
        data["why1"] = "Fictional owner assignment omitted."
        parent = capa.update_analysis(
            request(),
            parent.id,
            capa.CAPAAnalysisInput(
                expected_version=2,
                analysis_data=data,
                analysis_summary="Synthetic review.",
                verified_root_cause="Synthetic owner gap.",
            ),
            db,
            authenticated(),
        )
        parent = capa.start_plan(
            request(),
            parent.id,
            capa.CAPAStartPlan(expected_version=3, plan_summary="Assign and verify ownership."),
            db,
            authenticated(),
        )
        current(db)
        with pytest.raises(HTTPException) as invalid_owner:
            capa.create_capa_action(
                request(),
                parent.id,
                capa.CAPAActionCreate(
                    expected_capa_version=4,
                    title="Assign owner",
                    description="Document responsible person for fictional control.",
                    owner_user_id=uuid4(),
                    due_date=date.today(),
                ),
                db,
                authenticated(),
            )
        assert invalid_owner.value.status_code == 409
        current(db)
        action = capa.create_capa_action(
            request(),
            parent.id,
            capa.CAPAActionCreate(
                expected_capa_version=4,
                title="Assign owner",
                description="Document responsible person for fictional control.",
                owner_user_id=MEMBER,
                due_date=date.today(),
            ),
            db,
            authenticated(),
        )
        assert action.state == "open" and action.row_version == 1
        current(db)
        refreshed_parent = db.scalar(select(QMSCAPA).where(QMSCAPA.id == parent.id))
        assert refreshed_parent is not None and refreshed_parent.row_version == 5
        assert [item.id for item in capa.list_capa_actions(parent.id, db, authenticated())] == [
            action.id
        ]
        assert capa.get_capa_action(parent.id, action.id, db, authenticated()).id == action.id
        current(db, OTHER, TENANT_B)
        with pytest.raises(HTTPException) as hidden_action:
            capa.get_capa_action(parent.id, action.id, db, authenticated(OTHER, TENANT_B))
        assert hidden_action.value.status_code == 404
        current(db)
        with pytest.raises(HTTPException) as stale:
            capa.create_capa_action(
                request(),
                parent.id,
                capa.CAPAActionCreate(
                    expected_capa_version=4,
                    title="Stale",
                    description="Stale plan edit.",
                    owner_user_id=MEMBER,
                    due_date=date.today(),
                ),
                db,
                authenticated(),
            )
        assert stale.value.status_code == 409
        current(db)
        updated = capa.update_capa_action(
            request(),
            parent.id,
            action.id,
            capa.CAPAActionPatch(
                expected_capa_version=5,
                expected_action_version=1,
                description="Revised synthetic owner assignment.",
            ),
            db,
            authenticated(),
        )
        assert updated.row_version == 2
        current(db)
        refreshed_parent = db.scalar(select(QMSCAPA).where(QMSCAPA.id == parent.id))
        assert refreshed_parent is not None and refreshed_parent.row_version == 6
        with pytest.raises(HTTPException) as stale_action:
            capa.update_capa_action(
                request(),
                parent.id,
                action.id,
                capa.CAPAActionPatch(
                    expected_capa_version=6,
                    expected_action_version=1,
                    title="Lost update",
                ),
                db,
                authenticated(),
            )
        assert stale_action.value.status_code == 409
        db.rollback()
        current(db)
        with pytest.raises(DBAPIError):
            db.execute(
                text(
                    "UPDATE qms_capa_actions SET title='Bypass',row_version=row_version+1,"
                    "updated_at=updated_at+interval '1 second' WHERE id=:id"
                ),
                {"id": action.id},
            )
            db.commit()
        db.rollback()
        current(db)
        persisted_action = db.scalar(select(QMSCAPAAction).where(QMSCAPAAction.id == action.id))
        assert persisted_action is not None and persisted_action.title == "Assign owner"
        current(db, OWNER)
        events = list(
            db.execute(
                text(
                    "SELECT action,new_values FROM audit_events WHERE resource_id=:id "
                    "ORDER BY occurred_at,id"
                ),
                {"id": action.id},
            )
        )
        assert {event.action for event in events} == {"capa.action_created", "capa.action_updated"}
        assert all("description_hash" in event.new_values for event in events)
        assert "Revised synthetic" not in str([event.new_values for event in events])


def test_capa_actions_execute_with_independent_review_and_locked_plan() -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        process = create_process(db)
        access(db)
        parent = intake(db, process.id, root_cause_method="other")
        current(db)
        parent = capa.start_analysis(
            request(), parent.id, capa.CAPAStartAnalysis(expected_version=1), db, authenticated()
        )
        parent = capa.update_analysis(
            request(),
            parent.id,
            capa.CAPAAnalysisInput(
                expected_version=2,
                analysis_data={},
                analysis_summary="Synthetic analysis.",
                verified_root_cause="Synthetic cause.",
                other_method_name="Synthetic method",
            ),
            db,
            authenticated(),
        )
        parent = capa.start_plan(
            request(),
            parent.id,
            capa.CAPAStartPlan(expected_version=3, plan_summary="Assign synthetic action."),
            db,
            authenticated(),
        )
        with pytest.raises(HTTPException) as empty_plan:
            capa.start_implementation(
                request(),
                parent.id,
                capa.CAPAStartImplementation(expected_version=4),
                db,
                authenticated(),
            )
        assert empty_plan.value.status_code == 422
        current(db)
        action = capa.create_capa_action(
            request(),
            parent.id,
            capa.CAPAActionCreate(
                expected_capa_version=4,
                title="Assign synthetic control",
                description="Document a fictional owner.",
                owner_user_id=MEMBER,
                due_date=date.today(),
            ),
            db,
            authenticated(),
        )
        action_id = action.id
        current(db)
        parent = capa.start_implementation(
            request(),
            parent.id,
            capa.CAPAStartImplementation(expected_version=5),
            db,
            authenticated(),
        )
        assert parent.state == "implementation" and parent.row_version == 6
        assert parent.implementation_started_by_user_id == MEMBER
        with pytest.raises(HTTPException) as pending_action:
            capa.start_effectiveness_review(
                request(),
                parent.id,
                capa.CAPAStartEffectivenessReview(expected_version=6),
                db,
                authenticated(),
            )
        assert pending_action.value.status_code == 422
        with pytest.raises(HTTPException) as locked:
            capa.update_capa_action(
                request(),
                parent.id,
                action_id,
                capa.CAPAActionPatch(
                    expected_capa_version=6,
                    expected_action_version=1,
                    title="Changed after implementation",
                ),
                db,
                authenticated(),
            )
        assert locked.value.status_code == 409
        current(db)
        action = capa.transition_capa_action(
            request(),
            parent.id,
            action.id,
            capa.CAPAActionTransition(
                expected_capa_version=6,
                expected_action_version=1,
                target_state="in_progress",
            ),
            db,
            authenticated(),
        )
        assert action.state == "in_progress" and action.row_version == 2
        current(db)
        action = capa.transition_capa_action(
            request(),
            parent.id,
            action.id,
            capa.CAPAActionTransition(
                expected_capa_version=7,
                expected_action_version=2,
                target_state="completed",
            ),
            db,
            authenticated(),
        )
        assert action.state == "completed" and action.completed_by_user_id == MEMBER
        grant(db, capabilities=("capa.review",))
        current(db)
        with pytest.raises(HTTPException) as self_review:
            capa.transition_capa_action(
                request(),
                parent.id,
                action.id,
                capa.CAPAActionTransition(
                    expected_capa_version=8,
                    expected_action_version=3,
                    target_state="verified",
                    verification_notes="Self verification",
                ),
                db,
                authenticated(),
            )
        assert self_review.value.status_code == 403
        db.rollback()
        current(db)
        db.execute(text("SELECT set_config('app.capa_analysis_command','progress',true)"))
        with pytest.raises(DBAPIError):
            db.execute(
                text(
                    "UPDATE qms_capa_actions SET state='verified',"
                    "verified_by_user_id=:actor,verified_at=now(),verification_notes='Bypass',"
                    "row_version=row_version+1,updated_at=updated_at+interval '1 second' "
                    "WHERE id=:id"
                ),
                {"id": action.id, "actor": MEMBER},
            )
            db.commit()
        db.rollback()
        grant(db, user=OTHER, capabilities=("capa.read", "capa.review"))
        current(db, OTHER)
        verified = capa.transition_capa_action(
            request(),
            parent.id,
            action.id,
            capa.CAPAActionTransition(
                expected_capa_version=8,
                expected_action_version=3,
                target_state="verified",
                verification_notes="Independent synthetic review.",
            ),
            db,
            authenticated(OTHER),
        )
        assert verified.state == "verified" and verified.verified_by_user_id == OTHER
        current(db)
        refreshed_parent = db.scalar(select(QMSCAPA).where(QMSCAPA.id == parent.id))
        assert refreshed_parent is not None and refreshed_parent.row_version == 9
        with pytest.raises(DBAPIError):
            db.execute(
                text(
                    "UPDATE qms_capas SET state='effectiveness_review',"
                    "review_started_by_user_id=:actor,review_started_at=now(),"
                    "row_version=row_version+1,updated_at=updated_at+interval '1 second' "
                    "WHERE id=:id"
                ),
                {"id": parent.id, "actor": MEMBER},
            )
            db.commit()
        db.rollback()
        current(db)
        review = capa.start_effectiveness_review(
            request(),
            parent.id,
            capa.CAPAStartEffectivenessReview(expected_version=9),
            db,
            authenticated(),
        )
        assert review.state == "effectiveness_review" and review.row_version == 10
        assert review.review_started_by_user_id == MEMBER
        with pytest.raises(HTTPException) as frozen:
            capa.transition_capa_action(
                request(),
                parent.id,
                action_id,
                capa.CAPAActionTransition(
                    expected_capa_version=10,
                    expected_action_version=4,
                    target_state="cancelled",
                    cancellation_reason="Late change",
                ),
                db,
                authenticated(),
            )
        assert frozen.value.status_code == 409
        current(db, OTHER)
        result = capa.record_effectiveness_review(
            request(),
            parent.id,
            capa.CAPAEffectivenessDecision(
                expected_version=10,
                decision="effective",
                notes="Synthetic corrective action prevented recurrence.",
            ),
            db,
            authenticated(OTHER),
        )
        assert result.cycle_number == 1 and result.decision == "effective"
        current(db, OTHER)
        effective = capa.get_capa(db, authenticated(OTHER), parent.id)
        assert effective.state == "effective" and effective.row_version == 11
        assert effective.effective_by_user_id == OTHER
        assert [
            review.id
            for review in capa.list_effectiveness_reviews(parent.id, db, authenticated(OTHER))
        ] == [result.id]
        closed = capa.close_capa(
            request(),
            parent.id,
            capa.CAPAClose(expected_version=11, closure_notes="Synthetic closure approved."),
            db,
            authenticated(OTHER),
        )
        assert closed.state == "closed" and closed.row_version == 12
        with pytest.raises(HTTPException) as terminal:
            capa.close_capa(
                request(),
                parent.id,
                capa.CAPAClose(expected_version=12, closure_notes="Duplicate"),
                db,
                authenticated(OTHER),
            )
        assert terminal.value.status_code == 409
        current(db, OWNER)
        actions = [
            event.action
            for event in db.execute(
                text(
                    "SELECT action FROM audit_events WHERE resource_id=:id ORDER BY occurred_at,id"
                ),
                {"id": action_id},
            )
        ]
        assert actions.count("capa.action_transitioned") == 3
        review_event = db.execute(
            text(
                "SELECT new_values FROM audit_events WHERE resource_id=:id "
                "AND action='capa.effectiveness_recorded'"
            ),
            {"id": result.id},
        ).one()
        assert "notes_hash" in review_event.new_values
        assert "prevented recurrence" not in str(review_event.new_values)


def test_ineffective_review_preserves_cycle_and_requires_new_action() -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        process = create_process(db)
        access(db)
        parent = intake(db, process.id, root_cause_method="other")
        current(db)
        parent = capa.start_analysis(
            request(), parent.id, capa.CAPAStartAnalysis(expected_version=1), db, authenticated()
        )
        parent = capa.update_analysis(
            request(),
            parent.id,
            capa.CAPAAnalysisInput(
                expected_version=2,
                analysis_data={},
                analysis_summary="Synthetic summary",
                verified_root_cause="Synthetic cause",
                other_method_name="Synthetic method",
            ),
            db,
            authenticated(),
        )
        parent = capa.start_plan(
            request(),
            parent.id,
            capa.CAPAStartPlan(expected_version=3, plan_summary="Synthetic correction"),
            db,
            authenticated(),
        )
        first = capa.create_capa_action(
            request(),
            parent.id,
            capa.CAPAActionCreate(
                expected_capa_version=4,
                title="Initial correction",
                description="Synthetic initial correction",
                owner_user_id=MEMBER,
                due_date=date.today(),
            ),
            db,
            authenticated(),
        )
        parent = capa.start_implementation(
            request(),
            parent.id,
            capa.CAPAStartImplementation(expected_version=5),
            db,
            authenticated(),
        )
        first = capa.transition_capa_action(
            request(),
            parent.id,
            first.id,
            capa.CAPAActionTransition(
                expected_capa_version=6,
                expected_action_version=1,
                target_state="completed",
            ),
            db,
            authenticated(),
        )
        parent = capa.start_effectiveness_review(
            request(),
            parent.id,
            capa.CAPAStartEffectivenessReview(expected_version=7),
            db,
            authenticated(),
        )
        grant(db, user=OTHER, capabilities=("capa.read", "capa.review"))
        current(db, OTHER)
        first_review = capa.record_effectiveness_review(
            request(),
            parent.id,
            capa.CAPAEffectivenessDecision(
                expected_version=8,
                decision="ineffective",
                notes="Fictional issue recurred; add another control.",
            ),
            db,
            authenticated(OTHER),
        )
        assert first_review.cycle_number == 1 and first_review.decision == "ineffective"
        current(db)
        replanned = capa.get_capa(db, authenticated(), parent.id)
        assert replanned.state == "action_planned" and replanned.row_version == 9
        assert replanned.implementation_started_at is None and replanned.review_started_at is None
        with pytest.raises(HTTPException) as no_new_action:
            capa.start_implementation(
                request(),
                parent.id,
                capa.CAPAStartImplementation(expected_version=9),
                db,
                authenticated(),
            )
        assert no_new_action.value.status_code == 422
        second = capa.create_capa_action(
            request(),
            parent.id,
            capa.CAPAActionCreate(
                expected_capa_version=9,
                title="Additional prevention",
                description="Synthetic additional prevention",
                owner_user_id=MEMBER,
                due_date=date.today(),
            ),
            db,
            authenticated(),
        )
        parent = capa.start_implementation(
            request(),
            parent.id,
            capa.CAPAStartImplementation(expected_version=10),
            db,
            authenticated(),
        )
        second = capa.transition_capa_action(
            request(),
            parent.id,
            second.id,
            capa.CAPAActionTransition(
                expected_capa_version=11,
                expected_action_version=1,
                target_state="completed",
            ),
            db,
            authenticated(),
        )
        parent = capa.start_effectiveness_review(
            request(),
            parent.id,
            capa.CAPAStartEffectivenessReview(expected_version=12),
            db,
            authenticated(),
        )
        current(db, OTHER)
        second_review = capa.record_effectiveness_review(
            request(),
            parent.id,
            capa.CAPAEffectivenessDecision(
                expected_version=13,
                decision="effective",
                notes="Synthetic follow-up found no recurrence.",
            ),
            db,
            authenticated(OTHER),
        )
        assert second_review.cycle_number == 2 and second_review.active_action_count == 2
        history = capa.list_effectiveness_reviews(parent.id, db, authenticated(OTHER))
        assert [(item.cycle_number, item.decision) for item in history] == [
            (2, "effective"),
            (1, "ineffective"),
        ]
        assert first.state == "completed" and second.state == "completed"
        cancelled = capa.cancel_capa(
            request(),
            parent.id,
            capa.CAPACancel(expected_version=14, reason="Synthetic post-review cancellation."),
            db,
            authenticated(OTHER),
        )
        assert cancelled.state == "cancelled" and cancelled.effective_at is not None
        assert cancelled.cancelled_by_user_id == OTHER


def test_capa_cancellation_requires_reviewer_reason_and_is_terminal() -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        process = create_process(db)
        access(db)
        grant(db, user=OTHER, capabilities=("capa.read", "capa.review"))
        draft = intake(db, process.id, root_cause_method="other")
        draft_id = draft.id
        current(db, OTHER)
        with pytest.raises(ValidationError):
            capa.CAPACancel(expected_version=1, reason="   ")
        cancelled = capa.cancel_capa(
            request(),
            draft.id,
            capa.CAPACancel(expected_version=1, reason="Synthetic duplicate intake."),
            db,
            authenticated(OTHER),
        )
        assert cancelled.state == "cancelled" and cancelled.row_version == 2
        assert cancelled.analysis_started_at is None and cancelled.cancelled_by_user_id == OTHER
        with pytest.raises(HTTPException) as terminal:
            capa.cancel_capa(
                request(),
                draft.id,
                capa.CAPACancel(expected_version=2, reason="Second decision"),
                db,
                authenticated(OTHER),
            )
        assert terminal.value.status_code == 409
        current(db)
        with pytest.raises(DBAPIError):
            db.execute(
                text(
                    "UPDATE qms_capas SET name='Bypass',row_version=row_version+1,"
                    "updated_at=updated_at+interval '1 second' WHERE id=:id"
                ),
                {"id": draft.id},
            )
            db.commit()
        db.rollback()
        current(db)
        analysis = intake(db, process.id, root_cause_method="other")
        analysis = capa.start_analysis(
            request(),
            analysis.id,
            capa.CAPAStartAnalysis(expected_version=1),
            db,
            authenticated(),
        )
        current(db, OTHER)
        from_analysis = capa.cancel_capa(
            request(),
            analysis.id,
            capa.CAPACancel(expected_version=2, reason="Synthetic investigation withdrawn."),
            db,
            authenticated(OTHER),
        )
        assert from_analysis.analysis_started_at is not None
        assert from_analysis.plan_summary == "" and from_analysis.state == "cancelled"
        current(db, OWNER)
        event = db.execute(
            text(
                "SELECT new_values FROM audit_events "
                "WHERE resource_id=:id AND action='capa.cancelled'"
            ),
            {"id": draft_id},
        ).one()
        assert "cancellation_reason_hash" in event.new_values
        assert "Synthetic duplicate intake" not in str(event.new_values)


def test_capa_external_source_reference_is_hashed_and_frozen_after_draft() -> None:
    with Session(engine("PMC_TEST_RUNTIME_DATABASE_URL"), expire_on_commit=False) as db:
        process = create_process(db)
        access(db)
        row = intake(
            db,
            process.id,
            root_cause_method="other",
            source_reference="  External case 2026-41  ",
        )
        row_id = row.id
        assert row.source_reference == "External case 2026-41"
        with pytest.raises(ValidationError):
            capa.CAPAPatch(expected_version=1, source_reference=None)
        current(db)
        with pytest.raises(DBAPIError):
            db.execute(
                text(
                    "UPDATE qms_capas SET source_reference='Unrecorded draft change',"
                    "row_version=row_version+1,updated_at=updated_at+interval '1 second'"
                    " WHERE id=:id"
                ),
                {"id": row_id},
            )
            db.commit()
        db.rollback()
        current(db)
        edited = capa.update_capa(
            request(),
            row_id,
            capa.CAPAPatch(expected_version=1, source_reference="Revised case 2026-41"),
            db,
            authenticated(),
        )
        assert edited.source_reference == "Revised case 2026-41"
        analysis = capa.start_analysis(
            request(), row_id, capa.CAPAStartAnalysis(expected_version=2), db, authenticated()
        )
        assert analysis.state == "analysis"
        with pytest.raises(HTTPException) as locked:
            capa.update_capa(
                request(),
                row_id,
                capa.CAPAPatch(expected_version=3, source_reference="Changed after analysis"),
                db,
                authenticated(),
            )
        assert locked.value.status_code == 409
        current(db)
        with pytest.raises(DBAPIError):
            db.execute(
                text(
                    "UPDATE qms_capas SET source_reference='SQL bypass',"
                    "row_version=row_version+1,updated_at=updated_at+interval '1 second'"
                    " WHERE id=:id"
                ),
                {"id": row_id},
            )
            db.commit()
        db.rollback()
        current(db, OWNER)
        event = db.execute(
            text(
                "SELECT new_values FROM audit_events WHERE resource_id=:id "
                "AND action='capa.updated'"
            ),
            {"id": row_id},
        ).one()
        assert "source_reference_hash" in event.new_values
        assert "Revised case 2026-41" not in str(event.new_values)

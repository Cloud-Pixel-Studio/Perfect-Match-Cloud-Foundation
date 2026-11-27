# ruff: noqa: E501, S608 -- fixed fixture SQL and allowlisted kind identifiers.
"""HTTP and direct SQL evidence from disposable synthetic PostgreSQL only."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from test_qms_project_integrity import create, grant
from test_tenant_suspension_integrity import B_SITE, SITE, USERS, A, B, Boundary, context, sqlstate
from test_tenant_suspension_integrity import boundary as boundary

from pmc_api import audit_service

pytestmark = pytest.mark.skipif(
    "PMC_TEST_RUNTIME_DATABASE_URL" not in os.environ,
    reason="requires dedicated disposable PostgreSQL; never customer data",
)


def source_access(case: Boundary, role: str = "member") -> None:
    for cap in ("documents.read", "control_instances.read"):
        case.call(
            "POST",
            "/qms-access/grants",
            {"user_id": str(USERS[role]), "unit_id": str(SITE), "capability": cap},
            expected=201,
        )


def sources(
    case: Boundary,
    *,
    tenant: UUID = A,
    unit: UUID = SITE,
    suffix: str = "1",
    revision_status: str = "active",
    file_state: str = "clean",
    evidence_status: str = "accepted",
) -> dict[str, str]:
    ids = {
        key: str(uuid4())
        for key in (
            "process",
            "document",
            "revision",
            "control",
            "instance",
            "requirement",
            "evidence",
        )
    }
    params = {
        **ids,
        "tenant": tenant,
        "unit": unit,
        "actor": USERS["member"],
        "reviewer": USERS["owner"],
        "suffix": suffix,
        "rs": revision_status,
        "fs": file_state,
        "es": evidence_status,
        "hash": "a" * 64,
    }
    # Source lifecycle is tested by its own suites. This fixture constructs observed
    # source states without pretending to perform AV, storage or independent review.
    with case.admin.begin() as db:
        db.execute(text("SET LOCAL session_replication_role=replica"))
        for statement in (
            "INSERT INTO qms_processes(id,tenant_id,unit_id,code,name,process_type,sequence,department,description,inputs,outputs,status,row_version,created_by_user_id,created_at,updated_at) VALUES(:process,:tenant,:unit,'P-'||:suffix,'Synthetic process','core',10,'','','','','active',1,:actor,now(),now())",
            "INSERT INTO qms_documents(id,tenant_id,unit_id,process_id,code,title,document_type,status,current_revision_id,row_version,created_by_user_id,created_at,updated_at) VALUES(:document,:tenant,:unit,:process,'D-'||:suffix,'Source title','procedure','active',:revision,1,:actor,now(),now())",
            "INSERT INTO qms_document_revisions(id,tenant_id,document_id,revision,status,prepared_by_user_id,reviewed_by_user_id,approved_by_user_id,revision_date,effective_date,file_state,file_object_key,file_sha256,file_size,file_media_type,row_version,created_at) VALUES(:revision,:tenant,:document,'A',:rs,:actor,:reviewer,:reviewer,current_date,current_date,:fs,'synthetic.pdf',:hash,100,'application/pdf',1,now())",
            "INSERT INTO qms_controls(id,tenant_id,unit_id,process_id,code,name,objective,category,state,row_version,created_by_user_id,created_at,updated_at) VALUES(:control,:tenant,:unit,:process,'C-'||:suffix,'Synthetic control','Observe','other','active',1,:actor,now(),now())",
            "INSERT INTO qms_control_instances(id,tenant_id,unit_id,process_id,control_id,code,name,implementation_status,applicability,status,row_version,created_by_user_id,created_at,updated_at) VALUES(:instance,:tenant,:unit,:process,:control,'I-'||:suffix,'Implementation','not_started','applicable','active',1,:actor,now(),now())",
            "INSERT INTO qms_control_evidence_requirements(id,tenant_id,unit_id,process_id,control_id,name,row_version,created_by_user_id,created_at,updated_at) VALUES(:requirement,:tenant,:unit,:process,:control,'Required observation',1,:actor,now(),now())",
            "INSERT INTO qms_control_instance_evidence(id,tenant_id,unit_id,process_id,control_id,control_instance_id,requirement_definition_id,sequence,name,evidence_type,mandatory,status,submitted_by_user_id,submitted_at,reviewed_by_user_id,reviewed_at,review_decision,row_version,created_by_user_id,created_at,updated_at) VALUES(:evidence,:tenant,:unit,:process,:control,:instance,:requirement,10,'Evidence name','record',true,:es,CASE WHEN :es='draft' THEN NULL ELSE CAST(:actor AS uuid) END,CASE WHEN :es='draft' THEN NULL ELSE now() END,CASE WHEN :es IN ('accepted','rejected') THEN CAST(:reviewer AS uuid) ELSE NULL END,CASE WHEN :es IN ('accepted','rejected') THEN now() ELSE NULL END,'Synthetic decision',1,:actor,now(),now())",
        ):
            db.execute(text(statement), params)
    return ids


def setup(case: Boundary) -> tuple[dict[str, Any], dict[str, str]]:
    grant(case)
    source_access(case)
    return create(case), sources(case)


def path(p: dict[str, Any], kind: str, suffix: str = "links", *, step: int = 0) -> str:
    return f"/qms-projects/{p['id']}/steps/{p['steps'][step]['id']}/{kind}-{suffix}"


def payload(p: dict[str, Any], s: dict[str, str], kind: str, *, step: int = 0) -> dict[str, Any]:
    return {
        "expected_project_version": p["row_version"],
        "expected_step_version": p["steps"][step]["row_version"],
        "rationale": "Source supports planning",
        **(
            {
                "document_id": s["document"],
                "document_revision_id": s["revision"],
                "expected_document_version": 1,
                "expected_revision_version": 1,
            }
            if kind == "document"
            else {
                "evidence_id": s["evidence"],
                "expected_instance_version": 1,
                "expected_evidence_version": 1,
            }
        ),
    }


@pytest.mark.parametrize("kind", ["document", "evidence"])
def test_http_candidates_are_scoped_and_empty_pages_retain_versions(
    boundary: Boundary, kind: str
) -> None:
    p, s = setup(boundary)
    page = boundary.call("GET", path(p, kind, "candidates"), role="member")
    assert page["project_id"] == p["id"] and page["step_id"] == p["steps"][0]["id"]
    assert page["project_version"] == page["step_version"] == 1
    assert (
        len(page["items"]) == 1
        and page["items"][0]["document_id" if kind == "document" else "evidence_id"]
        == s[kind if kind == "document" else "evidence"]
    )
    for query in ("?offset=999", "?search=%25", "?search=%5F"):
        empty = boundary.call("GET", path(p, kind, "candidates") + query, role="member")
        assert empty["items"] == [] and empty["has_more"] is False
        assert empty["project_version"] == empty["step_version"] == 1


@pytest.mark.parametrize("kind", ["document", "evidence"])
def test_http_link_remove_receipts_snapshots_versions_and_private_audit(
    boundary: Boundary, kind: str
) -> None:
    p, s = setup(boundary)
    receipt = boundary.call("POST", path(p, kind), payload(p, s, kind), role="member", expected=201)
    p2, link = receipt["project"], receipt["link"]
    assert p2["row_version"] == p2["steps"][0]["row_version"] == 2
    for key in ("status", "notes", "assignee_user_id", "target_date"):
        assert p2["steps"][0][key] == p["steps"][0][key]
    assert link["target_process_id"] == s["process"] and link["snapshot_name"] == (
        "Source title" if kind == "document" else "Evidence name"
    )
    assert link["source_project_version"] == link["source_step_version"] == 2
    assert link["current_target_state"] == ("active" if kind == "document" else "accepted")
    removed = boundary.call(
        "POST",
        path(p, kind) + f"/{link['id']}/remove",
        {
            "expected_project_version": 2,
            "expected_step_version": 2,
            "expected_link_version": 1,
            "reason": " \ufeff Replaced source \ufeff ",
        },
        role="member",
    )
    assert removed["project"]["row_version"] == removed["project"]["steps"][0]["row_version"] == 3
    assert removed["link"]["status"] == "removed" and removed["link"]["row_version"] == 2
    assert (
        removed["link"]["snapshot_name"] == link["snapshot_name"]
        and removed["link"]["rationale"] == link["rationale"]
    )
    assert removed["link"]["removal_reason"] == "Replaced source"
    readded = boundary.call(
        "POST", path(p, kind), payload(removed["project"], s, kind), role="member", expected=201
    )
    assert readded["link"]["id"] != link["id"]
    page = boundary.call("GET", path(p, kind), role="member")
    assert [x["status"] for x in page["items"]] == ["active", "removed"]
    with boundary.admin.connect() as db:
        events = (
            db.execute(
                text(
                    "SELECT action,resource_type,new_values FROM audit_events WHERE resource_id=:id ORDER BY occurred_at"
                ),
                {"id": link["id"]},
            )
            .mappings()
            .all()
        )
        assert {x["action"] for x in events} == {
            f"qms_project.{kind}_linked",
            f"qms_project.{kind}_unlinked",
        }
        assert all(x["resource_type"] == f"qms_project_{kind}_link" for x in events)
        assert all(
            "rationale_hash" in x["new_values"]
            and "removal_reason_hash" in x["new_values"]
            and "snapshot_name" not in x["new_values"]
            and "rationale" not in x["new_values"]
            for x in events
        )


@pytest.mark.parametrize("kind", ["document", "evidence"])
def test_http_requires_exact_project_source_and_manage_permissions(
    boundary: Boundary, kind: str
) -> None:
    grant(boundary)
    p, s = create(boundary), sources(boundary)
    boundary.call("GET", path(p, kind), role="member", expected=403)
    boundary.call("POST", path(p, kind), payload(p, s, kind), role="member", expected=403)
    source_access(boundary)
    grant(boundary, "auditor", manage=False)
    source_access(boundary, "auditor")
    assert boundary.call("GET", path(p, kind), role="auditor")["items"] == []
    boundary.call("POST", path(p, kind), payload(p, s, kind), role="auditor", expected=403)
    boundary.call("GET", path(p, kind), expected=404)  # owner has no implicit operational authority
    receipt = boundary.call("POST", path(p, kind), payload(p, s, kind), role="member", expected=201)
    grants = boundary.call("GET", f"/qms-access/grants?unit_id={SITE}")
    target = next(
        g
        for g in grants
        if g["user_id"] == str(USERS["member"])
        and g["capability"]
        == ("documents.read" if kind == "document" else "control_instances.read")
        and g["status"] == "active"
    )
    boundary.call(
        "POST", f"/qms-access/grants/{target['id']}/revoke", {"reason": "Source read revoked"}
    )
    boundary.call("GET", path(p, kind), role="member", expected=403)
    with boundary.runtime.begin() as db:
        context(db, USERS["member"])
        assert db.scalar(text(f"SELECT count(*) FROM qms_project_{kind}_links")) == 0
    assert receipt["link"]["status"] == "active"


@pytest.mark.parametrize("kind", ["document", "evidence"])
@pytest.mark.parametrize("subject", ["tenant", "membership", "user"])
def test_suspended_actor_cannot_read_or_mutate(boundary: Boundary, kind: str, subject: str) -> None:
    p, s = setup(boundary)
    if subject == "tenant":
        boundary.change(subject, False)
    else:
        with boundary.admin.begin() as db:
            db.execute(
                text(
                    "UPDATE users SET status='disabled' WHERE id=:u"
                    if subject == "user"
                    else "UPDATE memberships SET status='revoked' WHERE tenant_id=:t AND user_id=:u"
                ),
                {"u": USERS["member"], "t": A},
            )
    boundary.call(
        "GET",
        path(p, kind, "candidates"),
        role="member",
        expected=403 if subject != "user" else 401,
    )
    boundary.call(
        "POST",
        path(p, kind),
        payload(p, s, kind),
        role="member",
        expected=403 if subject != "user" else 401,
    )
    with boundary.runtime.begin() as db:
        context(db, USERS["member"])
        assert db.scalar(text(f"SELECT count(*) FROM qms_project_{kind}_links")) == 0


@pytest.mark.parametrize("kind", ["document", "evidence"])
@pytest.mark.parametrize(
    "field", ["expected_project_version", "expected_step_version", "container", "target"]
)
def test_stale_selected_versions_do_not_advance_any_rows(
    boundary: Boundary, kind: str, field: str
) -> None:
    p, s = setup(boundary)
    body = payload(p, s, kind)
    key = (
        {"container": "expected_document_version", "target": "expected_revision_version"}
        if kind == "document"
        else {"container": "expected_instance_version", "target": "expected_evidence_version"}
    ).get(field, field)
    body[key] = 2
    boundary.call("POST", path(p, kind), body, role="member", expected=409)
    assert boundary.call("GET", f"/qms-projects/{p['id']}", role="member") == p
    assert boundary.call("GET", path(p, kind), role="member")["items"] == []


@pytest.mark.parametrize("kind", ["document", "evidence"])
@pytest.mark.parametrize("scope", ["tenant", "unit", "step", "source_pair"])
def test_wrong_company_unit_step_and_source_pair_are_hidden_or_conflict(
    boundary: Boundary, kind: str, scope: str
) -> None:
    p, s = setup(boundary)
    body = payload(p, s, kind)
    endpoint = path(p, kind)
    if scope == "tenant":
        other = sources(boundary, tenant=B, unit=B_SITE, suffix="other")
        body = payload(p, other, kind)
    elif scope == "unit":
        unit = uuid4()
        with boundary.admin.begin() as db:
            db.execute(
                text(
                    "INSERT INTO organization_units(id,tenant_id,unit_type,code,name,status,created_at,updated_at) VALUES(:id,:t,'site','OTHER','Other synthetic site','active',now(),now())"
                ),
                {"id": unit, "t": A},
            )
        body = payload(p, sources(boundary, unit=unit, suffix="other"), kind)
    elif scope == "step":
        other_project = create(boundary, code="OTHER")
        endpoint = endpoint.replace(p["steps"][0]["id"], other_project["steps"][0]["id"])
    else:
        other = sources(boundary, suffix="other")
        if kind == "document":
            body["document_revision_id"] = other["revision"]
        else:
            body["evidence_id"] = str(uuid4())
    boundary.call("POST", endpoint, body, role="member", expected=404 if scope == "step" else 409)
    assert boundary.call("GET", f"/qms-projects/{p['id']}", role="member") == p


@pytest.mark.parametrize(
    "revision_status,file_state,evidence_status",
    [
        ("draft", "clean", "draft"),
        ("superseded", "clean", "submitted"),
        ("draft", "quarantined", "rejected"),
    ],
)
def test_ineligible_sources_are_filtered_before_pagination_and_rejected(
    boundary: Boundary, revision_status: str, file_state: str, evidence_status: str
) -> None:
    p, _ = setup(boundary)
    bad = sources(
        boundary,
        suffix="0BAD",
        revision_status=revision_status,
        file_state=file_state,
        evidence_status=evidence_status,
    )
    for kind in ("document", "evidence"):
        page = boundary.call("GET", path(p, kind, "candidates") + "?limit=1", role="member")
        assert len(page["items"]) == 1 and page["has_more"] is False
        boundary.call("POST", path(p, kind), payload(p, bad, kind), role="member", expected=409)


@pytest.mark.parametrize("kind", ["document", "evidence"])
def test_duplicate_stale_removal_archive_history_and_rollback(
    boundary: Boundary, kind: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    p, s = setup(boundary)
    receipt = boundary.call("POST", path(p, kind), payload(p, s, kind), role="member", expected=201)
    p2, link = receipt["project"], receipt["link"]
    boundary.call("POST", path(p, kind), payload(p2, s, kind), role="member", expected=409)
    remove = {
        "expected_project_version": 2,
        "expected_step_version": 2,
        "expected_link_version": 2,
        "reason": "Retire",
    }
    endpoint = path(p, kind) + f"/{link['id']}/remove"
    boundary.call("POST", endpoint, remove, role="member", expected=409)

    def fail(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("Synthetic reference audit failure")

    monkeypatch.setattr(audit_service, "record_qms_project_reference", fail)
    with pytest.raises(RuntimeError, match="Synthetic reference audit failure"):
        boundary.call("POST", endpoint, {**remove, "expected_link_version": 1}, role="member")
    assert boundary.call("GET", f"/qms-projects/{p['id']}", role="member") == p2
    assert boundary.call("GET", path(p, kind), role="member")["items"] == [link]
    other = sources(boundary, suffix="other")
    with pytest.raises(RuntimeError, match="Synthetic reference audit failure"):
        boundary.call("POST", path(p, kind), payload(p2, other, kind), role="member", expected=201)
    assert boundary.call("GET", f"/qms-projects/{p['id']}", role="member") == p2
    archived = boundary.call(
        "POST",
        f"/qms-projects/{p['id']}/status",
        {"expected_version": 2, "target_status": "archived", "reason": "Pause"},
        role="member",
    )
    assert boundary.call("GET", path(p, kind), role="member")["items"] == [link]
    boundary.call(
        "POST", path(p, kind), payload(archived, other, kind), role="member", expected=409
    )


def insert_reference(
    db: Any, p: dict[str, Any], s: dict[str, str], kind: str, **changes: Any
) -> UUID:
    data = {
        "id": uuid4(),
        "tenant_id": A,
        "unit_id": SITE,
        "project_id": p["id"],
        "step_id": p["steps"][0]["id"],
        "source_project_version": p["row_version"] + 1,
        "source_step_version": p["steps"][0]["row_version"] + 1,
        "rationale": "SQL citation",
        "status": "active",
        "row_version": 1,
        "created_by_user_id": USERS["member"],
        "removal_reason": "",
        "linked_target_version": 1,
        **(
            {
                "document_id": s["document"],
                "document_revision_id": s["revision"],
                "linked_document_version": 1,
            }
            if kind == "document"
            else {"evidence_id": s["evidence"], "linked_instance_version": 1}
        ),
        **changes,
    }
    columns = ",".join(data)
    db.execute(
        text(
            f"INSERT INTO qms_project_{kind}_links({columns},created_at) VALUES({','.join(':' + key for key in data)},now())"
        ),
        data,
    )
    return UUID(str(data["id"]))


@pytest.mark.parametrize("kind", ["document", "evidence"])
@pytest.mark.parametrize(
    "tamper", ["command", "actor", "parent_version", "step_version", "scope", "snapshot"]
)
def test_direct_sql_guard_and_snapshot_derivation(
    boundary: Boundary, kind: str, tamper: str
) -> None:
    p, s = setup(boundary)
    with boundary.runtime.connect() as db:
        context(db, USERS["member"])
        db.execute(
            text("SELECT set_config('app.qms_project_reference_command',:c,true)"),
            {"c": "forged" if tamper == "command" else "link"},
        )
        changes = (
            {"created_by_user_id": USERS["owner"]}
            if tamper == "actor"
            else {"source_project_version": 1}
            if tamper == "parent_version"
            else {"source_step_version": 1}
            if tamper == "step_version"
            else {"step_id": uuid4()}
            if tamper == "scope"
            else {
                "snapshot_code": "FORGED",
                "snapshot_name": "FORGED",
                "target_process_id": uuid4(),
            }
            if tamper == "snapshot"
            else {}
        )
        if tamper != "snapshot":
            with pytest.raises(DBAPIError) as failure:
                insert_reference(db, p, s, kind, **changes)
                db.commit()
            assert sqlstate(failure.value) in {"23514", "42501"}
            db.rollback()
        else:
            identity = insert_reference(db, p, s, kind, **changes)
            db.commit()
            context(db, USERS["member"])
            row = (
                db.execute(
                    text(f"SELECT * FROM qms_project_{kind}_links WHERE id=:id"), {"id": identity}
                )
                .mappings()
                .one()
            )
            assert (
                row["snapshot_code"] == ("D-1" if kind == "document" else "I-1")
                and str(row["target_process_id"]) == s["process"]
            )
            assert (
                db.scalar(text("SELECT row_version FROM qms_projects WHERE id=:p"), {"p": p["id"]})
                == 2
            )
            assert (
                db.scalar(
                    text("SELECT row_version FROM qms_project_steps WHERE id=:s"),
                    {"s": p["steps"][0]["id"]},
                )
                == 2
            )


@pytest.mark.parametrize("kind", ["document", "evidence"])
@pytest.mark.parametrize(
    "change",
    [
        "snapshot_name='forged'",
        "rationale='forged'",
        "created_by_user_id=NULL",
        "status='active'",
        "source_project_version=99",
        "removed_by_user_id=created_by_user_id",
        "removed_at=now()",
    ],
)
def test_sql_removal_cannot_change_snapshot_restore_or_forge_metadata(
    boundary: Boundary, kind: str, change: str
) -> None:
    p, s = setup(boundary)
    receipt = boundary.call("POST", path(p, kind), payload(p, s, kind), role="member", expected=201)
    with boundary.runtime.connect() as db:
        context(db, USERS["member"])
        db.execute(text("SELECT set_config('app.qms_project_reference_command','unlink',true)"))
        assignments = {
            "status": "'removed'",
            "row_version": "2",
            "source_project_version": "3",
            "source_step_version": "3",
            "removal_reason": "'Retire'",
        }
        key, value = change.split("=", 1)
        assignments[key] = value
        with pytest.raises(DBAPIError):
            db.execute(
                text(
                    f"UPDATE qms_project_{kind}_links SET {','.join(k + '=' + v for k, v in assignments.items())} WHERE id=:id"
                ),
                {"id": receipt["link"]["id"]},
            )
            db.commit()
        db.rollback()
    assert boundary.call("GET", f"/qms-projects/{p['id']}", role="member") == receipt["project"]


@pytest.mark.parametrize("kind", ["document", "evidence"])
@pytest.mark.parametrize("competitor", ["note", "archive", "link"])
def test_bounded_concurrent_commands_share_parent_versions(
    boundary: Boundary, kind: str, competitor: str
) -> None:
    p, s = setup(boundary)

    def add() -> int:
        return cast(
            int,
            boundary.clients["member"].post(path(p, kind), json=payload(p, s, kind)).status_code,
        )

    def compete() -> int:
        if competitor == "note":
            return cast(
                int,
                (
                    boundary.clients["member"]
                    .patch(
                        f"/qms-projects/{p['id']}/steps/{p['steps'][0]['id']}",
                        json={
                            "expected_project_version": 1,
                            "expected_version": 1,
                            "notes": "Concurrent note",
                        },
                    )
                    .status_code
                ),
            )
        if competitor == "archive":
            return cast(
                int,
                (
                    boundary.clients["member"]
                    .post(
                        f"/qms-projects/{p['id']}/status",
                        json={
                            "expected_version": 1,
                            "target_status": "archived",
                            "reason": "Concurrent pause",
                        },
                    )
                    .status_code
                ),
            )
        return add()

    with ThreadPoolExecutor(max_workers=2) as pool:
        a, b = pool.submit(add), pool.submit(compete)
        results = [a.result(timeout=15), b.result(timeout=15)]
    assert sorted(results) == (
        [201, 409] if competitor == "link" else [200, 409] if results[1] == 200 else [201, 409]
    )
    current = boundary.call("GET", f"/qms-projects/{p['id']}", role="member")
    assert current["row_version"] == 2 and current["steps"][0]["row_version"] == (
        1 if competitor == "archive" and results[1] == 200 else 2
    )


@pytest.mark.parametrize("kind", ["document", "evidence"])
def test_source_transition_after_citation_preserves_snapshot_and_warns(
    boundary: Boundary, kind: str
) -> None:
    p, s = setup(boundary)
    link = boundary.call("POST", path(p, kind), payload(p, s, kind), role="member", expected=201)[
        "link"
    ]
    with boundary.admin.begin() as db:
        db.execute(text("SET LOCAL session_replication_role=replica"))
        db.execute(
            text(
                "UPDATE qms_documents SET status='obsolete',row_version=row_version+1 WHERE id=:id"
                if kind == "document"
                else "UPDATE qms_control_instances SET status='archived',row_version=row_version+1 WHERE id=:id"
            ),
            {"id": s["document" if kind == "document" else "instance"]},
        )
    observed = boundary.call("GET", path(p, kind), role="member")["items"][0]
    assert (
        observed["snapshot_name"] == link["snapshot_name"]
        and observed["linked_target_version"] == link["linked_target_version"]
    )
    assert observed["current_target_state"] == (
        "obsolete" if kind == "document" else "implementation_archived"
    )
    assert boundary.call("GET", path(p, kind, "candidates"), role="member")["items"] == []


@pytest.mark.parametrize("kind", ["document", "evidence"])
def test_reference_tables_force_rls_and_never_grant_delete_or_truncate(
    boundary: Boundary, kind: str
) -> None:
    with boundary.admin.connect() as db:
        assert db.execute(
            text(
                "SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid=CAST(:t AS regclass)"
            ),
            {"t": f"public.qms_project_{kind}_links"},
        ).one() == (True, True)
        for privilege in ("DELETE", "TRUNCATE"):
            assert (
                db.scalar(
                    text("SELECT has_table_privilege('pmcloud_app',:t,:p)"),
                    {"t": f"public.qms_project_{kind}_links", "p": privilege},
                )
                is False
            )


def test_candidates_cross_unit_authorized_actor_is_still_exactly_project_scoped(
    boundary: Boundary,
) -> None:
    p, s = setup(boundary)
    unit = uuid4()
    with boundary.admin.begin() as db:
        db.execute(
            text(
                "INSERT INTO organization_units(id,tenant_id,unit_type,code,name,status,created_at,updated_at) VALUES(:id,:t,'site','OTHER','Other synthetic site','active',now(),now())"
            ),
            {"id": unit, "t": A},
        )
    grant(boundary, unit=str(unit))
    for cap in ("documents.read", "control_instances.read"):
        boundary.call(
            "POST",
            "/qms-access/grants",
            {"user_id": str(USERS["member"]), "unit_id": str(unit), "capability": cap},
            expected=201,
        )
    other = sources(boundary, unit=unit, suffix="other")
    for kind in ("document", "evidence"):
        page = boundary.call("GET", path(p, kind, "candidates"), role="member")
        assert len(page["items"]) == 1
        candidate = page["items"][0]
        assert candidate["tenant_id"] == str(A) and candidate["unit_id"] == str(SITE)
        assert candidate["document_id" if kind == "document" else "evidence_id"] == s[kind]
        boundary.call("POST", path(p, kind), payload(p, other, kind), role="member", expected=409)


def test_candidate_pagination_exceeds_legacy_picker_ceilings_and_literal_search(
    boundary: Boundary,
) -> None:
    p, s = setup(boundary)
    with boundary.admin.begin() as db:
        db.execute(text("SET LOCAL session_replication_role=replica"))
        # Clone source records only in this disposable fixture; no source lifecycle claim.
        for index in range(1, 206):
            doc, rev, req, evidence = uuid4(), uuid4(), uuid4(), uuid4()
            params = {
                "doc": doc,
                "rev": rev,
                "req": req,
                "evidence": evidence,
                "d": s["document"],
                "r": s["revision"],
                "q": s["requirement"],
                "e": s["evidence"],
                "code": f"D-{index:04d}",
                "seq": index,
            }
            for table, original, patch in (
                (
                    "qms_documents",
                    "d",
                    "jsonb_build_object('id',CAST(:doc AS uuid),'code',CAST(:code AS text),'current_revision_id',CAST(:rev AS uuid))",
                ),
                (
                    "qms_document_revisions",
                    "r",
                    "jsonb_build_object('id',CAST(:rev AS uuid),'document_id',CAST(:doc AS uuid))",
                ),
                (
                    "qms_control_evidence_requirements",
                    "q",
                    "jsonb_build_object('id',CAST(:req AS uuid),'sequence',CAST(:seq AS integer))",
                ),
                (
                    "qms_control_instance_evidence",
                    "e",
                    "jsonb_build_object('id',CAST(:evidence AS uuid),'requirement_definition_id',CAST(:req AS uuid),'sequence',CAST(:seq AS integer))",
                ),
            ):
                db.execute(
                    text(
                        f"INSERT INTO {table} SELECT (jsonb_populate_record(NULL::{table},to_jsonb(x)||{patch})).* FROM {table} x WHERE id=:{original}"
                    ),
                    params,
                )
    for kind in ("document", "evidence"):
        seen: list[str] = []
        for offset in (0, 50, 100, 150, 200):
            page = boundary.call(
                "GET", path(p, kind, "candidates") + f"?offset={offset}", role="member"
            )
            assert page["has_more"] == (offset < 200) and page["offset"] == offset
            seen.extend(
                item["document_revision_id" if kind == "document" else "evidence_id"]
                for item in page["items"]
            )
        assert len(seen) == len(set(seen)) == 206
        empty = boundary.call("GET", path(p, kind, "candidates") + "?offset=206", role="member")
        assert empty["items"] == [] and not empty["has_more"] and empty["project_version"] == 1
        for query in ("%25", "%5F"):
            assert (
                boundary.call(
                    "GET", path(p, kind, "candidates") + f"?search={query}", role="member"
                )["items"]
                == []
            )


@pytest.mark.parametrize("kind", ["document", "evidence"])
def test_nonkey_source_transition_in_flight_does_not_freeze_historical_citation(
    boundary: Boundary, kind: str
) -> None:
    p, s = setup(boundary)
    with boundary.admin.connect() as source_db:
        transaction = source_db.begin()
        source_db.execute(text("SET LOCAL session_replication_role=replica"))
        source_db.execute(
            text(
                "UPDATE qms_documents SET status='obsolete',row_version=row_version+1 WHERE id=:id"
                if kind == "document"
                else "UPDATE qms_control_instances SET status='archived',row_version=row_version+1 WHERE id=:id"
            ),
            {"id": s["document" if kind == "document" else "instance"]},
        )
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(
                boundary.call,
                "POST",
                path(p, kind),
                payload(p, s, kind),
                role="member",
                expected=201,
            )
            try:
                linked = future.result(timeout=10)
            finally:
                transaction.commit()
    assert linked["link"]["current_target_state"] == (
        "active" if kind == "document" else "accepted"
    )
    page = boundary.call("GET", path(p, kind), role="member")
    assert page["items"][0]["current_target_state"] == (
        "obsolete" if kind == "document" else "implementation_archived"
    )


@pytest.mark.parametrize("value", ["\x00", "bad\ud800"])
def test_http_unsupported_unicode_is_private_422_before_postgresql(
    boundary: Boundary, value: str
) -> None:
    import json

    p, s = setup(boundary)
    response = boundary.clients["member"].post(
        path(p, "document"),
        content=json.dumps({**payload(p, s, "document"), "rationale": value}).encode(),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422
    assert boundary.call("GET", f"/qms-projects/{p['id']}", role="member") == p


@pytest.mark.parametrize("history", ["audit", "link"])
def test_downgrade_refuses_reference_and_audit_history_and_preserves_forced_rls(
    boundary: Boundary, history: str
) -> None:
    from test_tenant_suspension_integrity import migrate

    p, s = setup(boundary)
    boundary.call(
        "POST", path(p, "document"), payload(p, s, "document"), role="member", expected=201
    )
    if history == "audit":
        with boundary.admin.begin() as db:
            db.execute(text("TRUNCATE qms_project_document_links"))
    result = migrate("0050_qms_projects", "downgrade")
    assert (
        result.returncode != 0 and "cannot discard QMS project reference history" in result.stderr
    )
    with boundary.admin.connect() as db:
        assert (
            db.scalar(text("SELECT version_num FROM alembic_version"))
            == "0051_qms_project_references"
        )
        assert (
            db.scalar(
                text(
                    "SELECT relforcerowsecurity FROM pg_class WHERE oid='public.qms_project_document_links'::regclass"
                )
            )
            is True
        )

"""Rehearse the ISO upgrade from populated demo-era schema in disposable PostgreSQL."""

import hashlib
import os
from datetime import datetime

import pytest
from sqlalchemy import Text, cast, func, inspect, literal_column, select, table, text
from sqlalchemy.engine import Engine
from test_qms_party_process_links_integrity import create_party, link_body
from test_qms_party_requirements_integrity import ENDPOINT
from test_qms_project_reference_integrity import path, payload, setup
from test_tenant_suspension_integrity import SITE, Boundary, migrate
from test_tenant_suspension_integrity import boundary as boundary

pytestmark = pytest.mark.skipif(
    "PMC_TEST_RUNTIME_DATABASE_URL" not in os.environ,
    reason="requires dedicated disposable PostgreSQL with synthetic data",
)
DEMO_SCHEMA = "0051_qms_project_references"


def table_fingerprints(engine: Engine) -> dict[str, tuple[int, str]]:
    """Fingerprint every application row, including audit and session fixture rows."""
    results: dict[str, tuple[int, str]] = {}
    with engine.connect().execution_options(isolation_level="REPEATABLE READ") as db, db.begin():
        db.exec_driver_sql("SET TRANSACTION READ ONLY")
        names = inspect(db).get_table_names(schema="public")
        for name in sorted(set(names) - {"alembic_version"}):
            relation = table(name, schema="public").alias("item")
            statement = (
                select(cast(func.to_jsonb(relation.table_valued()), Text))
                .select_from(relation)
                .order_by(literal_column("1"))
            )
            rows = db.scalars(statement)
            digest = hashlib.sha256()
            count = 0
            for row in rows:
                digest.update(row.encode("utf-8"))
                digest.update(b"\n")
                count += 1
            results[name] = (count, digest.hexdigest())
    return results


def test_iso_upgrade_preserves_existing_project_document_and_evidence(boundary: Boundary) -> None:
    with boundary.admin.connect() as db:
        expected_head = db.scalar(text("SELECT version_num FROM public.alembic_version"))
    prepared = migrate(DEMO_SCHEMA, "downgrade")
    assert prepared.returncode == 0, prepared.stderr
    try:
        project, sources = setup(boundary)
        for kind in ("document", "evidence"):
            receipt = boundary.call(
                "POST",
                path(project, kind),
                payload(project, sources, kind),
                role="member",
                expected=201,
            )
            project = receipt["project"]
        old_links = {
            kind: boundary.call("GET", path(project, kind), role="member")
            for kind in ("document", "evidence")
        }
        assert all(len(page["items"]) == 1 for page in old_links.values())
        original = table_fingerprints(boundary.admin)
        for required in (
            "tenants",
            "qms_projects",
            "qms_project_steps",
            "qms_project_document_links",
            "qms_project_evidence_links",
            "audit_events",
            "application_sessions",
        ):
            assert original[required][0] > 0
    finally:
        upgraded = migrate("head")
        assert upgraded.returncode == 0, upgraded.stderr

    with boundary.admin.connect() as db:
        assert db.scalar(text("SELECT version_num FROM public.alembic_version")) == expected_head
    upgraded_tables = table_fingerprints(boundary.admin)
    assert original == {name: upgraded_tables[name] for name in original}
    for name in ("qms_context_records", "qms_context_revisions", "qms_party_process_links"):
        assert upgraded_tables[name][0] == 0 and name not in original

    party = create_party(boundary)
    link_url = f"{ENDPOINT}/{party['id']}/process-links?unit_id={SITE}"
    boundary.call("POST", link_url, link_body(boundary, 1), role="member", expected=201)
    linked = boundary.call("GET", link_url, role="member")
    assert linked["party_version"] == 2
    assert linked["items"][0]["process_id"] == boundary.process
    for kind, page in old_links.items():
        current = boundary.call("GET", path(project, kind), role="member")
        assert datetime.fromisoformat(current.pop("observed_at")) >= datetime.fromisoformat(
            page.pop("observed_at")
        )
        assert current == page

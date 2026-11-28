from __future__ import annotations

import json
import stat
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from botocore.exceptions import ClientError
from botocore.stub import Stubber
from sqlalchemy import Engine

from pmc_api import document_storage_reconciliation as cli
from pmc_api.document_storage_reconciliation import DocumentReference, InventoryError, reconcile
from pmc_api.storage import S3ObjectStorage, StoredObject

TENANT = UUID("4bf21a8c-90fa-4cc3-a269-1a0ea8e86b6c")
PREFIX = f"qms/{TENANT}/"
BUCKET = "synthetic-document-inventory"
NOW = datetime(2026, 11, 28, 12, tzinfo=UTC)


class Inventory:
    def __init__(
        self,
        listed: dict[str, tuple[int, datetime]],
        current: dict[str, int | str],
    ) -> None:
        self.listed = listed
        self.current = current
        self.lookups: list[str] = []

    def list_objects(self, bucket: str, prefix: str) -> Iterator[StoredObject]:
        assert (bucket, prefix) == (BUCKET, PREFIX)
        for key, (size, modified) in self.listed.items():
            yield StoredObject(key, size, modified)

    def object_metadata(self, bucket: str, key: str) -> dict[str, object]:
        assert bucket == BUCKET and key.startswith(PREFIX)
        self.lookups.append(key)
        result = self.current[key]
        if isinstance(result, str):
            raise ClientError({"Error": {"Code": result}}, "HeadObject")
        return {"content_length": result}


def test_reconciliation_classifies_inconsistencies_without_opening_files() -> None:
    earlier = NOW - timedelta(days=2)
    storage = Inventory(
        {
            PREFIX + "correct": (50, earlier),
            PREFIX + "mismatch": (38, earlier),
            PREFIX + "old": (20, earlier),
            PREFIX + "new": (12, NOW - cli.RECENT_INTERVAL),
            PREFIX + "invalid-size": (12, earlier),
        },
        {
            PREFIX + "mismatch": 39,
            PREFIX + "missing": "404",
            PREFIX + "now-present": 50,
        },
    )
    keys = ("correct", "missing", "mismatch", "now-present", "correct")
    references = [DocumentReference(uuid4(), PREFIX + key, 50) for key in keys]
    references.append(DocumentReference(uuid4(), PREFIX + "invalid-size", None))
    foreign = DocumentReference(uuid4(), f"qms/{uuid4()}/foreign", 20)
    report = reconcile(storage, BUCKET, TENANT, [*references, foreign], NOW)

    assert report.references == 7
    assert report.listed_objects == 5
    assert report.recent_unreferenced_objects == 1
    assert report.issues == [
        cli.Issue("missing_object", references[1].key, references[1].revision_id, 50),
        cli.Issue("size_mismatch", references[2].key, references[2].revision_id, 50, 39),
        cli.Issue("duplicate_reference", references[4].key, references[4].revision_id),
        cli.Issue("invalid_reference", references[5].key, references[5].revision_id),
        cli.Issue("invalid_reference", revision_id=foreign.revision_id),
        cli.Issue("unreferenced_object", PREFIX + "old", observed_bytes=20),
    ]
    assert storage.lookups == [PREFIX + key for key in ("missing", "mismatch", "now-present")]


def test_reconciliation_rejects_out_of_scope_listing() -> None:
    storage = Inventory({f"qms/{uuid4()}/another-company": (1, NOW)}, {})
    with pytest.raises(InventoryError, match="Invalid object listing"):
        reconcile(storage, BUCKET, TENANT, [], NOW)
    assert storage.lookups == []


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> cli.ReconciliationSettings:
    for name, value in {
        "DATABASE_URL": "postgresql+pg8000://synthetic@localhost/synthetic",
        "S3_ENDPOINT": "http://localhost:9999",
        "S3_ACCESS_KEY": "synthetic-read-only",
        "S3_SECRET_KEY": "synthetic-secret-not-used",
        "S3_DOCUMENTS_BUCKET": BUCKET,
    }.items():
        monkeypatch.setenv(f"PMC_RECONCILE_{name}", value)
    return cli.ReconciliationSettings()


def test_list_paginates_with_same_company_prefix(settings: cli.ReconciliationSettings) -> None:
    storage = S3ObjectStorage(settings)
    request = {"Bucket": BUCKET, "Prefix": PREFIX}
    with Stubber(storage._client) as stub:
        stub.add_response(
            "list_objects_v2",
            {"IsTruncated": True, "NextContinuationToken": "page-2"},
            request,
        )
        stub.add_response(
            "list_objects_v2",
            {
                "IsTruncated": False,
                "Contents": [{"Key": PREFIX + "second-page", "Size": 25, "LastModified": NOW}],
            },
            {**request, "ContinuationToken": "page-2"},
        )
        assert list(storage.list_objects(BUCKET, PREFIX)) == [
            StoredObject(PREFIX + "second-page", 25, NOW)
        ]
        stub.assert_no_pending_responses()


def test_cli_requires_separate_settings(
    settings: cli.ReconciliationSettings,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.delenv("PMC_RECONCILE_DATABASE_URL")
    monkeypatch.setenv("PMC_DATABASE_URL", settings.database_url)
    assert cli.main(["--tenant", str(TENANT)]) == 2
    assert capsys.readouterr().err == "Reconciliation incomplete during configuration.\n"


def test_cli_reports_no_issues_after_an_empty_inventory(
    settings: cli.ReconciliationSettings,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(cli, "load_references", lambda _engine, _company: [])
    monkeypatch.setattr(cli, "S3ObjectStorage", lambda _settings: Inventory({}, {}))
    assert cli.main(["--tenant", str(TENANT)]) == 0
    output = capsys.readouterr()
    assert output.err == ""
    assert json.loads(output.out) == {
        "references": 0,
        "listed_objects": 0,
        "recent_unreferenced_objects": 0,
        "issues": {},
    }


@pytest.mark.parametrize(("head_error", "expected_status"), [("403", 2), ("404", 1)])
def test_cli_redacts_failures_and_writes_details_only_to_private_file(
    settings: cli.ReconciliationSettings,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    head_error: str,
    expected_status: int,
) -> None:
    reference = DocumentReference(uuid4(), PREFIX + "private-file", 20)

    def read_database(_engine: Engine, tenant_id: UUID) -> list[DocumentReference]:
        assert tenant_id == TENANT
        return [reference]

    monkeypatch.setattr(cli, "load_references", read_database)
    monkeypatch.setattr(
        cli, "S3ObjectStorage", lambda _: Inventory({}, {reference.key: head_error})
    )
    path = tmp_path / "review.json"
    args = ["--tenant", str(TENANT), "--report", str(path)]
    assert cli.main(args) == expected_status
    output = capsys.readouterr()
    if head_error == "403":
        assert output.out == ""
        assert output.err == "Reconciliation incomplete during object inventory.\n"
        assert not path.exists()
        return

    assert output.err == "" and reference.key not in output.out
    assert json.loads(output.out)["issues"] == {"missing_object": 1}
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    initial_report = path.read_bytes()
    assert json.loads(initial_report)["issues"][0]["key"] == reference.key
    assert cli.main(args) == 2
    assert capsys.readouterr().err == "Reconciliation incomplete during private report output.\n"
    assert path.read_bytes() == initial_report

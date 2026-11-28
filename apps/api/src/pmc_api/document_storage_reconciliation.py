"""Read-only operations report for one company's private document storage."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from collections.abc import Iterator, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Literal, Protocol
from uuid import UUID

from botocore.exceptions import BotoCoreError, ClientError
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import Engine, create_engine, make_url, text
from sqlalchemy.exc import SQLAlchemyError

from pmc_api.storage import S3ObjectStorage, StoredObject

RECENT_INTERVAL = timedelta(hours=24)
IssueKind = Literal[
    "missing_object",
    "size_mismatch",
    "unreferenced_object",
    "invalid_reference",
    "duplicate_reference",
]


class ReconciliationSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PMC_RECONCILE_", hide_input_in_errors=True, str_min_length=1
    )

    database_url: str = Field(default="", repr=False)
    s3_endpoint: str = ""
    s3_access_key: str = Field(default="", repr=False)
    s3_secret_key: str = Field(default="", repr=False)
    s3_documents_bucket: str = ""
    s3_region: str = "us-east-1"


class DocumentInventory(Protocol):
    def list_objects(self, bucket: str, prefix: str) -> Iterator[StoredObject]: ...

    def object_metadata(self, bucket: str, key: str) -> dict[str, object]: ...


class InventoryError(RuntimeError):
    pass


@dataclass(frozen=True)
class DocumentReference:
    revision_id: UUID
    key: str
    size: int | None


@dataclass(frozen=True)
class Issue:
    kind: IssueKind
    key: str | None = None
    revision_id: UUID | None = None
    expected_bytes: int | None = None
    observed_bytes: int | None = None


@dataclass(frozen=True)
class Report:
    tenant_id: UUID
    observed_at: datetime
    references: int
    listed_objects: int
    recent_unreferenced_objects: int
    issues: list[Issue]


def load_references(engine: Engine, tenant_id: UUID) -> list[DocumentReference]:
    with engine.begin() as db:
        db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
        # A row filter could silently turn registered objects into orphans.
        db.execute(text("SET LOCAL row_security = off"))
        if db.scalar(text("SELECT rolsuper FROM pg_roles WHERE rolname = current_user")):
            raise InventoryError("Use a dedicated database inventory role")
        if not db.scalar(
            text("SELECT true FROM public.tenants WHERE id = :tenant"),
            {"tenant": tenant_id},
        ):
            raise InventoryError("Company does not exist")
        rows = db.execute(
            text("""
                SELECT id, file_object_key, file_size
                FROM public.qms_document_revisions
                WHERE tenant_id = :tenant AND file_object_key IS NOT NULL
                ORDER BY id
            """),
            {"tenant": tenant_id},
        )
        return [DocumentReference(row.id, row.file_object_key, row.file_size) for row in rows]


def _current_size(storage: DocumentInventory, bucket: str, key: str) -> int | None:
    try:
        size = storage.object_metadata(bucket, key).get("content_length")
    except ClientError as error:
        if error.response.get("Error", {}).get("Code") in {"404", "NoSuchKey", "NotFound"}:
            return None
        raise
    if type(size) is not int or size < 0:
        raise InventoryError("Invalid object size")
    return size


def reconcile(
    storage: DocumentInventory,
    bucket: str,
    tenant_id: UUID,
    references: Sequence[DocumentReference],
    observed_at: datetime,
) -> Report:
    prefix = f"qms/{tenant_id}/"
    objects: dict[str, StoredObject] = {}
    for stored in storage.list_objects(bucket, prefix):
        if not stored.key.startswith(prefix) or stored.key in objects:
            raise InventoryError("Invalid object listing")
        objects[stored.key] = stored

    issues: list[Issue] = []
    registered: set[str] = set()
    for reference in references:
        key = reference.key
        revision_id = reference.revision_id
        if not key.startswith(prefix) or key == prefix:
            issues.append(Issue("invalid_reference", revision_id=revision_id))
            continue
        if key in registered:
            issues.append(Issue("duplicate_reference", key, revision_id))
        registered.add(key)
        if reference.size is None or reference.size <= 0:
            issues.append(Issue("invalid_reference", key, revision_id))
            continue
        listed = objects.get(key)
        if listed and listed.size == reference.size:
            continue
        size = _current_size(storage, bucket, key)
        if size is None:
            issues.append(Issue("missing_object", key, revision_id, reference.size))
        elif size != reference.size:
            issues.append(Issue("size_mismatch", key, revision_id, reference.size, size))

    cutoff = observed_at - RECENT_INTERVAL
    recent = 0
    for stored in objects.values():
        if stored.key in registered:
            continue
        if stored.modified_at >= cutoff:
            recent += 1
        else:
            issues.append(Issue("unreferenced_object", stored.key, observed_bytes=stored.size))
    return Report(tenant_id, observed_at, len(references), len(objects), recent, issues)


def _write_private_report(path: Path, report: Report) -> None:
    with NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent) as pending:
        json.dump(asdict(report), pending, default=str, indent=2)
        pending.write("\n")
        pending.flush()
        # Publish the complete report without replacing an existing file or link.
        os.link(pending.name, path)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant", type=UUID, required=True, help="Company UUID")
    parser.add_argument("--report", type=Path, help="New private file for individual findings")
    args = parser.parse_args(argv)
    stage = "configuration"
    try:
        settings = ReconciliationSettings()
        url = make_url(settings.database_url)
        if url.drivername != "postgresql+pg8000":
            raise InventoryError("Inventory requires PostgreSQL over pg8000")
        stage = "database inventory"
        observed_at = datetime.now(UTC)
        engine = create_engine(url, hide_parameters=True)
        try:
            references = load_references(engine, args.tenant)
        finally:
            engine.dispose()
        stage = "object inventory"
        report = reconcile(
            S3ObjectStorage(settings),
            settings.s3_documents_bucket,
            args.tenant,
            references,
            observed_at,
        )
        if args.report is not None:
            stage = "private report output"
            _write_private_report(args.report, report)
    except (
        SQLAlchemyError,
        BotoCoreError,
        ClientError,
        InventoryError,
        KeyError,
        ValueError,
        OSError,
    ):
        print(f"Reconciliation incomplete during {stage}.", file=sys.stderr)
        return 2
    summary = {
        "references": report.references,
        "listed_objects": report.listed_objects,
        "recent_unreferenced_objects": report.recent_unreferenced_objects,
        "issues": Counter(issue.kind for issue in report.issues),
    }
    print(json.dumps(summary))
    return int(bool(report.issues))


if __name__ == "__main__":
    raise SystemExit(main())

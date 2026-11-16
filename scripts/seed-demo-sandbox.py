"""Populate an editable, synthetic local QMS practice area through authorized APIs.

No database bypass, customer data, reset, deletion, automatic attestations or
production target. Repeating the command preserves existing records and edits.
"""

from __future__ import annotations

import argparse
import json
from contextlib import ExitStack
from datetime import UTC, datetime, timedelta
from pathlib import Path
from runpy import run_path
from typing import Any

import httpx
from dotenv import dotenv_values

IDENTITY = run_path(str(Path(__file__).with_name("runtime-controls-e2e.py")))
API = "http://127.0.0.1:8000"
UNIT_CODE = "DEMO-PRACTICA"
MARKER = "Datos ficticios de práctica. Sin clientes reales ni certificaciones."
AUTHOR_CAPABILITIES = (
    "processes.read",
    "processes.manage",
    "documents.read",
    "documents.author",
    "documents.obsolete",
    "controls.read",
    "controls.manage",
    "control_instances.read",
    "control_instances.manage",
    "evidence.read",
    "evidence.create",
    "risks.read",
    "risks.manage",
    "risks.review",
    "ncr.read",
    "ncr.manage",
    "ncr.review",
    "capa.read",
    "capa.manage",
    "audits.read",
    "audits.manage",
)
REVIEWER_CAPABILITIES = (
    "documents.read",
    "documents.review",
    "documents.approve",
    "documents.release",
    "documents.obsolete",
    "controls.read",
    "control_instances.read",
    "control_instances.manage",
    "evidence.read",
    "evidence.review",
    "risks.read",
    "risks.review",
    "ncr.read",
    "ncr.review",
    "capa.read",
    "capa.review",
    "audits.read",
    "audits.review",
)


class DemoFailure(Exception):
    """Only constant stage/status messages; never include response/auth bodies."""


def validate_environment(env: dict[str, Any]) -> None:
    if env.get("PMC_ENVIRONMENT") != "development":
        raise DemoFailure("requires development environment")
    for key in (
        "KEYCLOAK_OWNER_PASSWORD",
        "KEYCLOAK_USER_A_PASSWORD",
        "KEYCLOAK_MULTI_USER_PASSWORD",
    ):
        if not env.get(key):
            raise DemoFailure("local demo credentials unavailable")


def pdf_document(title: str) -> bytes:
    """A real, self-contained one-page PDF with no embedded actions or links."""
    title = title.encode("ascii", "replace").decode().replace("\\", "\\\\")
    title = title.replace("(", "\\(").replace(")", "\\)")
    stream = (
        "BT /F1 16 Tf 48 760 Td (PERFECT MATCH QMS - SYNTHETIC DEMO) Tj "
        f"0 -36 Td /F1 12 Tf ({title}) Tj "
        "0 -30 Td (Practice document. Not approved. No real customer information.) Tj ET"
    ).encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length "
        + str(len(stream)).encode()
        + b" >>\nstream\n"
        + stream
        + b"\nendstream",
    ]
    result = b"%PDF-1.4\n"
    offsets = [0]
    for index, body in enumerate(objects, 1):
        offsets.append(len(result))
        result += f"{index} 0 obj\n".encode() + body + b"\nendobj\n"
    start = len(result)
    result += b"xref\n0 6\n0000000000 65535 f \n"
    result += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets[1:])
    return (
        result
        + f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{start}\n%%EOF\n".encode()
    )


class Sandbox:
    def __init__(
        self, owner: httpx.Client, author: httpx.Client, reviewer: httpx.Client
    ):
        self.owner, self.author, self.reviewer = owner, author, reviewer
        self.created: dict[str, int] = {}
        self.preserved: dict[str, int] = {}
        self.stage = "initialization"

    def request(
        self,
        client: httpx.Client,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        if not path.startswith("/") or path.startswith("//") or "://" in path:
            raise DemoFailure("only relative local API paths allowed")
        headers = IDENTITY["csrf"](client) if method != "GET" else {}
        response = client.request(
            method, API + path, json=body, headers=headers, **kwargs
        )
        if response.status_code not in (200, 201, 202):
            raise DemoFailure(f"{self.stage}: HTTP {response.status_code}")
        return response.json()

    def rows(
        self, client: httpx.Client, path: str, *, paginated: bool = True, **params: Any
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for offset in range(0, 1_000_001, 50):
            page = self.request(
                client,
                "GET",
                path,
                params={
                    **params,
                    "limit": 50 if paginated else 100,
                    **({"offset": offset} if paginated else {}),
                },
            )
            if not isinstance(page, list):
                raise DemoFailure("unexpected catalog response")
            if {row["id"] for row in rows} & {row["id"] for row in page}:
                raise DemoFailure("catalog pagination repeated a page")
            rows.extend(page)
            if not paginated:
                if len(page) >= 100:
                    raise DemoFailure(
                        "unpaged catalog full; cannot safely detect duplicates"
                    )
                return rows
            if len(page) < 50:
                return rows
        raise DemoFailure("catalog exceeds safe pagination boundary")

    def ensure(
        self,
        client: httpx.Client,
        path: str,
        body: dict[str, Any],
        *,
        query: dict[str, Any] | None = None,
        paginated: bool = True,
        key: str = "code",
        wrapper: str | None = None,
    ) -> tuple[dict[str, Any], bool]:
        matches = [
            r
            for r in self.rows(client, path, paginated=paginated, **(query or {}))
            if r.get(key) == body[key]
        ]
        if len(matches) > 1:
            raise DemoFailure("ambiguous demo identity; no overwrite attempted")
        if matches:
            for field in ("unit_id", "process_id", "program_id", "parent_id"):
                if field in body and matches[0].get(field) != body[field]:
                    raise DemoFailure(
                        "existing demo identifier belongs to another scope"
                    )
            self.preserved[path] = self.preserved.get(path, 0) + 1
            return matches[0], False
        row = self.request(client, "POST", path, body)
        self.created[path] = self.created.get(path, 0) + 1
        return (row[wrapper] if wrapper else row), True

    def run(self) -> dict[str, Any]:
        self.stage = "demo organization"
        members = self.rows(self.owner, "/organization/members", paginated=False)
        users = {}
        for client, username in zip(
            (self.owner, self.author, self.reviewer),
            ("pmc-local-owner", "pmc-user-a", "pmc-multi-user"),
            strict=True,
        ):
            user_id = self.request(client, "GET", "/auth/me")["id"]
            if not any(row["id"] == user_id for row in members):
                raise DemoFailure("expected development member unavailable")
            users[username] = user_id
        author_id, reviewer_id = users["pmc-user-a"], users["pmc-multi-user"]
        unit, fresh_unit = self.ensure(
            self.owner,
            "/organization/units",
            {
                "unit_type": "site",
                "code": UNIT_CODE,
                "name": "DEMO · Laboratorio de práctica",
                "description": MARKER,
            },
            paginated=False,
        )
        if unit["status"] != "active" or unit["unit_type"] != "site":
            raise DemoFailure("demo unit is archived or changed; it will not be reset")
        self.unit_id = unit["id"]
        for code, name in [
            ("DEMO-LAB-CALIDAD", "DEMO · Equipo de Calidad"),
            ("DEMO-LAB-OPERACIONES", "DEMO · Operaciones"),
        ]:
            self.ensure(
                self.owner,
                "/organization/units",
                {
                    "code": code,
                    "name": name,
                    "description": MARKER,
                    "unit_type": "department",
                    "parent_id": unit["id"],
                },
                paginated=False,
            )
        for user_id in (author_id, reviewer_id):
            self.ensure(
                self.owner,
                "/organization/assignments",
                {
                    "unit_id": unit["id"],
                    "user_id": user_id,
                    "assignment_role": "member",
                    "is_primary": False,
                },
                paginated=False,
                key="user_id",
                query={"unit_id": unit["id"]},
            )

        self.stage = "demo-only explicit responsibilities"
        for client, user_id, capabilities in [
            (self.author, author_id, AUTHOR_CAPABILITIES),
            (self.reviewer, reviewer_id, REVIEWER_CAPABILITIES),
        ]:
            effective = self.request(
                client, "GET", "/qms-access/effective", params={"unit_id": unit["id"]}
            )["capabilities"]
            for capability in capabilities:
                if capability not in effective:
                    if not fresh_unit:
                        raise DemoFailure(
                            "demo responsibility changed; no revoked permission restored"
                        )
                    self.request(
                        self.owner,
                        "POST",
                        "/qms-access/grants",
                        {
                            "unit_id": unit["id"],
                            "user_id": user_id,
                            "capability": capability,
                        },
                    )

        today = datetime.now(UTC).date()
        deadline = (today + timedelta(days=21)).isoformat()
        query = {"unit_id": unit["id"]}
        processes = []
        self.stage = "editable processes"
        for index, name in enumerate(
            ("Recepción e inspección", "Gestión documental", "Mejora continua"), 1
        ):
            process, _ = self.ensure(
                self.author,
                "/processes",
                {
                    **query,
                    "code": f"LAB-PROC-{index:03}",
                    "name": f"DEMO · {name}",
                    "process_type": "core",
                    "owner_user_id": author_id,
                    "description": MARKER,
                    "inputs": "Solicitudes y registros ficticios",
                    "outputs": "Resultados de práctica verificables",
                    "sequence": index * 10,
                },
                query=query,
            )
            processes.append(process)
        process = processes[0]
        scope = {**query, "process_id": process["id"]}

        self.stage = "draft controlled documents"
        for index, (name, kind) in enumerate(
            [
                ("Procedimiento de recepción", "procedure"),
                ("Lista de inspección", "form"),
                ("Política de calidad", "policy"),
            ],
            1,
        ):
            document, fresh = self.ensure(
                self.author,
                "/documents",
                {
                    **scope,
                    "code": f"LAB-DOC-{index:03}",
                    "title": f"DEMO · {name}",
                    "document_type": kind,
                    "owner_user_id": author_id,
                },
                query=query,
            )
            if fresh:
                revision = self.request(
                    self.author,
                    "POST",
                    f"/documents/{document['id']}/revisions",
                    {
                        "revision": "DEMO-1",
                        "change_summary": MARKER,
                        "revision_date": today.isoformat(),
                    },
                )
                response = self.author.put(
                    API
                    + f"/documents/{document['id']}/revisions/{revision['id']}/file",
                    content=pdf_document(f"Practice document {index}"),
                    headers={
                        **IDENTITY["csrf"](self.author),
                        "Content-Type": "application/pdf",
                    },
                )
                if response.status_code != 202:
                    raise DemoFailure("demo PDF upload failed; no approval attempted")

        self.stage = "controls, activities and evidence"
        for index, name in enumerate(
            ("Inspección de recepción", "Revisión documental", "Control editable"), 1
        ):
            control, fresh = self.ensure(
                self.author,
                "/controls",
                {
                    **scope,
                    "code": f"LAB-CTL-{index:03}",
                    "name": f"DEMO · {name}",
                    "objective": "Practicar asignación, ejecución y revisión independiente",
                    "description": MARKER,
                    "category": "process",
                    "owner_user_id": author_id,
                },
                query=query,
            )
            if fresh:
                for seq, title in [
                    (10, "Verificar identificación del lote"),
                    (20, "Revisar certificado"),
                ]:
                    self.request(
                        self.author,
                        "POST",
                        f"/controls/{control['id']}/activities",
                        {
                            "sequence": seq,
                            "name": f"DEMO · {title}",
                            "description": MARKER,
                            "success_criteria": "Registrar resultado de práctica",
                            "implementation_steps": "Consultar el procedimiento y documentar el resultado.",
                        },
                    )
                for seq, title in [
                    (10, "Registro de inspección"),
                    (20, "Certificado ficticio"),
                ]:
                    self.request(
                        self.author,
                        "POST",
                        f"/controls/{control['id']}/evidence-requirements",
                        {
                            "sequence": seq,
                            "name": f"DEMO · {title}",
                            "description": MARKER,
                            "acceptance_criteria": "Identificación, fecha y resultado ficticios completos",
                            "evidence_type": "record",
                            "mandatory": True,
                        },
                    )
                if index == 1:
                    control = self.request(
                        self.author,
                        "POST",
                        f"/controls/{control['id']}/activate",
                        {
                            "expected_version": control["row_version"],
                        },
                    )
                    instance = self.request(
                        self.author,
                        "POST",
                        "/control-instances",
                        {
                            "control_id": control["id"],
                            "code": "LAB-IMP-001",
                            "name": "DEMO · Inspección en almacén",
                            "owner_user_id": author_id,
                            "target_date": deadline,
                            "notes": MARKER,
                        },
                        params=scope,
                    )
                    for task in self.rows(
                        self.author,
                        "/control-instance-activities",
                        paginated=False,
                        instance_id=instance["id"],
                    ):
                        self.request(
                            self.author,
                            "PATCH",
                            f"/control-instance-activities/{task['id']}",
                            {
                                "expected_version": task["row_version"],
                                "assigned_to_user_id": author_id,
                                "target_date": deadline,
                                "notes": MARKER,
                            },
                        )
                    for evidence in self.rows(
                        self.author,
                        "/control-instance-evidence",
                        paginated=False,
                        instance_id=instance["id"],
                    ):
                        self.request(
                            self.author,
                            "PATCH",
                            f"/control-instance-evidence/{evidence['id']}",
                            {
                                "expected_version": evidence["row_version"],
                                "evidence_summary": MARKER
                                + " Pendiente de completar y revisar.",
                            },
                        )

        self.stage = "editable risks and opportunities"
        risks = []
        for index, (name, kind, category) in enumerate(
            [
                ("Material fuera de especificación", "risk", "supplier"),
                ("Uso de un documento desactualizado", "risk", "document"),
                ("Reducir tiempo de inspección", "opportunity", "process"),
            ],
            1,
        ):
            risk, _ = self.ensure(
                self.author,
                "/risks",
                {
                    **scope,
                    "code": f"LAB-RSK-{index:03}",
                    "name": f"DEMO · {name}",
                    "risk_type": kind,
                    "category": category,
                    "description": MARKER,
                    "likelihood": 3,
                    "impact": 4,
                    "residual_likelihood": 2,
                    "residual_impact": 2,
                    "owner_user_id": author_id,
                    "target_date": deadline,
                    "response_strategy": "enhance"
                    if kind == "opportunity"
                    else "mitigate",
                },
                query=query,
            )
            risks.append(risk)
        self.stage = "editable nonconformities"
        ncrs = []
        for index, name in enumerate(
            ("Certificado incompleto", "Etiqueta ilegible", "Registro sin fecha"), 1
        ):
            ncr, _ = self.ensure(
                self.author,
                "/nonconformities",
                {
                    **scope,
                    "code": f"LAB-NCR-{index:03}",
                    "name": f"DEMO · {name}",
                    "description": MARKER,
                    "source_type": "internal",
                    "severity": "minor",
                    "owner_user_id": author_id,
                    "target_date": deadline,
                },
                query=query,
            )
            ncrs.append(ncr)
        self.stage = "CAPA and assigned action plan"
        for index, source in enumerate(("ncr", "risk"), 1):
            capa, fresh = self.ensure(
                self.author,
                "/capas",
                {
                    **scope,
                    "code": f"LAB-CAPA-{index:03}",
                    "name": f"DEMO · {'Corregir recepción' if index == 1 else 'Prevenir errores documentales'}",
                    "source_type": source,
                    ("source_ncr_id" if source == "ncr" else "source_risk_id"): (
                        ncrs[0] if source == "ncr" else risks[1]
                    )["id"],
                    "problem_statement": MARKER + " Revisar causas y proponer mejoras.",
                    "owner_user_id": author_id,
                    "root_cause_method": "5why",
                    "target_date": deadline,
                },
                query=query,
            )
            if fresh and index == 1:
                base = f"/capas/{capa['id']}"
                capa = self.request(
                    self.author,
                    "POST",
                    base + "/analysis/start",
                    {
                        "expected_version": capa["row_version"],
                    },
                )
                capa = self.request(
                    self.author,
                    "PATCH",
                    base + "/analysis",
                    {
                        "expected_version": capa["row_version"],
                        "analysis_data": {
                            f"why{i}": text
                            for i, text in enumerate(
                                [
                                    "No se detectó el certificado incompleto.",
                                    "La lista no incluía esa comprobación.",
                                    "El cambio del proceso no actualizó la lista.",
                                    "Faltó revisar documentos relacionados.",
                                    "No se asignó esa revisión al responsable del cambio.",
                                ],
                                1,
                            )
                        },
                        "analysis_summary": "Ejemplo sintético para practicar; no es una investigación real.",
                        "verified_root_cause": "Ejemplo ficticio: lista sin revisión de cambios relacionados.",
                    },
                )
                capa = self.request(
                    self.author,
                    "POST",
                    base + "/plan/start",
                    {
                        "expected_version": capa["row_version"],
                        "plan_summary": MARKER,
                    },
                )
                self.request(
                    self.author,
                    "POST",
                    base + "/actions",
                    {
                        "expected_capa_version": capa["row_version"],
                        "title": "DEMO · Actualizar lista de inspección",
                        "description": MARKER,
                        "owner_user_id": author_id,
                        "due_date": deadline,
                    },
                )
        self.seed_audits(scope, author_id, reviewer_id, today, deadline)
        self.seed_workflow(author_id)
        return {
            "unit_code": UNIT_CODE,
            "created": self.created,
            "preserved": self.preserved,
            "production": False,
            "automatic_approvals": False,
            "reset_or_delete": False,
            "ready": "seed finished; validate readback separately",
        }

    def seed_audits(
        self,
        scope: dict[str, str],
        author_id: str,
        reviewer_id: str,
        today: Any,
        deadline: str,
    ) -> None:
        self.stage = "audit planning, scope, criteria, team and agenda"
        query = {"unit_id": scope["unit_id"]}
        program, _ = self.ensure(
            self.author,
            "/internal-audits/programs",
            {
                **query,
                "code": "LAB-AP-001",
                "name": "DEMO · Programa de auditorías",
                "objective": "Practicar planificación; ejecución aún no disponible.",
                "description": MARKER,
                "date_start": today.isoformat(),
                "date_end": deadline,
                "owner_user_id": author_id,
            },
            query=query,
        )
        for index in (1, 2):
            base = "/internal-audits/audits"
            audit, fresh = self.ensure(
                self.author,
                base,
                {
                    **query,
                    "program_id": program["id"],
                    "code": f"LAB-AUD-{index:03}",
                    "name": f"DEMO · {'Recepción' if index == 1 else 'Gestión documental'}",
                    "audit_type": "process",
                    "planned_start": (today + timedelta(days=7)).isoformat(),
                    "planned_end": (today + timedelta(days=8)).isoformat(),
                    "objective": MARKER,
                    "scope_summary": "Planificación editable de práctica",
                    "lead_auditor_user_id": reviewer_id,
                },
                query=query,
            )
            if not fresh:
                continue
            base += "/" + audit["id"]
            boundary = self.request(
                self.author,
                "POST",
                base + "/scopes",
                {
                    "expected_audit_version": audit["row_version"],
                    "sequence": 10,
                    "title": "DEMO · Registros y controles del proceso",
                    "description": MARKER,
                    "process_id": scope["process_id"],
                },
            )
            criterion = self.request(
                self.author,
                "POST",
                base + "/criteria",
                {
                    "expected_audit_version": boundary["audit_version"],
                    "sequence": 10,
                    "title": "DEMO · Registros completos",
                    "source_type": "internal",
                    "reference": "Criterio interno ficticio, no texto ISO licenciado",
                    "requirement": "Identificar fecha, lote y resultado en el registro de práctica.",
                    "scope_id": boundary["scope"]["id"],
                },
            )
            member = self.request(
                self.author,
                "POST",
                base + "/team-members",
                {
                    "expected_audit_version": criterion["audit_version"],
                    "user_id": reviewer_id,
                    "team_role": "auditor",
                    "responsibilities": MARKER,
                },
            )
            self.request(
                self.author,
                "POST",
                base + "/agenda",
                {
                    "expected_audit_version": member["audit_version"],
                    "sequence": 10,
                    "title": "DEMO · Revisión de registros",
                    "objective": MARKER,
                    "method": "sampling",
                    "location": "Laboratorio de práctica",
                    "starts_at": audit["planned_start"] + "T09:00:00Z",
                    "ends_at": audit["planned_start"] + "T10:00:00Z",
                    "scope_id": boundary["scope"]["id"],
                    "auditor_team_member_id": member["member"]["id"],
                },
            )

    def inventory(self) -> dict[str, Any]:
        """Read persisted practice records without changing any QMS state."""
        self.stage = "readback"
        units = self.rows(self.owner, "/organization/units", paginated=False)
        matches = [row for row in units if row["code"] == UNIT_CODE]
        if len(matches) != 1:
            raise DemoFailure("practice unit unavailable or ambiguous")
        query = {"unit_id": matches[0]["id"]}
        collections = {}
        for path in (
            "processes",
            "documents",
            "controls",
            "control-instances",
            "risks",
            "nonconformities",
            "capas",
            "internal-audits/programs",
            "internal-audits/audits",
        ):
            collections[path] = self.rows(self.author, "/" + path, **query)
        counts = {path: len(rows) for path, rows in collections.items()}
        counts["activities"] = counts["evidence"] = counts["pdf_clean"] = 0
        for document in collections["documents"]:
            revisions = self.request(
                self.author, "GET", f"/documents/{document['id']}/revisions"
            )
            counts["pdf_clean"] += sum(r["file_state"] == "clean" for r in revisions)
        for instance in collections["control-instances"]:
            for path, key in (
                ("control-instance-activities", "activities"),
                ("control-instance-evidence", "evidence"),
            ):
                counts[key] += len(
                    self.rows(
                        self.author,
                        "/" + path,
                        paginated=False,
                        instance_id=instance["id"],
                    )
                )
        for path in ("scopes", "criteria", "team-members", "agenda"):
            counts["audit_" + path] = sum(
                len(
                    self.rows(
                        self.author, f"/internal-audits/audits/{audit['id']}/{path}"
                    )
                )
                for audit in collections["internal-audits/audits"]
            )
        workflows = self.rows(self.owner, "/workflows", paginated=False)
        counts["workflows"] = sum(
            row["code"].startswith("LAB-WF-") for row in workflows
        )
        actions = self.request(
            self.author, "GET", "/action-center", params={"limit": 200}
        )
        counts["personal_practice_actions"] = sum(
            row["unit_id"] == query["unit_id"] or row["context"].startswith("LAB-WF-")
            for row in actions["items"]
        )
        events = self.request(self.owner, "GET", "/audit/events", params={"limit": 1})
        return {
            "unit_code": UNIT_CODE,
            "counts": counts,
            "audit_trail_readable": bool(events["items"]),
            "author_capabilities": self.request(
                self.author, "GET", "/qms-access/effective", params=query
            )["capabilities"],
            "note": "Persisted local API readback; not full browser or production acceptance.",
        }

    def seed_workflow(self, author_id: str) -> None:
        self.stage = "assigned practice workflow"
        definition, fresh = self.ensure(
            self.owner,
            "/workflows",
            {
                "code": "LAB-WF-001",
                "name": "DEMO · Solicitud interna de práctica",
                "description": MARKER
                + " No sustituye aprobaciones documentales o CAPA.",
            },
            paginated=False,
        )
        if not fresh:
            return
        version = self.request(
            self.owner, "POST", f"/workflows/{definition['id']}/versions", {}
        )
        base = f"/workflows/versions/{version['id']}"
        task = self.request(
            self.owner,
            "POST",
            base + "/steps",
            {
                "step_key": "practice",
                "name": "Completar solicitud de práctica",
                "step_type": "task",
                "is_start": True,
                "position": 0,
            },
        )
        end = self.request(
            self.owner,
            "POST",
            base + "/steps",
            {
                "step_key": "done",
                "name": "Práctica completada",
                "step_type": "end",
                "position": 1,
            },
        )
        self.request(
            self.owner,
            "POST",
            base + "/transitions",
            {
                "from_step_id": task["id"],
                "to_step_id": end["id"],
                "transition_key": "finish",
                "label": "Completar práctica",
            },
        )
        self.request(
            self.owner,
            "POST",
            base + "/assignments",
            {
                "step_id": task["id"],
                "target_type": "user",
                "target_user_id": author_id,
            },
        )
        self.request(self.owner, "POST", base + "/publish", {})
        self.request(
            self.owner,
            "POST",
            "/workflow-instances",
            {
                "workflow_version_id": version["id"],
                "title": "DEMO · Revisar solicitud ficticia",
                "reference": "LAB-WF-001 · práctica sin datos de clientes",
            },
        )
        # A second definition intentionally stays editable and unpublished.
        self.ensure(
            self.owner,
            "/workflows",
            {
                "code": "LAB-WF-EDIT",
                "name": "DEMO · Plantilla editable",
                "description": MARKER,
            },
            paginated=False,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument(
        "--apply", action="store_true", help="add synthetic local practice records"
    )
    modes.add_argument(
        "--verify", action="store_true", help="read persisted demo inventory only"
    )
    args = parser.parse_args()
    if not args.apply and not args.verify:
        print(
            "No writes. Use --apply after a verified local database recovery checkpoint."
        )
        return
    env = dotenv_values(Path.home() / ".config/pmcloud/dev.env")
    validate_environment(env)
    sandbox = None
    with ExitStack() as stack:
        clients = [
            stack.enter_context(httpx.Client(follow_redirects=True, timeout=30))
            for _ in range(3)
        ]
        try:
            selected = []
            for client, username, key in zip(
                clients,
                ("pmc-local-owner", "pmc-user-a", "pmc-multi-user"),
                (
                    "KEYCLOAK_OWNER_PASSWORD",
                    "KEYCLOAK_USER_A_PASSWORD",
                    "KEYCLOAK_MULTI_USER_PASSWORD",
                ),
                strict=True,
            ):
                IDENTITY["login"](client, username, str(env[key]))
                selected.append(IDENTITY["select_tenant"](client))
            if len(set(selected)) != 1:
                raise DemoFailure(
                    "demo accounts do not share the expected development company"
                )
            sandbox = Sandbox(*clients)
            result = sandbox.run() if args.apply else {}
            result["inventory"] = sandbox.inventory()
            print(json.dumps(result, ensure_ascii=False))
        finally:
            for client in clients:
                if "pm_csrf" in client.cookies:
                    try:
                        client.post(
                            API + "/auth/logout", headers=IDENTITY["csrf"](client)
                        )
                    except httpx.HTTPError:
                        pass


if __name__ == "__main__":
    try:
        main()
    except Exception as error:  # noqa: BLE001 -- redact auth bodies and URLs
        message = str(error) if isinstance(error, DemoFailure) else type(error).__name__
        raise SystemExit("Demo sandbox stopped: " + message) from None

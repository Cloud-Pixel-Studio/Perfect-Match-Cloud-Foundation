"""Create a persistent, coherent QMS demonstration in the local environment."""

from __future__ import annotations

import sys
from contextlib import ExitStack
from datetime import UTC, datetime, timedelta
from pathlib import Path
from runpy import run_path
from typing import Any

import httpx
from dotenv import dotenv_values

_identity = run_path(str(Path(__file__).with_name("runtime-controls-e2e.py")))
API = _identity["API"]
login, csrf, select_tenant, post = (
    _identity[name] for name in ("login", "csrf", "select_tenant", "post")
)

ALL_CAPABILITIES = (
    "documents.read",
    "documents.author",
    "documents.review",
    "documents.approve",
    "documents.release",
    "documents.obsolete",
    "evidence.read",
    "evidence.create",
    "evidence.review",
    "processes.read",
    "processes.manage",
    "controls.read",
    "controls.manage",
    "control_instances.read",
    "control_instances.manage",
    "risks.read",
    "risks.manage",
    "risks.review",
    "ncr.read",
    "ncr.manage",
    "ncr.review",
    "capa.read",
    "capa.manage",
    "capa.review",
    "audits.read",
    "audits.manage",
)
phase = "startup"


def checked(response: httpx.Response, status: int = 200) -> Any:
    if response.status_code != status:
        raise RuntimeError(f"demo request failed with HTTP {response.status_code}")
    return response.json()


def find(rows: list[dict[str, Any]], code: str) -> dict[str, Any] | None:
    return next((row for row in rows if row.get("code") == code), None)


def main() -> None:
    global phase
    if len(sys.argv) > 2:
        raise RuntimeError("provide at most one development environment file")
    env_path = (
        Path(sys.argv[1]).expanduser()
        if len(sys.argv) == 2
        else Path.home() / ".config/pmcloud/dev.env"
    )
    env = dotenv_values(env_path)
    if env.get("PMC_ENVIRONMENT") != "development":
        raise RuntimeError(
            "demo data can only be loaded into the local development environment"
        )
    with ExitStack() as stack:
        owner, author, reviewer = (
            stack.enter_context(httpx.Client(follow_redirects=True, timeout=30))
            for _ in range(3)
        )
        clients = (owner, author, reviewer)
        for client, username, key in (
            (owner, "pmc-local-owner", "KEYCLOAK_OWNER_PASSWORD"),
            (author, "pmc-user-a", "KEYCLOAK_USER_A_PASSWORD"),
            (reviewer, "pmc-multi-user", "KEYCLOAK_MULTI_USER_PASSWORD"),
        ):
            login(client, username, str(env[key]))
            select_tenant(client)

        phase = "organization and users"
        members = checked(owner.get(f"{API}/organization/members?limit=100"))
        user_ids: dict[str, str] = {}
        for prefix in ("pmc-local-owner", "pmc-user-a", "pmc-multi-user"):
            user_id = next(
                (
                    row["id"]
                    for row in members
                    if row["display_name"].startswith(prefix)
                ),
                None,
            )
            if user_id is None:
                raise RuntimeError(f"development member {prefix!r} is unavailable")
            user_ids[prefix] = user_id
        units = checked(owner.get(f"{API}/organization/units?limit=100"))
        unit = next(
            (
                row
                for row in units
                if row["code"] == "DEV-ACCESS-UI" and row["status"] == "active"
            ),
            None,
        )
        if unit is None:
            unit = checked(
                post(
                    owner,
                    f"{API}/organization/units",
                    {
                        "unit_type": "site",
                        "code": "DEV-ACCESS-UI",
                        "name": "Perfect Match Demonstration Site",
                        "description": (
                            "Synthetic development scope for visual and workflow validation."
                        ),
                    },
                ),
                201,
            )
        grants = checked(owner.get(f"{API}/qms-access/grants"))
        active = {
            (row["user_id"], row["unit_id"], row["capability"])
            for row in grants
            if row["status"] == "active"
        }
        capability_sets = {
            "pmc-user-a": ALL_CAPABILITIES,
            "pmc-multi-user": (
                "documents.read",
                "documents.review",
                "documents.approve",
                "documents.release",
                "documents.obsolete",
                "risks.read",
                "risks.review",
                "ncr.read",
                "ncr.review",
                "capa.read",
                "capa.review",
                "audits.read",
                "audits.review",
            ),
        }
        phase = "persistent demo capabilities"
        for prefix, capabilities in capability_sets.items():
            for capability in capabilities:
                key = (user_ids[prefix], unit["id"], capability)
                if key in active:
                    continue
                checked(
                    post(
                        owner,
                        f"{API}/qms-access/grants",
                        {
                            "user_id": key[0],
                            "unit_id": key[1],
                            "capability": capability,
                        },
                    ),
                    201,
                )
                active.add(key)

        phase = "demo process"
        processes = checked(
            author.get(
                f"{API}/processes",
                params={"unit_id": unit["id"], "limit": 100},
            )
        )
        process = find(processes, "DEMO-PROC-001")
        if process is None:
            process = checked(
                post(
                    author,
                    f"{API}/processes",
                    {
                        "unit_id": unit["id"],
                        "code": "DEMO-PROC-001",
                        "name": "Recepción y evaluación de proveedores",
                        "process_type": "core",
                        "owner_user_id": user_ids["pmc-user-a"],
                        "sequence": 20,
                        "department": "Operaciones y Calidad",
                        "description": "Proceso demostrativo para recepción, inspección y seguimiento de proveedores.",
                        "inputs": "Órdenes de compra, materiales recibidos y certificados del proveedor.",
                        "outputs": "Material aceptado, incidencias registradas y evaluación de desempeño.",
                    },
                ),
                201,
            )

        scope = {"unit_id": unit["id"], "process_id": process["id"]}
        phase = "released demo document"
        documents = checked(
            author.get(
                f"{API}/documents",
                params={
                    "unit_id": unit["id"],
                    "search": "DEMO-DOC-001",
                    "limit": 50,
                },
            )
        )
        document = find(documents, "DEMO-DOC-001")
        revision: dict[str, Any] | None = None
        if document is None:
            document = checked(
                post(
                    author,
                    f"{API}/documents",
                    {
                        **scope,
                        "code": "DEMO-DOC-001",
                        "title": "Procedimiento de recepción e inspección de materiales",
                        "document_type": "procedure",
                        "owner_user_id": user_ids["pmc-user-a"],
                    },
                ),
                201,
            )
            revision = checked(
                post(
                    author,
                    f"{API}/documents/{document['id']}/revisions",
                    {
                        "revision": "1.0",
                        "change_summary": "Emisión inicial para demostración del QMS.",
                        "revision_date": datetime.now(UTC).date().isoformat(),
                    },
                ),
                201,
            )
            pdf = (
                b"%PDF-1.7\n1 0 obj<</Type/Catalog>>endobj\n"
                b"% Perfect Match QMS demonstration procedure\n%%EOF\n"
            )
            checked(
                author.put(
                    f"{API}/documents/{document['id']}/revisions/{revision['id']}/file",
                    content=pdf,
                    headers={**csrf(author), "Content-Type": "application/pdf"},
                ),
                202,
            )
            revision = next(
                row
                for row in checked(
                    author.get(f"{API}/documents/{document['id']}/revisions")
                )
                if row["id"] == revision["id"]
            )
            for command in ("submit", "approve", "release"):
                revision = checked(
                    post(
                        reviewer,
                        f"{API}/documents/{document['id']}/revisions/{revision['id']}/{command}",
                        {"expected_version": revision["row_version"]},
                    )
                )
        else:
            revisions = checked(
                author.get(f"{API}/documents/{document['id']}/revisions")
            )
            revision = next(
                (
                    row
                    for row in revisions
                    if row["status"] == "active" and row["file_state"] == "clean"
                ),
                None,
            )

        phase = "demo control and implementation"
        controls = checked(
            author.get(
                f"{API}/controls",
                params={
                    "unit_id": unit["id"],
                    "process_id": process["id"],
                    "search": "DEMO-CTL-001",
                },
            )
        )
        control = find(controls, "DEMO-CTL-001")
        if control is None:
            control = checked(
                post(
                    author,
                    f"{API}/controls",
                    {
                        **scope,
                        "code": "DEMO-CTL-001",
                        "name": "Inspección de material recibido",
                        "objective": "Confirmar identidad, cantidad, condición y documentación antes de liberar materiales.",
                        "description": "Control demostrativo aplicado a cada recepción de materiales críticos.",
                        "category": "process",
                        "owner_user_id": user_ids["pmc-user-a"],
                    },
                ),
                201,
            )
            control = checked(
                post(
                    author,
                    f"{API}/controls/{control['id']}/activate",
                    {"expected_version": control["row_version"]},
                )
            )
        instances = checked(
            author.get(
                f"{API}/control-instances",
                params={
                    "unit_id": unit["id"],
                    "process_id": process["id"],
                    "limit": 100,
                },
            )
        )
        instance = find(instances, "DEMO-IMP-001")
        if instance is None:
            instance = checked(
                post(
                    author,
                    f"{API}/control-instances?unit_id={unit['id']}&process_id={process['id']}",
                    {
                        "control_id": control["id"],
                        "code": "DEMO-IMP-001",
                        "name": "Punto de inspección en almacén principal",
                        "owner_user_id": user_ids["pmc-user-a"],
                        "applicability": "applicable",
                        "target_date": (datetime.now(UTC) + timedelta(days=30))
                        .date()
                        .isoformat(),
                        "notes": "Implementación demostrativa para recepción de materiales críticos.",
                    },
                ),
                201,
            )

        phase = "demo risk"
        risks = checked(
            author.get(
                f"{API}/risks",
                params={
                    "unit_id": unit["id"],
                    "q": "DEMO-RSK-001",
                    "limit": 50,
                },
            )
        )
        risk = find(risks, "DEMO-RSK-001")
        if risk is None:
            risk = checked(
                post(
                    author,
                    f"{API}/risks",
                    {
                        **scope,
                        "code": "DEMO-RSK-001",
                        "name": "Recepción de material no conforme",
                        "risk_type": "risk",
                        "category": "supplier",
                        "source": "Evaluación de proveedores",
                        "description": "El proveedor puede entregar material fuera de especificación o sin certificado.",
                        "cause": "Cambios de lote sin notificación y revisión documental insuficiente.",
                        "potential_effect": "Paradas, retrabajo, retrasos y uso accidental de material no conforme.",
                        "likelihood": 4,
                        "impact": 5,
                        "residual_likelihood": 2,
                        "residual_impact": 3,
                        "response_strategy": "mitigate",
                        "mitigation_plan": "Aplicar inspección de recepción y monitorear desempeño mensual.",
                        "owner_user_id": user_ids["pmc-user-a"],
                        "target_date": (datetime.now(UTC) + timedelta(days=45))
                        .date()
                        .isoformat(),
                    },
                ),
                201,
            )
            for target in ("assessed", "monitoring"):
                risk = checked(
                    post(
                        reviewer,
                        f"{API}/risks/{risk['id']}/transition",
                        {
                            "expected_version": risk["row_version"],
                            "target_state": target,
                            "decision": "Evaluación demostrativa aprobada para seguimiento.",
                        },
                    )
                )

        phase = "demo nonconformity"
        ncrs = checked(
            author.get(
                f"{API}/nonconformities",
                params={
                    "unit_id": unit["id"],
                    "q": "DEMO-NCR-001",
                    "limit": 50,
                },
            )
        )
        ncr = find(ncrs, "DEMO-NCR-001")
        today = datetime.now(UTC).date()
        if ncr is None:
            ncr = checked(
                post(
                    author,
                    f"{API}/nonconformities",
                    {
                        **scope,
                        "code": "DEMO-NCR-001",
                        "name": "Certificado de material incompleto en recepción",
                        "source_type": "supplier",
                        "severity": "major",
                        "description": "Un lote crítico llegó con certificado sin referencia a la especificación vigente.",
                        "detected_date": today.isoformat(),
                        "owner_user_id": user_ids["pmc-user-a"],
                        "containment_required": True,
                        "containment_action": "Identificar y segregar el lote hasta validar la documentación.",
                        "containment_owner_user_id": user_ids["pmc-user-a"],
                        "containment_date": today.isoformat(),
                        "containment_completed": True,
                        "target_date": (today + timedelta(days=14)).isoformat(),
                    },
                ),
                201,
            )
            ncr = checked(
                post(
                    author,
                    f"{API}/nonconformities/{ncr['id']}/transition",
                    {
                        "expected_version": ncr["row_version"],
                        "target_state": "open",
                        "decision": "Registro revisado y abierto para tratamiento.",
                    },
                )
            )
            for target in ("containment", "investigation"):
                ncr = checked(
                    post(
                        reviewer,
                        f"{API}/nonconformities/{ncr['id']}/transition",
                        {
                            "expected_version": ncr["row_version"],
                            "target_state": target,
                            "decision": "Contención confirmada; continuar con investigación de causa.",
                        },
                    )
                )

        phase = "demo corrective action"
        capas = checked(
            author.get(
                f"{API}/capas",
                params={
                    "unit_id": unit["id"],
                    "q": "DEMO-CAPA-001",
                    "limit": 50,
                },
            )
        )
        capa = find(capas, "DEMO-CAPA-001")
        if capa is None:
            capa = checked(
                post(
                    author,
                    f"{API}/capas",
                    {
                        **scope,
                        "code": "DEMO-CAPA-001",
                        "name": "Fortalecer validación documental de proveedores",
                        "source_type": "ncr",
                        "source_ncr_id": ncr["id"],
                        "source_reference": "Caso demostrativo de recepción 2026-001",
                        "problem_statement": "La recepción permitió avanzar un lote con certificado incompleto.",
                        "owner_user_id": user_ids["pmc-user-a"],
                        "root_cause_method": "5why",
                        "target_date": (today + timedelta(days=60)).isoformat(),
                    },
                ),
                201,
            )
            capa = checked(
                post(
                    author,
                    f"{API}/capas/{capa['id']}/analysis/start",
                    {
                        "expected_version": capa["row_version"],
                    },
                )
            )
            capa = checked(
                author.patch(
                    f"{API}/capas/{capa['id']}/analysis",
                    json={
                        "expected_version": capa["row_version"],
                        "analysis_data": {
                            "why1": "El certificado incompleto no fue detenido en recepción.",
                            "why2": "La lista de inspección no exigía verificar la especificación vigente.",
                            "why3": "El procedimiento no diferenciaba materiales críticos.",
                            "why4": "La evaluación de riesgos no estaba conectada con la inspección.",
                            "why5": "Faltaba una revisión periódica conjunta entre Calidad y Compras.",
                        },
                        "analysis_summary": "Los cinco porqués identifican una brecha entre riesgo, procedimiento y lista de inspección.",
                        "verified_root_cause": "El procedimiento no convierte el riesgo del proveedor en una verificación documental obligatoria.",
                    },
                    headers=csrf(author),
                )
            )
            capa = checked(
                post(
                    author,
                    f"{API}/capas/{capa['id']}/plan/start",
                    {
                        "expected_version": capa["row_version"],
                        "plan_summary": "Actualizar procedimiento y lista de inspección; capacitar recepción y revisar eficacia tras 30 días.",
                    },
                )
            )
            checked(
                post(
                    author,
                    f"{API}/capas/{capa['id']}/actions",
                    {
                        "expected_capa_version": capa["row_version"],
                        "title": "Actualizar lista de inspección de recepción",
                        "description": "Añadir verificación de especificación vigente y certificado para materiales críticos.",
                        "owner_user_id": user_ids["pmc-user-a"],
                        "due_date": (today + timedelta(days=21)).isoformat(),
                    },
                ),
                201,
            )
            capa = checked(author.get(f"{API}/capas/{capa['id']}"))
            if revision is not None:
                checked(
                    post(
                        author,
                        f"{API}/capas/{capa['id']}/document-links",
                        {
                            "expected_version": capa["row_version"],
                            "document_id": document["id"],
                            "document_revision_id": revision["id"],
                        },
                    ),
                    201,
                )

        phase = "demo CAPA direct control traceability"
        capa = checked(author.get(f"{API}/capas/{capa['id']}"))
        control_links = checked(author.get(f"{API}/capas/{capa['id']}/control-links"))
        if not any(
            row["control_instance_id"] == instance["id"] and row["status"] == "active"
            for row in control_links
        ):
            checked(
                post(
                    author,
                    f"{API}/capas/{capa['id']}/control-links",
                    {
                        "expected_version": capa["row_version"],
                        "control_instance_id": instance["id"],
                    },
                ),
                201,
            )

        phase = "demo internal-audit planning"
        programs = checked(
            author.get(
                f"{API}/internal-audits/programs",
                params={"unit_id": unit["id"], "q": "DEMO-AP-001", "limit": 50},
            )
        )
        program = find(programs, "DEMO-AP-001")
        if program is None:
            program = checked(
                post(
                    author,
                    f"{API}/internal-audits/programs",
                    {
                        "unit_id": unit["id"],
                        "code": "DEMO-AP-001",
                        "name": "Programa de auditorías internas — demostración",
                        "objective": "Planificar la revisión del proceso de recepción y su información documentada.",
                        "description": "Datos sintéticos. La aprobación del programa no certifica cumplimiento ni independencia del equipo.",
                        "date_start": today.isoformat(),
                        "date_end": (today + timedelta(days=90)).isoformat(),
                        "owner_user_id": user_ids["pmc-user-a"],
                    },
                ),
                201,
            )
        if program["state"] == "draft":
            program = checked(
                post(
                    reviewer,
                    f"{API}/internal-audits/programs/{program['id']}/transition",
                    {
                        "expected_version": program["row_version"],
                        "target_state": "approved",
                        "decision": "Programa sintético revisado para demostrar planificación; no implica certificación.",
                    },
                )
            )
        # The audit list has no program/search filter. Read every page rather
        # than assuming the demo is absent because it is outside page one.
        audit = None
        for offset in range(0, 1_000_001, 50):
            audit_page = checked(
                author.get(
                    f"{API}/internal-audits/audits",
                    params={
                        "unit_id": unit["id"],
                        "limit": 50,
                        "offset": offset,
                    },
                )
            )
            audit = find(audit_page, "DEMO-AUD-001")
            if audit is not None or len(audit_page) < 50:
                break
        if audit is None and program["state"] != "cancelled":
            audit = checked(
                post(
                    author,
                    f"{API}/internal-audits/audits",
                    {
                        "unit_id": unit["id"],
                        "program_id": program["id"],
                        "code": "DEMO-AUD-001",
                        "name": "Auditoría del proceso de recepción y proveedores",
                        "audit_type": "process",
                        "planned_start": (today + timedelta(days=14)).isoformat(),
                        "planned_end": (today + timedelta(days=15)).isoformat(),
                        "objective": "Planificar la evaluación de los controles de recepción, documentos vigentes y tratamiento de incidencias.",
                        "scope_summary": "Resumen de planificación: recepción, certificados y registros del proveedor. Criterios, equipo e independencia quedan pendientes.",
                        "lead_auditor_user_id": user_ids["pmc-multi-user"],
                    },
                ),
                201,
            )
        if (
            audit is not None
            and audit["state"] == "draft"
            and program["state"] != "cancelled"
        ):
            checked(
                post(
                    author,
                    f"{API}/internal-audits/audits/{audit['id']}/transition",
                    {
                        "expected_version": audit["row_version"],
                        "target_state": "planned",
                        "decision": "Fechas y objetivo registrados. Independencia y ejecución todavía pendientes.",
                    },
                )
            )

        phase = "demo structured audit scope"
        if audit is not None and audit["state"] in {"draft", "planned"}:
            scope_title = "Recepción y aceptación de materiales — demostración"
            existing_scope = []
            for offset in range(0, 1_000_001, 50):
                page = checked(
                    author.get(
                        f"{API}/internal-audits/audits/{audit['id']}/scopes",
                        params={"limit": 50, "offset": offset},
                    )
                )
                existing_scope.extend(page)
                if len(page) < 50:
                    break
            if not any(item["title"] == scope_title for item in existing_scope):
                current_audit = checked(
                    author.get(f"{API}/internal-audits/audits/{audit['id']}")
                )
                occupied = {
                    item["sequence"] for item in existing_scope if item["status"] == "active"
                }
                sequence = next(
                    (value for value in range(10, 10001, 10) if value not in occupied), None
                )
                if sequence is None:
                    raise ValueError("No available demonstration scope order")
                checked(
                    post(
                        author,
                        f"{API}/internal-audits/audits/{audit['id']}/scopes",
                        {
                            "expected_audit_version": current_audit["row_version"],
                            "sequence": sequence,
                            "title": scope_title,
                            "description": (
                                "Datos sintéticos: revisar registros de recepción, certificados y "
                                "aceptación de materiales. No registra ejecución ni hallazgos."
                            ),
                            "process_id": process["id"] if process["status"] == "active" else None,
                        },
                    ),
                    201,
                )


        phase = "demo internal-audit criteria"
        if audit is not None:
            current_audit = checked(
                author.get(f"{API}/internal-audits/audits/{audit['id']}")
            )
            if current_audit["state"] in {"draft", "planned"}:
                scope_items = []
                criteria_items = []
                for collection, destination in [
                    ("scopes", scope_items),
                    ("criteria", criteria_items),
                ]:
                    for offset in range(0, 1_000_001, 50):
                        page = checked(
                            author.get(
                                f"{API}/internal-audits/audits/{audit['id']}/{collection}",
                                params={"limit": 50, "offset": offset},
                            )
                        )
                        destination.extend(page)
                        if len(page) < 50:
                            break
                demo_scope = next(
                    (
                        item
                        for item in scope_items
                        if item["status"] == "active"
                        and item["title"]
                        == "Recepción y aceptación de materiales — demostración"
                    ),
                    None,
                )
                criterion_title = "Aceptación documentada de materiales — demostración"
                if demo_scope and not any(
                    item["title"] == criterion_title for item in criteria_items
                ):
                    occupied = {
                        item["sequence"]
                        for item in criteria_items
                        if item["status"] == "active"
                    }
                    sequence = next(
                        (value for value in range(10, 10001, 10) if value not in occupied),
                        None,
                    )
                    if sequence is None:
                        raise ValueError("No available demonstration criterion order")
                    checked(
                        post(
                            author,
                            f"{API}/internal-audits/audits/{audit['id']}/criteria",
                            {
                                "expected_audit_version": current_audit["row_version"],
                                "sequence": sequence,
                                "title": criterion_title,
                                "source_type": "internal",
                                "reference": "DEMO-PROC-001 · procedimiento interno de recepción",
                                "requirement": (
                                    "Comprobar que los registros sintéticos identifican el material, "
                                    "el resultado de inspección y la persona responsable de su aceptación."
                                ),
                                "scope_id": demo_scope["id"],
                            },
                        ),
                        201,
                    )

        print(
            "Demo data ready: DEMO-PROC-001, DEMO-DOC-001, DEMO-CTL-001, "
            "DEMO-IMP-001, DEMO-RSK-001, DEMO-NCR-001 and DEMO-CAPA-001 "
            "with direct control traceability; internal-audit planning and structured scope "
            "and criteria demo preserved"
        )
        for client in clients:
            if "pm_csrf" in client.cookies:
                client.post(f"{API}/auth/logout", headers=csrf(client))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:  # noqa: BLE001 -- never expose credentials or auth URLs
        raise SystemExit(
            f"Demo seed failed during {phase}: {type(error).__name__}: {error}"
        ) from None

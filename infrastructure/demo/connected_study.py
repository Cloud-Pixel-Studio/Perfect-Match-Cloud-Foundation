"""Opt-in connected synthetic study records for the exact approved demo only."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


class StudyFailure(Exception):
    """Safe messages without tokens, passwords, response bodies or private URLs."""


def validate_milestones(capas, workflow_states, nonconformities):
    """A persisted parent is not proof that its teaching scenario finished."""
    closed_case = next((row for row in capas if row["code"] == "EST-CAPA-002"), None)
    if closed_case is None or closed_case["state"] != "closed":
        raise StudyFailure(
            "study closed CAPA scenario is incomplete or changed; no reset attempted"
        )
    incident = next(
        (row for row in nonconformities if row["code"] == "EST-NCR-002"), None
    )
    if incident is None or incident["state"] != "closed":
        raise StudyFailure(
            "study closed NCR scenario is incomplete or changed; no reset attempted"
        )
    completed = workflow_states.get("EST-WF-003", {}).get("instance_states", [])
    if "completed" not in completed:
        raise StudyFailure(
            "study completed workflow scenario is incomplete or changed; no reset attempted"
        )


def load_assets(root):
    root = Path(root).resolve()
    try:
        entries = json.loads((root / "manifest.json").read_text())["documents"]
        expected = {f"EST-DOC-{index:03}" for index in range(1, 9)}
        if len(entries) != 8 or {entry["code"] for entry in entries} != expected:
            raise StudyFailure("expected exactly eight distinct study documents")
        assets = {}
        for entry in entries:
            name = Path(entry["filename"])
            if name.is_absolute() or ".." in name.parts:
                raise StudyFailure("study asset path leaves its approved directory")
            path = root / name
            if (
                path.is_symlink()
                or not path.is_file()
                or not path.resolve().is_relative_to(root)
            ):
                raise StudyFailure("study asset is missing or substituted")
            if path.stat().st_size > 20 * 1024 * 1024:
                raise StudyFailure("study document exceeds the existing upload limit")
            data = path.read_bytes()
            if (
                not data.startswith(b"%PDF-")
                or len(data) != entry["size"]
                or hashlib.sha256(data).hexdigest() != entry["sha256"]
            ):
                raise StudyFailure("study PDF hash, size or format does not match")
            assets[entry["code"]] = {**entry, "bytes": data}
        return assets
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise StudyFailure(
            "study manifest or files unavailable; no write attempted"
        ) from error


def demo_module():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "study_demo_boundary", Path(__file__).with_name("seed.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ConnectedStudy:
    def __init__(self, boundary, author, reviewer, assets):
        self.boundary = boundary
        self.author, self.reviewer, self.assets = author, reviewer, assets
        self.sandbox = boundary.load_sandbox().Sandbox(author, author, reviewer)
        self.unit = next(
            row
            for row in self.rows("/organization/units", paginated=False)
            if row["code"] == "DEMO-PRACTICA"
        )
        self.uid = self.get("/auth/me")["id"]
        if self.uid != "20000000-0000-4000-8000-000000000007":
            raise StudyFailure(
                "only the dedicated synthetic study actor may create these examples"
            )
        self.processes, self.documents, self.instances = {}, {}, {}
        self.report = {
            "synthetic": True,
            "company": "tenant-a",
            "unit": self.unit["code"],
            "created": {},
            "preserved": {},
            "phases": [],
        }

    def request(self, method, path, body=None, *, reviewer=False, **kwargs):
        self.sandbox.stage = self.stage
        try:
            return self.sandbox.request(
                self.reviewer if reviewer else self.author, method, path, body, **kwargs
            )
        except Exception as error:
            if type(error).__name__ == "DemoFailure":
                raise StudyFailure(f"{method} {path.split('?')[0]}: {error}") from None
            raise

    def get(self, path, **kwargs):
        return self.request("GET", path, **kwargs)

    def rows(self, path, **kwargs):
        return self.sandbox.rows(self.author, path, **kwargs)

    @property
    def stage(self):
        return getattr(self, "_stage", "study initialization")

    @stage.setter
    def stage(self, value):
        self._stage = value
        self.sandbox.stage = value

    def ensure(self, path, body, *, paginated=True, query=None):
        request_path = path
        if path == "/control-instances":
            from urllib.parse import urlencode

            request_path += "?" + urlencode(
                {key: query[key] for key in ("unit_id", "process_id")}
            )
        row, fresh = self.sandbox.ensure(
            self.author, request_path, body, paginated=paginated, query=query
        )
        self.report["created" if fresh else "preserved"][path] = (
            self.report["created" if fresh else "preserved"].get(path, 0) + 1
        )
        return row, fresh

    def command(self, path, suffix, body=None, *, reviewer=False):
        current = self.get(path)
        return self.request(
            "POST",
            path + suffix,
            {"expected_version": current["row_version"], **(body or {})},
            reviewer=reviewer,
        )

    def scope(self, process=1):
        return {"unit_id": self.unit["id"], "process_id": self.processes[process]["id"]}

    def catalog(self):
        from datetime import UTC, datetime, timedelta

        self.today = datetime.now(UTC).date()
        self.deadline = (self.today + timedelta(days=14)).isoformat()
        self.stage = "connected process catalog"
        topics = [
            (
                "Compras, recepción e inspección",
                "core",
                "Compras y almacén",
                "Orden de compra, lote LOTE-DEMO-2411, certificado y especificación",
                "Registro de inspección, decisión de segregación y material trazable",
            ),
            (
                "Control de documentos y registros",
                "support",
                "Calidad documental",
                "Solicitudes de cambio y procedimientos vigentes",
                "Revisiones controladas, aprobaciones independientes y archivo privado",
            ),
            (
                "Producción y trazabilidad de lotes",
                "core",
                "Operaciones",
                "Material aceptado, orden de fabricación y revisión técnica",
                "Producto identificado, registros completos y evidencia del control",
            ),
            (
                "No conformidades y mejora correctiva",
                "management",
                "Gestión de calidad",
                "Incidencias, evaluación de riesgo y evidencia de control",
                "Contención, causa verificada, acciones y evaluación independiente",
            ),
            (
                "Planificación del sistema y auditorías",
                "management",
                "Dirección de calidad",
                "Objetivos del sistema, procesos, registros y competencias",
                "Programa y planes con alcance, criterios, equipo y agenda",
            ),
            (
                "Atención al cliente y entregas",
                "core",
                "Servicio al cliente",
                "Requisitos acordados, pedido y registro de expedición",
                "Entrega identificada, confirmación y seguimiento de incidencias",
            ),
        ]
        for index, (name, kind, department, inputs, outputs) in enumerate(topics, 1):
            row, _ = self.ensure(
                "/processes",
                {
                    "unit_id": self.unit["id"],
                    "code": f"EST-PROC-{index:03}",
                    "name": "DEMO · " + name,
                    "process_type": kind,
                    "owner_user_id": self.uid,
                    "sequence": index * 10,
                    "department": department,
                    "description": "Caso de estudio ficticio de Perfect Match Industries. Las entradas, salidas y responsables conectan documentos, controles, incidencias y mejora; no representa certificación.",
                    "inputs": inputs,
                    "outputs": outputs,
                },
                query={"unit_id": self.unit["id"]},
            )
            self.processes[index] = row
        self.stage = "meaningful controlled PDF library"
        process_map = {1: 1, 2: 1, 3: 2, 4: 4, 5: 4, 6: 1, 7: 1, 8: 5}
        types = {
            1: "procedure",
            2: "form",
            3: "procedure",
            4: "procedure",
            5: "other",
            6: "other",
            7: "other",
            8: "other",
        }
        for index in range(1, 9):
            asset = self.assets[f"EST-DOC-{index:03}"]
            doc, fresh = self.ensure(
                "/documents",
                {
                    **self.scope(process_map[index]),
                    "code": asset["code"],
                    "title": "DEMO · " + asset["title"],
                    "document_type": types[index],
                    "owner_user_id": self.uid,
                },
                query={"unit_id": self.unit["id"]},
            )
            if fresh:
                rev = self.request(
                    "POST",
                    f"/documents/{doc['id']}/revisions",
                    {
                        "revision": "1.0",
                        "change_summary": "Emisión de ejemplo de estudio, datos ficticios; preparación y revisión por actores demo distintos.",
                        "revision_date": self.today.isoformat(),
                    },
                )
                response = self.author.put(
                    self.boundary.API
                    + f"/documents/{doc['id']}/revisions/{rev['id']}/file",
                    content=asset["bytes"],
                    headers={
                        **self.boundary.csrf(self.author),
                        "Content-Type": "application/pdf",
                    },
                )
                if (
                    response.status_code != 202
                    or response.json().get("file_state") != "clean"
                ):
                    raise StudyFailure(
                        "study PDF not clean; release will not be attempted"
                    )
                rev = next(
                    row
                    for row in self.get(f"/documents/{doc['id']}/revisions")
                    if row["id"] == rev["id"]
                )
                for action in ("submit", "approve", "release"):
                    rev = self.request(
                        "POST",
                        f"/documents/{doc['id']}/revisions/{rev['id']}/{action}",
                        {"expected_version": rev["row_version"]},
                        reviewer=True,
                    )
            revisions = self.get(f"/documents/{doc['id']}/revisions")
            rev = next(
                (
                    row
                    for row in revisions
                    if row["status"] == "active" and row["file_state"] == "clean"
                ),
                None,
            )
            if rev is None or rev.get("file_sha256") != asset["sha256"]:
                raise StudyFailure(
                    "existing study document differs or is incomplete; no overwrite attempted"
                )
            self.documents[index] = {"document": doc, "revision": rev}
        self.report["phases"].append(
            "catalog and eight independently released clean PDFs"
        )

    def document_ref(self, index):
        item = self.documents[index]
        return {
            "document_id": item["document"]["id"],
            "document_revision_id": item["revision"]["id"],
        }

    def controls(self):
        self.stage = "control definitions, instructions and evidence requirements"
        names = [
            "Recepción documentada y verificación de certificado",
            "Uso exclusivo de revisiones documentales vigentes",
            "Identificación y registro de lotes en producción",
            "Seguimiento de acciones y causa raíz",
            "Preparación de planes de auditoría",
            "Confirmación de expedición y requisitos del cliente",
        ]
        process_map = [1, 2, 3, 4, 5, 6]
        doc_map = [1, 3, 2, 4, 8, 2]
        for index, name in enumerate(names, 1):
            scope = self.scope(process_map[index - 1])
            control, fresh = self.ensure(
                "/controls",
                {
                    **scope,
                    "code": f"EST-CTL-{index:03}",
                    "name": "DEMO · " + name,
                    "objective": "Mantener evidencia verificable del trabajo y detectar desviaciones antes de la siguiente decisión del proceso.",
                    "description": "Control ficticio para estudiar definición, implementación, actividades, evidencia y estado. Archivo de referencia: "
                    + f"EST-DOC-{doc_map[index - 1]:03}.",
                    "category": "supplier" if index == 1 else "process",
                    "owner_user_id": self.uid,
                    "guidance_purpose": "Convertir el requisito interno en trabajo asignado y evidencia revisable.",
                    "guidance_why": "Una casilla marcada no sustituye una revisión del registro ni demuestra conformidad del lote.",
                    "implementation_guidance": "Identificar responsable y alcance, ejecutar las actividades, adjuntar revisión documental vigente y enviar evidencia a un revisor independiente.",
                    "recommended_steps": "1. Comprobar documento vigente. 2. Ejecutar verificación. 3. Identificar desviaciones. 4. Conservar archivo y decisión. 5. Revisar por otro actor.",
                    "recommended_tools": "Procedimiento, lista de inspección, identificador de lote y registro controlado.",
                    "evidence_guidance": "Vincular la revisión limpia y liberada; conservar código, revisión y hash. La aceptación de evidencia no declara conforme un lote no conforme.",
                    "practical_notes": "Datos de estudio: sin clientes reales, sin certificación ni afirmación de auditoría ejecutada.",
                },
                query={"unit_id": self.unit["id"]},
            )
            if fresh:
                for sequence, title in [
                    (10, "Comprobar instrucción y alcance"),
                    (20, "Registrar resultados y desviaciones"),
                ]:
                    self.request(
                        "POST",
                        f"/controls/{control['id']}/activities",
                        {
                            "sequence": sequence,
                            "name": title,
                            "description": "Actividad de estudio asociada al proceso y al archivo controlado.",
                            "objective": "Demostrar trabajo realizado con resultado y responsable identificables.",
                            "why_it_matters": "Permite reconstruir qué se revisó y con qué información.",
                            "implementation_steps": "Consultar el PDF vigente, identificar lote o registro, completar el resultado y justificar cualquier desviación.",
                            "success_criteria": "Código de registro, fecha, resultado y responsable completos; las incidencias quedan relacionadas.",
                            "activity_kind": "qms_implementation",
                            "readiness_required": True,
                            "responsible_role": "Responsable del proceso de la sede demo",
                            "expected_output": "Registro trazable de comprobación con resultado y seguimiento.",
                            "evidence_expectations": "PDF de estudio vigente, registro de verificación y decisión independiente.",
                        },
                    )
                for sequence, title in [
                    (10, "Registro de comprobación cumplimentado"),
                    (20, "Documento y certificado de soporte"),
                ]:
                    self.request(
                        "POST",
                        f"/controls/{control['id']}/evidence-requirements",
                        {
                            "sequence": sequence,
                            "name": title,
                            "description": "Soporte documental de la ejecución ficticia del control.",
                            "acceptance_criteria": "Mismo alcance, lote o registro identificable, revisión vigente, archivo limpio y decisión de revisión por actor distinto.",
                            "evidence_type": "document",
                            "mandatory": True,
                        },
                    )
                if index <= 3:
                    self.command(f"/controls/{control['id']}", "/activate")
            if index > 3:
                continue
            instance, fresh_instance = self.ensure(
                "/control-instances",
                {
                    "control_id": control["id"],
                    "code": f"EST-IMP-{index:03}",
                    "name": "DEMO · " + name,
                    "owner_user_id": self.uid,
                    "applicability": "applicable",
                    "target_date": self.deadline,
                    "notes": "Aplicación de estudio en DEMO-PRACTICA. Las actividades y requisitos son snapshots de la definición activada.",
                },
                query={**scope},
            )
            if fresh_instance:
                self.command(
                    f"/control-instances/{instance['id']}",
                    "/transition",
                    {
                        "target_status": "in_progress",
                        "decision": "Iniciar la implementación ficticia con actividades y soporte documental identificados.",
                    },
                )
                tasks = self.rows(
                    "/control-instance-activities",
                    paginated=False,
                    instance_id=instance["id"],
                )
                for task in tasks:
                    task = self.request(
                        "PATCH",
                        f"/control-instance-activities/{task['id']}",
                        {
                            "expected_version": task["row_version"],
                            "assigned_to_user_id": self.uid,
                            "target_date": self.deadline,
                            "notes": "Actividad asignada para estudio; registrar resultados antes de completar.",
                        },
                    )
                    if index <= 2:
                        for target in ("in_progress", "under_review", "completed"):
                            task = self.request(
                                "POST",
                                f"/control-instance-activities/{task['id']}/transition",
                                {
                                    "expected_version": task["row_version"],
                                    "target_status": target,
                                    "decision": "Paso de ejercicio ejecutado según el procedimiento de estudio.",
                                    "completion_summary": "Verificados identificación, documento vigente y trazabilidad del registro. Desviaciones del caso se siguen por NCR y CAPA, no se omiten.",
                                },
                            )
                evidence = self.rows(
                    "/control-instance-evidence",
                    paginated=False,
                    instance_id=instance["id"],
                )
                for offset, item in enumerate(evidence):
                    doc_index = (2 if offset == 0 else 7) if index == 1 else 3
                    item = self.request(
                        "PATCH",
                        f"/control-instance-evidence/{item['id']}",
                        {
                            "expected_version": item["row_version"],
                            "evidence_summary": "Evidencia ficticia que identifica el registro y el archivo de soporte; aceptar el soporte no equivale a liberar material no conforme.",
                            **(self.document_ref(doc_index) if index <= 2 else {}),
                        },
                    )
                    if index <= 2:
                        item = self.request(
                            "POST",
                            f"/control-instance-evidence/{item['id']}/submit",
                            {"expected_version": item["row_version"]},
                        )
                        self.request(
                            "POST",
                            f"/control-instance-evidence/{item['id']}/review",
                            {
                                "expected_version": item["row_version"],
                                "target_status": "accepted",
                                "decision": "Revisión independiente ficticia: archivo vigente, limpio, trazable y adecuado como soporte del resultado declarado.",
                            },
                            reviewer=True,
                        )
                if index <= 2:
                    for status in ("under_review", "implemented"):
                        self.command(
                            f"/control-instances/{instance['id']}",
                            "/transition",
                            {
                                "target_status": status,
                                "decision": "Actividades requeridas completas y evidencias obligatorias aceptadas por revisor distinto.",
                            },
                        )
            self.instances[index] = self.get(f"/control-instances/{instance['id']}")
        self.report["phases"].append(
            "six detailed controls, three implementations, generated tasks and documentary evidence"
        )

    def link(self, path, suffix, body):
        return self.request(
            "POST",
            path + suffix,
            {"expected_version": self.get(path)["row_version"], **body},
        )

    def risks_and_ncrs(self):
        self.stage = "linked risks and opportunities"
        self.risks, self.ncrs = {}, {}
        topics = [
            (
                "Certificado de material incompleto en recepción",
                "supplier",
                4,
                5,
                "action_required",
            ),
            ("Uso de revisión documental sustituida", "document", 3, 5, "monitoring"),
            (
                "Pérdida de trazabilidad durante la identificación del lote",
                "process",
                3,
                4,
                "assessed",
            ),
            ("Entrega sin confirmación de requisitos", "customer", 2, 4, "draft"),
            (
                "Acceso a registros fuera de responsabilidad asignada",
                "security",
                2,
                5,
                "assessed",
            ),
            (
                "Reducir el tiempo de inspección sin omitir verificaciones",
                "process",
                3,
                4,
                "monitoring",
            ),
            (
                "Recurrencia de certificado tras acciones verificadas",
                "supplier",
                2,
                3,
                "closed",
            ),
            (
                "Preparación insuficiente del programa de auditoría",
                "strategic",
                3,
                3,
                "draft",
            ),
        ]
        for index, (name, category, likelihood, impact, desired) in enumerate(
            topics, 1
        ):
            process = (
                2
                if index in (2, 5)
                else 3
                if index == 3
                else 6
                if index == 4
                else 5
                if index == 8
                else 1
            )
            risk, fresh = self.ensure(
                "/risks",
                {
                    **self.scope(process),
                    "code": f"EST-RSK-{index:03}",
                    "name": "DEMO · " + name,
                    "risk_type": "opportunity" if index == 6 else "risk",
                    "category": category,
                    "source": "Evaluación interna de los casos ficticios EST-PROC y EST-DOC.",
                    "description": "Caso de estudio: "
                    + name
                    + ". Revisar el archivo asociado, el control aplicado y el seguimiento; no representa una evaluación de un cliente real.",
                    "cause": "Responsabilidades o verificaciones del proceso no suficientemente reflejadas en el registro de trabajo.",
                    "potential_effect": "Uso de información incompleta, retrabajo, retraso y dificultad para demostrar trazabilidad.",
                    "benefit": "Reducir espera manteniendo trazabilidad y revisión independiente."
                    if index == 6
                    else "",
                    "opportunity_action": "Medir el ciclo del registro y probar un checklist simplificado."
                    if index == 6
                    else "",
                    "mitigation_plan": "Aplicar el control relacionado, conservar su evidencia y seguir las incidencias mediante NCR/CAPA. Ver EST-DOC-006.",
                    "owner_user_id": self.uid,
                    "likelihood": likelihood,
                    "impact": impact,
                    "residual_likelihood": 2,
                    "residual_impact": 3,
                    "response_strategy": "enhance" if index == 6 else "mitigate",
                    "target_date": self.deadline,
                    "review_date": self.deadline,
                },
                query={"unit_id": self.unit["id"]},
            )
            if fresh:
                instance = self.instances[
                    2 if index in (2, 5) else 3 if index == 3 else 1
                ]
                self.link(
                    f"/risks/{risk['id']}",
                    "/control-links",
                    {"control_instance_id": instance["id"]},
                )
                self.link(
                    f"/risks/{risk['id']}",
                    "/document-links",
                    self.document_ref(3 if index in (2, 5) else 8 if index == 8 else 6),
                )
                targets = (
                    []
                    if desired == "draft"
                    else ["assessed"]
                    + (
                        ["action_required"]
                        if desired == "action_required"
                        else ["monitoring", "closed"]
                        if desired == "closed"
                        else ["monitoring"]
                        if desired == "monitoring"
                        else []
                    )
                )
                for state in targets:
                    self.command(
                        f"/risks/{risk['id']}",
                        "/transition",
                        {
                            "target_state": state,
                            "decision": "Evaluación ficticia revisada con el soporte y los controles relacionados.",
                            **(
                                {
                                    "closure_notes": "Caso de estudio cerrado tras seguimiento ficticio; se conserva la historia y el vínculo al control."
                                }
                                if state == "closed"
                                else {}
                            ),
                        },
                        reviewer=True,
                    )
            self.risks[index] = self.get(f"/risks/{risk['id']}")
        self.stage = "nonconformities with documentary, risk and evidence traceability"
        names = [
            "Certificado incompleto del lote LOTE-DEMO-2411",
            "Copia local de procedimiento sustituido",
            "Identificación de lote pendiente de confirmar",
            "Registro de expedición sin confirmación",
            "Alcance de auditoría sin referencia documental",
            "Reporte duplicado de certificado",
        ]
        desired_states = [
            "action_required",
            "action_required",
            "draft",
            "containment",
            "investigation",
            "cancelled",
        ]
        for index, (name, desired) in enumerate(
            zip(names, desired_states, strict=True), 1
        ):
            ncr, fresh = self.ensure(
                "/nonconformities",
                {
                    **self.scope(
                        2 if index == 2 else 6 if index == 4 else 5 if index == 5 else 1
                    ),
                    "code": f"EST-NCR-{index:03}",
                    "name": "DEMO · " + name,
                    "source_type": "supplier"
                    if index in (1, 6)
                    else "document"
                    if index == 2
                    else "internal",
                    "severity": "major" if index == 1 else "minor",
                    "description": "Registro ficticio para reconstruir qué requisito interno no se cumplió, qué archivo lo demuestra y qué seguimiento corresponde. "
                    + name,
                    "detected_date": self.today.isoformat(),
                    "owner_user_id": self.uid,
                    "containment_required": index in (1, 4),
                    "containment_action": "Identificar y segregar el lote o registro; detener su uso hasta completar la verificación."
                    if index in (1, 4)
                    else "",
                    "containment_owner_user_id": self.uid if index in (1, 4) else None,
                    "containment_date": self.today.isoformat()
                    if index in (1, 4)
                    else None,
                    "containment_completed": index == 1,
                    "disposition": "rework" if index == 1 else "information_only",
                    "disposition_notes": "Completar y verificar el soporte antes de liberar el material."
                    if index == 1
                    else "Conservar el registro como caso ficticio de estudio.",
                    "root_cause_summary": "La actualización del proceso no asignó explícitamente la revisión del documento relacionado.",
                    "target_date": self.deadline,
                },
                query={"unit_id": self.unit["id"]},
            )
            if fresh:
                instance = self.instances[2 if index == 2 else 1]
                evidence = self.rows(
                    "/control-instance-evidence",
                    paginated=False,
                    instance_id=instance["id"],
                )[0]
                for suffix, payload in [
                    ("/risk-links", {"risk_id": self.risks[min(index, 5)]["id"]}),
                    ("/control-links", {"control_instance_id": instance["id"]}),
                    ("/evidence-links", {"evidence_id": evidence["id"]}),
                    ("/document-links", self.document_ref(3 if index == 2 else 2)),
                ]:
                    self.link(f"/nonconformities/{ncr['id']}", suffix, payload)
                targets = (
                    []
                    if desired == "draft"
                    else ["cancelled"]
                    if desired == "cancelled"
                    else ["open"]
                    + (["containment"] if index in (1, 4) else [])
                    + ([] if desired == "containment" else ["investigation"])
                    + (["action_required"] if desired == "action_required" else [])
                )
                for state in targets:
                    self.command(
                        f"/nonconformities/{ncr['id']}",
                        "/transition",
                        {
                            "target_state": state,
                            "decision": "Registro duplicado de estudio, conservado sin borrado."
                            if state == "cancelled"
                            else "Decisión ficticia del ejercicio con contención y soporte identificados.",
                        },
                        reviewer=state != "open",
                    )
            self.ncrs[index] = self.get(f"/nonconformities/{ncr['id']}")
        self.report["phases"].append(
            "eight risks/opportunities and six NCRs with persistent cross-module snapshots"
        )

    def capas(self):
        from datetime import timedelta

        self.stage = "CAPA analysis, linked evidence and assigned actions"
        topics = [
            (
                "Completar verificación del certificado del proveedor",
                "ncr",
                1,
                "implementation",
            ),
            ("Evitar uso de revisiones sustituidas", "ncr", 2, "closed"),
            (
                "Investigar pérdidas de identificación durante producción",
                "risk",
                3,
                "analysis",
            ),
            (
                "Mejorar revisión de requisitos de entrega",
                "other",
                None,
                "action_planned",
            ),
        ]
        for index, (name, source, source_index, desired) in enumerate(topics, 1):
            body = {
                **self.scope(
                    2 if index == 2 else 3 if index == 3 else 6 if index == 4 else 1
                ),
                "code": f"EST-CAPA-{index:03}",
                "name": "DEMO · " + name,
                "source_type": source,
                "problem_statement": "Caso de estudio ficticio: "
                + name
                + ". Ver documentos, riesgo e incidencia relacionados; los registros del ejercicio no representan una decisión real sobre un cliente.",
                "owner_user_id": self.uid,
                "target_date": self.deadline,
                "root_cause_method": "fishbone" if index == 3 else "5why",
            }
            if source == "ncr":
                body["source_ncr_id"] = self.ncrs[source_index]["id"]
            elif source == "risk":
                body["source_risk_id"] = self.risks[source_index]["id"]
            else:
                body["source_reference"] = (
                    "EST-PROC-006 · observación interna de mejora ficticia"
                )
            capa, fresh = self.ensure(
                "/capas", body, query={"unit_id": self.unit["id"]}
            )
            if not fresh:
                continue
            base = f"/capas/{capa['id']}"
            instance = self.instances[2 if index == 2 else 1]
            evidence = self.rows(
                "/control-instance-evidence",
                paginated=False,
                instance_id=instance["id"],
            )[0]
            for suffix, payload in [
                ("/document-links", self.document_ref(5)),
                ("/control-links", {"control_instance_id": instance["id"]}),
                ("/evidence-links", {"evidence_id": evidence["id"]}),
            ]:
                self.link(base, suffix, payload)
            capa = self.command(base, "/analysis/start")
            if index == 3:
                analysis = capa["analysis_data"]
                for category in analysis:
                    analysis[category] = [
                        {
                            "statement": "Hipótesis ficticia: "
                            + {
                                "people": "el relevo de responsabilidades no identifica quién confirma el lote",
                                "method": "la instrucción no incluye la nueva verificación",
                                "machine": "el formato del registro no conserva el identificador",
                            }.get(
                                category,
                                "un cambio del proceso no quedó reflejado en su soporte",
                            ),
                            "evidence": "",
                            "rationale": "Hipótesis de estudio pendiente de contrastar con registros y responsables.",
                            "confirmed": False,
                        }
                    ]
            else:
                why = [
                    "El registro no incluía la verificación documental necesaria.",
                    "La instrucción utilizada no incorporó el cambio del proceso.",
                    "La revisión del cambio no identificó todos los documentos relacionados.",
                    "No existía un responsable explícito de verificar esa relación al cerrar el cambio.",
                    "El criterio de cierre no exigía evidencia de revisión de documentos dependientes.",
                ]
                analysis = {f"why{i}": answer for i, answer in enumerate(why, 1)}
            capa = self.request(
                "PATCH",
                base + "/analysis",
                {
                    "expected_version": capa["row_version"],
                    "analysis_data": analysis,
                    "analysis_summary": "Ejercicio ficticio de causalidad; contrastar cada afirmación con los registros indicados en EST-DOC-004.",
                    "verified_root_cause": "En este caso ficticio, el cierre del cambio no asignó la revisión de documentos dependientes ni exigió conservar su evidencia."
                    if index != 3
                    else "",
                },
            )
            if desired == "analysis":
                continue
            self.command(
                base,
                "/plan/start",
                {
                    "plan_summary": "Actualizar instrucción y checklist, asignar responsable, probar su aplicación y comprobar recurrencia. Plan detallado de estudio EST-DOC-005."
                },
            )
            actions = []
            for offset, title in enumerate(
                [
                    "Actualizar checklist y responsable de verificación",
                    "Comprobar aplicación y conservar evidencia",
                ],
                1,
            ):
                current = self.get(base)
                actions.append(
                    self.request(
                        "POST",
                        base + "/actions",
                        {
                            "expected_capa_version": current["row_version"],
                            "title": "DEMO · " + title,
                            "description": "Acción del plan ficticio EST-DOC-005. Registrar implementación y resultado; la persona verificadora debe ser distinta de quien completa.",
                            "owner_user_id": self.uid,
                            "due_date": (
                                self.today + timedelta(days=offset * 3)
                            ).isoformat(),
                        },
                    )
                )
            if desired == "action_planned":
                continue
            self.command(base, "/implementation/start")
            for offset, action in enumerate(actions):
                for state in (
                    ["in_progress"]
                    if desired == "implementation" and offset == 0
                    else []
                    if desired == "implementation"
                    else ["in_progress", "completed", "verified"]
                ):
                    parent = self.get(base)
                    action = self.request(
                        "POST",
                        base + f"/actions/{action['id']}/transition",
                        {
                            "expected_capa_version": parent["row_version"],
                            "expected_action_version": action["row_version"],
                            "target_state": state,
                            **(
                                {
                                    "verification_notes": "Revisión independiente ficticia de los resultados y soporte relacionados, solo para estudio."
                                }
                                if state == "verified"
                                else {}
                            ),
                        },
                        reviewer=state == "verified",
                    )
            if desired == "closed":
                self.command(base, "/effectiveness-review/start")
                self.command(
                    base,
                    "/effectiveness-reviews",
                    {
                        "decision": "effective",
                        "notes": "Caso de estudio ficticio resuelto: se revisaron los ejemplos de registro sin recurrencia en la muestra inventada. No es evidencia productiva ni certificación.",
                    },
                    reviewer=True,
                )
                self.command(
                    base,
                    "/close",
                    {
                        "closure_notes": "Cierre del escenario ficticio después de acciones verificadas y revisión de eficacia por otro actor. Conservar trazabilidad, documentos e historial."
                    },
                    reviewer=True,
                )
                ncr_path = f"/nonconformities/{self.ncrs[2]['id']}"
                for state in ("verification", "closed"):
                    self.command(
                        ncr_path,
                        "/transition",
                        {
                            "target_state": state,
                            "decision": "La CAPA asociada completó el flujo de estudio; se verifica y cierra la incidencia por decisión explícita, no automática.",
                            **(
                                {
                                    "closure_notes": "Escenario documental ficticio cerrado tras verificar las acciones; la revisión histórica y el archivo se conservan."
                                }
                                if state == "closed"
                                else {}
                            ),
                        },
                        reviewer=True,
                    )
        self.report["phases"].append(
            "four CAPAs: live implementation, independently closed case, fishbone hypotheses, pending action plan"
        )

    def audits(self):
        from datetime import timedelta

        self.stage = "audit programs and structured planning"
        self.audits_created = []
        programs = {}
        for index, name in enumerate(
            [
                "Aseguramiento de recepción y proveedores",
                "Control documental y trazabilidad",
                "Mejora del sistema y preparación de auditorías",
            ],
            1,
        ):
            program, fresh = self.ensure(
                "/internal-audits/programs",
                {
                    "unit_id": self.unit["id"],
                    "code": f"EST-PRG-{index:03}",
                    "name": "DEMO · " + name,
                    "objective": "Planificar revisiones de los procesos y documentos del escenario de estudio, con responsabilidades, alcance y criterios internos identificados.",
                    "description": "Programa ficticio para estudiar planificación y decisiones. No se afirma ejecución de auditorías, hallazgos ni certificaciones.",
                    "date_start": self.today.isoformat(),
                    "date_end": (self.today + timedelta(days=90)).isoformat(),
                    "owner_user_id": self.uid,
                },
                query={"unit_id": self.unit["id"]},
            )
            if fresh and index <= 2:
                for state in ("approved", "active"):
                    self.command(
                        f"/internal-audits/programs/{program['id']}",
                        "/transition",
                        {
                            "target_state": state,
                            "decision": "Revisión ficticia del programa y apertura del periodo de planificación de estudio.",
                        },
                        reviewer=True,
                    )
            programs[index] = program
        names = [
            "Recepción y trazabilidad del lote de estudio",
            "Revisiones y disponibilidad documental",
            "Seguimiento de NCR y CAPA",
            "Preparación de auditoría de operaciones",
        ]
        for index, name in enumerate(names, 1):
            starts = self.today + timedelta(days=7 + index * 2)
            audit, fresh = self.ensure(
                "/internal-audits/audits",
                {
                    "unit_id": self.unit["id"],
                    "program_id": programs[1 if index == 1 else 2 if index == 2 else 3][
                        "id"
                    ],
                    "code": f"EST-AUD-{index:03}",
                    "name": "DEMO · " + name,
                    "audit_type": "process",
                    "planned_start": starts.isoformat(),
                    "planned_end": starts.isoformat(),
                    "objective": "Preparar una revisión de los registros del escenario: identificar qué se revisaría, según qué criterio, con quién y en qué horario.",
                    "scope_summary": "Solo planificación ficticia de la sede DEMO-PRACTICA. La ejecución, hallazgos e informe no están implementados ni se simulan como terminados.",
                    "lead_auditor_user_id": self.uid,
                },
                query={"unit_id": self.unit["id"]},
            )
            base = f"/internal-audits/audits/{audit['id']}"
            if fresh:

                def child(suffix, payload, *, parent_path=base):
                    return self.request(
                        "POST",
                        parent_path + suffix,
                        {
                            "expected_audit_version": self.get(parent_path)[
                                "row_version"
                            ],
                            **payload,
                        },
                    )

                scope = child(
                    "/scopes",
                    {
                        "sequence": 10,
                        "title": "Proceso y registros del caso de estudio",
                        "description": "Revisar procedimiento, registros, resultados de control y seguimiento de desviaciones; usar los códigos EST para reconstruir la relación.",
                        "process_id": self.processes[
                            1
                            if index == 1
                            else 2
                            if index == 2
                            else 4
                            if index == 3
                            else 3
                        ]["id"],
                    },
                )["scope"]
                child(
                    "/criteria",
                    {
                        "sequence": 10,
                        "title": "Registros identificables y revisión de información vigente",
                        "requirement": "El registro debe identificar lote o caso, fecha, responsable, documento utilizado y seguimiento de cualquier desviación. Texto interno original del ejercicio, no reproducción de una norma ISO.",
                        "source_type": "internal",
                        "reference": "EST-DOC-008 y EST-DOC-001/003/004 · revisión 1.0 · documentos de estudio",
                        "scope_id": scope["id"],
                    },
                )
                auditor = child(
                    "/team-members",
                    {
                        "user_id": self.uid,
                        "team_role": "auditor",
                        "responsibilities": "Preparar muestreo, revisar trazabilidad y registrar las decisiones de planificación; no iniciar una auditoría no implementada.",
                    },
                )["member"]
                auditee = child(
                    "/team-members",
                    {
                        "user_id": "20000000-0000-4000-8000-000000000001",
                        "team_role": "auditee",
                        "responsibilities": "Presentar los registros ficticios de recepción y explicar el proceso del ejemplo.",
                    },
                )["member"]
                for sequence, hour, title in [
                    (10, 14, "Revisión de procedimiento y registros"),
                    (20, 15, "Trazabilidad de riesgo, incidencia y plan correctivo"),
                ]:
                    child(
                        "/agenda",
                        {
                            "sequence": sequence,
                            "title": title,
                            "objective": "Identificar la información que se consultaría y los responsables de explicar el caso de estudio.",
                            "method": "document_review",
                            "location": "DEMO-PRACTICA · sala de estudio",
                            "starts_at": starts.isoformat() + f"T{hour}:00:00Z",
                            "ends_at": starts.isoformat() + f"T{hour}:45:00Z",
                            "scope_id": scope["id"],
                            "auditor_team_member_id": auditor["id"],
                            "auditee_team_member_id": auditee["id"],
                        },
                    )
                if index <= 2:
                    self.command(
                        base,
                        "/transition",
                        {
                            "target_state": "planned",
                            "decision": "Plan de estudio estructurado; las confirmaciones humanas de independencia y competencia quedan pendientes. No autoriza ejecución.",
                        },
                    )
            preparation = self.request("GET", base + "/independence", reviewer=True)
            if preparation["ready_for_execution"] is not False:
                raise StudyFailure(
                    "planning example must never claim executable readiness"
                )
            self.audits_created.append(
                {
                    "code": audit["code"],
                    "id": audit["id"],
                    "ready_for_execution": False,
                    "human_attestations": "pending; no automatic attestation submitted",
                    "support_document": "EST-DOC-008",
                }
            )
        self.report["phases"].append(
            "three programs and four detailed audit plans; human attestations and execution remain pending"
        )

    def workflows(self):
        self.stage = "assigned workflows with meaningful work and review stages"
        reviewer_id = self.request("GET", "/auth/me", reviewer=True)["id"]
        for index, name in enumerate(
            [
                "Solicitud de revisión documental",
                "Seguimiento de certificado de proveedor",
                "Coordinación de acción de mejora",
                "Plantilla editable de solicitud interna",
            ],
            1,
        ):
            definition, fresh = self.ensure(
                "/workflows",
                {
                    "code": f"EST-WF-{index:03}",
                    "name": "DEMO · " + name,
                    "description": "Coordina tareas del caso EST-PROC/EST-NCR/EST-CAPA. Este workflow no concede permisos ni sustituye las decisiones específicas del documento o CAPA.",
                },
                paginated=False,
            )
            if not fresh:
                continue
            version = self.request(
                "POST", f"/workflows/{definition['id']}/versions", {}
            )
            base = f"/workflows/versions/{version['id']}"
            steps = []
            for position, (key, label, kind) in enumerate(
                [
                    ("prepare", "Preparar información y vincular códigos EST", "task"),
                    ("check", "Comprobar información por otro responsable", "approval"),
                    ("done", "Coordinación completada", "end"),
                ]
            ):
                steps.append(
                    self.request(
                        "POST",
                        base + "/steps",
                        {
                            "step_key": key,
                            "name": label,
                            "step_type": kind,
                            "is_start": position == 0,
                            "position": position,
                        },
                    )
                )
            for position, key in enumerate(["send", "finish"]):
                self.request(
                    "POST",
                    base + "/transitions",
                    {
                        "from_step_id": steps[position]["id"],
                        "to_step_id": steps[position + 1]["id"],
                        "transition_key": key,
                        "label": "Enviar a revisión"
                        if position == 0
                        else "Completar coordinación",
                    },
                )
            for step, user in [(steps[0], self.uid), (steps[1], reviewer_id)]:
                self.request(
                    "POST",
                    base + "/assignments",
                    {
                        "step_id": step["id"],
                        "target_type": "user",
                        "target_user_id": user,
                    },
                )
            if index == 4:
                continue
            self.request("POST", base + "/publish", {})
            instance = self.request(
                "POST",
                "/workflow-instances",
                {
                    "workflow_version_id": version["id"],
                    "title": "DEMO · " + name,
                    "reference": f"EST-WF-{index:03} · {['EST-DOC-003', 'EST-NCR-001 / EST-CAPA-001', 'EST-CAPA-002'][index - 1]}",
                },
            )
            if index >= 2:
                for offset in range(1 if index == 2 else 2):
                    actor = self.author if offset == 0 else self.reviewer
                    actions = self.sandbox.request(
                        actor, "GET", f"/workflow-instances/{instance['id']}/actions"
                    )
                    if not actions:
                        raise StudyFailure(
                            "study workflow lacks an authorized transition"
                        )
                    instance = self.sandbox.request(
                        actor,
                        "POST",
                        f"/workflow-instances/{instance['id']}/transition",
                        {
                            "expected_version": instance["row_version"],
                            "transition_id": actions[0]["id"],
                        },
                    )
        self.report["phases"].append(
            "four workflows: author task, independent review, completed coordination and editable template"
        )

    def verify(self):
        self.stage = "persisted linked study inventory"
        inventory = {}
        collections = {}
        expected_counts = {
            "processes": 6,
            "documents": 8,
            "controls": 6,
            "control-instances": 3,
            "risks": 8,
            "nonconformities": 6,
            "capas": 4,
            "internal-audits/programs": 3,
            "internal-audits/audits": 4,
        }
        for path in [
            "processes",
            "documents",
            "controls",
            "control-instances",
            "risks",
            "nonconformities",
            "capas",
            "internal-audits/programs",
            "internal-audits/audits",
        ]:
            rows = self.rows("/" + path, unit_id=self.unit["id"])
            subset = [row for row in rows if row["code"].startswith("EST-")]
            prefixes = {
                "processes": "EST-PROC-",
                "documents": "EST-DOC-",
                "controls": "EST-CTL-",
                "control-instances": "EST-IMP-",
                "risks": "EST-RSK-",
                "nonconformities": "EST-NCR-",
                "capas": "EST-CAPA-",
                "internal-audits/programs": "EST-PRG-",
                "internal-audits/audits": "EST-AUD-",
            }
            expected_codes = {
                f"{prefixes[path]}{i:03}" for i in range(1, expected_counts[path] + 1)
            }
            if (
                len(subset) != expected_counts[path]
                or {row["code"] for row in subset} != expected_codes
            ):
                raise StudyFailure("study catalog incomplete: " + path)
            collections[path] = subset
            inventory[path] = {
                "count": len(subset),
                "states": {
                    row["code"]: row.get(
                        "state", row.get("implementation_status", row.get("status"))
                    )
                    for row in subset
                },
            }
        structure = {
            "activity_definitions": 0,
            "evidence_requirements": 0,
            "accepted_evidence": 0,
            "active_links": 0,
            "audit_children": 0,
            "workflows": 0,
        }
        for control in collections["controls"]:
            for suffix, metric in [
                ("activities", "activity_definitions"),
                ("evidence-requirements", "evidence_requirements"),
            ]:
                children = self.rows(
                    f"/controls/{control['id']}/{suffix}", paginated=False
                )
                if len(children) != 2:
                    raise StudyFailure(
                        "study control definitions incomplete: " + control["code"]
                    )
                structure[metric] += len(children)
        for instance in collections["control-instances"]:
            tasks = self.rows(
                "/control-instance-activities",
                paginated=False,
                instance_id=instance["id"],
            )
            evidence = self.rows(
                "/control-instance-evidence",
                paginated=False,
                instance_id=instance["id"],
            )
            if len(tasks) != 2 or len(evidence) != 2:
                raise StudyFailure(
                    "study implementation children incomplete: " + instance["code"]
                )
            if instance["code"] in {"EST-IMP-001", "EST-IMP-002"} and (
                instance["implementation_status"] != "implemented"
                or any(x["status"] != "completed" for x in tasks)
                or any(
                    x["status"] != "accepted" or not x["document_revision_id"]
                    for x in evidence
                )
            ):
                raise StudyFailure(
                    "study completed implementation is not evidenced: "
                    + instance["code"]
                )
            structure["accepted_evidence"] += sum(
                x["status"] == "accepted" for x in evidence
            )
        for family, suffixes in [
            ("risks", ["control-links", "document-links"]),
            (
                "nonconformities",
                ["risk-links", "control-links", "evidence-links", "document-links"],
            ),
            ("capas", ["document-links", "control-links", "evidence-links"]),
        ]:
            for parent in collections[family]:
                for suffix in suffixes:
                    links = self.rows(f"/{family}/{parent['id']}/{suffix}")
                    active = [x for x in links if x["status"] == "active"]
                    if not active:
                        raise StudyFailure(
                            "study relationship missing: "
                            + parent["code"]
                            + "/"
                            + suffix
                        )
                    structure["active_links"] += len(active)
                if (
                    family == "capas"
                    and parent["code"] == "EST-CAPA-001"
                    and parent["state"]
                    not in {
                        "implementation",
                        "effectiveness_review",
                        "effective",
                        "closed",
                    }
                ):
                    raise StudyFailure(
                        "study implementation CAPA scenario is incomplete or changed"
                    )
                if family == "capas" and parent["code"] == "EST-CAPA-003":
                    data = parent.get("analysis_data", {})
                    if (
                        parent.get("root_cause_method") != "fishbone"
                        or not data
                        or any(not causes for causes in data.values())
                    ):
                        raise StudyFailure(
                            "study fishbone hypotheses are incomplete or changed"
                        )
                if (
                    family == "capas"
                    and parent["code"] == "EST-CAPA-004"
                    and parent["state"]
                    not in {
                        "action_planned",
                        "implementation",
                        "effectiveness_review",
                        "effective",
                        "closed",
                    }
                ):
                    raise StudyFailure(
                        "study action-plan CAPA scenario is incomplete or changed"
                    )
                if family == "capas" and parent["code"] != "EST-CAPA-003":
                    actions = self.rows(f"/capas/{parent['id']}/actions")
                    if len(actions) < 2:
                        raise StudyFailure(
                            "study CAPA action plan incomplete: " + parent["code"]
                        )
                    if parent["state"] == "closed" and any(
                        x["state"] != "verified" for x in actions
                    ):
                        raise StudyFailure(
                            "closed study CAPA lacks independently verified actions"
                        )
        audit_plans = []
        for audit in collections["internal-audits/audits"]:
            base = f"/internal-audits/audits/{audit['id']}"
            for suffix, expected in [
                ("scopes", 1),
                ("criteria", 1),
                ("team-members", 2),
                ("agenda", 2),
            ]:
                children = self.rows(base + "/" + suffix)
                if len(children) < expected:
                    raise StudyFailure(
                        "study audit plan incomplete: " + audit["code"] + "/" + suffix
                    )
                structure["audit_children"] += len(children)
            preparation = self.request("GET", base + "/independence", reviewer=True)
            competence = self.request("GET", base + "/competence", reviewer=True)
            if preparation["ready_for_execution"] is not False or not any(
                x["code"] == "execution_workflow" and x["status"] == "blocked"
                for x in preparation["checks"]
            ):
                raise StudyFailure(
                    "study audit incorrectly claims executable readiness"
                )
            audit_plans.append(
                {
                    "code": audit["code"],
                    "state": audit["state"],
                    "ready_for_execution": False,
                    "independence_reviews": preparation["review_version"],
                    "competence_reviews": competence["review_version"],
                    "support_document": "EST-DOC-008",
                }
            )
        definitions = self.rows("/workflows", paginated=False)
        workflows = [x for x in definitions if x["code"].startswith("EST-WF-")]
        if {x["code"] for x in workflows} != {f"EST-WF-{i:03}" for i in range(1, 5)}:
            raise StudyFailure("study workflow catalog incomplete")
        instances = self.rows("/workflow-instances", paginated=False)
        workflow_states = {}
        for definition in workflows:
            versions = self.rows(
                f"/workflows/{definition['id']}/versions", paginated=False
            )
            if not versions:
                raise StudyFailure("study workflow has no version")
            version = next(
                (x for x in versions if x["status"] == "published"), versions[0]
            )
            base = f"/workflows/versions/{version['id']}"
            for suffix, expected in [
                ("steps", 3),
                ("transitions", 2),
                ("assignments", 2),
            ]:
                if len(self.rows(base + "/" + suffix, paginated=False)) < expected:
                    raise StudyFailure(
                        "study workflow graph incomplete: " + definition["code"]
                    )
            related = [
                x for x in instances if x["workflow_version_id"] == version["id"]
            ]
            if definition["code"] != "EST-WF-004" and not related:
                raise StudyFailure(
                    "study workflow execution example missing: " + definition["code"]
                )
            if definition["code"] == "EST-WF-002":
                steps = self.rows(base + "/steps", paginated=False)
                review_step = next(
                    (step for step in steps if step["step_key"] == "check"), None
                )
                if not review_step or not any(
                    x["status"] == "completed"
                    or x["current_step_id"] == review_step["id"]
                    for x in related
                ):
                    raise StudyFailure(
                        "study independent-review workflow has not reached review"
                    )
            workflow_states[definition["code"]] = {
                "version_status": version["status"],
                "instance_states": [x["status"] for x in related],
            }
            structure["workflows"] += 1
        validate_milestones(
            collections["capas"], workflow_states, collections["nonconformities"]
        )
        inventory["workflow_states"] = workflow_states
        if set(self.documents) != set(range(1, 9)):
            raise StudyFailure("study document verification incomplete")
        inventory["structure"] = structure
        inventory["audits"] = audit_plans
        files = []
        for index, item in self.documents.items():
            response = self.author.get(
                self.boundary.API
                + f"/documents/{item['document']['id']}/revisions/{item['revision']['id']}/file"
            )
            if (
                response.status_code != 200
                or hashlib.sha256(response.content).hexdigest()
                != self.assets[f"EST-DOC-{index:03}"]["sha256"]
            ):
                raise StudyFailure(
                    "persisted document download hash does not match study PDF"
                )
            files.append(item["document"]["code"])
        inventory["verified_pdf_downloads"] = files
        inventory["actions"] = self.get("/action-center", params={"limit": 200})[
            "summary"
        ]
        self.report["inventory"] = inventory
        self.report["status"] = "PASS"
        return self.report


def main():
    import argparse
    import stat
    from contextlib import ExitStack

    import httpx
    from dotenv import dotenv_values

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--assets", type=Path, required=True)
    parser.add_argument("--backup-manifest", type=Path)
    parser.add_argument("--report-file", type=Path)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--apply", action="store_true")
    modes.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if (
        args.env_file.is_symlink()
        or stat.S_IMODE(args.env_file.stat().st_mode) != 0o600
    ):
        raise StudyFailure(
            "demo credentials require the existing private configuration"
        )
    env = dotenv_values(args.env_file)
    boundary = demo_module()
    if (
        env.get("DEMO_ORIGIN") != boundary.ORIGIN
        or env.get("POSTGRES_DB") != "pmqms_demo"
    ):
        raise StudyFailure("refusing a target outside the approved synthetic demo")
    assets = load_assets(args.assets)
    if args.apply:
        if not args.backup_manifest:
            raise StudyFailure(
                "verified recovery checkpoint required before adding study records"
            )
        backup = json.loads(args.backup_manifest.read_text())
        if (
            backup.get("checkpoint") != "CP-CONNECTED-DATA-00"
            or backup.get("tables") != 57
            or not backup.get("restoration", "").startswith("PASS")
        ):
            raise StudyFailure(
                "recovery verification unavailable; no study write attempted"
            )
    study = None
    with ExitStack() as stack:
        clients = []
        try:
            for username, key in [
                ("pmc-demo-full", "KEYCLOAK_DEMO_FULL_PASSWORD"),
                ("pmc-multi-user", "KEYCLOAK_MULTI_USER_PASSWORD"),
            ]:
                client = stack.enter_context(
                    httpx.Client(
                        timeout=120,
                        follow_redirects=False,
                        event_hooks={"request": [boundary.check_request]},
                    )
                )
                clients.append(client)
                boundary.login(client, username, env[key])
                response = client.get(boundary.API + "/auth/tenants")
                if response.status_code != 200:
                    raise StudyFailure("study company lookup unavailable")
                company = next(
                    (row for row in response.json() if row["slug"] == "tenant-a"), None
                )
                if company is None:
                    raise StudyFailure("study actor is not in the required company")
                response = client.post(
                    boundary.API + "/auth/tenant",
                    json={"tenant_id": company["id"]},
                    headers=boundary.csrf(client),
                )
                if response.status_code != 200:
                    raise StudyFailure("study company selection failed")
            study = ConnectedStudy(boundary, *clients, assets)
            if args.apply:
                for phase in [
                    study.catalog,
                    study.controls,
                    study.risks_and_ncrs,
                    study.capas,
                    study.audits,
                    study.workflows,
                ]:
                    phase()
                    if args.report_file:
                        args.report_file.write_text(
                            json.dumps(
                                {**study.report, "status": "in_progress"},
                                ensure_ascii=False,
                                indent=2,
                            )
                            + "\n"
                        )
                        args.report_file.chmod(0o600)
            else:
                study.stage = "read-only study hydration"
                processes = study.rows("/processes", unit_id=study.unit["id"])
                study.processes = {
                    index: next(
                        row
                        for row in processes
                        if row["code"] == f"EST-PROC-{index:03}"
                    )
                    for index in range(1, 7)
                }
                docs = study.rows("/documents", unit_id=study.unit["id"])
                for index in range(1, 9):
                    doc = next(
                        row for row in docs if row["code"] == f"EST-DOC-{index:03}"
                    )
                    revision = next(
                        row
                        for row in study.get(f"/documents/{doc['id']}/revisions")
                        if row["status"] == "active" and row["file_state"] == "clean"
                    )
                    study.documents[index] = {"document": doc, "revision": revision}
            result = study.verify()
            if args.report_file:
                args.report_file.write_text(
                    json.dumps(result, ensure_ascii=False, indent=2) + "\n"
                )
                args.report_file.chmod(0o600)
            print(json.dumps(result, ensure_ascii=False))
        except Exception as error:  # Retain only safe stage/type, then re-raise.
            if args.report_file:
                args.report_file.write_text(
                    json.dumps(
                        {
                            **(study.report if study else {}),
                            "status": "FAIL",
                            "stage": study.stage if study else "authentication",
                            "exception": type(error).__name__,
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                    + "\n"
                )
                args.report_file.chmod(0o600)
            raise
        finally:
            for client in clients:
                if "pm_csrf" in client.cookies:
                    try:
                        client.post(
                            boundary.API + "/auth/logout", headers=boundary.csrf(client)
                        )
                    except httpx.HTTPError:
                        pass


if __name__ == "__main__":
    try:
        main()
    except Exception as error:  # noqa: BLE001 -- never print private authentication URLs/bodies
        message = (
            str(error) if isinstance(error, StudyFailure) else type(error).__name__
        )
        raise SystemExit("Connected study stopped: " + message) from None

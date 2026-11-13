from __future__ import annotations

from collections.abc import Awaitable, Callable
from uuid import uuid4

from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from pmc_api import __version__
from pmc_api.action_center import router as action_center_router
from pmc_api.antivirus import scanner_is_ready
from pmc_api.audit import router as audit_router
from pmc_api.auth import router as auth_router
from pmc_api.capa import router as capa_router
from pmc_api.capa_links import router as capa_links_router
from pmc_api.capa_trace_links import router as capa_trace_links_router
from pmc_api.config import get_settings
from pmc_api.control_definitions import router as control_definitions_router
from pmc_api.control_instance_activities import router as control_instance_activities_router
from pmc_api.control_instance_evidence import router as control_instance_evidence_router
from pmc_api.controls import router as controls_router
from pmc_api.database import database_is_ready
from pmc_api.documents import router as documents_router
from pmc_api.internal_audit_agenda import router as internal_audit_agenda_router
from pmc_api.internal_audit_competence import router as internal_audit_competence_router
from pmc_api.internal_audit_criteria import router as internal_audit_criteria_router
from pmc_api.internal_audit_independence import router as internal_audit_independence_router
from pmc_api.internal_audit_scope import router as internal_audit_scope_router
from pmc_api.internal_audit_team import router as internal_audit_team_router
from pmc_api.internal_audits import router as internal_audits_router
from pmc_api.ncr_links import router as ncr_links_router
from pmc_api.nonconformities import router as nonconformities_router
from pmc_api.organization import router as organization_router
from pmc_api.processes import router as processes_router
from pmc_api.qms_access import router as qms_access_router
from pmc_api.risk_links import router as risk_links_router
from pmc_api.risks import router as risks_router
from pmc_api.storage import object_storage_is_ready
from pmc_api.tenant import router as tenant_router
from pmc_api.workflow import router as workflow_router


class DependencyHealth(BaseModel):
    database: str
    object_storage: str
    malware_scanner: str


class HealthResponse(BaseModel):
    status: str
    version: str
    dependencies: DependencyHealth


app = FastAPI(
    title="Perfect Match Cloud API",
    version=__version__,
    docs_url=None,
    redoc_url=None,
)
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.web_url],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "X-CSRF-Token"],
)


@app.middleware("http")
async def request_correlation(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    request.state.request_id = uuid4()
    response = await call_next(request)
    response.headers["X-Request-ID"] = str(request.state.request_id)
    return response


app.include_router(auth_router)
app.include_router(action_center_router)
app.include_router(tenant_router)
app.include_router(audit_router)
app.include_router(organization_router)
app.include_router(qms_access_router)
app.include_router(processes_router)
app.include_router(controls_router)
app.include_router(control_definitions_router)
app.include_router(control_instance_activities_router)
app.include_router(control_instance_evidence_router)
app.include_router(documents_router)
app.include_router(internal_audits_router)
app.include_router(internal_audit_scope_router)
app.include_router(internal_audit_team_router)
app.include_router(internal_audit_agenda_router)
app.include_router(internal_audit_independence_router)
app.include_router(internal_audit_competence_router)
app.include_router(internal_audit_criteria_router)
app.include_router(nonconformities_router)
app.include_router(capa_router)
app.include_router(capa_links_router)
app.include_router(capa_trace_links_router)
app.include_router(ncr_links_router)
app.include_router(risks_router)
app.include_router(risk_links_router)
app.include_router(workflow_router)


@app.get("/health", response_model=HealthResponse)
def health(response: Response) -> HealthResponse:
    database_ready = database_is_ready()
    storage_ready = object_storage_is_ready()
    scanner_ready = scanner_is_ready()
    healthy = database_ready and storage_ready and scanner_ready
    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return HealthResponse(
        status="ok" if healthy else "degraded",
        version=__version__,
        dependencies=DependencyHealth(
            database="ok" if database_ready else "unavailable",
            object_storage="ok" if storage_ready else "unavailable",
            malware_scanner="ok" if scanner_ready else "unavailable",
        ),
    )

from __future__ import annotations

from collections.abc import Awaitable, Callable
from uuid import uuid4

from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from pmc_api import __version__
from pmc_api.audit import router as audit_router
from pmc_api.auth import router as auth_router
from pmc_api.config import get_settings
from pmc_api.database import database_is_ready
from pmc_api.organization import router as organization_router
from pmc_api.storage import object_storage_is_ready
from pmc_api.tenant import router as tenant_router


class DependencyHealth(BaseModel):
    database: str
    object_storage: str


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
app.include_router(tenant_router)
app.include_router(audit_router)
app.include_router(organization_router)


@app.get("/health", response_model=HealthResponse)
def health(response: Response) -> HealthResponse:
    database_ready = database_is_ready()
    storage_ready = object_storage_is_ready()
    healthy = database_ready and storage_ready
    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return HealthResponse(
        status="ok" if healthy else "degraded",
        version=__version__,
        dependencies=DependencyHealth(
            database="ok" if database_ready else "unavailable",
            object_storage="ok" if storage_ready else "unavailable",
        ),
    )

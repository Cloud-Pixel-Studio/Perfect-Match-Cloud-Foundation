from __future__ import annotations

from fastapi import FastAPI, Response, status
from pydantic import BaseModel

from pmc_api import __version__
from pmc_api.database import database_is_ready
from pmc_api.storage import object_storage_is_ready


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

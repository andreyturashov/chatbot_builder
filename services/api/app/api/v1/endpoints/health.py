from datetime import UTC, datetime

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.db.session import check_db_connection
from app.schemas.health import DbHealthResponse, HealthCheckResponse

router = APIRouter(prefix="/health", tags=["health"])


@router.get(
    "",
    response_model=HealthCheckResponse,
    summary="Service Health Check",
    description="Returns the current operational status of the service.",
)
async def health_check() -> HealthCheckResponse:
    return HealthCheckResponse(
        status="ok",
        service=settings.APP_NAME,
        environment=settings.APP_ENV,
        timestamp=datetime.now(UTC),
    )


@router.get(
    "/db",
    response_model=DbHealthResponse,
    summary="Database Connectivity Check",
    description="Tests connectivity with the PostgreSQL database instance.",
)
async def db_health_check() -> JSONResponse:
    is_connected, error = await check_db_connection()
    status_code = status.HTTP_200_OK if is_connected else status.HTTP_503_SERVICE_UNAVAILABLE

    response_data = DbHealthResponse(
        status="connected" if is_connected else "disconnected",
        database="postgresql+asyncpg",
        error=error,
        timestamp=datetime.now(UTC),
    )

    return JSONResponse(
        status_code=status_code,
        content=response_data.model_dump(mode="json"),
    )

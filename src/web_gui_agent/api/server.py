"""FastAPI app assembly and process-facing health endpoint."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from web_gui_agent.api.routes.tasks import router as task_router
from web_gui_agent.api.schemas.task import ErrorResponse
from web_gui_agent.application.task_service import TaskService
from web_gui_agent.composition_root import build_task_service
from web_gui_agent.config.settings import Settings, get_settings
from web_gui_agent.domain.errors import DomainError, ErrorCode


def create_app(
    settings: Settings | None = None,
    task_service: TaskService | None = None,
) -> FastAPI:
    configured_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        app.state.task_service = task_service or build_task_service(configured_settings)
        yield

    app = FastAPI(
        title="Web GUI Agent",
        version="0.1.0",
        lifespan=lifespan,
    )

    @app.exception_handler(DomainError)
    async def handle_domain_error(_: Request, exc: DomainError) -> JSONResponse:
        status_code = _status_for_error(exc.error.code)
        body = ErrorResponse(code=exc.error.code, message=exc.error.message)
        return JSONResponse(status_code=status_code, content=body.model_dump(mode="json"))

    @app.get("/healthz", tags=["health"])
    async def health_check() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(task_router)
    return app


def _status_for_error(code: ErrorCode) -> int:
    if code is ErrorCode.TASK_NOT_FOUND:
        return status.HTTP_404_NOT_FOUND
    if code in {ErrorCode.INVALID_STATE_TRANSITION, ErrorCode.VERSION_CONFLICT}:
        return status.HTTP_409_CONFLICT
    return status.HTTP_400_BAD_REQUEST


app = create_app()

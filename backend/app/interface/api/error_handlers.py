from __future__ import annotations

import structlog
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.domain.errors import (
    DomainError,
    DuplicateTelemetryError,
    IllegalStateTransitionError,
    InvariantViolationError,
    UnknownZoneError,
    VehicleNotFoundError,
)

log = structlog.get_logger(__name__)

_DOMAIN_STATUS: dict[type[DomainError], int] = {
    InvariantViolationError: status.HTTP_422_UNPROCESSABLE_ENTITY,
    UnknownZoneError: status.HTTP_422_UNPROCESSABLE_ENTITY,
    DuplicateTelemetryError: status.HTTP_409_CONFLICT,
    VehicleNotFoundError: status.HTTP_404_NOT_FOUND,
    IllegalStateTransitionError: status.HTTP_409_CONFLICT,
}


def _problem(
    *,
    status_code: int,
    code: str,
    title: str,
    detail: str,
    errors: list[dict[str, str]] | None = None,
) -> JSONResponse:
    body: dict[str, object] = {
        "type": code,
        "title": title,
        "status": status_code,
        "detail": detail,
    }
    if errors:
        body["errors"] = errors
    return JSONResponse(
        status_code=status_code, content=body, media_type="application/problem+json"
    )


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def _on_domain_error(_req: Request, exc: DomainError) -> JSONResponse:
        status_code = _DOMAIN_STATUS.get(type(exc), status.HTTP_400_BAD_REQUEST)
        log.info("api.domain_error", code=exc.code, status=status_code, message=exc.message)
        return _problem(
            status_code=status_code,
            code=exc.code,
            title=exc.code.replace("_", " ").title(),
            detail=exc.message,
        )

    @app.exception_handler(RequestValidationError)
    async def _on_validation_error(_req: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [
            {
                "field": ".".join(str(p) for p in err.get("loc", ())),
                "code": err.get("type", "invalid"),
                "message": err.get("msg", ""),
            }
            for err in exc.errors()
        ]
        return _problem(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="validation_error",
            title="Validation Error",
            detail="Request body failed validation.",
            errors=errors,
        )

    @app.exception_handler(Exception)
    async def _on_unhandled(_req: Request, exc: Exception) -> JSONResponse:
        log.exception("api.unhandled_error", error=str(exc))
        return _problem(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="internal_error",
            title="Internal Server Error",
            detail="Something went wrong.",
        )

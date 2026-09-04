"""ApiError exception type and FastAPI handlers.

`packages/contracts/README.md`: "FastAPI's default validation body is not
the public contract. Services must map validation failures to `ApiError`
before responding." This module is the single place every service does
that mapping.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .schemas import ApiError, ApiErrorCode


def new_request_id() -> str:
    return f"request_{uuid.uuid4().hex}"


class ApiException(Exception):
    """Raise from any route to produce a contract-shaped ApiError response."""

    def __init__(
        self,
        *,
        error: ApiErrorCode,
        message: str,
        status_code: int,
        retryable: bool,
        details: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.error = error
        self.message = message
        self.status_code = status_code
        self.retryable = retryable
        self.details = details
        self.headers = headers or {}

    def to_body(self, request_id: str) -> dict[str, Any]:
        return ApiError(
            error=self.error,
            message=self.message,
            retryable=self.retryable,
            request_id=request_id,
            details=self.details,
        ).model_dump(mode="json", by_alias=True, exclude_none=True)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiException)
    async def _handle_api_exception(_request: Request, exc: ApiException) -> JSONResponse:
        request_id = new_request_id()
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.to_body(request_id),
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def _handle_validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
        request_id = new_request_id()
        body = ApiError(
            error="invalid_request",
            message="Request does not satisfy the frozen contract.",
            retryable=False,
            request_id=request_id,
            details={"errors": exc.errors()},
        ).model_dump(mode="json", by_alias=True, exclude_none=True)
        return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content=body)

    @app.exception_handler(Exception)
    async def _handle_unexpected_error(_request: Request, _exc: Exception) -> JSONResponse:
        request_id = new_request_id()
        body = ApiError(
            error="internal_error",
            message="An unexpected error occurred.",
            retryable=True,
            request_id=request_id,
        ).model_dump(mode="json", by_alias=True, exclude_none=True)
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=body)

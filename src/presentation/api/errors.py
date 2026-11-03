from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from domain.exceptions import (
    LlmError,
    LlmFailedError,
    LlmUnavailableError,
    NotEnoughDataError,
)
from presentation.api.schemas.cards import ClientErrorResponse, ErrorResponse

logger = logging.getLogger(__name__)

LLM_ERROR_RESPONSES: dict[type[LlmError], tuple[int, str]] = {
    LlmUnavailableError: (503, "Модель временно недоступна, повторите запрос позже"),
    LlmFailedError: (502, "Модель не дала годного ответа, причина в логе сервиса"),
}
INVALID_JSON_DETAIL = "Некорректный JSON в теле запроса"
NOT_OBJECT_DETAIL = "Тело запроса должно быть JSON-объектом"
WRONG_TYPES_DETAIL = "Неверный тип полей: {fields}"
NOT_ENOUGH_DATA_DETAIL = "Мало данных: нужны название и характеристики или описание"
FIELD_PATH_DEPTH = 3


async def handle_llm_error(_: Request, exc: LlmError) -> JSONResponse:
    status_code, detail = LLM_ERROR_RESPONSES[type(exc)]
    logger.error("llm_failure status=%s reason=%s", status_code, exc)
    return JSONResponse(
        status_code=status_code,
        content=ErrorResponse(detail=detail).model_dump(),
    )


async def handle_not_enough_data(_: Request, exc: NotEnoughDataError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=ClientErrorResponse(
            detail=NOT_ENOUGH_DATA_DETAIL,
            missing_fields=list(exc.missing_fields),
        ).model_dump(),
    )


async def handle_request_validation(
    _: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    errors = exc.errors()
    if any(error["type"] == "json_invalid" for error in errors):
        return JSONResponse(
            status_code=400,
            content=ErrorResponse(detail=INVALID_JSON_DETAIL).model_dump(),
        )
    return JSONResponse(
        status_code=422,
        content=ClientErrorResponse(detail=_validation_detail(errors)).model_dump(
            exclude_none=True
        ),
    )


async def handle_http_exception(request: Request, exc: HTTPException) -> JSONResponse:
    if exc.status_code == 400:
        return JSONResponse(
            status_code=400,
            content=ErrorResponse(detail=INVALID_JSON_DETAIL).model_dump(),
        )
    return await http_exception_handler(request, exc)


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(LlmError, handle_llm_error)
    app.add_exception_handler(NotEnoughDataError, handle_not_enough_data)
    app.add_exception_handler(RequestValidationError, handle_request_validation)
    app.add_exception_handler(HTTPException, handle_http_exception)


def _validation_detail(errors: list[dict]) -> str:
    paths = [
        ".".join(str(part) for part in error["loc"][1:FIELD_PATH_DEPTH])
        for error in errors
    ]
    fields = [path for path in dict.fromkeys(paths) if path]
    if not fields:
        return NOT_OBJECT_DETAIL
    return WRONG_TYPES_DETAIL.format(fields=", ".join(fields))

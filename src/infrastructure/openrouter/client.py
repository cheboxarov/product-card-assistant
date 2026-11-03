from __future__ import annotations

import asyncio
import json

from openai import APIConnectionError, APIStatusError, AsyncOpenAI
from openai.types.chat import ChatCompletion

from domain.exceptions import LlmError, LlmFailedError, LlmUnavailableError
from domain.interfaces.infrastructure.llm_client import LlmClient, LlmRequest

ATTEMPT_TIMEOUT_SECONDS = 200
MAX_OUTPUT_TOKENS = 16000
REASON_LIMIT = 300
TEMPORARY_STATUSES = frozenset({408, 429})
FIRST_SERVER_ERROR_STATUS = 500
BAD_REQUEST_STATUS = 400


class OpenRouterClient(LlmClient):
    def __init__(self, *, client: AsyncOpenAI, model: str) -> None:
        self._client = client
        self._model = model

    async def complete_json(self, request: LlmRequest) -> str:
        try:
            async with asyncio.timeout(ATTEMPT_TIMEOUT_SECONDS):
                response = await self._client.chat.completions.create(
                    model=self._model,
                    messages=[
                        {"role": "system", "content": request.system},
                        {"role": "user", "content": request.user},
                    ],
                    response_format={
                        "type": "json_schema",
                        "json_schema": {
                            "name": request.schema_name,
                            "strict": True,
                            "schema": request.json_schema,
                        },
                    },
                    max_tokens=MAX_OUTPUT_TOKENS,
                )
        except TimeoutError as exc:
            raise LlmUnavailableError(
                f"OpenRouter не ответил за {ATTEMPT_TIMEOUT_SECONDS} с",
                retryable=True,
            ) from exc
        except APIConnectionError as exc:
            raise LlmUnavailableError(
                f"Сетевой сбой OpenRouter: {type(exc).__name__}",
                retryable=True,
            ) from exc
        except APIStatusError as exc:
            raise _status_error(exc.status_code, exc.body) from exc
        except json.JSONDecodeError as exc:
            raise LlmFailedError(
                "OpenRouter вернул ответ не в формате JSON",
                retryable=True,
            ) from exc
        return _extract_json(response)


def _extract_json(response: object) -> str:
    if not isinstance(response, ChatCompletion):
        raise LlmFailedError(
            "OpenRouter вернул ответ не в формате JSON", retryable=True
        )
    error = getattr(response, "error", None)
    if error is not None:
        code = error.get("code") if isinstance(error, dict) else None
        raise _status_error(code, error)
    if not response.choices:
        raise LlmFailedError("В ответе OpenRouter нет choices", retryable=True)
    choice = response.choices[0]
    if choice.finish_reason != "stop":
        raise LlmFailedError(
            f"Модель не закончила ответ: finish_reason={choice.finish_reason}",
            retryable=choice.finish_reason == "length",
        )
    content = choice.message.content
    if content is None or not content.strip():
        raise LlmFailedError("Модель вернула пустой ответ", retryable=True)
    return content


def _status_error(status: object, error: object) -> LlmError:
    reason = _reason(status, error)
    if isinstance(status, int) and (
        status in TEMPORARY_STATUSES or status >= FIRST_SERVER_ERROR_STATUS
    ):
        return LlmUnavailableError(reason, retryable=True)
    return LlmFailedError(reason, retryable=False)


def _reason(status: object, error: object) -> str:
    reason = f"OpenRouter ответил {status}"
    if not isinstance(error, dict):
        return reason
    reason = f"{reason}: {error.get('message')}"
    metadata = error.get("metadata")
    if status == BAD_REQUEST_STATUS and isinstance(metadata, dict):
        reason = f"{reason} {metadata.get('raw')}"
    return reason[:REASON_LIMIT]

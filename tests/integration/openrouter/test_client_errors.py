from __future__ import annotations

import asyncio

import httpx2
import pytest

from domain.exceptions import LlmFailedError, LlmUnavailableError
from infrastructure.openrouter import client as client_module
from tests.integration.openrouter.conftest import (
    LLM_REQUEST,
    PROMPT_TEXT,
    TEST_API_KEY,
    completion_body,
)

# Test cases:
# 1. HTTP 408, 429, 5xx: временный сбой
# 2. HTTP 400, 401, 402, 403, 404: постоянный сбой
# 3. HTTP 200 с error: класс сбоя по error.code, как у статусов
# 4. HTTP 200 без choices, с пустым контентом, не JSON: негодный ответ, повторяемый, 502
# 5. finish_reason content_filter и error: постоянный сбой, length: сбой с повтором
# 6. Таймаут и обрыв сети: временный сбой
# 7. Попытка дольше предела: временный сбой
# 8. В причине нет ключа и текста промпта, при 400 есть metadata.raw


async def failure_of(client) -> Exception:
    with pytest.raises((LlmUnavailableError, LlmFailedError)) as caught:
        await client.complete_json(LLM_REQUEST)
    return caught.value


@pytest.mark.parametrize("status", [408, 429, 500, 502, 503])
async def test_case_1(client_for, status) -> None:
    # 1. HTTP 408, 429, 5xx: временный сбой
    # Arrange
    client = client_for(
        lambda _: httpx2.Response(
            status, json={"error": {"code": status, "message": "сбой"}}
        )
    )

    # Act
    error = await failure_of(client)

    # Assert
    assert isinstance(error, LlmUnavailableError)
    assert error.retryable is True


@pytest.mark.parametrize("status", [400, 401, 402, 403, 404])
async def test_case_2(client_for, status) -> None:
    # 2. HTTP 400, 401, 402, 403, 404: постоянный сбой
    # Arrange
    client = client_for(
        lambda _: httpx2.Response(
            status, json={"error": {"code": status, "message": "сбой"}}
        )
    )

    # Act
    error = await failure_of(client)

    # Assert
    assert isinstance(error, LlmFailedError)
    assert error.retryable is False


@pytest.mark.parametrize(
    ("code", "error_type", "retryable"),
    [
        (429, LlmUnavailableError, True),
        (502, LlmUnavailableError, True),
        (401, LlmFailedError, False),
        (None, LlmFailedError, False),
    ],
)
async def test_case_3(client_for, code, error_type, retryable) -> None:
    # 3. HTTP 200 с error: класс сбоя по error.code, как у статусов
    # Arrange
    client = client_for(
        lambda _: httpx2.Response(
            200,
            json={"id": "gen-1", "error": {"code": code, "message": "сбой"}},
        )
    )

    # Act
    error = await failure_of(client)

    # Assert
    assert isinstance(error, error_type)
    assert error.retryable is retryable


@pytest.mark.parametrize(
    "response",
    [
        httpx2.Response(200, json={"id": "gen-1", "choices": []}),
        httpx2.Response(200, json=completion_body(None)),
        httpx2.Response(200, json=completion_body("   ")),
        httpx2.Response(200, text="<html>шлюз</html>"),
        httpx2.Response(
            200,
            content=b"{broken",
            headers={"Content-Type": "application/json"},
        ),
    ],
)
async def test_case_4(client_for, response) -> None:
    # 4. HTTP 200 без choices, с пустым контентом, не JSON: негодный ответ, повторяемый, 502
    # Arrange
    client = client_for(lambda _: response)

    # Act
    error = await failure_of(client)

    # Assert
    assert isinstance(error, LlmFailedError)
    assert error.retryable is True


@pytest.mark.parametrize(
    ("finish_reason", "retryable"),
    [("length", True), ("content_filter", False), ("error", False)],
)
async def test_case_5(client_for, finish_reason, retryable) -> None:
    # 5. finish_reason content_filter и error: постоянный сбой, length: сбой с повтором
    # Arrange
    client = client_for(
        lambda _: httpx2.Response(
            200, json=completion_body('{"a":', finish_reason=finish_reason)
        )
    )

    # Act
    error = await failure_of(client)

    # Assert
    assert isinstance(error, LlmFailedError)
    assert error.retryable is retryable
    assert finish_reason in str(error)


@pytest.mark.parametrize(
    "exception",
    [httpx2.ReadTimeout, httpx2.ConnectError, httpx2.RemoteProtocolError],
)
async def test_case_6(client_for, exception) -> None:
    # 6. Таймаут и обрыв сети: временный сбой
    # Arrange
    def handler(request: httpx2.Request) -> httpx2.Response:
        raise exception("сбой сети", request=request)

    client = client_for(handler)

    # Act
    error = await failure_of(client)

    # Assert
    assert isinstance(error, LlmUnavailableError)
    assert error.retryable is True


async def test_case_7(client_for, monkeypatch) -> None:
    # 7. Попытка дольше предела: временный сбой
    # Arrange
    async def handler(_: httpx2.Request) -> httpx2.Response:
        await asyncio.sleep(5)
        return httpx2.Response(200, json=completion_body("{}"))

    monkeypatch.setattr(client_module, "ATTEMPT_TIMEOUT_SECONDS", 0.05)
    client = client_for(handler)

    # Act
    error = await failure_of(client)

    # Assert
    assert isinstance(error, LlmUnavailableError)
    assert error.retryable is True


async def test_case_8(client_for) -> None:
    # 8. В причине нет ключа и текста промпта, при 400 есть metadata.raw
    # Arrange
    raw = "'required' is required to be supplied"
    client = client_for(
        lambda _: httpx2.Response(
            400,
            json={
                "error": {
                    "code": 400,
                    "message": "Provider returned error",
                    "metadata": {"raw": raw, "provider_name": "Meta"},
                }
            },
        )
    )

    # Act
    reason = str(await failure_of(client))

    # Assert
    assert raw in reason
    assert TEST_API_KEY not in reason
    assert PROMPT_TEXT not in reason

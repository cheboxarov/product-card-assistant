from __future__ import annotations

import asyncio
import logging

from application.services.card_generation import service as service_module
from domain.exceptions import LlmFailedError, LlmUnavailableError
from domain.interfaces.infrastructure.llm_client import LlmRequest
from tests.fakes import FakeLlmClient, card_texts_json, review_json
from tests.integration.api.conftest import CARDS_PATH, MANOMETER

# Test cases:
# 1. Временный сбой дважды: 503, два вызова, одна строка лога без текста промпта
# 2. Постоянный сбой: 502, один вызов, одна строка лога
# 3. Временный сбой, затем успех: 200, повторён только сбойный вызов, лога нет
# 4. Ответ не прошёл схему дважды: 502, два вызова
# 5. Ответ не прошёл схему, затем успех: 200
# 6. Граф не уложился в общий таймаут: 503


def failures(caplog) -> list[logging.LogRecord]:
    return [record for record in caplog.records if record.levelno >= logging.ERROR]


async def test_case_1(api_client_for, caplog) -> None:
    # 1. Временный сбой дважды: 503, два вызова, одна строка лога без текста промпта
    # Arrange
    llm = FakeLlmClient(
        LlmUnavailableError("OpenRouter ответил 429", retryable=True),
        LlmUnavailableError("OpenRouter ответил 500", retryable=True),
    )
    client = api_client_for(llm)

    # Act
    response = await client.post(CARDS_PATH, json=MANOMETER)

    # Assert
    assert response.status_code == 503
    assert response.json() == {
        "detail": "Модель временно недоступна, повторите запрос позже"
    }
    assert len(llm.requests) == 2
    assert [record.getMessage() for record in failures(caplog)] == [
        "llm_failure status=503 reason=OpenRouter ответил 500"
    ]


async def test_case_2(api_client_for, caplog) -> None:
    # 2. Постоянный сбой: 502, один вызов, одна строка лога
    # Arrange
    llm = FakeLlmClient(LlmFailedError("OpenRouter ответил 402", retryable=False))
    client = api_client_for(llm)

    # Act
    response = await client.post(CARDS_PATH, json=MANOMETER)

    # Assert
    assert response.status_code == 502
    assert response.json() == {
        "detail": "Модель не дала годного ответа, причина в логе сервиса"
    }
    assert len(llm.requests) == 1
    assert len(failures(caplog)) == 1


async def test_case_3(api_client_for, caplog) -> None:
    # 3. Временный сбой, затем успех: 200, повторён только сбойный вызов, лога нет
    # Arrange
    llm = FakeLlmClient(
        LlmUnavailableError("OpenRouter ответил 429", retryable=True),
        card_texts_json(),
        review_json(),
    )
    client = api_client_for(llm)

    # Act
    response = await client.post(CARDS_PATH, json=MANOMETER)

    # Assert
    assert response.status_code == 200
    assert len(llm.requests) == 3
    assert failures(caplog) == []


async def test_case_4(api_client_for) -> None:
    # 4. Ответ не прошёл схему дважды: 502, два вызова
    # Arrange
    llm = FakeLlmClient("не json", '{"seo_title": 5}')
    client = api_client_for(llm)

    # Act
    response = await client.post(CARDS_PATH, json=MANOMETER)

    # Assert
    assert response.status_code == 502
    assert len(llm.requests) == 2


async def test_case_5(api_client_for) -> None:
    # 5. Ответ не прошёл схему, затем успех: 200
    # Arrange
    llm = FakeLlmClient("не json", card_texts_json(), review_json())
    client = api_client_for(llm)

    # Act
    response = await client.post(CARDS_PATH, json=MANOMETER)

    # Assert
    assert response.status_code == 200
    assert len(llm.requests) == 3


async def test_case_6(api_client_for, monkeypatch) -> None:
    # 6. Граф не уложился в общий таймаут: 503
    # Arrange
    class SlowLlmClient(FakeLlmClient):
        async def complete_json(self, request: LlmRequest) -> str:
            await asyncio.sleep(5)
            return card_texts_json()

    monkeypatch.setattr(service_module, "GRAPH_TIMEOUT_SECONDS", 0.05)
    client = api_client_for(SlowLlmClient())

    # Act
    response = await client.post(CARDS_PATH, json=MANOMETER)

    # Assert
    assert response.status_code == 503

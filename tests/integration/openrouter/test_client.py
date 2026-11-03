from __future__ import annotations

import json

import httpx2

from tests.integration.openrouter.conftest import (
    LLM_REQUEST,
    PROMPT_TEXT,
    TEST_API_KEY,
    completion_body,
)

# Test cases:
# 1. Клиент шлёт модель, сообщения, строгую схему и предел токенов, возвращает текст ответа
# 2. В теле запроса низкий уровень размышлений, иначе они съедают предел токенов


async def test_case_1(client_for) -> None:
    # 1. Клиент шлёт модель, сообщения, строгую схему и предел токенов, возвращает текст ответа
    # Arrange
    seen: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return httpx2.Response(200, json=completion_body('{"a": 1}'))

    client = client_for(handler)

    # Act
    result = await client.complete_json(LLM_REQUEST)

    # Assert
    assert result == '{"a": 1}'
    assert str(seen[0].url) == "https://openrouter.ai/api/v1/chat/completions"
    assert seen[0].headers["authorization"] == f"Bearer {TEST_API_KEY}"
    body = json.loads(seen[0].content)
    assert body["model"] == "test/model"
    assert body["max_tokens"] == 16000
    assert body["messages"] == [
        {"role": "system", "content": "система"},
        {"role": "user", "content": PROMPT_TEXT},
    ]
    assert body["response_format"] == {
        "type": "json_schema",
        "json_schema": {
            "name": "card_texts",
            "strict": True,
            "schema": {"type": "object"},
        },
    }


async def test_case_2(client_for) -> None:
    # 2. В теле запроса низкий уровень размышлений, иначе они съедают предел токенов
    # Arrange
    seen: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return httpx2.Response(200, json=completion_body('{"a": 1}'))

    client = client_for(handler)

    # Act
    await client.complete_json(LLM_REQUEST)

    # Assert
    assert json.loads(seen[0].content)["reasoning"] == {"effort": "low"}

from __future__ import annotations

from tests.fakes import FakeLlmClient, card_texts_json
from tests.integration.api.conftest import CARDS_PATH, MANOMETER

# Test cases:
# 1. Прибор из задания: 200 по контракту, тексты от модели, характеристики из specs в порядке входа
# 2. Число в specs становится строкой, null становится «данных нет»
# 3. Лишние поля запроса игнорируются
# 4. В порт LLM уходят данные прибора и схема ответа


async def test_case_1(api_client_for) -> None:
    # 1. Прибор из задания: 200 по контракту, тексты от модели, характеристики из specs в порядке входа
    # Arrange
    client = api_client_for(FakeLlmClient(card_texts_json()))

    # Act
    response = await client.post(CARDS_PATH, json=MANOMETER)

    # Assert
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"card", "missing_fields", "needs_clarification", "warnings"}
    assert body["card"]["seo_title"] == "Манометр DM 02 Манотомь 0–1,6 МПа"
    assert body["card"]["commercial"] == {
        "audience": "служба КИПиА",
        "tasks": "контроль давления",
    }
    assert body["card"]["characteristics"] == [
        {"name": name, "value": value} for name, value in MANOMETER["specs"].items()
    ]


async def test_case_2(api_client_for) -> None:
    # 2. Число в specs становится строкой, null становится «данных нет»
    # Arrange
    client = api_client_for(FakeLlmClient(card_texts_json()))
    payload = {**MANOMETER, "specs": {"Диаметр": 100, "Точность": 1.5, "Защита": None}}

    # Act
    response = await client.post(CARDS_PATH, json=payload)

    # Assert
    assert response.json()["card"]["characteristics"] == [
        {"name": "Диаметр", "value": "100"},
        {"name": "Точность", "value": "1.5"},
        {"name": "Защита", "value": "данных нет"},
    ]


async def test_case_3(api_client_for) -> None:
    # 3. Лишние поля запроса игнорируются
    # Arrange
    client = api_client_for(FakeLlmClient(card_texts_json()))

    # Act
    response = await client.post(CARDS_PATH, json={**MANOMETER, "price": 100})

    # Assert
    assert response.status_code == 200


async def test_case_4(api_client_for) -> None:
    # 4. В порт LLM уходят данные прибора и схема ответа
    # Arrange
    llm = FakeLlmClient(card_texts_json())
    client = api_client_for(llm)

    # Act
    await client.post(CARDS_PATH, json=MANOMETER)

    # Assert
    request = llm.requests[0]
    assert "Манометр DM 02" in request.user
    assert "0–1,6 МПа" in request.user
    assert request.schema_name == "card_texts"
    assert set(request.json_schema["properties"]) == {
        "seo_title",
        "seo_description",
        "search_queries",
        "commercial",
    }

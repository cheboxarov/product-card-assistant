from __future__ import annotations

from tests.fakes import CLEAN_DESCRIPTION, FakeLlmClient, card_texts_json, review_json
from tests.integration.api.conftest import CARDS_PATH, MANOMETER

# Test cases:
# 1. Прибор из задания: 200 по контракту, тексты от модели, характеристики из specs в порядке входа
# 2. Число в specs становится строкой, null становится «данных нет»
# 3. Лишние поля запроса игнорируются
# 4. В порт LLM уходят данные прибора и схема ответа


async def test_case_1(api_client_for) -> None:
    # 1. Прибор из задания: 200 по контракту, тексты от модели, характеристики из specs в порядке входа
    # Arrange
    client = api_client_for(FakeLlmClient(card_texts_json(), review_json()))

    # Act
    response = await client.post(CARDS_PATH, json=MANOMETER)

    # Assert
    assert response.status_code == 200
    body = response.json()
    assert list(body) == [
        "card",
        "missing_fields",
        "needs_clarification",
        "warnings",
        "markdown",
    ]
    assert list(body["card"]) == [
        "seo_title",
        "seo_description",
        "characteristics",
        "search_queries",
        "commercial",
    ]
    assert body["card"]["seo_title"] == "Манометр показывающий Манотомь"
    assert body["card"]["seo_description"] == CLEAN_DESCRIPTION
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
    client = api_client_for(FakeLlmClient(card_texts_json(), review_json()))
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
    client = api_client_for(FakeLlmClient(card_texts_json(), review_json()))

    # Act
    response = await client.post(CARDS_PATH, json={**MANOMETER, "price": 100})

    # Assert
    assert response.status_code == 200


async def test_case_4(api_client_for) -> None:
    # 4. В порт LLM уходят данные прибора и схема ответа
    # Arrange
    llm = FakeLlmClient(card_texts_json(), review_json())
    client = api_client_for(llm)

    # Act
    await client.post(CARDS_PATH, json=MANOMETER)

    # Assert
    write, review = llm.requests
    assert "Манометр DM 02" in write.user
    assert "0–1,6 МПа" in write.user
    assert write.schema_name == "card_texts"
    assert write.reasoning_effort is None
    assert set(write.json_schema["properties"]) == {
        "description_facts",
        "missing_characteristics",
        "needs_clarification",
        "seo_title",
        "seo_description",
        "search_queries",
        "commercial",
    }
    assert review.schema_name == "card_review"
    assert review.reasoning_effort == "low"
    assert set(review.json_schema["properties"]) == {"issues"}

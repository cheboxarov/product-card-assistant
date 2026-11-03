from __future__ import annotations

import pytest

from tests.fakes import FakeLlmClient, card_texts_json
from tests.integration.api.conftest import CARDS_PATH, MANOMETER

# Test cases:
# 1. Битый JSON: 400, модель не вызвана
# 2. Неверный тип поля: 422, detail называет поле, модель не вызвана
# 3. Тело не объект или его нет: 422 с русским detail
# 4. Мало данных: 422 с missing_fields, модель не вызвана
# 5. Хватает данных, часть пустая: 200, в missing_fields подписи пустых
# 6. Пустое значение в specs: «данных нет» в списке и название в missing_fields
# 7. Тело не в UTF-8: 400 с русским текстом, модель не вызвана


async def test_case_1(api_client_for) -> None:
    # 1. Битый JSON: 400, модель не вызвана
    # Arrange
    llm = FakeLlmClient()
    client = api_client_for(llm)

    # Act
    response = await client.post(
        CARDS_PATH,
        content=b'{"name": "x",',
        headers={"Content-Type": "application/json"},
    )

    # Assert
    assert response.status_code == 400
    assert response.json() == {"detail": "Некорректный JSON в теле запроса"}
    assert llm.requests == []


@pytest.mark.parametrize(
    ("payload", "field"),
    [
        ({"name": "x", "specs": "строка"}, "specs"),
        ({"name": "x", "specs": []}, "specs"),
        ({"name": 5, "description": "y"}, "name"),
        ({"name": "x", "manufacturer": ["y"]}, "manufacturer"),
        ({"name": "x", "description": {"a": 1}}, "description"),
        ({"name": "x", "specs": {"Вес": {"a": 1}}}, "specs.Вес"),
        ({"name": "x", "specs": {"Вес": [1]}}, "specs.Вес"),
        ({"name": "x", "specs": {"Вес": True}}, "specs.Вес"),
    ],
)
async def test_case_2(api_client_for, payload, field) -> None:
    # 2. Неверный тип поля: 422, detail называет поле, модель не вызвана
    # Arrange
    llm = FakeLlmClient()
    client = api_client_for(llm)

    # Act
    response = await client.post(CARDS_PATH, json=payload)

    # Assert
    assert response.status_code == 422
    assert response.json() == {"detail": f"Неверный тип полей: {field}"}
    assert llm.requests == []


@pytest.mark.parametrize(
    "kwargs",
    [
        {"json": [1, 2]},
        {"json": "строка"},
        {"content": b"", "headers": {"Content-Type": "application/json"}},
    ],
)
async def test_case_3(api_client_for, kwargs) -> None:
    # 3. Тело не объект или его нет: 422 с русским detail
    # Arrange
    client = api_client_for(FakeLlmClient())

    # Act
    response = await client.post(CARDS_PATH, **kwargs)

    # Assert
    assert response.status_code == 422
    assert response.json() == {"detail": "Тело запроса должно быть JSON-объектом"}


@pytest.mark.parametrize(
    ("payload", "missing"),
    [
        ({}, ["Название", "Производитель", "Характеристики", "Описание"]),
        ({"name": "  "}, ["Название", "Производитель", "Характеристики", "Описание"]),
        ({"name": "x"}, ["Производитель", "Характеристики", "Описание"]),
        (
            {"manufacturer": "y", "specs": {"Вес": "1 кг"}, "description": "z"},
            ["Название"],
        ),
        (
            {"name": "x", "manufacturer": "y", "specs": {"Вес": None}},
            ["Вес", "Описание"],
        ),
        (
            {
                "name": "x",
                "manufacturer": "y",
                "specs": {"Вес": "  "},
                "description": "",
            },
            ["Вес", "Описание"],
        ),
    ],
)
async def test_case_4(api_client_for, payload, missing) -> None:
    # 4. Мало данных: 422 с missing_fields, модель не вызвана
    # Arrange
    llm = FakeLlmClient()
    client = api_client_for(llm)

    # Act
    response = await client.post(CARDS_PATH, json=payload)

    # Assert
    assert response.status_code == 422
    assert response.json() == {
        "detail": "Мало данных: нужны название и характеристики или описание",
        "missing_fields": missing,
    }
    assert llm.requests == []


@pytest.mark.parametrize(
    ("payload", "missing"),
    [
        (MANOMETER, []),
        ({**MANOMETER, "manufacturer": None}, ["Производитель"]),
        ({**MANOMETER, "description": "   "}, ["Описание"]),
        ({**MANOMETER, "specs": {}}, []),
        ({"name": "x", "description": "y"}, ["Производитель"]),
    ],
)
async def test_case_5(api_client_for, payload, missing) -> None:
    # 5. Хватает данных, часть пустая: 200, в missing_fields подписи пустых
    # Arrange
    llm = FakeLlmClient(card_texts_json())
    client = api_client_for(llm)

    # Act
    response = await client.post(CARDS_PATH, json=payload)

    # Assert
    assert response.status_code == 200
    assert response.json()["missing_fields"] == missing
    assert len(llm.requests) == 1


async def test_case_6(api_client_for) -> None:
    # 6. Пустое значение в specs: «данных нет» в списке и название в missing_fields
    # Arrange
    client = api_client_for(FakeLlmClient(card_texts_json()))
    payload = {**MANOMETER, "specs": {"Класс точности": "1,5", "Защита": None}}

    # Act
    response = await client.post(CARDS_PATH, json=payload)

    # Assert
    body = response.json()
    assert body["card"]["characteristics"] == [
        {"name": "Класс точности", "value": "1,5"},
        {"name": "Защита", "value": "данных нет"},
    ]
    assert body["missing_fields"] == ["Защита"]


async def test_case_7(api_client_for) -> None:
    # 7. Тело не в UTF-8: 400 с русским текстом, модель не вызвана
    # Arrange
    llm = FakeLlmClient()
    client = api_client_for(llm)

    # Act
    response = await client.post(
        CARDS_PATH,
        content='{"name": "Манометр"}'.encode("cp1251"),
        headers={"Content-Type": "application/json"},
    )

    # Assert
    assert response.status_code == 400
    assert response.json() == {"detail": "Некорректный JSON в теле запроса"}
    assert llm.requests == []

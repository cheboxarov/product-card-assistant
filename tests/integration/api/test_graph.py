from __future__ import annotations

import pytest

from domain.exceptions import LlmFailedError, LlmUnavailableError
from tests.fakes import CLEAN_DESCRIPTION, FakeLlmClient, card_texts_json, review_json
from tests.integration.api.conftest import CARDS_PATH, MANOMETER

# Test cases:
# 1. Чистый проход: написание и ревью, правки нет, warnings пуст
# 2. Замечание кода: правка, успех, замечание ушло модели указанием, в warnings его нет
# 3. Замечание ревью: правка, успех, цитата и причина ушли модели
# 4. Замечания кода и ревью собираются за один проход и уходят в одну правку
# 5. Лимит правок: 3 написания, 3 ревью, незакрытые замечания в warnings текстом для человека
# 6. Ложная цитата ревьюера отброшена: правки нет, warnings пуст
# 7. Ложная цитата факта и выдуманное значение отброшены с warning, остальные факты в списке
# 8. Короткий текст: правки нет, warning есть
# 9. Правка сократила текст ниже 800: warning о длине есть, новой правки нет
# 10. Число вне входа в заголовке и в запросе: правка, модель получила оба замечания
# 11. Число вне входа осталось после лимита: warning для человека
# 12. Сбой ревью: повторён только ревью, написание не повторено
# 13. Сбой правки: повторён тот же запрос правки, счётчик правок не сбился
# 14. Сбой ревью после повторов: 503, черновик не отдаётся
# 15. Постоянный сбой правки: 502, черновик не отдаётся
# 16. Факты, отсутствующие названия и уточнения берутся с первого написания, тексты с последнего
# 17. Вторая правка получает замечания только к последнему тексту
# 18. Правка видит в прошлом ответе списки первого написания
# 19. missing_fields: сначала пустые поля входа, затем названия от модели, дублей нет
# 20. Значение из description попадает в список, а specs главнее
# 21. Пустые specs и manufacturer не доходят до модели ни в написании, ни в ревью, ни в правке
# 22. Подтверждённый факт заполняет пустую строку specs и убирает имя из missing_fields


def filler_issue(quote: str = "контроль давления") -> dict[str, str]:
    return {"kind": "filler", "quote": quote, "reason": "убери фразу"}


LONG_TITLE = "я" * 71


async def test_case_1(api_client_for) -> None:
    # 1. Чистый проход: написание и ревью, правки нет, warnings пуст
    # Arrange
    llm = FakeLlmClient(card_texts_json(), review_json())
    client = api_client_for(llm)

    # Act
    response = await client.post(CARDS_PATH, json=MANOMETER)

    # Assert
    assert response.status_code == 200
    assert response.json()["warnings"] == []
    assert [request.schema_name for request in llm.requests] == [
        "card_texts",
        "card_review",
    ]


async def test_case_2(api_client_for) -> None:
    # 2. Замечание кода: правка, успех, замечание ушло модели указанием, в warnings его нет
    # Arrange
    llm = FakeLlmClient(
        card_texts_json(seo_title=LONG_TITLE),
        review_json(),
        card_texts_json(seo_title="Манометр показывающий"),
        review_json(),
    )
    client = api_client_for(llm)

    # Act
    response = await client.post(CARDS_PATH, json=MANOMETER)

    # Assert
    body = response.json()
    assert body["card"]["seo_title"] == "Манометр показывающий"
    assert body["warnings"] == []
    assert len(llm.requests) == 4
    revision = llm.requests[2].user
    assert "<previous_answer>" in revision
    assert LONG_TITLE in revision
    assert "- Заголовок 71 символов, нужно до 70. Сократи." in revision


async def test_case_3(api_client_for) -> None:
    # 3. Замечание ревью: правка, успех, цитата и причина ушли модели
    # Arrange
    llm = FakeLlmClient(
        card_texts_json(commercial={"audience": "служба КИПиА", "tasks": "вода"}),
        review_json(filler_issue("вода")),
        card_texts_json(),
        review_json(),
    )
    client = api_client_for(llm)

    # Act
    response = await client.post(CARDS_PATH, json=MANOMETER)

    # Assert
    body = response.json()
    assert body["card"]["commercial"]["tasks"] == "контроль давления"
    assert body["warnings"] == []
    assert "- «вода»: убери фразу" in llm.requests[2].user


async def test_case_4(api_client_for) -> None:
    # 4. Замечания кода и ревью собираются за один проход и уходят в одну правку
    # Arrange
    llm = FakeLlmClient(
        card_texts_json(seo_title=LONG_TITLE),
        review_json(filler_issue()),
        card_texts_json(),
        review_json(),
    )
    client = api_client_for(llm)

    # Act
    await client.post(CARDS_PATH, json=MANOMETER)

    # Assert
    revision = llm.requests[2].user
    assert "- Заголовок 71 символов, нужно до 70. Сократи." in revision
    assert "- «контроль давления»: убери фразу" in revision


async def test_case_5(api_client_for) -> None:
    # 5. Лимит правок: 3 написания, 3 ревью, незакрытые замечания в warnings текстом для человека
    # Arrange
    llm = FakeLlmClient(
        card_texts_json(seo_title=LONG_TITLE),
        review_json(filler_issue()),
        card_texts_json(seo_title=LONG_TITLE),
        review_json(filler_issue()),
        card_texts_json(seo_title=LONG_TITLE),
        review_json(
            {
                "kind": "unsupported_claim",
                "quote": "контроль давления",
                "reason": "убери фразу из <device>",
            }
        ),
    )
    client = api_client_for(llm)

    # Act
    response = await client.post(CARDS_PATH, json=MANOMETER)

    # Assert
    assert response.status_code == 200
    assert llm.responses == []
    assert response.json()["warnings"] == [
        "Заголовок длиннее 70 символов (71): сократите его перед публикацией.",
        "Не подтверждено данными о приборе: «контроль давления». Проверьте или уберите.",
    ]


async def test_case_6(api_client_for) -> None:
    # 6. Ложная цитата ревьюера отброшена: правки нет, warnings пуст
    # Arrange
    llm = FakeLlmClient(
        card_texts_json(),
        review_json(filler_issue("такой фразы в текстах нет")),
    )
    client = api_client_for(llm)

    # Act
    response = await client.post(CARDS_PATH, json=MANOMETER)

    # Assert
    assert response.json()["warnings"] == []
    assert len(llm.requests) == 2


async def test_case_7(api_client_for) -> None:
    # 7. Ложная цитата факта и выдуманное значение отброшены с warning, остальные факты в списке
    # Arrange
    llm = FakeLlmClient(
        card_texts_json(
            description_facts=[
                {
                    "name": "Степень защиты",
                    "value": "IP68",
                    "quote": "степень защиты IP68",
                },
                {
                    "name": "Предел",
                    "value": "2,5 МПа",
                    "quote": "неагрессивных к медным сплавам",
                },
                {
                    "name": "Материал",
                    "value": "нержавеющая сталь",
                    "quote": "неагрессивных к медным сплавам",
                },
                {
                    "name": "Измеряемая среда",
                    "value": "неагрессивные к медным сплавам жидкости и газы",
                    "quote": "неагрессивных к медным сплавам жидкостей и газов",
                },
            ]
        ),
        review_json(),
    )
    client = api_client_for(llm)

    # Act
    response = await client.post(CARDS_PATH, json=MANOMETER)

    # Assert
    body = response.json()
    names = [item["name"] for item in body["card"]["characteristics"]]
    assert names == [*MANOMETER["specs"], "Измеряемая среда"]
    assert body["card"]["characteristics"][-1]["value"] == (
        "неагрессивные к медным сплавам жидкости и газы"
    )
    assert body["warnings"] == [
        f"Характеристика «{name}» не добавлена: значение не подтверждено описанием прибора, проверьте вручную."
        for name in ("Степень защиты", "Предел", "Материал")
    ]
    assert len(llm.requests) == 2


async def test_case_8(api_client_for) -> None:
    # 8. Короткий текст: правки нет, warning есть
    # Arrange
    llm = FakeLlmClient(card_texts_json(seo_description="Манометр."), review_json())
    client = api_client_for(llm)

    # Act
    response = await client.post(CARDS_PATH, json=MANOMETER)

    # Assert
    assert response.json()["warnings"] == [
        "Описание короче 800 символов (9): данных о приборе мало, дополните их или допишите текст вручную."
    ]
    assert len(llm.requests) == 2


async def test_case_9(api_client_for) -> None:
    # 9. Правка сократила текст ниже 800: warning о длине есть, новой правки нет
    # Arrange
    llm = FakeLlmClient(
        card_texts_json(),
        review_json(filler_issue("Манометр показывает")),
        card_texts_json(seo_description="Манометр."),
        review_json(),
    )
    client = api_client_for(llm)

    # Act
    response = await client.post(CARDS_PATH, json=MANOMETER)

    # Assert
    body = response.json()
    assert body["card"]["seo_description"] == "Манометр."
    assert len(body["warnings"]) == 1
    assert body["warnings"][0].startswith("Описание короче 800 символов (9)")
    assert len(llm.requests) == 4


async def test_case_10(api_client_for) -> None:
    # 10. Число вне входа в заголовке и в запросе: правка, модель получила оба замечания
    # Arrange
    llm = FakeLlmClient(
        card_texts_json(
            seo_title="Манометр 2,5 МПа",
            search_queries=["манометр 16 мпа", "манометр купить", "манометр 1,6 мпа"],
        ),
        review_json(),
        card_texts_json(),
        review_json(),
    )
    client = api_client_for(llm)

    # Act
    response = await client.post(CARDS_PATH, json=MANOMETER)

    # Assert
    assert response.json()["warnings"] == []
    revision = llm.requests[2].user
    assert (
        "- Число 2,5 в поле seo_title не встречается в данных о приборе. Убери его."
        in revision
    )
    assert (
        "- Число 16 в поле search_queries не встречается в данных о приборе. Убери его."
        in revision
    )
    assert "1,6 в поле" not in revision


async def test_case_11(api_client_for) -> None:
    # 11. Число вне входа осталось после лимита: warning для человека
    # Arrange
    title = card_texts_json(seo_title="Манометр 2.5 МПа")
    llm = FakeLlmClient(
        title, review_json(), title, review_json(), title, review_json()
    )
    client = api_client_for(llm)

    # Act
    response = await client.post(CARDS_PATH, json=MANOMETER)

    # Assert
    assert response.json()["warnings"] == [
        "Число 2,5 в заголовке не встречается в данных о приборе: проверьте его."
    ]
    assert len(llm.requests) == 6


async def test_case_12(api_client_for) -> None:
    # 12. Сбой ревью: повторён только ревью, написание не повторено
    # Arrange
    llm = FakeLlmClient(
        card_texts_json(),
        LlmUnavailableError("OpenRouter ответил 429", retryable=True),
        review_json(),
    )
    client = api_client_for(llm)

    # Act
    response = await client.post(CARDS_PATH, json=MANOMETER)

    # Assert
    assert response.status_code == 200
    assert [request.schema_name for request in llm.requests] == [
        "card_texts",
        "card_review",
        "card_review",
    ]
    assert llm.requests[1] == llm.requests[2]


async def test_case_13(api_client_for) -> None:
    # 13. Сбой правки: повторён тот же запрос правки, счётчик правок не сбился
    # Arrange
    first = card_texts_json(seo_title=LONG_TITLE)
    llm = FakeLlmClient(
        first,
        review_json(),
        LlmFailedError(
            "Модель не закончила ответ: finish_reason=length", retryable=True
        ),
        first,
        review_json(),
        first,
        review_json(),
    )
    client = api_client_for(llm)

    # Act
    response = await client.post(CARDS_PATH, json=MANOMETER)

    # Assert
    assert response.status_code == 200
    assert llm.responses == []
    assert llm.requests[2] == llm.requests[3]
    assert len(llm.requests) == 7


@pytest.mark.parametrize(
    "responses",
    [
        (
            card_texts_json(),
            LlmUnavailableError("OpenRouter ответил 500", retryable=True),
            LlmUnavailableError("OpenRouter ответил 500", retryable=True),
        ),
        (
            card_texts_json(seo_title=LONG_TITLE),
            review_json(),
            LlmUnavailableError("OpenRouter ответил 500", retryable=True),
            LlmUnavailableError("OpenRouter ответил 500", retryable=True),
        ),
    ],
)
async def test_case_14(api_client_for, responses) -> None:
    # 14. Сбой ревью после повторов: 503, черновик не отдаётся
    # Arrange
    client = api_client_for(FakeLlmClient(*responses))

    # Act
    response = await client.post(CARDS_PATH, json=MANOMETER)

    # Assert
    assert response.status_code == 503
    assert "card" not in response.json()


async def test_case_15(api_client_for) -> None:
    # 15. Постоянный сбой правки: 502, черновик не отдаётся
    # Arrange
    llm = FakeLlmClient(
        card_texts_json(seo_title=LONG_TITLE),
        review_json(),
        LlmFailedError("OpenRouter ответил 402", retryable=False),
    )
    client = api_client_for(llm)

    # Act
    response = await client.post(CARDS_PATH, json=MANOMETER)

    # Assert
    assert response.status_code == 502
    assert len(llm.requests) == 3


async def test_case_16(api_client_for) -> None:
    # 16. Факты, отсутствующие названия и уточнения берутся с первого написания, тексты с последнего
    # Arrange
    llm = FakeLlmClient(
        card_texts_json(
            seo_title=LONG_TITLE,
            description_facts=[
                {
                    "name": "Измеряемая среда",
                    "value": "жидкости и газы",
                    "quote": "жидкостей и газов",
                }
            ],
            missing_characteristics=["Степень защиты корпуса"],
            needs_clarification=[{"field": "Класс точности", "reason": "первое"}],
        ),
        review_json(),
        card_texts_json(
            seo_title="Манометр показывающий",
            description_facts=[
                {"name": "Другое", "value": "жидкости", "quote": "жидкостей"},
            ],
            missing_characteristics=["Выдумка второго написания"],
            needs_clarification=[{"field": "Другое", "reason": "второе"}],
        ),
        review_json(),
    )
    client = api_client_for(llm)

    # Act
    response = await client.post(CARDS_PATH, json=MANOMETER)

    # Assert
    body = response.json()
    assert body["card"]["seo_title"] == "Манометр показывающий"
    assert body["card"]["characteristics"][4:] == [
        {"name": "Измеряемая среда", "value": "жидкости и газы"},
        {"name": "Степень защиты корпуса", "value": "данных нет"},
    ]
    assert body["missing_fields"] == ["Степень защиты корпуса"]
    assert body["needs_clarification"] == [
        {"field": "Класс точности", "reason": "первое"}
    ]


async def test_case_17(api_client_for) -> None:
    # 17. Вторая правка получает замечания только к последнему тексту
    # Arrange
    llm = FakeLlmClient(
        card_texts_json(seo_title=LONG_TITLE),
        review_json(),
        card_texts_json(seo_title="Манометр 2,5"),
        review_json(),
        card_texts_json(),
        review_json(),
    )
    client = api_client_for(llm)

    # Act
    response = await client.post(CARDS_PATH, json=MANOMETER)

    # Assert
    assert response.json()["warnings"] == []
    second_revision = llm.requests[4].user
    assert "Число 2,5 в поле seo_title" in second_revision
    assert "Заголовок 71 символов" not in second_revision


async def test_case_18(api_client_for) -> None:
    # 18. Правка видит в прошлом ответе списки первого написания
    # Arrange
    llm = FakeLlmClient(
        card_texts_json(
            seo_title=LONG_TITLE,
            missing_characteristics=["Степень защиты корпуса"],
        ),
        review_json(),
        card_texts_json(seo_title=LONG_TITLE, missing_characteristics=["Выдумка"]),
        review_json(),
        card_texts_json(),
        review_json(),
    )
    client = api_client_for(llm)

    # Act
    await client.post(CARDS_PATH, json=MANOMETER)

    # Assert
    assert "Степень защиты корпуса" in llm.requests[4].user
    assert "Выдумка" not in llm.requests[4].user


async def test_case_19(api_client_for) -> None:
    # 19. missing_fields: сначала пустые поля входа, затем названия от модели, дублей нет
    # Arrange
    llm = FakeLlmClient(
        card_texts_json(
            missing_characteristics=["Класс точности", "Защита", "Измеряемая среда"]
        ),
        review_json(),
    )
    client = api_client_for(llm)
    payload = {
        "name": "Манометр",
        "specs": {"Диапазон": "0–1,6 МПа", "Защита": None},
        "description": "   ",
    }

    # Act
    response = await client.post(CARDS_PATH, json=payload)

    # Assert
    body = response.json()
    assert body["missing_fields"] == [
        "Производитель",
        "Защита",
        "Описание",
        "Класс точности",
        "Измеряемая среда",
    ]
    assert body["card"]["characteristics"] == [
        {"name": "Диапазон", "value": "0–1,6 МПа"},
        {"name": "Защита", "value": "данных нет"},
        {"name": "Класс точности", "value": "данных нет"},
        {"name": "Измеряемая среда", "value": "данных нет"},
    ]


async def test_case_20(api_client_for) -> None:
    # 20. Значение из description попадает в список, а specs главнее
    # Arrange
    llm = FakeLlmClient(
        card_texts_json(
            description_facts=[
                {
                    "name": "класс  ТОЧНОСТИ",
                    "value": "неагрессивные",
                    "quote": "неагрессивных",
                }
            ],
            needs_clarification=[
                {
                    "field": "Класс точности",
                    "reason": "в характеристиках 1,5, в описании 1,0",
                }
            ],
        ),
        review_json(),
    )
    client = api_client_for(llm)

    # Act
    response = await client.post(CARDS_PATH, json=MANOMETER)

    # Assert
    body = response.json()
    assert body["card"]["characteristics"] == [
        {"name": name, "value": value} for name, value in MANOMETER["specs"].items()
    ]
    assert body["needs_clarification"] == [
        {"field": "Класс точности", "reason": "в характеристиках 1,5, в описании 1,0"}
    ]
    assert body["warnings"] == []


async def test_case_21(api_client_for) -> None:
    # 21. Пустые specs и manufacturer не доходят до модели ни в написании, ни в ревью, ни в правке
    # Arrange
    llm = FakeLlmClient(
        card_texts_json(seo_title=LONG_TITLE),
        review_json(),
        card_texts_json(),
        review_json(),
    )
    client = api_client_for(llm)
    payload = {
        "name": "Манометр",
        "manufacturer": "  ",
        "specs": {"Диапазон": "0–1,6 МПа", "Пустая": None, "Другая": ""},
        "description": "Для жидкостей.",
    }

    # Act
    response = await client.post(CARDS_PATH, json=payload)

    # Assert
    assert response.status_code == 200
    assert len(llm.requests) == 4
    for request in llm.requests:
        assert "<manufacturer>" not in request.user
        assert "Пустая" not in request.user
        assert "Другая" not in request.user
    assert "Пустая" in response.json()["missing_fields"]
    assert CLEAN_DESCRIPTION == response.json()["card"]["seo_description"]


async def test_case_22(api_client_for) -> None:
    # 22. Подтверждённый факт заполняет пустую строку specs и убирает имя из missing_fields
    # Arrange
    llm = FakeLlmClient(
        card_texts_json(
            description_facts=[
                {
                    "name": "Класс точности",
                    "value": "1,5",
                    "quote": "Класс точности 1,5",
                }
            ],
            missing_characteristics=["Класс точности"],
        ),
        review_json(),
    )
    client = api_client_for(llm)
    payload = {
        "name": "Манометр",
        "manufacturer": "Манотомь",
        "specs": {"Класс точности": None, "Диаметр": "100 мм", "Защита": None},
        "description": "Класс точности 1,5",
    }

    # Act
    response = await client.post(CARDS_PATH, json=payload)

    # Assert
    body = response.json()
    assert body["card"]["characteristics"] == [
        {"name": "Класс точности", "value": "1,5"},
        {"name": "Диаметр", "value": "100 мм"},
        {"name": "Защита", "value": "данных нет"},
    ]
    assert body["missing_fields"] == ["Защита"]
    assert body["warnings"] == []

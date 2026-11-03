from __future__ import annotations

import pytest

from application.services.card_generation.llm_schemas import WriteCardOutput
from application.services.card_generation.prompts import review_card, write_card
from application.services.card_generation.prompts.rules import render_device
from domain.entities.product import Product
from tests.fakes import card_texts_json

# Test cases:
# 1. Пустые значения specs, пустой manufacturer и пустое описание не попадают в сведения о приборе
# 2. Заполненный прибор: порядок тегов и значения как во входе
# 3. Первое написание: сведения о приборе без прошлого ответа
# 4. Правка: сведения о приборе, прошлый ответ целиком и все замечания
# 5. Ревьюер получает только тексты, без списков фактов
# 6. В system написания описаны поля name, value и quote


FULL_PRODUCT = Product(
    name="Манометр DM 02",
    manufacturer="Манотомь",
    specs={"Диапазон": "0–1,6 МПа", "Диаметр": 100, "Точность": 1.5},
    description="Для жидкостей и газов.",
)


@pytest.mark.parametrize(
    ("manufacturer", "description"),
    [(None, None), ("", ""), ("   ", "  \n "), ("—", "-")],
)
def test_case_1(manufacturer, description) -> None:
    # 1. Пустые значения specs, пустой manufacturer и пустое описание не попадают в сведения о приборе
    # Arrange
    product = Product(
        name="Термометр ТБ-63",
        manufacturer=manufacturer,
        specs={
            "Диапазон": "0–120 °С",
            "Защита": None,
            "Класс": "",
            "Вес": "  ",
            "Материал": "—",
        },
        description=description,
    )

    # Act
    device = render_device(product)

    # Assert
    assert device == (
        "<device>\n"
        "<name>Термометр ТБ-63</name>\n"
        "<specs>\n"
        "- Диапазон: 0–120 °С\n"
        "</specs>\n"
        "</device>"
    )


def test_case_2() -> None:
    # 2. Заполненный прибор: порядок тегов и значения как во входе
    # Act
    device = render_device(FULL_PRODUCT)

    # Assert
    assert device == (
        "<device>\n"
        "<name>Манометр DM 02</name>\n"
        "<manufacturer>Манотомь</manufacturer>\n"
        "<specs>\n"
        "- Диапазон: 0–1,6 МПа\n"
        "- Диаметр: 100\n"
        "- Точность: 1.5\n"
        "</specs>\n"
        "<description>\n"
        "Для жидкостей и газов.\n"
        "</description>\n"
        "</device>"
    )


def test_case_3() -> None:
    # 3. Первое написание: сведения о приборе без прошлого ответа
    # Act
    message = write_card.build_first_message(FULL_PRODUCT)

    # Assert
    assert message.startswith(render_device(FULL_PRODUCT))
    assert message.endswith("Заполни все поля ответа.")
    assert "<previous_answer>" not in message


def test_case_4() -> None:
    # 4. Правка: сведения о приборе, прошлый ответ целиком и все замечания
    # Arrange
    previous = WriteCardOutput.model_validate_json(
        card_texts_json(seo_title="Прошлый заголовок")
    )

    # Act
    message = write_card.build_revision_message(
        FULL_PRODUCT,
        previous,
        ["Первое замечание", "«цитата»: причина"],
    )

    # Assert
    assert message.startswith(render_device(FULL_PRODUCT))
    assert '"seo_title": "Прошлый заголовок"' in message
    assert '"description_facts": []' in message
    assert "<remarks>\n- Первое замечание\n- «цитата»: причина\n</remarks>" in message


def test_case_5() -> None:
    # 5. Ревьюер получает только тексты, без списков фактов
    # Arrange
    draft = WriteCardOutput.model_validate_json(card_texts_json())

    # Act
    message = review_card.build_message(FULL_PRODUCT, draft)

    # Assert
    assert message.startswith(render_device(FULL_PRODUCT))
    assert '"seo_title"' in message
    assert '"search_queries"' in message
    assert '"commercial"' in message
    assert "description_facts" not in message
    assert "missing_characteristics" not in message


def test_case_6() -> None:
    # 6. В system написания описаны поля name, value и quote
    # Act
    system = write_card.SYSTEM

    # Assert
    assert "description_facts" in system
    for field in ("- name:", "- value:", "- quote:"):
        assert field in system

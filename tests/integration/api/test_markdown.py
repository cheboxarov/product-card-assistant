from __future__ import annotations

from domain.entities.card import (
    CardDraft,
    CardTexts,
    Characteristic,
    Clarification,
    Commercial,
)
from presentation.api.markdown import render_markdown
from tests.fakes import FakeLlmClient, card_texts_json, review_json
from tests.integration.api.conftest import CARDS_PATH, MANOMETER

# Test cases:
# 1. Полный черновик: все секции по порядку, текст точный
# 2. Нечего уточнять и нет предупреждений: этих секций нет
# 3. Ответ API содержит markdown с данными этого черновика


TEXTS = CardTexts(
    seo_title="Манометр DM 02",
    seo_description="Текст описания.",
    search_queries=("манометр", "манометр купить", "манометр dm 02"),
    commercial=Commercial(audience="Служба КИПиА.", tasks="Контроль давления."),
)
CHARACTERISTICS = (
    Characteristic(name="Диапазон", value="0–1,6 МПа"),
    Characteristic(name="Защита", value="данных нет"),
)


def test_case_1() -> None:
    # 1. Полный черновик: все секции по порядку, текст точный
    # Arrange
    draft = CardDraft(
        texts=TEXTS,
        characteristics=CHARACTERISTICS,
        missing_fields=("Производитель", "Защита"),
        needs_clarification=(
            Clarification(
                field="Класс точности", reason="в характеристиках 1,5, в описании 1,0"
            ),
        ),
        warnings=("Описание короче 800 символов (15).",),
    )

    # Act
    result = render_markdown(draft)

    # Assert
    assert result == (
        "# Манометр DM 02\n"
        "\n"
        "Текст описания.\n"
        "\n"
        "## Характеристики\n"
        "\n"
        "- Диапазон: 0–1,6 МПа\n"
        "- Защита: данных нет\n"
        "\n"
        "## Поисковые запросы\n"
        "\n"
        "- манометр\n"
        "- манометр купить\n"
        "- манометр dm 02\n"
        "\n"
        "## Кому подходит\n"
        "\n"
        "Служба КИПиА.\n"
        "\n"
        "## Какие задачи решает\n"
        "\n"
        "Контроль давления.\n"
        "\n"
        "## Что уточнить\n"
        "\n"
        "- Производитель: данных нет\n"
        "- Защита: данных нет\n"
        "- Класс точности: в характеристиках 1,5, в описании 1,0\n"
        "\n"
        "## Предупреждения\n"
        "\n"
        "- Описание короче 800 символов (15).\n"
    )


def test_case_2() -> None:
    # 2. Нечего уточнять и нет предупреждений: этих секций нет
    # Arrange
    draft = CardDraft(
        texts=TEXTS,
        characteristics=CHARACTERISTICS,
        missing_fields=(),
        needs_clarification=(),
        warnings=(),
    )

    # Act
    result = render_markdown(draft)

    # Assert
    assert "## Что уточнить" not in result
    assert "## Предупреждения" not in result
    assert result.endswith("Контроль давления.\n")


async def test_case_3(api_client_for) -> None:
    # 3. Ответ API содержит markdown с данными этого черновика
    # Arrange
    client = api_client_for(
        FakeLlmClient(
            card_texts_json(missing_characteristics=["Степень защиты корпуса"]),
            review_json(),
        )
    )

    # Act
    response = await client.post(CARDS_PATH, json=MANOMETER)

    # Assert
    body = response.json()
    assert body["markdown"].startswith(f"# {body['card']['seo_title']}\n")
    assert "- Диапазон измерений: 0–1,6 МПа\n" in body["markdown"]
    assert "- Степень защиты корпуса: данных нет\n" in body["markdown"]
    assert body["card"]["seo_description"] in body["markdown"]

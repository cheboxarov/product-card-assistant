from __future__ import annotations

import re

import pytest

from domain.entities.card import CardDraft
from tests.llm.conftest import CASES, CaseRun

# Test cases:
# 1. Карточка получена, сбоя нет
# 2. В текстах нет слов и значений, запрещённых для этого случая
# 3. В характеристиках нет значений, запрещённых для этого случая
# 4. Расхождение и неясное значение попали в уточнения
# 5. На входе без расхождений уточнений нет
# 6. В текстах нет запрещённых слов, которых нет во входе
# 7. Длинный паспорт: все обязательные факты в списке характеристик
# 8. Заголовок до 70 символов, описание до 1200
# 9. Там, где данных хватает, описание от 800 символов


CASE_IDS = list(CASES)
GOLDEN_CASE_IDS = [
    case_id for case_id, case in CASES.items() if case["expect"].get("golden_facts")
]
ENOUGH_DATA_CASE_IDS = ["C1", "C2", "C3", "C5", "C7", "C9"]
TITLE_MAX = 70
DESCRIPTION_MIN = 800
DESCRIPTION_MAX = 1200
GLOBAL_FORBIDDEN = (
    *r"отоплен водоснабж \bжкх\b нефт химическ пищев энергетик котельн".split(),
    *r"металлург фармацевт гост сертифик декларац поверк госреестр".split(),
    *r"надёжн надежн долговеч прочн износ вибро влаго пылезащ взрыв".split(),
    *r"нержаве латун бронз \bстал[ьи]\b алюмин пластик полимер".split(),
    *r"удобн качествен оптимальн эффективн лучш демпфер глицерин".split(),
    *r"гарант трубопровод компресс насос".split(),
    r"\bip\s?\d",
    r"высок\w+ точн",
    r"прост\w+ монтаж",
)


def draft_of(live_runs: dict[str, CaseRun], case_id: str) -> CardDraft:
    run = live_runs[case_id]
    assert run.draft is not None, f"сбой: {run.error}"
    return run.draft


def texts_blob(draft: CardDraft) -> str:
    texts = draft.texts
    return "\n".join(
        (
            texts.seo_title,
            texts.seo_description,
            *texts.search_queries,
            texts.commercial.audience,
            texts.commercial.tasks,
        )
    )


def characteristics_lines(draft: CardDraft) -> list[str]:
    return [f"{item.name} :: {item.value}" for item in draft.characteristics]


def source_blob(case_id: str) -> str:
    device = CASES[case_id]["device"]
    specs = [f"{name} {value}" for name, value in device["specs"].items()]
    return "\n".join(
        (device["name"], device["manufacturer"], device["description"], *specs)
    )


def found_patterns(patterns: list[str] | tuple[str, ...], text: str) -> list[str]:
    return [pattern for pattern in patterns if re.search(pattern, text, re.I)]


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_case_1(live_runs, case_id) -> None:
    # 1. Карточка получена, сбоя нет
    # Act
    run = live_runs[case_id]

    # Assert
    assert run.error is None
    assert run.draft is not None


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_case_2(live_runs, case_id) -> None:
    # 2. В текстах нет слов и значений, запрещённых для этого случая
    # Arrange
    forbidden = CASES[case_id]["expect"].get("forbidden_in_text", [])

    # Act
    found = found_patterns(forbidden, texts_blob(draft_of(live_runs, case_id)))

    # Assert
    assert found == []


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_case_3(live_runs, case_id) -> None:
    # 3. В характеристиках нет значений, запрещённых для этого случая
    # Arrange
    forbidden = CASES[case_id]["expect"].get("forbidden_in_facts", [])
    lines = "\n".join(characteristics_lines(draft_of(live_runs, case_id)))

    # Act
    found = found_patterns(forbidden, lines)

    # Assert
    assert found == []


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_case_4(live_runs, case_id) -> None:
    # 4. Расхождение и неясное значение попали в уточнения
    # Arrange
    expected = CASES[case_id]["expect"].get("must_clarify", [])
    clarifications = draft_of(live_runs, case_id).needs_clarification
    blob = "\n".join(f"{item.field} {item.reason}" for item in clarifications)

    # Act
    found = found_patterns(expected, blob)

    # Assert
    assert found == expected


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_case_5(live_runs, case_id) -> None:
    # 5. На входе без расхождений уточнений нет
    # Arrange
    should_be_empty = CASES[case_id]["expect"].get("clar_should_be_empty", False)

    # Act
    clarifications = draft_of(live_runs, case_id).needs_clarification

    # Assert
    if should_be_empty:
        assert clarifications == ()


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_case_6(live_runs, case_id) -> None:
    # 6. В текстах нет запрещённых слов, которых нет во входе
    # Arrange
    source = source_blob(case_id)

    # Act
    found = found_patterns(GLOBAL_FORBIDDEN, texts_blob(draft_of(live_runs, case_id)))

    # Assert
    invented = [pattern for pattern in found if not re.search(pattern, source, re.I)]
    assert invented == []


@pytest.mark.parametrize("case_id", GOLDEN_CASE_IDS)
def test_case_7(live_runs, case_id) -> None:
    # 7. Длинный паспорт: все обязательные факты в списке характеристик
    # Arrange
    golden = CASES[case_id]["expect"]["golden_facts"]
    must = [fact for fact in golden if fact["tier"] == "must"]
    lines = characteristics_lines(draft_of(live_runs, case_id))

    # Act
    missed = [
        fact["id"]
        for fact in must
        if not any(re.search(fact["pattern"], line, re.I) for line in lines)
    ]

    # Assert
    assert missed == []


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_case_8(live_runs, case_id) -> None:
    # 8. Заголовок до 70 символов, описание до 1200
    # Act
    texts = draft_of(live_runs, case_id).texts

    # Assert
    assert len(texts.seo_title) <= TITLE_MAX
    assert len(texts.seo_description) <= DESCRIPTION_MAX


@pytest.mark.parametrize("case_id", ENOUGH_DATA_CASE_IDS)
def test_case_9(live_runs, case_id) -> None:
    # 9. Там, где данных хватает, описание от 800 символов
    # Act
    texts = draft_of(live_runs, case_id).texts

    # Assert
    assert len(texts.seo_description) >= DESCRIPTION_MIN

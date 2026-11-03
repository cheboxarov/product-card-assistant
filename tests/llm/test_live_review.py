from __future__ import annotations

import asyncio
import json
import pathlib
from dataclasses import dataclass

import pytest

from application.services.card_generation.llm_schemas import (
    ReviewCardOutput,
    WriteCardOutput,
)
from application.services.card_generation.prompts import review_card
from application.services.card_generation.service import (
    CARD_REVIEW_SCHEMA_NAME,
    REVIEW_REASONING_EFFORT,
)
from bootstrap.settings import Settings
from domain.card_rules import review_issue
from domain.entities.card import CardTexts, Commercial
from domain.interfaces.infrastructure.llm_client import LlmRequest
from infrastructure.openrouter.client import OpenRouterClient
from presentation.api.schemas.cards import CardRequest
from tests.llm.conftest import CASES, MAX_CARDS_AT_ONCE, CaseRun, build_counted_client

# Test cases:
# 1. Подмешанные выдумки и вода найдены все
# 2. На чистых текстах на весь набор не больше одного ложного замечания
# 3. Цитата каждого замечания есть в текстах


REVIEW_CASES = {
    path.stem: json.loads(path.read_text(encoding="utf-8"))
    for path in sorted((pathlib.Path(__file__).parent / "review_cases").glob("*.json"))
}
PLANTED_CASE_IDS = [
    case_id for case_id, case in REVIEW_CASES.items() if case["planted"]
]
CLEAN_CASE_IDS = [
    case_id for case_id, case in REVIEW_CASES.items() if not case["planted"]
]
FALSE_REMARKS_LIMIT = 1


@dataclass
class ReviewRun:
    case_id: str
    issues: list[dict[str, str]]


@pytest.fixture(scope="module")
def live_reviews(live_settings: Settings) -> dict[str, ReviewRun]:
    return asyncio.run(run_all_reviews(live_settings))


async def run_all_reviews(settings: Settings) -> dict[str, ReviewRun]:
    total = CaseRun("итого")
    client = build_counted_client(settings, total)
    llm = OpenRouterClient(client=client, model=settings.openrouter_model)
    semaphore = asyncio.Semaphore(MAX_CARDS_AT_ONCE)
    runs = await asyncio.gather(
        *(run_review(case_id, llm, semaphore) for case_id in REVIEW_CASES)
    )
    await client.close()
    print(f"\nИтого: вызовов {total.calls}, ${total.cost:.4f}")
    return {run.case_id: run for run in runs}


async def run_review(
    case_id: str,
    llm: OpenRouterClient,
    semaphore: asyncio.Semaphore,
) -> ReviewRun:
    case = REVIEW_CASES[case_id]
    device = CASES[case["device_case"]]["device"]
    product = CardRequest.model_validate(device).to_product()
    async with semaphore:
        raw = await llm.complete_json(
            LlmRequest(
                system=review_card.SYSTEM,
                user=review_card.build_message(product, draft_of(case)),
                schema_name=CARD_REVIEW_SCHEMA_NAME,
                json_schema=ReviewCardOutput.model_json_schema(),
                reasoning_effort=REVIEW_REASONING_EFFORT,
            )
        )
    issues = ReviewCardOutput.model_validate_json(raw).model_dump()["issues"]
    print(f"\n=== {case_id}: замечаний {len(issues)}")
    for issue in issues:
        print(f"{issue['kind']} | {issue['quote']} | {issue['reason']}")
    return ReviewRun(case_id, issues)


def draft_of(case: dict) -> WriteCardOutput:
    card = case["card"]
    return WriteCardOutput.model_construct(
        seo_title=card["seo_title"],
        seo_description=card["seo_description"],
        search_queries=card["search_queries"],
        commercial=Commercial(**card["commercial"]),
    )


def texts_of(case: dict) -> CardTexts:
    card = case["card"]
    return CardTexts(
        seo_title=card["seo_title"],
        seo_description=card["seo_description"],
        search_queries=tuple(card["search_queries"]),
        commercial=Commercial(**card["commercial"]),
    )


def normalized(text: str) -> str:
    return " ".join(text.lower().split()).strip(" .,;:!?")


def planted_found(planted: dict[str, str], issue: dict[str, str]) -> bool:
    quote = normalized(issue["quote"])
    return (
        normalized(planted["anchor"]) in quote
        or quote in normalized(planted["span"])
        or normalized(planted["span"]) in quote
    )


@pytest.mark.parametrize("case_id", PLANTED_CASE_IDS)
def test_case_1(live_reviews, case_id) -> None:
    # 1. Подмешанные выдумки и вода найдены все
    # Arrange
    issues = live_reviews[case_id].issues

    # Act
    missed = [
        planted["id"]
        for planted in REVIEW_CASES[case_id]["planted"]
        if not any(planted_found(planted, issue) for issue in issues)
    ]

    # Assert
    assert missed == []


def test_case_2(live_reviews) -> None:
    # 2. На чистых текстах на весь набор не больше одного ложного замечания
    # Act
    false_remarks = [
        (case_id, issue["quote"])
        for case_id in CLEAN_CASE_IDS
        for issue in live_reviews[case_id].issues
    ]

    # Assert
    assert len(false_remarks) <= FALSE_REMARKS_LIMIT, false_remarks


@pytest.mark.parametrize("case_id", list(REVIEW_CASES))
def test_case_3(live_reviews, case_id) -> None:
    # 3. Цитата каждого замечания есть в текстах
    # Arrange
    texts = texts_of(REVIEW_CASES[case_id])

    # Act
    not_found = [
        issue["quote"]
        for issue in live_reviews[case_id].issues
        if review_issue(texts, **issue) is None
    ]

    # Assert
    assert not_found == []

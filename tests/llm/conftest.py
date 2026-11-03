from __future__ import annotations

import asyncio
import json
import pathlib
import time
from dataclasses import dataclass

import pytest
from openai import AsyncOpenAI
from pydantic import ValidationError

from application.services.card_generation.service import CardGenerationService
from bootstrap.settings import Settings
from domain.entities.card import CardDraft
from domain.exceptions import LlmError
from domain.use_cases.generate_card import GenerateCard
from infrastructure.openrouter.client import OpenRouterClient
from presentation.api.markdown import render_markdown
from presentation.api.schemas.cards import CardRequest

CASES = {
    path.stem: json.loads(path.read_text(encoding="utf-8"))
    for path in sorted((pathlib.Path(__file__).parent / "cases").glob("*.json"))
}
MAX_CARDS_AT_ONCE = 4


@dataclass
class CaseRun:
    case_id: str
    draft: CardDraft | None = None
    error: LlmError | None = None
    seconds: float = 0
    calls: int = 0
    cost: float = 0


@pytest.fixture(scope="module")
def live_settings() -> Settings:
    try:
        return Settings()
    except ValidationError:
        pytest.skip("нет ключа PRODUCT_CARD_OPENROUTER_API_KEY")


@pytest.fixture(scope="module")
def live_runs(live_settings: Settings) -> dict[str, CaseRun]:
    return asyncio.run(run_all_cases(live_settings))


def build_openai_client(settings: Settings, run: CaseRun) -> AsyncOpenAI:
    client = AsyncOpenAI(
        api_key=settings.openrouter_api_key.get_secret_value(),
        base_url=settings.openrouter_base_url,
        max_retries=0,
    )
    completions = client.chat.completions
    create = completions.create

    async def counted_create(*args, **kwargs):
        response = await create(*args, **kwargs)
        run.calls += 1
        run.cost += getattr(getattr(response, "usage", None), "cost", 0) or 0
        return response

    completions.create = counted_create
    return client


async def run_all_cases(settings: Settings) -> dict[str, CaseRun]:
    semaphore = asyncio.Semaphore(MAX_CARDS_AT_ONCE)
    runs = await asyncio.gather(
        *(run_case(case_id, settings, semaphore) for case_id in CASES)
    )
    print(
        f"\nИтого: вызовов {sum(run.calls for run in runs)}, "
        f"${sum(run.cost for run in runs):.4f}"
    )
    return {run.case_id: run for run in runs}


async def run_case(
    case_id: str,
    settings: Settings,
    semaphore: asyncio.Semaphore,
) -> CaseRun:
    run = CaseRun(case_id)
    product = CardRequest.model_validate(CASES[case_id]["device"]).to_product()
    async with semaphore:
        client = build_openai_client(settings, run)
        generate_card = GenerateCard(
            card_generator=CardGenerationService(
                llm_client=OpenRouterClient(
                    client=client, model=settings.openrouter_model
                ),
            )
        )
        started = time.monotonic()
        try:
            run.draft = await generate_card.execute(product)
        except LlmError as exc:
            run.error = exc
        run.seconds = time.monotonic() - started
        await client.close()
    print_run(run)
    return run


def print_run(run: CaseRun) -> None:
    head = (
        f"\n=== {run.case_id}: {run.seconds:.0f} с, "
        f"вызовов {run.calls}, ${run.cost:.4f}"
    )
    if run.draft is None:
        print(f"{head}, сбой: {run.error}")
        return
    texts = run.draft.card.texts
    print(
        f"{head}, заголовок {len(texts.seo_title)}, описание {len(texts.seo_description)}"
    )
    print(render_markdown(run.draft))

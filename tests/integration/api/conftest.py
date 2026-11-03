from __future__ import annotations

from collections.abc import AsyncIterator, Callable

import httpx2
import pytest
from fastapi import FastAPI

from application.services.card_generation.service import CardGenerationService
from domain.use_cases.generate_card import GenerateCard
from presentation.api.routes.cards import build_cards_router
from tests.fakes import FakeLlmClient

CARDS_PATH = "/api/v1/cards"
MANOMETER = {
    "name": "Манометр DM 02",
    "manufacturer": "Манотомь",
    "specs": {
        "Диапазон измерений": "0–1,6 МПа",
        "Класс точности": "1,5",
        "Присоединение": "G1/2",
        "Диаметр корпуса": "100 мм",
    },
    "description": "Прибор предназначен для измерения избыточного давления неагрессивных к медным сплавам жидкостей и газов.",
}


def build_test_app(llm: FakeLlmClient) -> FastAPI:
    app = FastAPI()
    app.include_router(
        build_cards_router(
            generate_card=GenerateCard(
                card_generator=CardGenerationService(llm_client=llm),
            )
        )
    )
    return app


@pytest.fixture
async def api_client_for() -> AsyncIterator[
    Callable[[FakeLlmClient], httpx2.AsyncClient]
]:
    clients: list[httpx2.AsyncClient] = []

    def build(llm: FakeLlmClient) -> httpx2.AsyncClient:
        client = httpx2.AsyncClient(
            transport=httpx2.ASGITransport(app=build_test_app(llm)),
            base_url="http://cards.test",
        )
        clients.append(client)
        return client

    yield build
    for client in clients:
        await client.aclose()

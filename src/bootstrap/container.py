from __future__ import annotations

from dataclasses import dataclass

from fastapi import APIRouter
from openai import AsyncOpenAI

from application.services.card_generation.service import CardGenerationService
from bootstrap.settings import Settings
from domain.use_cases.generate_card import GenerateCard
from infrastructure.openrouter.client import OpenRouterClient
from presentation.api.routes.cards import build_cards_router


@dataclass(slots=True)
class ApplicationContainer:
    cards_router: APIRouter
    openai_client: AsyncOpenAI

    async def close(self) -> None:
        await self.openai_client.close()


def build_openai_client(settings: Settings) -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=settings.openrouter_api_key.get_secret_value(),
        base_url=settings.openrouter_base_url,
        max_retries=0,
    )


def build_generate_card(*, openai_client: AsyncOpenAI, model: str) -> GenerateCard:
    return GenerateCard(
        card_generator=CardGenerationService(
            llm_client=OpenRouterClient(client=openai_client, model=model),
        ),
    )


def build_api_container(settings: Settings) -> ApplicationContainer:
    openai_client = build_openai_client(settings)
    return ApplicationContainer(
        cards_router=build_cards_router(
            generate_card=build_generate_card(
                openai_client=openai_client,
                model=settings.openrouter_model,
            ),
        ),
        openai_client=openai_client,
    )

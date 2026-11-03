from __future__ import annotations

from fastapi import APIRouter

from domain.use_cases.generate_card import GenerateCard
from presentation.api.schemas.cards import CardRequest, CardResponse


def build_cards_router(*, generate_card: GenerateCard) -> APIRouter:
    router = APIRouter(prefix="/api/v1/cards", tags=["cards"])

    @router.post("", response_model=CardResponse)
    async def create_card(payload: CardRequest) -> CardResponse:
        draft = await generate_card.execute(payload.to_product())
        return CardResponse.from_draft(draft)

    return router

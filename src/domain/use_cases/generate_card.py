from __future__ import annotations

from domain.entities.card import CardDraft
from domain.entities.product import Product
from domain.interfaces.application.card_generator import CardGenerator


class GenerateCard:
    def __init__(self, *, card_generator: CardGenerator) -> None:
        self._card_generator = card_generator

    async def execute(self, product: Product) -> CardDraft:
        return await self._card_generator.generate(product)

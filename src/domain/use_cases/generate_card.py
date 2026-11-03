from __future__ import annotations

from dataclasses import replace

from domain.card_rules import (
    find_missing_input,
    has_too_little_data,
    missing_after_assembly,
)
from domain.entities.card import CardDraft
from domain.entities.product import Product
from domain.exceptions import NotEnoughDataError
from domain.interfaces.application.card_generator import CardGenerator


class GenerateCard:
    def __init__(self, *, card_generator: CardGenerator) -> None:
        self._card_generator = card_generator

    async def execute(self, product: Product) -> CardDraft:
        missing = find_missing_input(product)
        if has_too_little_data(product):
            raise NotEnoughDataError(missing)
        draft = await self._card_generator.generate(product)
        known = missing_after_assembly(missing, draft.characteristics)
        return replace(draft, missing_fields=(*known, *draft.missing_fields))

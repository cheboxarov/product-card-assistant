from __future__ import annotations

from typing import Protocol

from domain.entities.card import CardDraft
from domain.entities.product import Product


class CardGenerator(Protocol):
    async def generate(self, product: Product) -> CardDraft: ...

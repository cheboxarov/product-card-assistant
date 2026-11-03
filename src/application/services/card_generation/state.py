from __future__ import annotations

from typing import TypedDict

from application.services.card_generation.llm_schemas import CardTextsOutput
from domain.entities.product import Product


class CardState(TypedDict, total=False):
    product: Product
    texts: CardTextsOutput

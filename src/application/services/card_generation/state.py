from __future__ import annotations

from typing import TypedDict

from application.services.card_generation.llm_schemas import WriteCardOutput
from domain.entities.card import CardIssue
from domain.entities.product import Product


class CardState(TypedDict, total=False):
    product: Product
    draft: WriteCardOutput
    issues: tuple[CardIssue, ...]
    revisions: int

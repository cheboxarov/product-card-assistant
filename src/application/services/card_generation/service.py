from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from application.services.card_generation.llm_schemas import CardTextsOutput
from application.services.card_generation.prompts.write_card import (
    SYSTEM,
    build_user_message,
)
from application.services.card_generation.state import CardState
from domain.card_rules import characteristics_from_specs
from domain.entities.card import Card, CardDraft, Commercial
from domain.entities.product import Product
from domain.interfaces.application.card_generator import CardGenerator
from domain.interfaces.infrastructure.llm_client import LlmClient, LlmRequest

CARD_TEXTS_SCHEMA_NAME = "card_texts"


class CardGenerationService(CardGenerator):
    def __init__(self, *, llm_client: LlmClient) -> None:
        self._llm_client = llm_client
        builder = StateGraph(CardState)
        builder.add_node("write_card", self._write_card)
        builder.add_edge(START, "write_card")
        builder.add_edge("write_card", END)
        self._graph = builder.compile()

    async def generate(self, product: Product) -> CardDraft:
        state = await self._graph.ainvoke({"product": product})
        return CardDraft(card=_build_card(product, state["texts"]))

    async def _write_card(self, state: CardState) -> dict[str, CardTextsOutput]:
        raw = await self._llm_client.complete_json(
            LlmRequest(
                system=SYSTEM,
                user=build_user_message(state["product"]),
                schema_name=CARD_TEXTS_SCHEMA_NAME,
                json_schema=CardTextsOutput.model_json_schema(),
            )
        )
        return {"texts": CardTextsOutput.model_validate_json(raw)}


def _build_card(product: Product, texts: CardTextsOutput) -> Card:
    return Card(
        seo_title=texts.seo_title,
        seo_description=texts.seo_description,
        characteristics=characteristics_from_specs(product.specs),
        search_queries=tuple(texts.search_queries),
        commercial=Commercial(
            audience=texts.commercial.audience,
            tasks=texts.commercial.tasks,
        ),
    )

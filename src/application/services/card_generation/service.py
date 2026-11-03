from __future__ import annotations

import asyncio

from langgraph.graph import END, START, StateGraph
from langgraph.types import RetryPolicy
from pydantic import BaseModel, ValidationError

from application.services.card_generation.llm_schemas import (
    ReviewCardOutput,
    WriteCardOutput,
)
from application.services.card_generation.prompts import review_card, write_card
from application.services.card_generation.state import CardState
from domain.card_rules import (
    assemble_characteristics,
    clarification_warnings,
    find_card_issues,
    review_issue,
    short_description_warnings,
)
from domain.entities.card import (
    CardDraft,
    CardIssue,
    CardTexts,
)
from domain.entities.product import Product
from domain.exceptions import LlmError, LlmFailedError, LlmUnavailableError
from domain.interfaces.application.card_generator import CardGenerator
from domain.interfaces.infrastructure.llm_client import LlmClient, LlmRequest

CARD_TEXTS_SCHEMA_NAME = "card_texts"
CARD_REVIEW_SCHEMA_NAME = "card_review"
GRAPH_TIMEOUT_SECONDS = 450
NODE_MAX_ATTEMPTS = 2
MAX_REVISIONS = 2


def is_retryable(exc: BaseException) -> bool:
    return isinstance(exc, LlmError) and exc.retryable


class CardGenerationService(CardGenerator):
    def __init__(self, *, llm_client: LlmClient) -> None:
        self._llm_client = llm_client
        retry_policy = RetryPolicy(
            max_attempts=NODE_MAX_ATTEMPTS,
            retry_on=is_retryable,
        )
        builder = StateGraph(CardState)
        builder.add_node("write_card", self._write_card, retry_policy=retry_policy)
        builder.add_node("check_card", self._check_card)
        builder.add_node("review_card", self._review_card, retry_policy=retry_policy)
        builder.add_edge(START, "write_card")
        builder.add_edge("write_card", "check_card")
        builder.add_edge("check_card", "review_card")
        builder.add_conditional_edges("review_card", _next_step, ["write_card", END])
        self._graph = builder.compile()

    async def generate(self, product: Product) -> CardDraft:
        try:
            async with asyncio.timeout(GRAPH_TIMEOUT_SECONDS):
                state = await self._graph.ainvoke({"product": product, "revisions": 0})
        except TimeoutError as exc:
            raise LlmUnavailableError(
                f"Граф не уложился в {GRAPH_TIMEOUT_SECONDS} с",
                retryable=False,
            ) from exc
        return _build_draft(product, state["draft"], state["issues"])

    async def _write_card(self, state: CardState) -> CardState:
        product = state["product"]
        previous = state.get("draft")
        if previous is None:
            user = write_card.build_first_message(product)
        else:
            user = write_card.build_revision_message(
                product,
                previous,
                [issue.remark for issue in state["issues"]],
            )
        raw = await self._llm_client.complete_json(
            LlmRequest(
                system=write_card.SYSTEM,
                user=user,
                schema_name=CARD_TEXTS_SCHEMA_NAME,
                json_schema=WriteCardOutput.model_json_schema(),
            )
        )
        answer = _parse_answer(WriteCardOutput, raw)
        if previous is None:
            return {"draft": answer}
        return {
            "draft": answer.model_copy(
                update={
                    "description_facts": previous.description_facts,
                    "missing_characteristics": previous.missing_characteristics,
                    "needs_clarification": previous.needs_clarification,
                }
            ),
            "revisions": state["revisions"] + 1,
        }

    async def _check_card(self, state: CardState) -> CardState:
        return {"issues": find_card_issues(state["product"], _to_texts(state["draft"]))}

    async def _review_card(self, state: CardState) -> CardState:
        draft = state["draft"]
        raw = await self._llm_client.complete_json(
            LlmRequest(
                system=review_card.SYSTEM,
                user=review_card.build_message(state["product"], draft),
                schema_name=CARD_REVIEW_SCHEMA_NAME,
                json_schema=ReviewCardOutput.model_json_schema(),
            )
        )
        review = _parse_answer(ReviewCardOutput, raw)
        texts = _to_texts(draft)
        found = (
            review_issue(
                texts,
                kind=issue.kind,
                quote=issue.quote,
                reason=issue.reason,
            )
            for issue in review.issues
        )
        return {
            "issues": (*state["issues"], *(item for item in found if item is not None))
        }


def _next_step(state: CardState) -> str:
    if state["issues"] and state["revisions"] < MAX_REVISIONS:
        return "write_card"
    return END


def _parse_answer[T: BaseModel](schema: type[T], raw: str) -> T:
    try:
        return schema.model_validate_json(raw)
    except ValidationError as exc:
        raise LlmFailedError(
            f"Ответ модели не прошёл схему, ошибок: {exc.error_count()}",
            retryable=True,
        ) from None


def _to_texts(draft: WriteCardOutput) -> CardTexts:
    return CardTexts(
        seo_title=draft.seo_title,
        seo_description=draft.seo_description,
        search_queries=tuple(draft.search_queries),
        commercial=draft.commercial,
    )


def _build_draft(
    product: Product,
    draft: WriteCardOutput,
    issues: tuple[CardIssue, ...],
) -> CardDraft:
    texts = _to_texts(draft)
    assembled = assemble_characteristics(
        product,
        facts=draft.description_facts,
        missing_names=draft.missing_characteristics,
    )
    return CardDraft(
        texts=texts,
        characteristics=assembled.characteristics,
        missing_fields=assembled.added_missing,
        needs_clarification=tuple(draft.needs_clarification),
        warnings=(
            *assembled.warnings,
            *clarification_warnings(product, draft.needs_clarification),
            *short_description_warnings(texts.seo_description),
            *(issue.warning for issue in issues),
        ),
    )

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, StrictFloat, StrictInt, StrictStr, StringConstraints

from domain.entities.card import CardDraft
from domain.entities.product import Product
from presentation.api.markdown import render_markdown

SpecName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
SpecValue = StrictStr | StrictInt | StrictFloat | None


class CardRequest(BaseModel):
    name: str | None = None
    manufacturer: str | None = None
    specs: dict[SpecName, SpecValue] | None = None
    description: str | None = None

    def to_product(self) -> Product:
        return Product(
            name=self.name,
            manufacturer=self.manufacturer,
            specs=self.specs or {},
            description=self.description,
        )


class CharacteristicResponse(BaseModel):
    name: str
    value: str


class CommercialResponse(BaseModel):
    audience: str
    tasks: str


class CardBodyResponse(BaseModel):
    seo_title: str
    seo_description: str
    characteristics: list[CharacteristicResponse]
    search_queries: list[str]
    commercial: CommercialResponse


class ClarificationResponse(BaseModel):
    field: str
    reason: str


class CardResponse(BaseModel):
    card: CardBodyResponse
    missing_fields: list[str]
    needs_clarification: list[ClarificationResponse]
    warnings: list[str]
    markdown: str

    @classmethod
    def from_draft(cls, draft: CardDraft) -> CardResponse:
        texts = draft.card.texts
        return cls(
            card=CardBodyResponse(
                seo_title=texts.seo_title,
                seo_description=texts.seo_description,
                characteristics=[
                    CharacteristicResponse(name=item.name, value=item.value)
                    for item in draft.card.characteristics
                ],
                search_queries=list(texts.search_queries),
                commercial=CommercialResponse(
                    audience=texts.commercial.audience,
                    tasks=texts.commercial.tasks,
                ),
            ),
            missing_fields=list(draft.missing_fields),
            needs_clarification=[
                ClarificationResponse(field=item.field, reason=item.reason)
                for item in draft.needs_clarification
            ],
            warnings=list(draft.warnings),
            markdown=render_markdown(draft),
        )


class ErrorResponse(BaseModel):
    detail: str


class ClientErrorResponse(BaseModel):
    detail: str
    missing_fields: list[str] | None = None

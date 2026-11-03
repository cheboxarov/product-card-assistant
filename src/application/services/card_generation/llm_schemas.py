from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from domain.card_rules import QUERIES_MAX, QUERIES_MIN
from domain.entities.card import Clarification, Commercial, DescriptionFact


class WriteCardOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description_facts: list[DescriptionFact]
    missing_characteristics: Annotated[list[str], Field(max_length=5)]
    needs_clarification: list[Clarification]
    seo_title: str
    seo_description: str
    search_queries: Annotated[
        list[str], Field(min_length=QUERIES_MIN, max_length=QUERIES_MAX)
    ]
    commercial: Commercial


class ReviewIssueOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["unsupported_claim", "filler", "language_error"]
    quote: str
    reason: str


class ReviewCardOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    issues: list[ReviewIssueOutput]

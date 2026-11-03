from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class DescriptionFactOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    value: str
    quote: str


class ClarificationOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str
    reason: str


class CommercialOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    audience: str
    tasks: str


class WriteCardOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description_facts: list[DescriptionFactOutput]
    missing_characteristics: Annotated[list[str], Field(max_length=5)]
    needs_clarification: list[ClarificationOutput]
    seo_title: str
    seo_description: str
    search_queries: Annotated[list[str], Field(min_length=3, max_length=5)]
    commercial: CommercialOutput


class ReviewIssueOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["unsupported_claim", "filler"]
    quote: str
    reason: str


class ReviewCardOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    issues: list[ReviewIssueOutput]

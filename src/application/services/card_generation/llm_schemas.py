from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class CommercialOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    audience: str
    tasks: str


class CardTextsOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    seo_title: str
    seo_description: str
    search_queries: list[str]
    commercial: CommercialOutput

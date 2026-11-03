from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Characteristic:
    name: str
    value: str


@dataclass(frozen=True, slots=True)
class Commercial:
    audience: str
    tasks: str


@dataclass(frozen=True, slots=True)
class Card:
    seo_title: str
    seo_description: str
    characteristics: tuple[Characteristic, ...]
    search_queries: tuple[str, ...]
    commercial: Commercial


@dataclass(frozen=True, slots=True)
class Clarification:
    field: str
    reason: str


@dataclass(frozen=True, slots=True)
class CardDraft:
    card: Card
    missing_fields: tuple[str, ...] = ()
    needs_clarification: tuple[Clarification, ...] = ()
    warnings: tuple[str, ...] = ()

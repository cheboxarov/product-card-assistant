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
class CardTexts:
    seo_title: str
    seo_description: str
    search_queries: tuple[str, ...]
    commercial: Commercial


@dataclass(frozen=True, slots=True)
class Card:
    texts: CardTexts
    characteristics: tuple[Characteristic, ...]


@dataclass(frozen=True, slots=True)
class Clarification:
    field: str
    reason: str


@dataclass(frozen=True, slots=True)
class DescriptionFact:
    name: str
    value: str
    quote: str


@dataclass(frozen=True, slots=True)
class AssembledCharacteristics:
    characteristics: tuple[Characteristic, ...]
    added_missing: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CardIssue:
    remark: str
    warning: str


@dataclass(frozen=True, slots=True)
class CardDraft:
    card: Card
    missing_fields: tuple[str, ...] = ()
    needs_clarification: tuple[Clarification, ...] = ()
    warnings: tuple[str, ...] = ()

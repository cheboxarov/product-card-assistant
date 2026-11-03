from __future__ import annotations

from domain.card_rules import NO_DATA
from domain.entities.card import CardDraft


def render_markdown(draft: CardDraft) -> str:
    texts = draft.texts
    sections = [
        f"# {texts.seo_title}",
        texts.seo_description,
        _section(
            "Характеристики",
            [f"{item.name}: {item.value}" for item in draft.characteristics],
        ),
        _section("Поисковые запросы", texts.search_queries),
        f"## Кому подходит\n\n{texts.commercial.audience}",
        f"## Какие задачи решает\n\n{texts.commercial.tasks}",
        _section(
            "Что уточнить",
            [
                *(f"{name}: {NO_DATA}" for name in draft.missing_fields),
                *(f"{item.field}: {item.reason}" for item in draft.needs_clarification),
            ],
        ),
        _section("Предупреждения", draft.warnings),
    ]
    return "\n\n".join(section for section in sections if section) + "\n"


def _section(title: str, items: list[str] | tuple[str, ...]) -> str:
    if not items:
        return ""
    lines = "\n".join(f"- {item}" for item in items)
    return f"## {title}\n\n{lines}"

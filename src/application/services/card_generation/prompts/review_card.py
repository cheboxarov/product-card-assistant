from __future__ import annotations

import json

from application.services.card_generation.llm_schemas import WriteCardOutput
from application.services.card_generation.prompts.rules import render_device
from domain.entities.product import Product

SYSTEM = (
    "Ты проверяешь тексты товара в B2B-магазине контрольно-измерительных приборов. "
    "Ищи неподтверждённые утверждения и воду. Верни JSON по схеме."
)


def build_message(product: Product, draft: WriteCardOutput) -> str:
    texts = draft.model_dump(
        include={"seo_title", "seo_description", "search_queries", "commercial"}
    )
    texts_json = json.dumps(texts, ensure_ascii=False, indent=1)
    return f"""{render_device(product)}

<texts>
{texts_json}
</texts>

Проверь <texts> по сведениям из <device>."""

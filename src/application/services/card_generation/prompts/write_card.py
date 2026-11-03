from __future__ import annotations

import json

from application.services.card_generation.llm_schemas import WriteCardOutput
from application.services.card_generation.prompts.rules import render_device
from domain.entities.product import Product

SYSTEM = (
    "Ты готовишь черновик карточки товара для B2B-магазина контрольно-измерительных приборов. "
    "Используй только данные из входа. Не выдумывай характеристики и свойства. Верни JSON по схеме."
)


def build_first_message(product: Product) -> str:
    return f"{render_device(product)}\n\nЗаполни все поля ответа."


def build_revision_message(
    product: Product,
    previous: WriteCardOutput,
    remarks: list[str],
) -> str:
    previous_json = json.dumps(previous.model_dump(), ensure_ascii=False, indent=1)
    lines = "\n".join(f"- {remark}" for remark in remarks)
    return f"""{render_device(product)}

<previous_answer>
{previous_json}
</previous_answer>

<remarks>
{lines}
</remarks>

Выше твой прошлый ответ и замечания к нему. Верни ответ целиком в той же схеме."""

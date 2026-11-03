from __future__ import annotations

import json

from domain.entities.product import Product

SYSTEM = (
    "Ты готовишь черновик карточки товара для B2B-магазина контрольно-измерительных приборов. "
    "Используй только данные из входа. Не выдумывай характеристики и свойства. Верни JSON по схеме."
)


def build_user_message(product: Product) -> str:
    product_json = json.dumps(
        {
            "name": product.name,
            "manufacturer": product.manufacturer,
            "specs": dict(product.specs),
            "description": product.description,
        },
        ensure_ascii=False,
    )
    return (
        f"Вход: {product_json}\n"
        "seo_title: SEO-заголовок до 70 символов\n"
        "seo_description: связный текст на русском, примерно 130-160 слов\n"
        "search_queries: 3-5 поисковых запросов\n"
        "commercial: audience (кому подходит), tasks (какие задачи решает)"
    )

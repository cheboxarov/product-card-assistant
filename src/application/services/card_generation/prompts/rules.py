from __future__ import annotations

from domain.card_rules import is_empty
from domain.entities.product import Product


def render_device(product: Product) -> str:
    lines = ["<device>", f"<name>{product.name}</name>"]
    if not is_empty(product.manufacturer):
        lines.append(f"<manufacturer>{product.manufacturer}</manufacturer>")
    specs = [
        f"- {name}: {value}"
        for name, value in product.specs.items()
        if not is_empty(value)
    ]
    if specs:
        lines.extend(["<specs>", *specs, "</specs>"])
    if not is_empty(product.description):
        lines.append(f"<description>\n{product.description}\n</description>")
    lines.append("</device>")
    return "\n".join(lines)

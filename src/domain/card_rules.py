from __future__ import annotations

from collections.abc import Mapping

from domain.entities.card import Characteristic
from domain.entities.product import Product

NO_DATA = "данных нет"
NAME_LABEL = "Название"
MANUFACTURER_LABEL = "Производитель"
SPECS_LABEL = "Характеристики"
DESCRIPTION_LABEL = "Описание"


def characteristics_from_specs(
    specs: Mapping[str, str | int | float | None],
) -> tuple[Characteristic, ...]:
    return tuple(
        Characteristic(
            name=name,
            value=NO_DATA if _is_empty(value) else str(value),
        )
        for name, value in specs.items()
    )


def find_missing_input(product: Product) -> tuple[str, ...]:
    missing: list[str] = []
    if _is_empty(product.name):
        missing.append(NAME_LABEL)
    if _is_empty(product.manufacturer):
        missing.append(MANUFACTURER_LABEL)
    if product.specs:
        missing.extend(
            name for name, value in product.specs.items() if _is_empty(value)
        )
    else:
        missing.append(SPECS_LABEL)
    if _is_empty(product.description):
        missing.append(DESCRIPTION_LABEL)
    return tuple(missing)


def has_too_little_data(product: Product) -> bool:
    has_specs = any(not _is_empty(value) for value in product.specs.values())
    return _is_empty(product.name) or (not has_specs and _is_empty(product.description))


def _is_empty(value: str | int | float | None) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())

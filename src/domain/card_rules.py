from __future__ import annotations

from collections.abc import Mapping

from domain.entities.card import Characteristic

NO_DATA = "данных нет"


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


def _is_empty(value: str | int | float | None) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())

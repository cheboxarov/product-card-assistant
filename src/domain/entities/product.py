from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Product:
    name: str | None
    manufacturer: str | None
    specs: Mapping[str, str | int | float | None]
    description: str | None

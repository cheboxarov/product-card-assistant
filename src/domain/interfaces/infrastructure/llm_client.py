from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class LlmRequest:
    system: str
    user: str
    schema_name: str
    json_schema: dict[str, Any]


class LlmClient(Protocol):
    async def complete_json(self, request: LlmRequest) -> str: ...

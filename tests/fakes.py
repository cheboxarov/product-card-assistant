from __future__ import annotations

import json

from domain.interfaces.infrastructure.llm_client import LlmClient, LlmRequest

CLEAN_DESCRIPTION = (
    "Манометр показывает избыточное давление, это помогает следить за режимом работы. "
    * 11
).strip()


def card_texts_json(**overrides: object) -> str:
    answer: dict[str, object] = {
        "description_facts": [],
        "missing_characteristics": [],
        "needs_clarification": [],
        "seo_title": "Манометр показывающий Манотомь",
        "seo_description": CLEAN_DESCRIPTION,
        "search_queries": ["манометр купить", "манометр манотомь", "манометр давление"],
        "commercial": {"audience": "служба КИПиА", "tasks": "контроль давления"},
    }
    return json.dumps({**answer, **overrides}, ensure_ascii=False)


def review_json(*issues: dict[str, str]) -> str:
    return json.dumps({"issues": list(issues)}, ensure_ascii=False)


class FakeLlmClient(LlmClient):
    def __init__(self, *responses: str | Exception) -> None:
        self.responses = list(responses)
        self.requests: list[LlmRequest] = []

    async def complete_json(self, request: LlmRequest) -> str:
        self.requests.append(request)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

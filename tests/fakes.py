from __future__ import annotations

import json

from domain.interfaces.infrastructure.llm_client import LlmClient, LlmRequest


def card_texts_json(**overrides: object) -> str:
    texts: dict[str, object] = {
        "seo_title": "Манометр DM 02 Манотомь 0–1,6 МПа",
        "seo_description": "Манометр DM 02 показывает избыточное давление.",
        "search_queries": ["манометр DM 02", "манометр Манотомь", "манометр 1,6 МПа"],
        "commercial": {"audience": "служба КИПиА", "tasks": "контроль давления"},
    }
    return json.dumps({**texts, **overrides}, ensure_ascii=False)


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

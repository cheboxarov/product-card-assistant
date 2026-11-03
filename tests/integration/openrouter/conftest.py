from __future__ import annotations

from collections.abc import AsyncIterator, Callable

import httpx2
import pytest
from openai import AsyncOpenAI

from domain.interfaces.infrastructure.llm_client import LlmRequest
from infrastructure.openrouter.client import OpenRouterClient

TEST_API_KEY = "test-openrouter-key"
PROMPT_TEXT = "текст промпта"
LLM_REQUEST = LlmRequest(
    system="система",
    user=PROMPT_TEXT,
    schema_name="card_texts",
    json_schema={"type": "object"},
)


def completion_body(content: str | None, finish_reason: str = "stop") -> dict:
    return {
        "id": "gen-1",
        "object": "chat.completion",
        "created": 1793626098,
        "model": "meta/muse-spark-1.3-contributor",
        "provider": "Meta",
        "choices": [
            {
                "index": 0,
                "finish_reason": finish_reason,
                "native_finish_reason": "completed",
                "message": {"role": "assistant", "content": content},
            }
        ],
    }


@pytest.fixture
async def client_for() -> AsyncIterator[
    Callable[[Callable[[httpx2.Request], httpx2.Response]], OpenRouterClient]
]:
    clients: list[AsyncOpenAI] = []

    def build(handler: Callable[[httpx2.Request], httpx2.Response]) -> OpenRouterClient:
        openai_client = AsyncOpenAI(
            api_key=TEST_API_KEY,
            base_url="https://openrouter.ai/api/v1",
            max_retries=0,
            http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(handler)),
        )
        clients.append(openai_client)
        return OpenRouterClient(client=openai_client, model="test/model")

    yield build
    for openai_client in clients:
        await openai_client.close()

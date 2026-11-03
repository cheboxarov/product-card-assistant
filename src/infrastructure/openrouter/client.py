from __future__ import annotations

from openai import AsyncOpenAI

from domain.interfaces.infrastructure.llm_client import LlmClient, LlmRequest

MAX_OUTPUT_TOKENS = 16000


class OpenRouterClient(LlmClient):
    def __init__(self, *, client: AsyncOpenAI, model: str) -> None:
        self._client = client
        self._model = model

    async def complete_json(self, request: LlmRequest) -> str:
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": request.system},
                {"role": "user", "content": request.user},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": request.schema_name,
                    "strict": True,
                    "schema": request.json_schema,
                },
            },
            max_tokens=MAX_OUTPUT_TOKENS,
        )
        return response.choices[0].message.content

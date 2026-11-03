from __future__ import annotations

import httpx2

from bootstrap.app import create_app
from bootstrap.settings import Settings

# Test cases:
# 1. create_app собирает маршрут и обработчики ошибок: битый JSON даёт 400, запроса к модели нет


async def test_case_1() -> None:
    # 1. create_app собирает маршрут и обработчики ошибок: битый JSON даёт 400, запроса к модели нет
    # Arrange
    app = create_app(Settings(_env_file=None, openrouter_api_key="test-key"))

    # Act
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=app),
        base_url="http://cards.test",
    ) as client:
        response = await client.post(
            "/api/v1/cards",
            content=b"{",
            headers={"Content-Type": "application/json"},
        )

    # Assert
    assert response.status_code == 400

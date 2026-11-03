from __future__ import annotations

import httpx2

from bootstrap.app import create_app
from bootstrap.settings import Settings

# Test cases:
# 1. create_app собирает маршрут и обработчики ошибок: битый JSON даёт 400, запроса к модели нет
# 2. GET / отдаёт страницу с формой и встроенными примерами, в схеме API страницы нет


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


async def test_case_2() -> None:
    # 2. GET / отдаёт страницу с формой и встроенными примерами, в схеме API страницы нет
    # Arrange
    app = create_app(Settings(_env_file=None, openrouter_api_key="test-key"))

    # Act
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=app),
        base_url="http://cards.test",
    ) as client:
        response = await client.get("/")
        schema = await client.get("/openapi.json")

    # Assert
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/html; charset=utf-8"
    assert '<form id="card-form"' in response.text
    assert "Манометр показывающий DM 02" in response.text
    assert "Преобразователь давления измерительный ПД100-1Х1" in response.text
    assert list(schema.json()["paths"]) == ["/api/v1/cards"]

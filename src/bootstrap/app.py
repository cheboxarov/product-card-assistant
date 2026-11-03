from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from bootstrap.container import build_api_container
from bootstrap.settings import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    container = build_api_container(settings or Settings())

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            await container.close()

    app = FastAPI(title="product-card-assistant", version="0.1.0", lifespan=lifespan)
    app.include_router(container.cards_router)
    return app

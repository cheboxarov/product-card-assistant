from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

INDEX_PATH = Path(__file__).resolve().parents[2] / "web" / "index.html"


def build_web_router() -> APIRouter:
    router = APIRouter()

    @router.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        return FileResponse(INDEX_PATH)

    return router

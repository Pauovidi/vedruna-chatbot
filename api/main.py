from __future__ import annotations

from fastapi import FastAPI

from api.routers import chat, elevenlabs, health, tools, vedruna, webhooks
from core.config import get_settings


def create_app() -> FastAPI:
    get_settings().assert_production_ready()
    app = FastAPI(title="Vedruna Chatbot", version="0.1.0")
    app.include_router(health.router)
    app.include_router(chat.router)
    app.include_router(elevenlabs.router)
    app.include_router(tools.router)
    app.include_router(webhooks.router)
    app.include_router(vedruna.router)
    return app


app = create_app()

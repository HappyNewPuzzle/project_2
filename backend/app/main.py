import logging

from fastapi import FastAPI

from app.api.routes.chat import router as chat_router
from app.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
    )
    app.include_router(chat_router)
    return app


app = create_app()

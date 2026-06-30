"""FastAPI 애플리케이션을 만들고 라우터와 종료 처리를 연결하는 진입점."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes.auth import router as auth_router
from app.api.routes.chat import router as chat_router
from app.api.routes.characters import router as characters_router
from app.api.routes.health import router as health_router
from app.api.routes.memories import router as memories_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.middleware import RequestContextMiddleware
from app.db.session import get_engine


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """서버 수명 주기를 관리한다.

    yield 이전은 시작 시점, yield 이후는 종료 시점에 실행된다.
    현재는 시작 작업이 없고 종료할 때 DB 커넥션 풀만 안전하게 닫는다.
    """

    yield
    await get_engine().dispose()


def create_app() -> FastAPI:
    """설정값을 읽어 하나의 FastAPI 앱 객체를 조립한다."""

    # get_settings()는 캐시되므로 애플리케이션 전체에서 같은 설정을 공유한다.
    settings = get_settings()

    # 운영 수집기가 파싱할 수 있는 구조화 로그와 요청 ID 필터를 설정한다.
    configure_logging(
        settings.log_level,
        json_logs=settings.log_json,
    )

    # lifespan을 넘기면 FastAPI가 서버 종료 시 DB 엔진 정리를 호출한다.
    app = FastAPI(
        title=settings.app_name,
        version="0.6.0",
        lifespan=lifespan,
    )

    # 모든 HTTP 요청에 request ID와 접근 로그를 추가한다.
    app.add_middleware(RequestContextMiddleware)

    # 기능별 라우터를 앱에 등록한다. 실제 URL 처리는 각 routes 파일이 담당한다.
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(chat_router)
    app.include_router(characters_router)
    app.include_router(memories_router)
    return app


# uvicorn app.main:app 명령이 가져가는 실제 애플리케이션 객체다.
app = create_app()

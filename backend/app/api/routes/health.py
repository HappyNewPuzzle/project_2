"""인증 없이 사용할 수 있는 liveness와 readiness endpoint."""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.dependencies import SessionDependency

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
async def liveness() -> dict[str, str]:
    """프로세스가 HTTP 요청을 처리할 수 있는지만 확인한다."""

    return {"status": "ok"}


@router.get("/ready")
async def readiness(session: SessionDependency) -> dict[str, str]:
    """필수 의존성인 PostgreSQL에 실제 쿼리가 가능한지 확인한다."""

    try:
        await session.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not ready.",
        ) from exc
    return {"status": "ready"}

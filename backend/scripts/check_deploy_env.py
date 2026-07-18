"""배포 전 환경 설정이 위험한 기본값으로 남아 있지 않은지 점검한다."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

# 파일 경로로 실행해도 `backend/app` 패키지를 찾을 수 있게 backend 루트를 추가한다.
sys.path.append(str(Path(__file__).resolve().parents[1]))
from app.core.config import get_settings


@dataclass(frozen=True, slots=True)
class CheckResult:
    """하나의 점검 결과를 사람이 읽기 쉬운 메시지와 함께 표현한다."""

    level: str
    message: str


def _is_local_origin(origin: str) -> bool:
    """origin이 로컬 개발 서버를 가리키는지 판단한다."""

    return (
        origin.startswith("http://localhost")
        or origin.startswith("http://127.0.0.1")
        or origin.startswith("http://0.0.0.0")
    )


def check_settings(
    *,
    production: bool,
    allow_missing_openai: bool,
    allow_dev_secret: bool,
) -> list[CheckResult]:
    """현재 Settings 값을 읽고 배포 전 확인해야 할 항목을 점검한다."""

    try:
        settings = get_settings()
    except Exception as exc:
        return [CheckResult("ERROR", f"Settings could not be loaded: {exc}")]

    results: list[CheckResult] = []

    # DB URL은 async SQLAlchemy 엔진과 맞는 asyncpg 드라이버를 사용해야 한다.
    if settings.database_url.startswith("postgresql+asyncpg://"):
        results.append(CheckResult("OK", "DATABASE_URL uses asyncpg PostgreSQL."))
    else:
        results.append(
            CheckResult(
                "ERROR",
                "DATABASE_URL must start with postgresql+asyncpg://",
            )
        )

    # 운영에서 개발용 JWT secret을 그대로 쓰면 토큰 위조 위험이 커진다.
    dev_secret_values = {
        "dev-only-change-this-secret-key-123456",
        "replace_with_a_long_random_secret",
    }
    if settings.jwt_secret_key in dev_secret_values and not allow_dev_secret:
        results.append(
            CheckResult(
                "ERROR",
                "JWT_SECRET_KEY still uses a documented development value.",
            )
        )
    elif len(settings.jwt_secret_key) < 32:
        results.append(
            CheckResult("ERROR", "JWT_SECRET_KEY must be at least 32 characters.")
        )
    else:
        results.append(CheckResult("OK", "JWT_SECRET_KEY length looks acceptable."))

    # 실제 LLM 호출을 받을 환경에서는 OpenAI API 키가 있어야 한다.
    if settings.openai_api_key:
        results.append(CheckResult("OK", "OPENAI_API_KEY is configured."))
    elif allow_missing_openai:
        results.append(
            CheckResult(
                "WARN",
                "OPENAI_API_KEY is missing; chat requests will fail until configured.",
            )
        )
    else:
        results.append(CheckResult("ERROR", "OPENAI_API_KEY is required."))

    # CORS wildcard는 편하지만 운영에서는 의도치 않은 웹사이트까지 허용할 수 있다.
    cors_origins = settings.cors_origin_list
    if "*" in cors_origins:
        results.append(
            CheckResult("ERROR", "CORS_ALLOWED_ORIGINS must not contain '*'.")
        )
    elif production and any(_is_local_origin(origin) for origin in cors_origins):
        results.append(
            CheckResult(
                "ERROR",
                "Production CORS_ALLOWED_ORIGINS must not point to localhost.",
            )
        )
    else:
        results.append(CheckResult("OK", "CORS_ALLOWED_ORIGINS is explicit."))

    # 운영 로그는 수집기가 파싱하기 쉬운 JSON 형태를 권장한다.
    if production and not settings.log_json:
        results.append(CheckResult("WARN", "LOG_JSON=false is not recommended in production."))
    else:
        results.append(CheckResult("OK", "Logging mode is acceptable."))

    return results


def main() -> int:
    """CLI 인자를 읽고 점검 결과를 출력한 뒤 종료 코드를 반환한다."""

    parser = argparse.ArgumentParser(
        description="Check deployment-related backend environment settings.",
    )
    parser.add_argument(
        "--production",
        action="store_true",
        help="Fail on localhost CORS origins and other production risks.",
    )
    parser.add_argument(
        "--allow-missing-openai",
        action="store_true",
        help="Warn instead of failing when OPENAI_API_KEY is missing.",
    )
    parser.add_argument(
        "--allow-dev-secret",
        action="store_true",
        help="Allow documented development JWT secret values.",
    )
    args = parser.parse_args()

    results = check_settings(
        production=args.production,
        allow_missing_openai=args.allow_missing_openai,
        allow_dev_secret=args.allow_dev_secret,
    )

    has_error = False
    for result in results:
        print(f"[{result.level}] {result.message}")
        if result.level == "ERROR":
            has_error = True

    return 1 if has_error else 0


if __name__ == "__main__":
    sys.exit(main())

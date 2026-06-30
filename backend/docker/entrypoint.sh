#!/bin/sh
set -eu

# DB가 준비된 뒤 최신 schema를 적용하고, 성공한 경우에만 API 프로세스를 시작한다.
alembic upgrade head

# exec를 사용해 uvicorn이 PID 1이 되고 종료 신호를 직접 받게 한다.
exec "$@"

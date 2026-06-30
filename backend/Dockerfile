# syntax=docker/dockerfile:1

# 작은 공식 Python 이미지를 사용해 이미지 크기와 공격 표면을 줄인다.
FROM python:3.12-slim

# Python 로그가 즉시 컨테이너 stdout으로 나오고 .pyc를 만들지 않게 한다.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# dependency 파일을 먼저 복사하면 앱 코드만 바뀔 때 pip layer를 재사용할 수 있다.
COPY requirements.txt .
RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements.txt

# 실행에 필요한 코드, migration, 진입 스크립트만 이미지에 넣는다.
COPY alembic.ini .
COPY alembic ./alembic
COPY app ./app
COPY docker/entrypoint.sh ./docker/entrypoint.sh

# 앱은 8000 포트만 사용하므로 root 권한이 필요 없다.
RUN addgroup --system app \
    && adduser --system --ingroup app --no-create-home app \
    && chmod +x ./docker/entrypoint.sh \
    && chown -R app:app /app

USER app
EXPOSE 8000

# curl 설치 없이 Python 표준 라이브러리로 liveness를 확인한다.
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/live', timeout=2)"]

ENTRYPOINT ["./docker/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--no-access-log"]

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml ./
COPY src ./src
RUN uv pip install --system --no-cache -e ".[dev]"

COPY alembic.ini ./
COPY migrations ./migrations
COPY data ./data
COPY tests ./tests

CMD ["uvicorn", "LeakyWallet.main:app", "--host", "0.0.0.0", "--port", "8000"]

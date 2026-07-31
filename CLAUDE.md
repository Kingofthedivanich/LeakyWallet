# LeakyWallet

Telegram-бот: сканирует почту, находит подписки, напоминает о списаниях.

## Стек
Python 3.12, aiogram 3, FastAPI, SQLAlchemy 2.0 (async), PostgreSQL 16,
Redis 7, ARQ, Alembic, pydantic v2, pytest-asyncio.

## Команды
- `make up` — поднять окружение
- `make test` — pytest
- `make lint` — ruff check + ruff format
- `make migrate m="msg"` — создать миграцию
- `make upgrade` — применить миграции

## Правила
- Async везде, где есть I/O. Синхронный код только в чистых функциях.
- Деньги — Decimal. Даты в БД — UTC, timezone-aware.
- Слои: handlers → services → repositories → models. Пропускать слой нельзя.
- services/ не импортирует aiogram.
- Новая логика — с тестом. Тесты не ходят в сеть.
- Type hints обязательны, mypy в strict на src/.
- Секреты только через config.py, никаких os.getenv по коду.

## Чего не делать
- Не хранить тела писем. Только извлечённые поля и message_id.
- Не делать блокирующие вызовы в хендлерах — всё тяжёлое в очередь.
- Не добавлять зависимости без необходимости.

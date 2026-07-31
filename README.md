# LeakyWallet

Telegram-бот, который сканирует почту, находит подписки и напоминает о списаниях.

## Запуск

```bash
cp .env.example .env
make up
```

После этого:
- API: http://localhost:8000/healthz
- Postgres: localhost:5432
- Redis: localhost:6379

## Команды

| Команда | Что делает |
|---|---|
| `make up` | поднять окружение (app, worker, postgres, redis) |
| `make down` | остановить окружение |
| `make logs` | логи всех контейнеров |
| `make test` | прогнать тесты (внутри контейнера `app`) |
| `make lint` | ruff check + ruff format --check + mypy (на хосте) |
| `make migrate m="msg"` | создать миграцию (внутри контейнера `app`) |
| `make upgrade` | применить миграции (внутри контейнера `app`) |

`test`/`migrate`/`upgrade` требуют, чтобы окружение уже было поднято
(`make up`) — команды выполняются через `docker compose exec app ...`.
На Windows это осознанный выбор: `asyncpg` не может подключиться к
проброшенному Docker Desktop порту напрямую с хоста (обрывает соединение
на уровне ProactorEventLoop), а изнутри контейнера всё работает штатно.

## Статус

Этап 3 — ручные подписки (добавление, список, карточка, редактирование, удаление, сводка).

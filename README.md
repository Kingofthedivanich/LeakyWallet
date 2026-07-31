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
| `make test` | прогнать тесты |
| `make lint` | ruff check + ruff format --check + mypy |
| `make migrate m="msg"` | создать миграцию |
| `make upgrade` | применить миграции |

## Статус

Этап 0 — скелет проекта.

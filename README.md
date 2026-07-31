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

Этап 5 — OAuth и хранение токенов (код готов, живой тест на реальном
Google-аккаунте — см. ниже).

## Подключение Gmail (для живого теста Этапа 5)

1. В [Google Cloud Console](https://console.cloud.google.com/) создайте
   проект (или используйте существующий).
2. **APIs & Services → Library** — включите **Gmail API**.
3. **APIs & Services → OAuth consent screen**:
   - User type: External.
   - Publishing status: Testing.
   - Scopes: добавьте `.../auth/gmail.readonly` (restricted scope).
   - Test users: добавьте свой Google-аккаунт — без этого вход будет
     заблокирован, пока приложение не прошло верификацию Google.
4. **APIs & Services → Credentials → Create credentials → OAuth client ID**:
   - Application type: Web application.
   - Authorized redirect URIs: `http://localhost:8000/oauth/callback`
     (ровно как в `.env`, включая `http://localhost`, без порта‑алиасов).
5. Скопируйте Client ID и Client Secret в `.env`:
   ```
   GOOGLE_CLIENT_ID=...
   GOOGLE_CLIENT_SECRET=...
   GOOGLE_REDIRECT_URI=http://localhost:8000/oauth/callback
   ```
6. `make up` (пересоберёт контейнер с новым `.env`), пропишите
   `TELEGRAM_BOT_TOKEN`, поговорите с ботом → Настройки → 📧 Почта →
   «Подключить Gmail» → войдите тестовым аккаунтом → «Разрешить».
   Бот должен прислать подтверждение с адресом почты.

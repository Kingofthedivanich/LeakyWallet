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
| `make backup` | дамп Postgres в `backups/<таймстамп>.sql` |
| `make restore f=backups/<file>.sql` | восстановить БД из дампа |

`test`/`migrate`/`upgrade` требуют, чтобы окружение уже было поднято
(`make up`) — команды выполняются через `docker compose exec app ...`.
На Windows это осознанный выбор: `asyncpg` не может подключиться к
проброшенному Docker Desktop порту напрямую с хоста (обрывает соединение
на уровне ProactorEventLoop), а изнутри контейнера всё работает штатно.

## Статус

Этап 10 — продакшен: Sentry (включается сам, если задан `SENTRY_DSN`),
structlog с correlation id (`request_id` на каждый HTTP-запрос,
`job_id` на каждую джобу воркера — прокидываются через
`structlog.contextvars` и попадают в каждую строку лога), graceful
shutdown (polling-таск и ARQ-воркер корректно дожидаются завершения при
остановке, `stop_grace_period: 30s` в compose), healthcheck'и для `app` и
`worker` в docker-compose, `make backup`/`make restore` для Postgres,
GitHub Actions (`.github/workflows/ci.yml`) — lint + тесты на каждый PR.
Инструкция по разворачиванию — раздел «Продакшен» ниже. Стадии 5–6 (OAuth и
скан почты) по-прежнему ждут вашей проверки на реальном Google-аккаунте —
см. ниже.

## Подключение Gmail (для живого теста Этапов 5–6)

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
7. Сразу после подключения бот сам поставит первый скан в очередь
   (`docker logs leakywallet-worker-1 -f`, чтобы видеть прогресс). Если в
   ящике есть письма от сервисов из `data/services.yaml` или с ключевыми
   словами (invoice/receipt/чек/подписка) за последние 12 месяцев — бот
   пришлёт «Скан завершён. Найдено кандидатов: N». Кандидаты пока просто
   логируются воркером (`parse_candidate` — заглушка, реальный парсинг
   в Этапе 7). Повторно вызвать скан: подождать 15 минут (cron) или
   перезапустить `scan_email_account` вручную.

## Продакшен

### Переменные окружения

Кроме уже описанных выше (`GOOGLE_*`, `OPENROUTER_*`, `FERNET_KEY`), в
боевом окружении задайте:

- `ENVIRONMENT=production` — переключает structlog на JSON-формат логов
  (в остальных окружениях — читаемый консольный вывод).
- `SENTRY_DSN` — если задан, ошибки из `app` и `worker` автоматически летят
  в Sentry (`src/LeakyWallet/sentry.py`); если пусто — Sentry просто не
  инициализируется, ничего не падает.
- `TELEGRAM_USE_WEBHOOK=true`, `TELEGRAM_WEBHOOK_URL`,
  `TELEGRAM_WEBHOOK_SECRET` — вместо polling бот регистрирует вебхук у
  Telegram (нужен домен с HTTPS перед `app`, например reverse-proxy).
- `FERNET_KEY` — обязателен, если почта вообще будет подключаться
  (шифрование токенов). Ротация ключа = потеря доступа к уже сохранённым
  токенам, переподключайте почту заново.

### Логи и трассировка

Каждая строка лога — JSON с `request_id` (HTTP-запросы к `app`, включая
`/webhook`) или `job_id` (джобы `worker`), плюс `level`/`timestamp`/
`event`. Это позволяет склеить все логи одного запроса или одной джобы
по `grep`/фильтру в системе агрегации логов, не разворачивая трассировку
вручную.

### Остановка без потери данных

`app` (uvicorn) и `worker` (ARQ) оба реагируют на `SIGTERM`: `app`
дожидается завершения polling-таска (при вебхуке его просто нет) и
активных HTTP-запросов; `worker` (по умолчанию в ARQ, `handle_signals=True`)
доигрывает уже взятые в работу джобы перед выходом. `stop_grace_period:
30s` у `worker` в `docker-compose.yml` даёт на это время — не уменьшайте
без необходимости, если джобы (например, `scan_email_account`) могут идти
дольше.

### Бэкапы

```bash
make backup                          # -> backups/<YYYYMMDD_HHMMSS>.sql
make restore f=backups/<file>.sql    # восстановить в текущую БД
```

`backups/` в `.gitignore` — дампы не коммитятся, храните их отдельно
(например, вне репозитория, с ротацией).

### CI

`.github/workflows/ci.yml` на каждый push в `master` и каждый PR: джоба
`lint` (ruff check + ruff format --check + mypy) и джоба `test` (pytest
против postgres:16-alpine + redis:7-alpine как GitHub Actions services).
CI не собирает Docker-образ — тесты гоняются напрямую через `pip install
-e ".[dev]"`, так что PR можно проверить ещё до `docker build`.

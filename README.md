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
| `make test` | прогнать тесты (внутри `app`, в отдельной БД `<POSTGRES_DB>_test`) |
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

**Тесты и dev-БД разделены на две базы.** `tests/conftest.py` на каждый
запуск делает `DROP`/`CREATE` всех таблиц — если направить это на обычную
`leakywallet`, живые данные (например, только что просканированная почта)
будут уничтожены безвозвратно. Поэтому:
- `postgres` при первом старте (`scripts/init-test-db.sh`) сам создаёт
  `<POSTGRES_DB>_test` рядом с основной базой;
- `make test` явно подставляет `DATABASE_URL` с суффиксом `_test`;
- `tests/conftest.py` вдобавок отказывается работать, если имя базы не
  оканчивается на `_test` — так что случайный `docker compose exec app
  pytest` в обход `make test` упадёт с понятной ошибкой вместо того, чтобы
  тихо стереть dev-данные.

## Статус

**Подписки vs разовые платежи.** Живые данные показали: сопоставление письма
с сервисом каталога по домену/ключевым словам не отличает настоящую
recurring-подписку от разовой покупки, которая просто пришла от того же
отправителя (например, Steam — покупки игр, а не подписка; Яндекс — такси/
маркет/еда под одним широким доменом `yandex.ru`). После 3+ транзакций
`ReceiptService` сам проверяет (`utils/money.amounts_are_consistent`,
`utils/dates.has_same_day_repeat`): если суммы скачут сильнее, чем на
коэффициент вариации 0.5, или было хотя бы одно списание дважды в один
день — подписка помечается `is_recurring=false` (миграция `7779432b41ba`) и
пропадает из «Мои подписки»/напоминаний/детектора «спящих», но остаётся
видна в «Аналитике» отдельным блоком «Разовые платежи по категориям».
Порог откалиброван на реальном датасете: Яндекс (CV≈5.6) и Steam (CV≈1.6)
корректно уходят в разовые, легитимная подписка с одной сменой цены
(CV≈0.47) — остаётся подпиской.

Этап 10 — продакшен: Sentry (включается сам, если задан `SENTRY_DSN`),
structlog с correlation id (`request_id` на каждый HTTP-запрос,
`job_id` на каждую джобу воркера — прокидываются через
`structlog.contextvars` и попадают в каждую строку лога), graceful
shutdown (polling-таск и ARQ-воркер корректно дожидаются завершения при
остановке, `stop_grace_period: 30s` в compose), healthcheck'и для `app` и
`worker` в docker-compose, `make backup`/`make restore` для Postgres,
GitHub Actions (`.github/workflows/ci.yml`) — lint + тесты на каждый PR.
Инструкция по разворачиванию — раздел «Продакшен» ниже.

**Живой тест Этапов 5–6 пройден** на реальном Google-аккаунте: OAuth,
подключение Gmail и bootstrap-скан (1137 писем за 12 месяцев) отработали
без проблем в самом потоке. Скан нашёл 292 подписки-транзакции — по пути
вскрылись и были исправлены две гонки при параллельной обработке кандидатов
воркером: `parse_candidate`-джобы могли одновременно создать дубликат
`Service` (ловилось падением джобы, `ServiceRepository.get_or_create`) или,
хуже, тихо задвоить `Subscription` для одного и того же отправителя без
каталога (не падало вообще — теперь закрыто partial unique index'ами в
БД + `SubscriptionRepository.get_or_create_email`, миграция `e9397fe3f8e2`).
Заодно нашёлся архитектурный пробел: `tests/conftest.py` дропал и
пересоздавал таблицы прямо в dev-БД, так как `DATABASE_URL` для тестов и
для `app`/`worker` совпадали — во время живого теста это стёрло только что
собранные данные. Починено отдельной `_test`-базой + guard'ом в conftest
(см. «Команды» выше).

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
   пришлёт «Скан завершён. Найдено кандидатов: N». Каждый кандидат уходит
   в `parse_candidate` (правила → LLM-фоллбэк → подписка/транзакция или
   «не распознано» — Этапы 7–8); результат смотрите в боте («Мои подписки»,
   «Аналитика») или прямо в БД. Повторно вызвать скан: подождать 15 минут
   (cron) или перезапустить `scan_email_account` вручную.

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

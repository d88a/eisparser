# Текущая рабочая конфигурация VDS

Дата фиксации: 2026-03-01

## Сервер
- IP: `213.189.219.55`
- ОС: Debian 12
- Пользователь приложения: `eisparser`
- Каталог проекта: `/opt/eisparser`

## Приложение
- Виртуальное окружение: `/opt/eisparser/.venv`
- API запуск:
  - `/opt/eisparser/.venv/bin/python -m uvicorn api.app:app --host 127.0.0.1 --port 8000`
- `PYTHONPATH` для запуска: `/opt/eisparser/src`

## PostgreSQL
- База: `eisparser_db`
- Пользователь: `eisparser_user`
- DSN:
  - `postgresql://eisparser_user:<PASSWORD>@127.0.0.1:5432/eisparser_db`

## .env
- Путь: `/opt/eisparser/src/.env`
- Права: `600`
- Владелец: `eisparser:eisparser`
- Ключевые параметры:
  - `DATABASE_URL=postgresql://eisparser_user:...@127.0.0.1:5432/eisparser_db`
  - `AI_STAGE2_DELAY_S=5`
  - `WORKER_ENABLE_STAGE4=true`
  - `USER_ACCESS_MODE=PUBLIC` (или `AUTH_REQUIRED`)
  - `ADMIN_SECURITY_FAIL_FAST=true`
  - `ADMIN_TOKEN_SECRET=<отдельный секрет, не равен ADMIN_PASSWORD>`
  - `EIS_RETRY_COUNT=3`
  - `EIS_RETRY_BACKOFF_S=2.0`
  - `EIS_REQUEST_TIMEOUT_S=30`
  - `CEREBRAS_BASE_URL=https://openrouter.ai/api/v1`
  - `CEREBRAS_MODEL=openai/gpt-oss-20b:free`

## Systemd-сервисы

### API
- `/etc/systemd/system/eisparser-api.service`
- Ключевые строки:
  - `User=eisparser`
  - `Group=eisparser`
  - `WorkingDirectory=/opt/eisparser`
  - `Environment=PYTHONPATH=/opt/eisparser/src`
  - `ExecStart=/opt/eisparser/.venv/bin/python -m uvicorn api.app:app --host 127.0.0.1 --port 8000`

### Worker ingest
- `/etc/systemd/system/eisparser-worker-ingest.service`
- `ExecStart=/opt/eisparser/.venv/bin/python /opt/eisparser/src/main.py worker-ingest --interval 300 --limit 10`

### Worker listing
- `/etc/systemd/system/eisparser-worker-listing.service`
- `ExecStart=/opt/eisparser/.venv/bin/python /opt/eisparser/src/main.py worker-listing --interval 300 --limit 10 --top-n 10`

## Логи
- API: `/opt/eisparser/results/logs/api.log`
- Worker: `/opt/eisparser/results/logs/worker.log`
- Cleanup: `/opt/eisparser/results/logs/cleanup.log`

Проверка:
```bash
tail -n 120 /opt/eisparser/results/logs/api.log
tail -n 200 /opt/eisparser/results/logs/worker.log
```

## Очистка старых записей
- SQL: `/opt/eisparser/scripts/cleanup_old.sql`
- Cron: `/etc/cron.d/eisparser_cleanup`
```cron
20 3 * * * root sudo -u postgres psql -d eisparser_db -f /opt/eisparser/scripts/cleanup_old.sql >> /opt/eisparser/results/logs/cleanup.log 2>&1
```

## Важное по безопасности
После публикации логов/скриншотов ротировать:
- `ADMIN_PASSWORD`
- `ADMIN_TOKEN_SECRET`
- `CEREBRAS_API_KEY`
- пароль БД

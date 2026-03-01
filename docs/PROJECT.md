# EIS Parser - архитектура и рабочий контур

## Назначение
Система автоматизирует обработку закупок недвижимости:
1. Stage 1 - загрузка и сохранение закупок ЕИС.
2. Stage 2 - ИИ-анализ текста закупки.
3. Stage 3 - генерация ссылок 2ГИС.
4. Stage 4 - сбор объявлений по ссылке Stage 3.

## Контракт этапов
- Каноническая ссылка процесса хранится в `zakupki.two_gis_url`.
- Stage 4 работает только по `two_gis_url`.
- Stage 2 pending: статусы `raw` и `ai_error`.
- Канонические backend-статусы и наборы очередей вынесены в `src/models/statuses.py`.

## Lifecycle статусов закупки
`raw -> ai_ready | ai_error -> url_ready -> stage4_done | stage4_error`

Допустимые переходы фиксируются в `PIPELINE_LIFECYCLE_TRANSITIONS` (`src/models/statuses.py`).

## Структура проекта
```text
eisparser/
├── src/
│   ├── api/
│   ├── config/
│   ├── models/
│   ├── repositories/
│   ├── services/
│   ├── web/
│   ├── pipeline.py
│   └── main.py
├── deploy/
├── docs/
├── results/
└── tests/
```

## Конфигурация (`src/.env`)
Ключевые переменные:
- `DATABASE_URL` / `DATABASE_PATH`
- `ADMIN_PASSWORD`
- `ADMIN_TOKEN_SECRET`
- `ADMIN_TOKEN_TTL_SECONDS`
- `USER_ACCESS_MODE` (`PUBLIC` или `AUTH_REQUIRED`)
- `SERVER_RELOAD`
- `CEREBRAS_API_KEY`, `CEREBRAS_BASE_URL`, `CEREBRAS_MODEL`
- `AI_STAGE2_DELAY_S`
- `STAGE1_MAX_PAGES`
- `WORKER_ENABLE_STAGE4`

Логика выбора БД:
1. если задан `DATABASE_URL` - PostgreSQL;
2. если `DATABASE_URL` пуст - SQLite (`DATABASE_PATH`).

## Запуск

### Локально
```powershell
$env:PYTHONPATH="src"
python src\main.py server --host 127.0.0.1 --port 8000
python src\main.py worker-ingest --interval 300 --limit 10
python src\main.py worker-listing --interval 300 --limit 10 --top-n 10
```

### Прод (VDS)
- API и воркеры работают через systemd.
- Базовый путь проекта: `/opt/eisparser`.

Подробные runbook:
- `docs/DEPLOY_AND_RUN.md`
- `docs/WORKER_VDS.md`
- `docs/LOCAL_TUNNEL_RUN.md`

## Тесты
```powershell
$env:PYTHONPATH="src"
python -m pytest -q
```

## Admin Auth
- Cookie `admin_token` хранит подписанный токен с TTL (HMAC), без хранения пароля.
- Для прода обязательно задать:
  - сложный `ADMIN_PASSWORD`
  - отдельный случайный `ADMIN_TOKEN_SECRET`

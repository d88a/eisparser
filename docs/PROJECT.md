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
├── docs/
├── results/
├── scripts/
└── zakupki/
```

## Конфигурация (`src/.env`)
Ключевые переменные:
- `DATABASE_URL` / `DATABASE_PATH`
- `ADMIN_PASSWORD`
- `CEREBRAS_API_KEY`, `CEREBRAS_BASE_URL`, `CEREBRAS_MODEL`
- `AI_STAGE2_DELAY_S`
- `STAGE1_MAX_PAGES` (default `10`)
- `WORKER_ENABLE_STAGE4`
- `PROXY_URL` (опционально)

Логика выбора БД:
1. если задан `DATABASE_URL` - PostgreSQL;
2. если `DATABASE_URL` пуст - SQLite (`DATABASE_PATH`).

## Важные технические правила

### Stage 1
- При недоступности страницы 1 ЕИС цикл Stage 1 прерывается.
- Поля `bid_end_date` и `initial_price` заполняются из карточки, при отсутствии - fallback из `combined_text`.
- Ограничение сканирования по страницам: `STAGE1_MAX_PAGES`.

### Stage 2
- Выборка pending идет по `raw`/`ai_error`.
- `decisions` не является обязательным фильтром запуска Stage 2.
- В ответе `run_stage2` возвращаются `processed_reg_numbers` и `failed_reg_numbers`.

### БД
- `DatabaseService` обязан прокидывать `database_url` во все репозитории.
- При старте логируется backend: PostgreSQL/SQLite.

## Запуск

### Локально
```powershell
python src\main.py server --host 127.0.0.1 --port 8000
python src\main.py worker --interval 300 --limit 10 --top-n 10
```

### Прод (NetAngels)
- Админка через ASGI (`APP_PATH=/home/c77461/priv-mag.ru/app/asgi.py`).
- Воркер через cron (`--max-cycles 1` каждые 5 минут).

Подробные runbook:
- `docs/DEPLOY_AND_RUN.md`
- `docs/WORKER_VDS.md`
- `docs/LOCAL_TUNNEL_RUN.md`

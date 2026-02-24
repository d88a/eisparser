# EIS Parser — админ-панель модерации закупок (MVP)

## Назначение
Система автоматизирует обработку закупок недвижимости:
1. Stage 1: загрузка списка закупок с ЕИС.
2. Stage 2: ИИ-анализ.
3. Stage 3: генерация ссылок 2ГИС.
4. Stage 4: сбор объявлений по ссылке из Stage 3.

## Контракт Stage 3 -> Stage 4
- Каноническая ссылка процесса хранится в `zakupki.two_gis_url`.
- Stage 4 запускается только по этой ссылке и не пересчитывает ее.
- Если ссылки нет, UI показывает: `Ссылки нет (Этап 3)`.

## Структура проекта
```text
eisparser/
├── src/
│   ├── api/                # FastAPI + роуты
│   ├── config/             # настройки и .env
│   ├── models/             # dataclass-модели
│   ├── repositories/       # слой доступа к БД (SQLite/PostgreSQL)
│   ├── services/           # бизнес-логика
│   ├── web/                # templates + static
│   ├── pipeline.py         # оркестратор стадий
│   └── main.py             # CLI и запуск сервера
├── docs/
├── results/                # локальная SQLite БД
├── scripts/                # db-скрипты (инициализация/миграция)
└── zakupki/                # временные файлы загрузки
```

## Конфигурация (`src/.env`)
Ключевые переменные:
- `DATABASE_URL` — PostgreSQL URL, например `postgresql://user:pass@host:5432/eisparser`.
- `DATABASE_PATH` — путь к SQLite (fallback для локальной разработки).
- `ADMIN_PASSWORD`
- `CEREBRAS_API_KEY`
- `CEREBRAS_BASE_URL`
- `CEREBRAS_MODEL`
- `COORDINATES_CSV_PATH`
- `AI_STAGE2_DELAY_S`
- `STAGE4_HEADLESS`
- `STAGE4_USE_REAL_CHROME`
- `WORKER_ENABLE_STAGE4` (`true` по умолчанию; `false` = worker без Stage 4)
- `PROXY_URL` (опционально)

Логика выбора БД:
1. Если задан `DATABASE_URL` -> PostgreSQL.
2. Если `DATABASE_URL` пуст -> SQLite через `DATABASE_PATH`.

## Как поднять PostgreSQL
Пример через Docker:
```powershell
docker run --name eisparser-postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_USER=eis -e POSTGRES_DB=eisparser -p 5432:5432 -d postgres:16
```

Пример `DATABASE_URL`:
```text
postgresql://eis:postgres@127.0.0.1:5432/eisparser
```

## Инициализация схемы PostgreSQL
```powershell
python scripts\init_postgres.py --database-url "postgresql://eis:postgres@127.0.0.1:5432/eisparser"
```

Используется SQL-схема: `scripts/postgres_schema.sql`.

## Миграция данных из SQLite -> PostgreSQL
Источник по умолчанию: `results/eis_data.db`.

```powershell
python scripts\migrate_sqlite_to_postgres.py --sqlite-path results\eis_data.db --database-url "postgresql://eis:postgres@127.0.0.1:5432/eisparser"
```

Полезная опция:
```powershell
python scripts\migrate_sqlite_to_postgres.py --sqlite-path results\eis_data.db --database-url "postgresql://eis:postgres@127.0.0.1:5432/eisparser" --reset
```

Переносятся таблицы:
- `zakupki`
- `ai_results`
- `listings`
- `decisions`
- `user_overrides`
- `user_selections`
- `users`

## Раздельный запуск процессов (одна общая PostgreSQL)
### Сервер (фоновый автопроцесс)
На сервере NetAngels задайте тот же `DATABASE_URL`, выставьте `WORKER_ENABLE_STAGE4=false` и запускайте worker:
```powershell
python src\main.py worker --interval 300 --limit 10 --top-n 10
```

### ПК владельца (админка)
На ПК задайте тот же `DATABASE_URL` и запускайте UI:
```powershell
python src\main.py server --host 127.0.0.1 --port 8000
```

Оба процесса работают с одной БД: изменения видны сразу с обеих сторон.
Stage 4 запускается на ПК оператора вручную/по локальному расписанию.

## Фоновый worker Stage 1-4
Production-режим:
```powershell
python src\main.py worker --interval 300 --limit 10 --top-n 10
```

Режим хостинга (только Stage 1-3):
```text
WORKER_ENABLE_STAGE4=false
```

Что делает worker в цикле:
1. Stage 1 (по `--limit`)
2. Stage 2 для закупок, ожидающих AI (`raw`/`ai_error`), без зависимости от `decisions`
3. Stage 3 для закупок со статусом `ai_ready`
4. Stage 4 для закупок со статусом `url_ready` (по `--top-n`, если `WORKER_ENABLE_STAGE4=true`)
5. Сон `--interval` секунд

Защита от двойного запуска:
- PostgreSQL advisory lock (второй воркер завершается сразу с warning в логе).

Поведение Stage 1:
- При недоступности страницы 1 ЕИС после всех ретраев Stage 1 завершается сразу с ошибкой и без перехода к страницам 2+.
- Лимит Stage 1 (`--limit`) считается только по новым сохраненным закупкам (`saved_new`), а существующие учитываются отдельно как `skipped_existing`.
- Поля `bid_end_date` и `initial_price` заполняются при сохранении закупки; если в карточке ЕИС пусто, выполняется извлечение из `combined_text`.

Логи:
- `results/logs/worker.log` + ротация файлов.

systemd unit:
- `deploy/systemd/eisparser-worker.service`
- пошаговый деплой: `docs/WORKER_VDS.md`

## Локальный fallback на SQLite
Если `DATABASE_URL` не задан, проект продолжает работать на SQLite без изменений запуска.

## Полезные команды
```powershell
python src\main.py stats
python src\main.py stage1 --limit 10
python src\main.py stage2 --limit 5
python src\main.py stage3 --limit 5
python src\main.py stage4 --top-n 5 --limit 2 --details
```

# Документация проекта EIS Parser (актуальная)

## Основные документы
- `docs/PROJECT.md` — архитектура, запуск, PostgreSQL/SQLite, миграция данных.
- `docs/INTERN_TASKS.md` — актуальное техническое задание.
- `docs/WORKER_VDS.md` — запуск фонового воркера Stage 1-4 и systemd на VDS.

## Режимы БД
1. `DATABASE_URL` задан: используется PostgreSQL (рабочий сетевой режим).
2. `DATABASE_URL` не задан: используется SQLite через `DATABASE_PATH` (локальная разработка).

## Быстрый старт PostgreSQL
1. Заполните `DATABASE_URL` в `src/.env`.
2. Инициализируйте схему:
```powershell
python scripts\init_postgres.py --database-url "postgresql://user:pass@host:5432/eisparser"
```
3. (Опционально) Перенесите данные из SQLite:
```powershell
python scripts\migrate_sqlite_to_postgres.py --sqlite-path results\eis_data.db --database-url "postgresql://user:pass@host:5432/eisparser"
```
4. Запускайте процессы как обычно (`src/main.py`), оба будут работать с одной PostgreSQL.

## Раздельный запуск (сервер + ПК)
- На сервере (NetAngels): worker Stage 1-3 с тем же `DATABASE_URL` и `WORKER_ENABLE_STAGE4=false`.
- На ПК владельца: админка (`python src\main.py server`) с тем же `DATABASE_URL`.
- На ПК оператора: Stage 4 запускается вручную или по локальному расписанию.
- Изменения видны обоим процессам сразу, так как БД общая.

## Фоновый воркер (production)
Запуск:
```powershell
python src\main.py worker --interval 300 --limit 10 --top-n 10
```

Для хостинга (только Stage 1-3):
```powershell
# в src/.env
WORKER_ENABLE_STAGE4=false
```

Лог:
- `results/logs/worker.log` (с ротацией).

## Важное поведение Stage 1
- Если страница 1 ЕИС недоступна после ретраев, Stage 1 завершается сразу с ошибкой.
- Переход к страницам 2+ в этом цикле не выполняется.
- Лимит `--limit` расходуется только на новые сохраненные закупки (`saved_new`), а существующие считаются отдельно (`skipped_existing`).
- При сохранении закупки Stage 1 заполняет `bid_end_date` и `initial_price` из карточки ЕИС, а при отсутствии пытается извлечь из текста документов.

## Критерий Stage 2
- Stage 2 берет закупки из `zakupki` со статусами `raw` и `ai_error` (retry).
- Таблица `decisions` не используется как входной фильтр для Stage 2.

## Архив
- Исторические материалы вынесены в `docs/archive/` и не считаются источником актуальных требований.

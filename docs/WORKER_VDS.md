# Worker на VDS (Stage 1-4)

## Режим запуска
```bash
PYTHONPATH=/opt/eisparser/src /opt/eisparser/.venv/bin/python /opt/eisparser/src/main.py worker --interval 300 --limit 10 --top-n 10
PYTHONPATH=/opt/eisparser/src /opt/eisparser/.venv/bin/python /opt/eisparser/src/main.py worker-ingest --interval 300 --limit 10
PYTHONPATH=/opt/eisparser/src /opt/eisparser/.venv/bin/python /opt/eisparser/src/main.py worker-listing --interval 300 --limit 10 --top-n 10
```

## Ключевые переменные env
- `WORKER_ENABLE_STAGE4`
- `STAGE1_MAX_PAGES`
- `AI_STAGE2_DELAY_S`
- `PROXY_URL` (если используется)
- `EIS_RETRY_COUNT`
- `EIS_RETRY_BACKOFF_S`
- `EIS_REQUEST_TIMEOUT_S`
- `CEREBRAS_MODEL`
- `DATABASE_URL`
- `USER_ACCESS_MODE`

## Systemd (текущий прод)
Файлы юнитов в репозитории:
- `deploy/systemd/eisparser-worker-ingest.service`
- `deploy/systemd/eisparser-worker-listing.service`
- `deploy/systemd/eisparser-worker.service` (legacy)

Проверка:
```bash
systemctl status eisparser-worker-ingest --no-pager
systemctl status eisparser-worker-listing --no-pager
```

## Логи
```bash
tail -n 200 /opt/eisparser/results/logs/worker.log
tail -f /opt/eisparser/results/logs/worker.log
```

Если `journalctl` пустой, это нормально, если логирование настроено в файл.

## Диагностика очередей
```bash
cd /opt/eisparser
. .venv/bin/activate
export PYTHONPATH=/opt/eisparser/src
python - <<'PY'
from services.database_service import DatabaseService
db = DatabaseService()
print(db.zakupki.get_status_counts())
PY
```

## Единый формат диагностики этапов
Строки прогресса пишутся в формате:
`stage_progress reg_number=<id> stage=<2|4> result=<ok|error|skip> reason=<reason>`

Примеры выборок:
```bash
# последние записи по конкретной закупке
grep "stage_progress reg_number=32000000001" /opt/eisparser/results/logs/worker.log | tail -n 30

# ошибки по Stage 2/4
grep "stage_progress" /opt/eisparser/results/logs/worker.log | grep "result=error" | tail -n 50
```

## Быстрые команды диагностики
```bash
# 1) очереди по статусам
python - <<'PY'
from services.database_service import DatabaseService
db = DatabaseService()
print(db.zakupki.get_status_counts())
PY

# 2) зависшие записи (stage4_error + ai_error)
python - <<'PY'
from services.database_service import DatabaseService
db = DatabaseService()
print("stage4_error:", len(db.zakupki.get_by_status("stage4_error")))
print("ai_error:", len(db.zakupki.get_by_status("ai_error")))
PY

# 2b) долго в одном статусе (пример: старше 6 часов)
python - <<'PY'
from datetime import datetime, timedelta
from services.database_service import DatabaseService

db = DatabaseService()
threshold = datetime.now() - timedelta(hours=6)
statuses = ["raw", "ai_ready", "url_ready", "ai_error", "stage4_error"]

for status in statuses:
    stuck = 0
    for z in db.zakupki.get_by_status(status):
        ts = z.processed_at or z.prepared_at
        if ts and ts < threshold:
            stuck += 1
    print(f"{status}: stuck>{6}h = {stuck}")
PY

# 3) длительность этапов по логам (грубая оценка по таймстампам)
grep "stage_progress" /opt/eisparser/results/logs/worker.log | tail -n 200
```

## Retry-логика
- Stage 2 повторно берет `ai_error`.
- Stage 4 повторно берет `stage4_error`.

## Ежедневный Stage 1 чек-лист
1. Проверить сервисы:
```bash
systemctl status eisparser-api --no-pager
systemctl status eisparser-worker-ingest --no-pager
systemctl status eisparser-worker-listing --no-pager
```
2. Проверить последние циклы ingest:
```bash
tail -n 300 /opt/eisparser/results/logs/worker.log | grep -E "Cron iteration start|Cycle [0-9]+ started|Stage 1 started|Stage 1 finished"
```
3. Убедиться, что нет crash-loop (повторяющиеся фатальные ошибки без успешных циклов):
```bash
tail -n 300 /opt/eisparser/results/logs/worker.log | grep -E "Traceback|Unexpected cycle error|Failed to acquire advisory lock"
```
4. Проверить env деградации в `/opt/eisparser/src/.env`:
- `PROXY_URL` (если нужен прокси)
- `EIS_RETRY_COUNT`
- `EIS_RETRY_BACKOFF_S`
- `EIS_REQUEST_TIMEOUT_S`

## Быстрая реакция при недоступности ЕИС
1. Симптомы:
- регулярные ошибки Stage 1 с `timeout/http_5xx/network_error`;
- Stage 1 завершается без новых загрузок несколько циклов подряд.
2. Действия:
```bash
grep -E "search_page|print_form|documents_list|document_download|Stage 1" /opt/eisparser/results/logs/worker.log | tail -n 120
```
3. При необходимости временно усилить деградационный профиль:
- увеличить `EIS_RETRY_COUNT` (например, `5`);
- увеличить `EIS_RETRY_BACKOFF_S` (например, `3.0`);
- проверить/включить `PROXY_URL`.
4. После изменения env:
```bash
systemctl restart eisparser-worker-ingest
systemctl status eisparser-worker-ingest --no-pager
tail -n 120 /opt/eisparser/results/logs/worker.log
```

## Рекомендуемые параметры на текущем тарифе
- `worker-ingest`: `--limit 5..10`, `AI_STAGE2_DELAY_S=4..6`
- `worker-listing`: `--limit 5..10`, `--top-n 10`

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
- `CEREBRAS_MODEL`
- `DATABASE_URL`

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

## Retry-логика
- Stage 2 повторно берет `ai_error`.
- Stage 4 повторно берет `stage4_error`.

## Рекомендуемые параметры на текущем тарифе
- `worker-ingest`: `--limit 5..10`, `AI_STAGE2_DELAY_S=4..6`
- `worker-listing`: `--limit 5..10`, `--top-n 10`

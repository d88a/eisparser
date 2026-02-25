# Worker на VDS (Stage 1-4)

## Режим запуска
```bash
python src/main.py worker --interval 300 --limit 10 --top-n 10
```

Параметры:
- `--interval` - интервал между циклами в секундах (default `300`).
- `--limit` - лимит закупок на цикл для Stage 1/3/4.
- `--top-n` - количество объявлений на закупку в Stage 4.
- `--details` - (опционально) сбор расширенных характеристик.

## Ключевые переменные env
- `WORKER_ENABLE_STAGE4` (`false` на хостинге, если Stage 4 запускается не там).
- `STAGE1_MAX_PAGES` (default `10`).
- `AI_STAGE2_DELAY_S` (пауза между запросами в Stage 2).
- `CEREBRAS_MODEL` (модель Stage 2).

## Логи воркера
- файл: `results/logs/worker.log`;
- для cron: `/home/c77461/priv-mag.ru/app/src/results/logs/cron_worker.log`;
- есть явный маркер cron-итерации:
  - `Cron iteration start: ts=... pid=... cycle=...`.

## Защита от двойного запуска
Воркер использует PostgreSQL advisory lock (`704127301905221`).
Если lock занят, второй процесс завершается с кодом `75`.

## Что важно по поведению
- `worker --max-cycles 1` должен завершаться после одного цикла - это норма для cron.
- Stage 2 запускается при наличии pending (`raw`, `ai_error`).
- Сообщение `Worker stopped` в cron-режиме не означает поломку.

## Диагностика cron
```bash
crontab -l
tail -n 200 /home/c77461/priv-mag.ru/app/src/results/logs/cron_worker.log
```

## systemd (для отдельного VDS)
Файл unit: `deploy/systemd/eisparser-worker.service`

Установка:
```bash
cd /opt/eisparser
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
sudo cp deploy/systemd/eisparser-worker.service /etc/systemd/system/eisparser-worker.service
sudo systemctl daemon-reload
sudo systemctl enable eisparser-worker
sudo systemctl start eisparser-worker
```

Проверка:
```bash
sudo systemctl status eisparser-worker
journalctl -u eisparser-worker -f
```

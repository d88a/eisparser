# Worker на VDS (Stage 1-4)

## Режим запуска
```bash
python src/main.py worker --interval 300 --limit 10 --top-n 10
```

Параметры:
- `--interval` интервал между циклами в секундах (по умолчанию `300`).
- `--limit` лимит закупок на цикл для этапов Stage 1/3/4.
- `--top-n` количество объявлений на закупку в Stage 4.
- `--details` (опционально) сбор расширенных характеристик.

## Логи воркера
- Файл: `results/logs/worker.log`
- Ротация: 5 файлов по 5 MB (`worker.log`, `worker.log.1` ...)
- В логах есть: старт/стоп, этапы, счётчики, ошибки и traceback для необработанных исключений.

## Защита от двойного запуска
При старте воркер берёт PostgreSQL advisory lock (`704127301905221`).
Если lock уже занят, второй процесс завершится сразу с кодом `75` и запишет предупреждение в лог.
В `systemd` этот код исключён из автоперезапуска (`RestartPreventExitStatus=75`), поэтому restart-loop не возникает.

## systemd unit
Файл в репозитории: `deploy/systemd/eisparser-worker.service`

### Установка на сервере
1. Скопировать проект в `/opt/eisparser`.
2. Заполнить `/opt/eisparser/src/.env` (обязательно `DATABASE_URL`, `CEREBRAS_API_KEY`, `ADMIN_PASSWORD`).
3. Создать виртуальное окружение и установить зависимости:
```bash
cd /opt/eisparser
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```
4. Установить unit:
```bash
sudo cp deploy/systemd/eisparser-worker.service /etc/systemd/system/eisparser-worker.service
sudo systemctl daemon-reload
sudo systemctl enable eisparser-worker
sudo systemctl start eisparser-worker
```

### Управление сервисом
```bash
sudo systemctl status eisparser-worker
sudo systemctl restart eisparser-worker
sudo systemctl stop eisparser-worker
sudo systemctl start eisparser-worker
```

### Проверка логов
```bash
journalctl -u eisparser-worker -f
# и/или
cd /opt/eisparser
tail -f results/logs/worker.log
```

## Пример логов (2 цикла)
```text
2026-02-20 09:18:12 | INFO     | eisparser.worker | Worker started: interval=5s limit=1 top_n=1 details=False
2026-02-20 09:18:12 | INFO     | eisparser.worker | Cycle 1 started
2026-02-20 09:18:20 | INFO     | eisparser.worker | Stage 1 finished: success=True message=Загружено 1 новых закупок (пропущено 0 существующих)
2026-02-20 09:18:23 | INFO     | eisparser.worker | Stage 2 finished: success=True message=обработано 1
2026-02-20 09:18:24 | INFO     | eisparser.worker | Stage 3 finished: success=True message=Сформировано 1 ссылок из 1
2026-02-20 09:19:09 | INFO     | eisparser.worker | Stage 4 finished: processed=1 total_listings=1 errors=0
2026-02-20 09:19:09 | INFO     | eisparser.worker | Cycle 1 finished in 56.78 sec
2026-02-20 09:19:14 | INFO     | eisparser.worker | Cycle 2 started
2026-02-20 09:19:16 | INFO     | eisparser.worker | Stage 1 finished: success=True message=Загружено 0 новых закупок (пропущено 1 существующих)
2026-02-20 09:19:16 | INFO     | eisparser.worker | Stage 2 skipped: no new purchases in this cycle
2026-02-20 09:19:17 | INFO     | eisparser.worker | Stage 3 finished: success=False message=Сформировано 0 ссылок из 1
2026-02-20 09:19:59 | INFO     | eisparser.worker | Stage 4 finished: processed=1 total_listings=1 errors=0
2026-02-20 09:19:59 | INFO     | eisparser.worker | Cycle 2 finished in 44.41 sec
2026-02-20 09:19:59 | INFO     | eisparser.worker | Worker stopped
```

## Проверочный сценарий
1. Запустить один воркер и убедиться, что идёт цикл Stage 1 -> Stage 4.
2. Запустить второй воркер: он должен завершиться с сообщением `Worker is already running ... Exiting.`
3. Проверить появление новых данных в `zakupki`, `ai_results`, `listings`.

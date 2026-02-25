# Перенос и запуск проекта (NetAngels + локально)

## 1) Безопасный деплой на NetAngels

Критично:
- не перезаписывать `/home/c77461/priv-mag.ru/app/asgi.py`;
- не перезаписывать `/home/c77461/priv-mag.ru/app/src/.env`.

### Локально перед деплоем
```powershell
cd D:\Anna\eisparser
git status
```

### Копировать только измененный код
```powershell
scp src\pipeline.py c77461@priv-mag.ru:/home/c77461/priv-mag.ru/app/src/pipeline.py
scp src\api\routes.py c77461@priv-mag.ru:/home/c77461/priv-mag.ru/app/src/api/routes.py
scp src\services\database_service.py c77461@priv-mag.ru:/home/c77461/priv-mag.ru/app/src/services/database_service.py
scp src\services\worker_service.py c77461@priv-mag.ru:/home/c77461/priv-mag.ru/app/src/services/worker_service.py
scp src\services\ai_processor_service.py c77461@priv-mag.ru:/home/c77461/priv-mag.ru/app/src/services/ai_processor_service.py
scp src\web\static\js\stage2.js c77461@priv-mag.ru:/home/c77461/priv-mag.ru/app/src/web/static/js/stage2.js
```

### На сервере
```bash
cd /home/c77461/priv-mag.ru/app
/home/c77461/priv-mag.ru/.env/bin/pip install -r requirements.txt
```

### В панели NetAngels
- `Python ASGI` -> `Перезапустить Python ASGI`.
- Проверить: `APP_PATH=/home/c77461/priv-mag.ru/app/asgi.py`.

## 2) Smoke-check после деплоя

Важно: внутренний API проверять с `Host`, иначе возможен ложный `404`.

```bash
curl -i --max-time 10 -H "Host: priv-mag.ru" "http://$APP_IP:$APP_PORT/api/admin/zakupki_all?offset=0&limit=1"
```

Ожидается:
- `401` без админ-куки (это нормально), либо
- `200` с валидной сессией.

Не должно быть `404`.

Проверка backend БД:
```bash
PYTHONPATH=/home/c77461/priv-mag.ru/app/src /home/c77461/priv-mag.ru/.env/bin/python - <<'PY'
from services.database_service import DatabaseService
db = DatabaseService()
print("repo_is_postgres =", db.zakupki.is_postgres)
print("zakupki_count =", len(db.zakupki.get_all()))
PY
```

Ожидается `repo_is_postgres = True`.

### Индексы для ускорения Stage 2 (выполнить один раз в Adminer)
```sql
CREATE INDEX IF NOT EXISTS idx_zakupki_status ON zakupki(status);
CREATE INDEX IF NOT EXISTS idx_ai_results_reg_number ON ai_results(reg_number);
CREATE INDEX IF NOT EXISTS idx_zakupki_processed_at ON zakupki(processed_at);
```

## 3) Фон на хостинге (cron)

Разовый запуск:
```bash
cd /home/c77461/priv-mag.ru/app
/home/c77461/priv-mag.ru/.env/bin/python src/main.py worker --max-cycles 1
```

Cron (каждые 5 минут):
```cron
*/5 * * * * cd /home/c77461/priv-mag.ru/app && /home/c77461/priv-mag.ru/.env/bin/python src/main.py worker --max-cycles 1 >> /home/c77461/priv-mag.ru/app/src/results/logs/cron_worker.log 2>&1
```

Логи:
```bash
tail -f /home/c77461/priv-mag.ru/app/src/results/logs/cron_worker.log
```

Проверка, что cron реально запускает итерации:
```bash
crontab -l
tail -n 200 /home/c77461/priv-mag.ru/app/src/results/logs/cron_worker.log
```
Ожидаемо в логе:
- `Cron iteration start: ...`
- `Worker stopped` после `--max-cycles 1` (норма для cron-режима).

## 4) Локальный запуск с туннелем

См. отдельный документ: `docs/LOCAL_TUNNEL_RUN.md`.

## 5) Если что-то сломалось
1. Проверить `APP_PATH` в панели.
2. Проверить, что `src/.env` на сервере существует и содержит `DATABASE_URL`.
3. Повторить внутренний curl с `Host`.
4. Откатить только измененные `.py`/`.js` файлы из backup.

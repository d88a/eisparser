# Подключение к VDS и рабочий регламент команды

Дата: 2026-03-06  
Сервер проекта EIS Parser: `213.189.219.55`  
Рабочий каталог проекта: `/opt/eisparser`

## 1) Быстрое подключение (Windows PowerShell)

### 1.1. Одноразовая проверка ключа
```powershell
ssh -i $env:USERPROFILE\.ssh\id_ed25519_eisparser root@213.189.219.55 "echo KEY_OK"
```

Ожидаемый ответ: `KEY_OK`.

### 1.2. Постоянный alias `eis-vds`
Создать/обновить файл `C:\Users\<USER>\.ssh\config`:
```sshconfig
Host eis-vds
  HostName 213.189.219.55
  User root
  IdentityFile ~/.ssh/id_ed25519_eisparser
  IdentitiesOnly yes
```

Проверка:
```powershell
ssh -G eis-vds | Select-String "hostname|user|identityfile"
ssh eis-vds "echo CONNECTED"
```

## 2) Базовые правила работы на сервере

1. Не редактировать `.env` без фиксации изменений в задаче/отчёте.
2. Не запускать разрушительные команды (`rm -rf`, `DROP`, `TRUNCATE`) без бэкапа.
3. Работать с проектом только в `/opt/eisparser`.
4. После любого обновления кода делать `compileall` и перезапуск нужных сервисов.
5. Любое изменение systemd/nginx фиксировать в документации.

## 3) Ежедневный рабочий цикл (чеклист)

### 3.1. Подключиться
```bash
ssh eis-vds
cd /opt/eisparser
```

### 3.2. Проверить состояние сервисов
```bash
systemctl status eisparser-api --no-pager
systemctl status eisparser-worker-ingest --no-pager
systemctl status eisparser-worker-listing --no-pager
```

### 3.3. Быстрая проверка API и логов
```bash
curl -sS http://127.0.0.1:8000/ >/dev/null && echo "API OK"
tail -n 80 /opt/eisparser/results/logs/api.log
tail -n 120 /opt/eisparser/results/logs/worker.log
```

## 4) Как вносить изменения в код

### 4.1. На локальном ПК
1. Изменить файлы.
2. Проверить локально:
```powershell
python -m compileall -q src
pytest -q
```

### 4.2. Загрузка на сервер
Пример (из корня проекта):
```powershell
scp src\api\app.py eis-vds:/opt/eisparser/src/api/app.py
scp -r src\api\routes eis-vds:/opt/eisparser/src/api/
```

### 4.3. Применение на сервере
```bash
ssh eis-vds
cd /opt/eisparser
find /opt/eisparser/src -type d -name "__pycache__" -exec rm -rf {} +
python -m compileall -q /opt/eisparser/src
systemctl restart eisparser-api
systemctl restart eisparser-worker-ingest
systemctl restart eisparser-worker-listing
systemctl status eisparser-api --no-pager
tail -n 80 /opt/eisparser/results/logs/api.log
```

## 5) Работа с окружением и БД

### 5.1. Проверка, что подключён PostgreSQL
```bash
cd /opt/eisparser
. .venv/bin/activate
export PYTHONPATH=/opt/eisparser/src
python - <<'PY'
from config.settings import settings
from services.database_service import DatabaseService
db = DatabaseService()
print("DATABASE_URL =", repr(settings.database_url))
print("BACKEND =", "PostgreSQL" if db.database_url else "SQLite")
PY
```

### 5.2. Быстрая проверка количества записей
```bash
sudo -u postgres psql -d eisparser_db -c "select count(*) from zakupki;"
sudo -u postgres psql -d eisparser_db -c "select count(*) from ai_results;"
```

## 6) Частые проблемы и быстрые действия

### 6.1. `502 Bad Gateway`
1. Проверить API:
```bash
systemctl status eisparser-api --no-pager
ss -ltnp | grep ':8000' || echo "8000 не слушается"
tail -n 120 /opt/eisparser/results/logs/api.log
```
2. Перезапустить API:
```bash
systemctl restart eisparser-api
```

### 6.2. API запустился, но нет данных в UI
1. Проверить, что backend = PostgreSQL (блок 5.1).
2. Проверить ошибки в `api.log` (обычно отсутствует метод/файл после неполного деплоя).
3. Дозалить отсутствующие файлы и снова перезапустить сервис.

### 6.3. Stage 2 массово даёт `ai_error`
1. Проверить `worker.log` на `429` и `token_quota_exceeded`.
2. Не увеличивать нагрузку; уменьшать `--limit` и/или увеличивать `AI_STAGE2_DELAY_S`.
3. Проверить лимиты модели/провайдера.

## 7) Минимальный стандарт отчёта после работ

После каждого изменения фиксировать:
1. Что изменено (файлы/сервисы).
2. Какие команды выполнены.
3. Результат проверок (`status`, `compileall`, ключевые строки логов).
4. Риски и что делать при откате.

## 8) Команды отката (быстрый шаблон)

```bash
cp /opt/eisparser/src/<file>.bak_YYYYMMDD /opt/eisparser/src/<file>
find /opt/eisparser/src -type d -name "__pycache__" -exec rm -rf {} +
python -m compileall -q /opt/eisparser/src
systemctl restart eisparser-api
tail -n 80 /opt/eisparser/results/logs/api.log
```

---

Если меняются IP, пользователь, ключи, пути или названия сервисов, сначала обновляется этот файл, затем выполняются работы.

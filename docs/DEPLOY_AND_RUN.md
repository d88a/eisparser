# Перенос и запуск проекта на VDS

## Прод-окружение
- Сервер: `213.189.219.55`
- Каталог проекта: `/opt/eisparser`
- Пользователь приложения: `eisparser`
- Systemd сервисы:
  - `eisparser-api`
  - `eisparser-worker-ingest`
  - `eisparser-worker-listing`

## 1) Деплой кода на сервер

### Вариант A: копирование архива
На ПК:
```powershell
cd D:\Anna\eisparser
tar -czf deploy_vds.tar.gz src deploy requirements.txt pytest.ini
scp deploy_vds.tar.gz root@213.189.219.55:/opt/eisparser/
```

На сервере:
```bash
cd /opt/eisparser
tar -xzf deploy_vds.tar.gz
chown -R eisparser:eisparser /opt/eisparser
```

### Вариант B: точечное копирование файлов
```powershell
scp D:\Anna\eisparser\src\api\app.py root@213.189.219.55:/opt/eisparser/src/api/app.py
scp D:\Anna\eisparser\src\repositories\zakupka_repo.py root@213.189.219.55:/opt/eisparser/src/repositories/zakupka_repo.py
scp -r D:\Anna\eisparser\src\api\routes root@213.189.219.55:/opt/eisparser/src/api/
```

## 2) Проверка окружения
```bash
cd /opt/eisparser
. .venv/bin/activate
export PYTHONPATH=/opt/eisparser/src
python -m compileall -q /opt/eisparser/src
```

## 3) Проверка подключения БД
```bash
cd /opt/eisparser
. .venv/bin/activate
export PYTHONPATH=/opt/eisparser/src
python - <<'PY'
from config.settings import settings
from services.database_service import DatabaseService
db = DatabaseService()
print("DATABASE_URL =", repr(settings.database_url))
print("DATABASE_PATH =", settings.database_path)
print("BACKEND =", "PostgreSQL" if db.database_url else "SQLite")
PY

sudo -u postgres psql -d eisparser_db -c "select count(*) as zakupki from zakupki;"
sudo -u postgres psql -d eisparser_db -c "select count(*) as ai_results from ai_results;"
```

## 4) Перезапуск сервисов
```bash
systemctl daemon-reload
systemctl restart eisparser-api
systemctl restart eisparser-worker-ingest
systemctl restart eisparser-worker-listing

systemctl status eisparser-api --no-pager
systemctl status eisparser-worker-ingest --no-pager
systemctl status eisparser-worker-listing --no-pager
```

## 5) Smoke-check API
```bash
curl -i --max-time 10 http://127.0.0.1:8000/
curl -i --max-time 10 http://127.0.0.1:8000/api/admin/zakupki_all?offset=0\&limit=1
```

## 6) Логи
```bash
tail -n 120 /opt/eisparser/results/logs/api.log
tail -n 200 /opt/eisparser/results/logs/worker.log
```

## 7) Обязательные security-настройки
В `/opt/eisparser/src/.env`:
```env
ADMIN_PASSWORD=<сложный_пароль>
ADMIN_TOKEN_SECRET=<длинный_случайный_секрет>
# для strict-режима:
# ADMIN_SECURITY_FAIL_FAST=true
```

## 8) Типовой сбой после частичного деплоя
Симптом: `500` на `/api/admin/zakupki_all` и ошибка
`AttributeError: 'ZakupkaRepository' object has no attribute 'get_admin_all_page'`.

Причина: на сервер попал новый `admin.py`, но старый `zakupka_repo.py`.

Исправление:
```powershell
scp D:\Anna\eisparser\src\repositories\zakupka_repo.py root@213.189.219.55:/opt/eisparser/src/repositories/zakupka_repo.py
```
```bash
systemctl restart eisparser-api
```

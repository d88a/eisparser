# EIS Parser - документация (актуально)

## Карта документов
- `docs/PROJECT.md` - архитектура и бизнес-логика этапов.
- `docs/DEPLOY_AND_RUN.md` - безопасный деплой на NetAngels и локальный запуск.
- `docs/WORKER_VDS.md` - воркер, cron/systemd, логи и диагностика.
- `docs/LOCAL_TUNNEL_RUN.md` - SSH-туннель к PostgreSQL и запуск админки на ПК.
- `docs/INTERN_TASKS.md` - актуальный backlog задач для стажера.

## Ключевые правила эксплуатации
1. На проде не перезаписывать:
- `/home/c77461/priv-mag.ru/app/asgi.py`
- `/home/c77461/priv-mag.ru/app/src/.env`

2. Режим БД:
- если `DATABASE_URL` задан, используется PostgreSQL;
- если `DATABASE_URL` пуст, fallback на SQLite через `DATABASE_PATH`.

3. Stage 2:
- pending-очередь формируется по статусам `raw` и `ai_error`;
- `decisions` не является обязательным фильтром для Stage 2.

4. Stage 1:
- максимум страниц задается `STAGE1_MAX_PAGES` (default `10`);
- при недоступности страницы 1 Stage 1 прерывается без сканирования следующих страниц.

## Быстрые smoke-check команды (после деплоя)
```bash
curl -i --max-time 10 -H "Host: priv-mag.ru" "http://$APP_IP:$APP_PORT/api/admin/zakupki_all?offset=0&limit=1"
PYTHONPATH=/home/c77461/priv-mag.ru/app/src /home/c77461/priv-mag.ru/.env/bin/python - <<'PY'
from services.database_service import DatabaseService
db = DatabaseService()
print("repo_is_postgres =", db.zakupki.is_postgres)
print("zakupki_count =", len(db.zakupki.get_all()))
PY
```

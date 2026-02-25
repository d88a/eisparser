# Задание стажеру: инцидент Stage 2 (AI) `latin-1` в Authorization

## Контекст
На проде при запуске Stage 2 массово падает AI-обработка с ошибкой:
- `'latin-1' codec can't encode characters in position 7-10`
- в логах: `Header latin-1 encode error: Authorization ...`
- закупки переходят в `ai_error`, `processed=0`.

## Что проверить (обязательно, в таком порядке)
1. Проверить фактический ключ в runtime, а не в локальном `.env`:
```bash
cd /home/c77461/priv-mag.ru/app
PYTHONPATH=/home/c77461/priv-mag.ru/app/src /home/c77461/priv-mag.ru/.env/bin/python - <<'PY'
import os
k = os.getenv("CEREBRAS_API_KEY", "")
print("len=", len(k))
print("repr=", repr(k))
print("latin1_ok=", all(ord(ch) < 256 for ch in k))
print("ords_head=", [ord(ch) for ch in k[:16]])
PY
```

2. Проверить, откуда берется значение (панель env vs `src/.env`):
```bash
grep -n "CEREBRAS_API_KEY" /home/c77461/priv-mag.ru/app/src/.env
```

3. Проверить модель и базовый URL в runtime:
```bash
PYTHONPATH=/home/c77461/priv-mag.ru/app/src /home/c77461/priv-mag.ru/.env/bin/python - <<'PY'
from config.settings import settings
print("CEREBRAS_MODEL=", repr(settings.cerebras_model))
print("CEREBRAS_BASE_URL=", repr(settings.cerebras_base_url))
PY
```

## Что исправить в коде
1. В `src/services/ai_processor_service.py` добавить fail-fast в `_call_cerebras`:
- перед `requests.post` валидировать `Authorization` и proxy на latin-1;
- если невалидно, писать понятный лог с категорией `auth_or_header_encoding`;
- возвращать `None` без лишних ретраев.

2. Добавить безопасную нормализацию ключа:
- `strip()` для API ключа;
- удалить обрамляющие кавычки, если есть (`"..."`/`'...'`);
- не логировать ключ целиком.

3. Добавить диагностику источника конфигурации:
- в startup-логах: длина ключа (`key_len`) и флаг `latin1_ok` (без печати самого ключа);
- логировать, что используется `settings.cerebras_*`.

## Что проверить после фикса
1. Ручной запрос к Cerebras:
```bash
curl --max-time 40 https://api.cerebras.ai/v1/chat/completions \
  -H "Authorization: Bearer $CEREBRAS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"llama3.1-8b","messages":[{"role":"user","content":"ping"}],"max_tokens":5}'
```

2. Прогон одного цикла:
```bash
cd /home/c77461/priv-mag.ru/app
/home/c77461/priv-mag.ru/.env/bin/python src/main.py worker --max-cycles 1 --limit 10
tail -n 200 /home/c77461/priv-mag.ru/app/src/results/logs/cron_worker.log
```

Ожидается:
- нет ошибок `latin-1` для Authorization;
- есть `Cerebras status: 200` минимум по части закупок;
- часть `raw/ai_error` переходит в `ai_ready`.

## Формат отчета
1. Причина инцидента (1 абзац).
2. Измененные файлы.
3. Команды проверки + вывод.
4. До/после по количеству `ai_error` и `ai_ready`.

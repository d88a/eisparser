# АРХИВНЫЙ ИНЦИДЕНТ (старый сервер)\r\n\r\nЭтот файл сохранен для истории и не используется как текущий runbook.\r\nАктуальные инструкции: docs/DEPLOY_AND_RUN.md, docs/VDS_CURRENT_SETUP.md.\r\n\r\n# Р—Р°РґР°РЅРёРµ СЃС‚Р°Р¶РµСЂСѓ: РёРЅС†РёРґРµРЅС‚ Stage 2 (AI) `latin-1` РІ Authorization

## РљРѕРЅС‚РµРєСЃС‚
РќР° РїСЂРѕРґРµ РїСЂРё Р·Р°РїСѓСЃРєРµ Stage 2 РјР°СЃСЃРѕРІРѕ РїР°РґР°РµС‚ AI-РѕР±СЂР°Р±РѕС‚РєР° СЃ РѕС€РёР±РєРѕР№:
- `'latin-1' codec can't encode characters in position 7-10`
- РІ Р»РѕРіР°С…: `Header latin-1 encode error: Authorization ...`
- Р·Р°РєСѓРїРєРё РїРµСЂРµС…РѕРґСЏС‚ РІ `ai_error`, `processed=0`.

## Р§С‚Рѕ РїСЂРѕРІРµСЂРёС‚СЊ (РѕР±СЏР·Р°С‚РµР»СЊРЅРѕ, РІ С‚Р°РєРѕРј РїРѕСЂСЏРґРєРµ)
1. РџСЂРѕРІРµСЂРёС‚СЊ С„Р°РєС‚РёС‡РµСЃРєРёР№ РєР»СЋС‡ РІ runtime, Р° РЅРµ РІ Р»РѕРєР°Р»СЊРЅРѕРј `.env`:
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

2. РџСЂРѕРІРµСЂРёС‚СЊ, РѕС‚РєСѓРґР° Р±РµСЂРµС‚СЃСЏ Р·РЅР°С‡РµРЅРёРµ (РїР°РЅРµР»СЊ env vs `src/.env`):
```bash
grep -n "CEREBRAS_API_KEY" /home/c77461/priv-mag.ru/app/src/.env
```

3. РџСЂРѕРІРµСЂРёС‚СЊ РјРѕРґРµР»СЊ Рё Р±Р°Р·РѕРІС‹Р№ URL РІ runtime:
```bash
PYTHONPATH=/home/c77461/priv-mag.ru/app/src /home/c77461/priv-mag.ru/.env/bin/python - <<'PY'
from config.settings import settings
print("CEREBRAS_MODEL=", repr(settings.cerebras_model))
print("CEREBRAS_BASE_URL=", repr(settings.cerebras_base_url))
PY
```

## Р§С‚Рѕ РёСЃРїСЂР°РІРёС‚СЊ РІ РєРѕРґРµ
1. Р’ `src/services/ai_processor_service.py` РґРѕР±Р°РІРёС‚СЊ fail-fast РІ `_call_cerebras`:
- РїРµСЂРµРґ `requests.post` РІР°Р»РёРґРёСЂРѕРІР°С‚СЊ `Authorization` Рё proxy РЅР° latin-1;
- РµСЃР»Рё РЅРµРІР°Р»РёРґРЅРѕ, РїРёСЃР°С‚СЊ РїРѕРЅСЏС‚РЅС‹Р№ Р»РѕРі СЃ РєР°С‚РµРіРѕСЂРёРµР№ `auth_or_header_encoding`;
- РІРѕР·РІСЂР°С‰Р°С‚СЊ `None` Р±РµР· Р»РёС€РЅРёС… СЂРµС‚СЂР°РµРІ.

2. Р”РѕР±Р°РІРёС‚СЊ Р±РµР·РѕРїР°СЃРЅСѓСЋ РЅРѕСЂРјР°Р»РёР·Р°С†РёСЋ РєР»СЋС‡Р°:
- `strip()` РґР»СЏ API РєР»СЋС‡Р°;
- СѓРґР°Р»РёС‚СЊ РѕР±СЂР°РјР»СЏСЋС‰РёРµ РєР°РІС‹С‡РєРё, РµСЃР»Рё РµСЃС‚СЊ (`"..."`/`'...'`);
- РЅРµ Р»РѕРіРёСЂРѕРІР°С‚СЊ РєР»СЋС‡ С†РµР»РёРєРѕРј.

3. Р”РѕР±Р°РІРёС‚СЊ РґРёР°РіРЅРѕСЃС‚РёРєСѓ РёСЃС‚РѕС‡РЅРёРєР° РєРѕРЅС„РёРіСѓСЂР°С†РёРё:
- РІ startup-Р»РѕРіР°С…: РґР»РёРЅР° РєР»СЋС‡Р° (`key_len`) Рё С„Р»Р°Рі `latin1_ok` (Р±РµР· РїРµС‡Р°С‚Рё СЃР°РјРѕРіРѕ РєР»СЋС‡Р°);
- Р»РѕРіРёСЂРѕРІР°С‚СЊ, С‡С‚Рѕ РёСЃРїРѕР»СЊР·СѓРµС‚СЃСЏ `settings.cerebras_*`.

## Р§С‚Рѕ РїСЂРѕРІРµСЂРёС‚СЊ РїРѕСЃР»Рµ С„РёРєСЃР°
1. Р СѓС‡РЅРѕР№ Р·Р°РїСЂРѕСЃ Рє Cerebras:
```bash
curl --max-time 40 https://api.cerebras.ai/v1/chat/completions \
  -H "Authorization: Bearer $CEREBRAS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"llama3.1-8b","messages":[{"role":"user","content":"ping"}],"max_tokens":5}'
```

2. РџСЂРѕРіРѕРЅ РѕРґРЅРѕРіРѕ С†РёРєР»Р°:
```bash
cd /home/c77461/priv-mag.ru/app
/home/c77461/priv-mag.ru/.env/bin/python src/main.py worker --max-cycles 1 --limit 10
tail -n 200 /home/c77461/priv-mag.ru/app/src/results/logs/cron_worker.log
```

РћР¶РёРґР°РµС‚СЃСЏ:
- РЅРµС‚ РѕС€РёР±РѕРє `latin-1` РґР»СЏ Authorization;
- РµСЃС‚СЊ `Cerebras status: 200` РјРёРЅРёРјСѓРј РїРѕ С‡Р°СЃС‚Рё Р·Р°РєСѓРїРѕРє;
- С‡Р°СЃС‚СЊ `raw/ai_error` РїРµСЂРµС…РѕРґРёС‚ РІ `ai_ready`.

## Р¤РѕСЂРјР°С‚ РѕС‚С‡РµС‚Р°
1. РџСЂРёС‡РёРЅР° РёРЅС†РёРґРµРЅС‚Р° (1 Р°Р±Р·Р°С†).
2. РР·РјРµРЅРµРЅРЅС‹Рµ С„Р°Р№Р»С‹.
3. РљРѕРјР°РЅРґС‹ РїСЂРѕРІРµСЂРєРё + РІС‹РІРѕРґ.
4. Р”Рѕ/РїРѕСЃР»Рµ РїРѕ РєРѕР»РёС‡РµСЃС‚РІСѓ `ai_error` Рё `ai_ready`.


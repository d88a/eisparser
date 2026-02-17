# EIS Parser — анализ госзакупок недвижимости

## Обзор
EIS Parser — пайплайн обработки госзакупок недвижимости из ЕИС:
1. Загрузка закупок и документов с ЕИС.
2. ИИ‑извлечение параметров объекта (город, площадь, комнаты и т.д.).
3. Генерация ссылки 2ГИС по параметрам.
4. Сбор рыночных объявлений (2ГИС/ДомКлик/Циан) для сравнения.

## Актуальная структура проекта

```
eisparser/
├── src/
│   ├── api/                # FastAPI (UI + API)
│   ├── config/             # Настройки и константы
│   ├── gis/                # Генерация URL 2ГИС
│   ├── models/             # Модели данных
│   ├── repositories/       # Репозитории SQLite
│   ├── services/           # Бизнес‑логика и сервисы
│   ├── utils/              # Логирование и утилиты
│   ├── web/                # Шаблоны и статические файлы UI
│   ├── main.py             # CLI (запуск стадий и сервера)
│   └── pipeline.py         # Оркестратор стадий
├── docs/                   # Документация
├── map/                    # Геоданные
├── results/                # SQLite БД
└── tests/                  # Тесты
```

## Как запустить сервер (UI)

### Вариант 1 — через CLI
```bash
python src/main.py server --host 127.0.0.1 --port 8000
```

### Вариант 2 — напрямую через uvicorn
```bash
uvicorn api.app:app --reload --host 127.0.0.1 --port 8000
```

UI будет доступен по адресу: `http://127.0.0.1:8000/`.

## CLI: запуск стадий пайплайна

### Stage 1 — загрузка закупок
```bash
python src/main.py stage1 --limit 10
```

### Stage 2 — ИИ‑обработка
```bash
python src/main.py stage2 --limit 10
```

### Stage 3 — генерация ссылок 2ГИС
```bash
python src/main.py stage3 --limit 10
```

### Stage 4 — сбор объявлений
```bash
python src/main.py stage4 --top-n 20 --limit 10 --details
```

### Статистика
```bash
python src/main.py stats
```

## Конфигурация
Настройки задаются через `src/config/settings.py` и переменные окружения.

Ключевые параметры:
- `GEMINI_API_KEY` — ключ Gemini (для ИИ‑анализа, если используется).
- `DATABASE_PATH` — путь к SQLite БД (по умолчанию `results/eis_data.db`).
- `COORDINATES_CSV_PATH` — путь к CSV с координатами городов.
- `STAGE4_HEADLESS`, `STAGE4_USE_REAL_CHROME` — режим запуска браузера.

## База данных (SQLite)

### Таблица `zakupki`
- `reg_number` (PK)
- `description`, `link`, `combined_text`
- `two_gis_url`
- `status`, `prepared_by_user_id`, `prepared_at`

### Таблица `ai_results`
- `reg_number` (PK)
- `city`, `area_min_m2`, `rooms_parsed`, `floor`, `price_rub`

### Таблица `listings`
- `zakupka_reg_number`, `rank`, `price_rub`, `address`, `rooms`, `area_m2`, `building_year`, `external_url`

### Дополнительно
- `users`, `decisions`, `user_overrides` — для human‑in‑the‑loop и переопределений.

## Важно
- **Stage 4 должен запускаться пользователем** (данные объявлений быстро устаревают).
- **AIResult read‑only**: правки делаются через `user_overrides`.
- Для 2ГИС может требоваться VPN (зарубежные IP блокируются).


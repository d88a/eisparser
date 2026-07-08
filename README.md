# EIS Parser

**EIS Parser** — система автоматизации поиска коммерческой недвижимости через государственные закупки (ЕИС, zakupki.gov.ru). Проект мониторит публикации закупок недвижимости, анализирует текст закупок с помощью AI, генерирует поисковые ссылки на 2ГИС и собирает объявления о продаже/аренде объектов по найденным параметрам.

Пайплайн извлекает из текста закупки структурированные параметры (город, площадь, адрес, этаж, год постройки, заказчик), строит по ним поисковую ссылку 2ГИС и скрапит сайты объявлений, собирая кандидатов-объектов коммерческой недвижимости с логикой резервирования для конечных пользователей.

## Возможности

- Мониторинг закупок недвижимости на ЕИС (zakupki.gov.ru)
- AI-анализ текста закупки → структурированные параметры
- Автоматическая генерация поисковых ссылок 2ГИС
- Сбор объявлений (цена, площадь, этаж, адрес, внешний источник)
- Web-UI: админ-кабинет пайплайна + публичный пользовательский контур с резервированием
- Фоновые воркеры (systemd) для непрерывной работы Stage 1–4

## Архитектура

Пайплайн из 4 этапов. Каноническая ссылка процесса хранится в `zakupki.two_gis_url`; Stage 4 работает только по ней. Детально — в [`docs/PROJECT.md`](docs/PROJECT.md).

| Этап | Назначение | Переход статуса закупки |
|------|-----------|--------------------------|
| **Stage 1** | Загрузка и сохранение закупок ЕИС | `→ raw` |
| **Stage 2** | AI-анализ текста закупки → структурированные параметры | `raw`/`ai_error` → `ai_ready`/`ai_error` |
| **Stage 3** | Генерация поисковой ссылки 2ГИС по параметрам | `ai_ready` → `url_ready` |
| **Stage 4** | Сбор объявлений по ссылке Stage 3 (Playwright + 2ГИС) | `url_ready` → `stage4_done`/`stage4_error` |

Lifecycle: `raw → ai_ready | ai_error → url_ready → stage4_done | stage4_error`.
Допустимые переходы зафиксированы в `PIPELINE_LIFECYCLE_TRANSITIONS` (`src/models/statuses.py`).

## Технологии

- **Python 3.11**
- **FastAPI** + Uvicorn — REST API и web-UI (Jinja2)
- **PostgreSQL** (production) / SQLite (fallback, локально)
- **Playwright** + playwright-stealth — headless-браузер для Stage 4 (2ГИС)
- **OpenAI-compatible AI** (по умолчанию Cerebras, `gpt-oss-120b`) — Stage 2
- **systemd** — фоновые воркеры
- BeautifulSoup4, pdfplumber, python-docx, openpyxl, olefile, xlrd — разбор вложений закупок

## Структура проекта

```text
eisparser/
├── src/
│   ├── api/                # FastAPI: app + маршруты
│   │   ├── app.py
│   │   └── routes/         # health, auth, stage1-4, user, admin, common
│   ├── config/             # settings.py — загрузка .env
│   ├── models/             # доменные модели + statuses.py (lifecycle)
│   ├── repositories/       # слой БД (base.py + *_repo.py)
│   ├── services/           # бизнес-логика этапов и сервисы
│   ├── gis/                # генерация/парсинг 2ГИС-ссылок (filters, generator, parser)
│   ├── realty_scraper/     # Playwright-скрапинг объявлений (two_gis_playwright)
│   ├── web/                # templates/ + static/ (Jinja2 UI)
│   ├── pipeline.py         # оркестрация Stage 1-4
│   ├── main.py             # CLI entrypoint
│   ├── text_extraction.py  # извлечение текста из вложений
│   └── utils/logger.py
├── deploy/systemd/         # unit-файлы воркеров
├── docs/                   # PROJECT.md, screenshots/
├── scripts/                # init_postgres, migrate, schema, cleanup
├── tests/                  # pytest
└── requirements.txt
```

## Установка и запуск

### Требования

- Python 3.11+
- (production) PostgreSQL; локально — SQLite
- Playwright: `python -m playwright install chromium`

### Установка

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m playwright install chromium
```

### Конфигурация

```bash
cp src/.env.example src/.env
# заполните src/.env (см. таблицу переменных ниже)
```

### Команды CLI

Запуск из корня проекта с `PYTHONPATH=src`:

```bash
export PYTHONPATH=src
python src/main.py stats                                   # статистика по закупкам/AI/объявлениям
python src/main.py stage1 --limit 10                       # Stage 1: загрузка закупок
python src/main.py stage2 --limit 5                        # Stage 2: AI-анализ
python src/main.py stage3 --limit 5                        # Stage 3: ссылки 2ГИС
python src/main.py stage4 --top-n 10 --limit 2 --details   # Stage 4: сбор объявлений
python src/main.py server --host 127.0.0.1 --port 8000 --reload   # web-UI / API
```

Фоновые воркеры:

```bash
python src/main.py worker          --interval 300 --limit 10 --top-n 10   # Stage 1-4
python src/main.py worker-ingest   --interval 300 --limit 10              # Stage 1-2
python src/main.py worker-listing  --interval 300 --limit 10 --top-n 10   # Stage 3-4
```

### Production (systemd)

Unit-файлы в `deploy/systemd/`:
`eisparser-worker.service` (Stage 1–4), `eisparser-worker-ingest.service` (Stage 1–2), `eisparser-worker-listing.service` (Stage 3–4).

Логика выбора БД: при заданном `DATABASE_URL` используется PostgreSQL, иначе SQLite (`DATABASE_PATH`).

## API endpoints

Admin-контур требует аутентификации (`admin_token`). Публичный контур регулируется `USER_ACCESS_MODE` (`PUBLIC`/`AUTH_REQUIRED`).

### Health

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/api/health` | Проверка состояния сервиса |

### Stage 1–2 (admin)

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/api/stage1` | Список загруженных закупок |
| POST | `/api/actions/save_stage1_selected` | Сохранить выбранные закупки |
| POST | `/api/actions/run_stage2` | Запуск AI-анализа |
| GET | `/api/stage2` | Результаты Stage 2 |
| GET | `/api/stage2/{reg_number}` | Детали по закупке |
| POST | `/api/decisions` | Решение по закупке |

### Stage 3–4 (admin)

| Метод | Путь | Описание |
|-------|------|----------|
| POST | `/api/actions/run_stage3` | Генерация ссылок 2ГИС |
| GET | `/api/stage3` | Данные Stage 3 |
| POST | `/api/actions/run_stage4` | Сбор объявлений |
| GET | `/api/stage4` | Данные Stage 4 |
| GET | `/api/stage4/{reg_number}/listings` | Объявления по закупке |

### Admin

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/api/admin/pipeline_status` | Статусы по этапам |
| GET | `/api/admin/zakupki_all` | Все закупки (админ) |
| POST | `/api/admin/batch_stage2` | Пакетный Stage 2 |
| POST | `/api/admin/batch_stage3` | Пакетный Stage 3 |
| POST | `/api/admin/cleanup_selected` | Очистка выбранных |

### Public / User

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/api/public/zakupki` | Доступные закупки |
| GET | `/api/public/zakupki/{reg_number}` | Детали закупки |
| GET | `/api/public/reservations` | Резервы пользователя |
| GET | `/api/public/favorites` | Избранное |
| GET | `/api/public/account` | Данные аккаунта |
| POST | `/api/public/account/profile` | Обновить профиль |
| POST | `/api/public/account/password` | Сменить пароль |
| POST | `/api/public/zakupki/{reg_number}/reserve` | Зарезервировать закупку |
| POST | `/api/public/zakupki/{reg_number}/reserve-cheapest` | Резерв самого дешёвого объявления |
| POST | `/api/public/zakupki/{reg_number}/unreserve` | Снять резерв |

Web-страницы: `/`, `/admin`, `/admin/stage2..4`, `/admin/login`, `/public/zakupki`, `/public/reservations`, `/public/account`, `/public/login`, `/public/register`.

## Переменные окружения

Конфигурация в `src/.env` (референс — `src/.env.example`).

| Переменная | Описание | По умолчанию |
|-----------|----------|--------------|
| `CEREBRAS_API_KEY` | API-ключ AI (OpenAI-compatible) | — |
| `CEREBRAS_BASE_URL` | Базовый URL AI-провайдера | `https://api.cerebras.ai/v1` |
| `CEREBRAS_MODEL` | Модель для Stage 2 | `gpt-oss-120b` |
| `AI_STAGE2_DELAY_S` | Задержка между AI-запросами, сек | `2.0` |
| `ADMIN_PASSWORD` | Пароль админа (обязательно сменить) | `change_me` |
| `ADMIN_TOKEN_SECRET` | Секрет HMAC admin-токена (рекомендуется) | = `ADMIN_PASSWORD` |
| `ADMIN_SECURITY_FAIL_FAST` | Строгий отказ при слабой конфигурации | `false` |
| `USER_ACCESS_MODE` | `PUBLIC` или `AUTH_REQUIRED` | `PUBLIC` |
| `SERVER_RELOAD` | Uvicorn reload (dev) | `false` |
| `DATABASE_URL` | PostgreSQL DSN (пусто → SQLite) | — |
| `DATABASE_PATH` | Путь к SQLite | `../results/eis_data.db` |
| `STAGE1_MAX_PAGES` | Глубина сканирования ЕИС, страниц | `10` |
| `STAGE4_HEADLESS` | Headless-режим браузера | `true` |
| `STAGE4_USE_REAL_CHROME` | Использовать реальный Chrome | `true` |
| `STAGE4_PAGE_TIMEOUT_S` | Таймаут страницы, сек | `60` |
| `WORKER_ENABLE_STAGE4` | Запуск Stage 4 в воркере | `true` |
| `RESERVATION_TTL_HOURS` | TTL резерва, часы | `72` |
| `PROXY_URL` | Прокси (опционально) | — |
| `BILLING_ENABLED` | Флаг биллинга (future) | `false` |
| `LIMITS_USER_STAGE4_RUNS_ENABLED` | Лимит запусков Stage 4 (future) | `false` |
| `LIMITS_MAX_SELECTED_ITEMS_ENABLED` | Лимит выбранных объектов (future) | `false` |

## Тесты

```bash
export PYTHONPATH=src
python -m pytest -q
```

## Скриншоты

Интерфейс этапов — в [`docs/screenshots/`](docs/screenshots/): `stage1_pg.png`, `stage2_pg.png`, `stage3_pg.png`, `stage4_pg.png`.

## Лицензия

MIT. Подробности — см. [LICENSE](LICENSE).

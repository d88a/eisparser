# Подготовка к коммерциализации (без включения в продукт)

Дата: 2026-03-01

## Цель
Подготовить технический фундамент для платных ограничений и аналитики, не меняя текущую бесплатную продуктовую логику и default-поведение.

## 1) События пользовательских действий

Минимальный набор событий:
- `user_page_opened` (`/user/available`, `/user/selections`)
- `user_selection_added`
- `user_selection_removed`
- `user_stage4_run_started`
- `user_stage4_run_finished`
- `user_access_denied` (`USER_ACCESS_MODE=AUTH_REQUIRED`)

Обязательные поля события:
- `event_id` (uuid)
- `event_type`
- `event_ts` (UTC)
- `user_id` (nullable для anonymous)
- `reg_number` (nullable)
- `request_id` (для трассировки)
- `metadata_json` (свободные поля)

Принцип записи:
- Запись событий async/неблокирующая (ошибка записи не ломает API).
- Ретрай или буфер в памяти не требуется на первом этапе; допускается best-effort.

## 2) Хранение аналитики

Минимальные таблицы:
1. `usage_events`
   - `id` bigint PK
   - `event_id` text unique
   - `event_type` text
   - `event_ts` timestamp
   - `user_id` integer null
   - `reg_number` text null
   - `request_id` text null
   - `metadata_json` json/text
2. `feature_flags`
   - `flag_key` text PK
   - `enabled` bool
   - `rollout_percent` integer (0..100)
   - `updated_at` timestamp
3. `user_feature_overrides`
   - `id` bigint PK
   - `user_id` integer
   - `flag_key` text
   - `enabled` bool
   - `updated_at` timestamp

Индексы:
- `usage_events(event_ts)`
- `usage_events(event_type, event_ts)`
- `usage_events(user_id, event_ts)`

Оценка нагрузки (первый этап):
- 2-10 событий на активного пользователя в сессию.
- До 100k событий/сутки укладываются в одну таблицу PostgreSQL без шардирования.
- Ротация: архивировать события старше 90-180 дней в отдельное хранилище.

## 3) Feature flags для тарифных ограничений

Флаги (по умолчанию `enabled=false`):
- `billing.enabled`
- `limits.user_stage4_runs.enabled`
- `limits.max_selected_items.enabled`
- `limits.api_rate_limit.enabled`

Правила:
- В коде всегда есть fallback в текущую бесплатную модель.
- Включение флагов только через конфиг/таблицу, без hardcode.
- На этапе подготовки флаги не влияют на поведение API.

## 4) Риски и безопасное включение

Риски:
- Рост latency API при синхронной записи событий.
- Ошибки миграции и блокировки таблиц под нагрузкой.
- Ошибки в правилах flags могут ограничить бесплатных пользователей.

Снижение рисков:
- События пишутся best-effort и не участвуют в критическом пути.
- Все флаги по умолчанию выключены.
- Нужен dry-run на staging с репликой продовой БД.

Порядок безопасного включения:
1. Деплой схемы БД (только новые таблицы и индексы).
2. Деплой кода записи событий, но с `billing.enabled=false`.
3. Мониторинг 3-7 дней: latency, ошибки записи, рост БД.
4. Поэтапный rollout флагов: 1% -> 10% -> 50% -> 100%.
5. При аномалии: мгновенный rollback выключением flags.

## 5) Rollback

Быстрый rollback без отката кода:
1. Выключить все коммерческие флаги (`enabled=false`).
2. Оставить сбор событий включенным или выключить `billing.enabled=false`.
3. Проверить восстановление baseline по API-метрикам.

Откат схемы (при крайней необходимости):
- Таблицы не удалять сразу; сначала отключить запись/чтение.
- Удаление только после подтвержденного простоя и бэкапа.

# Задания стажеру (актуально на 2026-03-06)

Источник постановки:
1. `docs/ARCHITECT_2_ACTION_REPORT_2026-03-02.md`
2. `docs/ARCHITECT_2_PLAYBOOK.md`

## 1) Контекст и статус

Закрыто в прошлом цикле:
1. `A`: магические строки статусов убраны из `pipeline.py` и `worker_service.py`.
2. `B`: добавлен тест деградации ingest-цикла.
3. `C`: `overrides-smoke` сделан переносимым.

Новый цикл работ: переходим к шагам 2 и 3 из отчета главного архитектора.

Статус выполнения (обновлено 2026-03-06):
1. `D` (Stage 1 стабилизация): docs обновлены, добавлен ежедневный Stage 1 чек-лист и runbook реакции на недоступность ЕИС.
2. `E` (baseline PUBLIC): формулировки выровнены в docs; подтверждено smoke-тестом `tests/test_http_access_modes.py`.
3. `F` (feature flags заготовки): в `src/.env.example` добавлены выключенные флаги (`BILLING_ENABLED`, `LIMITS_USER_STAGE4_RUNS_ENABLED`, `LIMITS_MAX_SELECTED_ITEMS_ENABLED`) без изменения runtime-логики.

Факт-проверка на VDS (2026-03-06):
1. `systemctl status`:
   1. `eisparser-api` — `active (running)`;
   2. `eisparser-worker-ingest` — `active (running)`;
   3. `eisparser-worker-listing` — `active (running)`.
2. API smoke:
   1. `/api/user/available_zakupki` -> `200`;
   2. `/api/admin/pipeline_status` без cookie -> `401`.
3. Ingest лог:
   1. есть регулярные `Cron iteration start`/`Cycle N started`;
   2. есть `Stage 1 started`/`Stage 1 finished`.
4. В `/opt/eisparser/src/.env` добавлены и применены:
   1. `USER_ACCESS_MODE=PUBLIC`;
   2. `EIS_RETRY_COUNT=3`;
   3. `EIS_RETRY_BACKOFF_S=2.0`;
   4. `EIS_REQUEST_TIMEOUT_S=30`;
   5. `PROXY_URL=` (пусто, не используется).

---

## 2) Активные задачи спринта

## Задача D (P1): стабилизация Stage 1 в проде

### Цель
Подтвердить, что ingest-контур стабилен после регламентов ЕИС, а параметры деградации (proxy/retry) корректно заданы и документированы.

### Разрешенные файлы
1. `docs/WORKER_VDS.md`
2. `docs/VDS_CURRENT_SETUP.md`
3. `docs/DEPLOY_AND_RUN.md`

### Что сделать (по шагам)
1. На VDS проверить состояние сервисов:
   1. `systemctl status eisparser-api --no-pager`
   2. `systemctl status eisparser-worker-ingest --no-pager`
   3. `systemctl status eisparser-worker-listing --no-pager`
2. Проверить ingest-логи за последние 200-400 строк:
   1. наличие регулярных циклов (`Cron iteration start` / `Cycle N started`);
   2. наличие запусков Stage 1;
   3. отсутствие повторяющихся crash-loop симптомов.
3. Подтвердить, что параметры деградации заданы в `/opt/eisparser/src/.env`:
   1. `PROXY_URL` (если используется);
   2. `EIS_RETRY_COUNT`;
   3. `EIS_RETRY_BACKOFF_S`;
   4. `EIS_REQUEST_TIMEOUT_S`.
4. Обновить `docs/WORKER_VDS.md`:
   1. добавить короткий ежедневный чек-лист эксплуатации Stage 1;
   2. добавить блок “быстрая реакция при недоступности ЕИС”.
5. Обновить `docs/VDS_CURRENT_SETUP.md` и/или `docs/DEPLOY_AND_RUN.md`, если по факту найдены расхождения с рабочим контуром.

### Критерии приемки
1. Есть подтверждение регулярной работы ingest-цикла по логам.
2. Proxy/retry параметры подтверждены и отражены в документации.
3. В docs есть операционный чек-лист для Stage 1.

---

## Задача E (P1): зафиксировать продуктовый baseline PUBLIC

### Цель
Подтвердить, что бесплатный пользовательский контур остается в режиме `USER_ACCESS_MODE=PUBLIC`, при этом админский контур изолирован.

### Разрешенные файлы
1. `docs/PROJECT.md`
2. `docs/DEPLOY_AND_RUN.md`
3. `docs/VDS_CURRENT_SETUP.md`
4. `tests/test_http_access_modes.py` (только при необходимости уточнений)

### Что сделать (по шагам)
1. Проверить по коду/конфигу:
   1. default режима доступа пользователей — `PUBLIC`;
   2. admin endpoint-ы не становятся публичными.
2. Выполнить smoke-проверку на стенде/локали:
   1. user API доступен без admin cookie в `PUBLIC`;
   2. admin API без cookie возвращает `401`.
3. Сверить документацию, чтобы везде было единообразно:
   1. что `PUBLIC` — базовый режим;
   2. что `AUTH_REQUIRED` — опциональный переключатель;
   3. что админский контур независим от user-контурa.
4. Если есть расхождения в формулировках между docs — выровнять.

### Критерии приемки
1. Baseline `PUBLIC` подтвержден проверками.
2. Админский контур остается защищенным.
3. Документация не противоречит фактическому поведению.

---

## Задача F (P2): безопасные заготовки под будущие тарифы (без включения)

### Цель
Подготовить технические заготовки для будущей коммерциализации без изменения текущего бесплатного поведения.

### Разрешенные файлы
1. `docs/COMMERCIALIZATION_PREP.md`
2. `docs/PROJECT.md`
3. `docs/VDS_CURRENT_SETUP.md`
4. `src/.env.example` (если нужно добавить выключенные флаги)

### Что сделать (по шагам)
1. Проверить, что в документации явно указано:
   1. все коммерческие ограничения сейчас выключены;
   2. включение возможно только через feature flags;
   3. baseline поведение API не меняется.
2. При необходимости добавить в `src/.env.example` выключенные флаги вида:
   1. `BILLING_ENABLED=false`
   2. `LIMITS_USER_STAGE4_RUNS_ENABLED=false`
   3. `LIMITS_MAX_SELECTED_ITEMS_ENABLED=false`
3. Проверить, что добавленные флаги не влияют на текущую логику (только заготовка, без включения ограничений).
4. Обновить docs по этим флагам (кратко, без лишней детализации).

### Критерии приемки
1. Флаги/документация готовы, но продуктовое поведение не изменено.
2. Нет смешения user/admin контуров.

---

## 3) Общие ограничения

1. Не менять lifecycle статусов без согласования.
2. Не ослаблять `admin_required`.
3. Не менять продовый `.env` через PR.
4. Не коммитить секреты.

---

## 4) Обязательные команды проверки

1. `python -m compileall -q src`
2. `python -m pytest -q`

Дополнительно по задаче D (на VDS):
1. `systemctl status eisparser-worker-ingest --no-pager`
2. `tail -n 200 /opt/eisparser/results/logs/worker.log`

---

## 5) Формат отчета стажера

1. Список измененных файлов по задачам `D/E/F`.
2. Что сделано по каждому пункту.
3. Фактический вывод команд:
   1. `python -m compileall -q src`
   2. `python -m pytest -q`
   3. VDS-команды по логам/сервисам для задачи D.
4. Короткий smoke по API (user/admin).
5. Остаточные риски и предложения на следующий спринт.

Отчет без фактического вывода команд не принимается.

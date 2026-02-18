Stage 2 — AI Interpretation Review (Human-in-the-Loop)
Контекст проекта

В проекте уже реализованы:

decision-workflow (approve / reject)

View-модель ZakupkaStageView

Stage 1 UI (Intake + gate)

API для решений и запуска этапов

Твоя задача — реализовать Stage 2 как отдельный визуальный gate для проверки AI-интерпретации требований закупки.

Stage 2 НЕ про рынок, НЕ про аналитику, НЕ про редактирование данных.

Цель Stage 2

Дать пользователю возможность ответить на вопрос:

«Правильно ли AI понял требования закупки?»

И:

либо допустить закупку к Stage 3,

либо остановить её с комментарием.

Общие ограничения (ОБЯЗАТЕЛЬНО)

❌ Нельзя:

автоматически запускать Stage 3

редактировать AI-данные

скрывать raw текст

добавлять аналитику, скоринг, confidence %

✅ Нужно:

показывать, что именно прочитал AI

показывать, что именно он извлёк

дать approve / reject

запускать Stage 3 только вручную

ЧАСТЬ 1. Backend API (обязательно)
Задача 1. Endpoint получения данных Stage 2

Добавить endpoint:

GET /api/stage2

Поведение:

принимает user_id (временно можно захардкодить)

возвращает список закупок approved на Stage 1

использует:

ViewService.get_zakupka_stage_view(user_id, stage=2)

Задача 2. Endpoint сохранения решений Stage 2

Использовать уже существующий:

POST /api/decisions


Параметры:

user_id

reg_number

stage = 2

decision = approved / rejected

comment (обязательно при reject)

⚠️ Новую таблицу НЕ создавать.

Задача 3. Endpoint запуска Stage 3

Добавить endpoint:

POST /api/actions/run_stage3

Поведение:

находит закупки:

user_id

stage = 2

decision = approved

запускает Stage 3 ТОЛЬКО для них

ничего не делает, если approved = 0

ЧАСТЬ 2. UI — Stage 2 экран

Файл:

/stage2


(отдельная страница или роут)

Задача 4. Структура экрана

Экран должен состоять из 4 логических зон:

Header

Stage 2 — AI Interpretation Review

counters: total / approved / rejected / pending

Список закупок

reg_number

short description

статус решения

индикатор: AI processed / not processed

AI Interpretation Panel (ключевая часть)

Actions

Задача 5. AI Interpretation Panel (ОБЯЗАТЕЛЬНО)

При выборе закупки показать:

5.1 Raw text

combined_text

прокручиваемый блок

обрезка допустима, но не скрывать смысл

5.2 Extracted fields (структурированно)

Показывать поля AIResult, например:

City

Region

Object type

Rooms

Area min / max

Price max

Constraints (если есть)

⚠️ Если поле отсутствует → явно показать null / not found.

Задача 6. Решения пользователя

Для выбранной закупки:

✅ Approve interpretation

❌ Reject interpretation

Comment:

обязателен при reject

необязателен при approve

Решение сохраняется сразу через API.

Задача 7. Запуск Stage 3

Кнопка:

▶ Run Stage 3 for Approved


Поведение:

активна только если есть approved

при клике:

вызывает /api/actions/run_stage3

показывает результат (запущено / нечего запускать)

ЧАСТЬ 3. Smoke-test (обязательно)

Написать простой сценарий:

Есть закупка, approved на Stage 1

Есть AIResult

UI показывает:

raw text

extracted fields

Reject с комментарием сохраняется

Approve → закупка попадает в запуск Stage 3

Тест может быть:

ручной

или Python-скрипт

Главное — воспроизводимость.

Что НЕ нужно делать

редактирование AIResult

подсветка «хорошо / плохо»

автосортировка

пагинация

авторизация

Критерии приёмки (я буду проверять именно это)

Stage 2 реально блокирует путь к Stage 3

Пользователь видит:

что читал AI

что он понял

Решения сохраняются корректно

Stage 3 запускается только вручную и только по approved

UI не содержит бизнес-логики

Архитектурная подсказка (прочитать внимательно)

Stage 2 — это не улучшение AI.
Это инструмент выявления его ошибок.

Если UI «помогает» принять решение — он неправильный.
UI должен мешать ошибаться, а не подсказывать.

Результат

После выполнения задачи:

Stage 2 станет полноценным gate

можно будет безопасно переходить к Stage 3

появится реальное доверие к пайплайну
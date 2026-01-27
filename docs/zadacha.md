Контекст проекта

У нас есть Python-проект с пайплайном обработки закупок недвижимости (Stage 1–4).
Нужно добавить workflow решений пользователя, чтобы можно было:

одобрять / отклонять закупки на каждом этапе;

запускать следующий этап только для одобренных.

Ты работаешь только с backend / БД-слоем.
UI делать НЕ НУЖНО.

Задача 1. Таблица пользователей
Что нужно сделать

Добавить таблицу users.

Требования

SQLite

Поля:

id (INTEGER, PK)

email (TEXT)

role (TEXT)

created_at (TIMESTAMP)

Результат

SQL для создания таблицы

Метод инициализации в DatabaseService

Задача 2. Таблица решений пользователей
Что нужно сделать

Добавить таблицу decisions.

Поля

id (INTEGER, PK)

user_id (FK → users.id)

reg_number (TEXT)

stage (INTEGER)

decision (TEXT: approved / rejected / skipped)

comment (TEXT, nullable)

created_at (TIMESTAMP)

Ограничения

НЕЛЬЗЯ хранить decision в zakupki

Одну закупку можно решать много раз

Задача 3. Репозиторий решений

Создать DecisionRepository.

Методы

add_decision(user_id, reg_number, stage, decision, comment=None)

get_last_decision(user_id, reg_number, stage)

get_approved_reg_numbers(user_id, stage) -> List[str]

Требования

Использовать existing BaseRepository

Логировать ошибки

Без бизнес-логики

Задача 4. Интеграция с Pipeline (минимально)
Что сделать

Добавить отдельный метод, НЕ переписывая пайплайн:

get_zakupki_for_stage(user_id, stage)


Который:

берёт approved reg_number из decisions

возвращает соответствующие Zakupka

Задача 5. Smoke-тесты (обязательно)

Написать простой сценарий:

Создать user

Добавить 3 решения (2 approved, 1 rejected)

Проверить, что выборка вернула только approved

Можно без pytest — обычный Python-скрипт.

Что НЕ НУЖНО делать

UI / frontend

авторизацию

роли сложнее admin

изменение логики Stage 1–4

оптимизацию запросов

Критерий приёмки

Таблицы создаются

Репозиторий работает

Можно получить список закупок для этапа по user_id

Код читаемый, без магии

VI. Твой архитектурный контроль (важно)

Когда стажёр принесёт результат, ты проверяешь:

Нет ли decision в zakupki

Нет ли глобального состояния

Нет ли “одного правильного решения”

Можно ли легко добавить второго пользователя

Если всё это соблюдено — фундамент заложен правильно.
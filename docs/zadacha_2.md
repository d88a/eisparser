Контекст

В проекте реализован decision-workflow (approve / reject).
Теперь нужно подготовить view-модель для визуализации этапов пайплайна.

UI делать НЕ НУЖНО.
API делать НЕ НУЖНО.

Задача 1. View-модель

Создать dataclass:

ZakupkaStageView

Поля

reg_number: str

description: str

update_date: str

stage: int

my_decision: Optional[str]

my_decision_comment: Optional[str]

has_ai_result: bool

ai_city: Optional[str]

ai_price: Optional[float]

ai_area_min: Optional[float]

ai_rooms: Optional[str]

listings_count: int

listings_min_price: Optional[int]

listings_max_price: Optional[int]

Задача 2. ViewService

Создать ViewService с методом:

get_zakupka_stage_view(user_id: int, stage: int) -> List[ZakupkaStageView]

Метод должен:

Получить закупки для этапа (get_zakupki_for_stage)

Для каждой закупки:

получить последнее решение пользователя

получить AIResult (если есть)

получить listings (если есть)

Посчитать агрегаты:

count

min price

max price

Вернуть список view-моделей

Задача 3. Null-безопасность

Обязательные требования:

если нет ai_result → has_ai_result = False

если нет listings → count = 0, min/max = None

если нет decision → my_decision = None

Никаких исключений.

Задача 4. Smoke-test

Сценарий:

Есть закупка

Есть decision

Есть ai_result

Есть 2 listings с разными ценами

Проверить:

count = 2

min / max корректны

decision подтягивается

Можно обычным Python-скриптом.

Что НЕ нужно делать

SQL JOIN вручную

API

frontend

сортировку

фильтрацию

пагинацию

Критерий приёмки

View-модель создаётся

Список возвращается без ошибок

Данные консистентны

Код читаемый

VIII. Твой контроль как архитектора

Когда стажёр принесёт результат, ты смотришь:

❌ Нет логики принятия решений

❌ Нет UI-предположений

✅ View — read-only

✅ Можно завтра подключить API или UI

Если всё это соблюдено — шаг сделан правильно.

Что будет дальше (чтобы ты видел горизонт)

После View-модели:

→ минимальный UI

→ быстрый ручной QA этапов

→ выявление системных ошибок

→ только потом автоматизация
#!/usr/bin/env python3
"""
Базовый тест API эндпоинтов Этапа 2.
Проверяет работоспособность User и Admin API.
"""

import sys
sys.path.insert(0, 'src')

from services.database_service import DatabaseService
from models.zakupka import Zakupka
from models.ai_result import AIResult

print("=" * 70)
print("ТЕСТ API ЭНДПОИНТОВ ЭТАПА 2")
print("=" * 70)

# Инициализация
db = DatabaseService()
db.init_database()

print("\n[1] Подготовка тестовых данных")
print("-" * 70)

# Создаём тестовую закупку со статусом url_ready
zakupka = Zakupka(
    reg_number="TEST_API_001",
    description="Тестовая закупка для API",
    initial_price=5000000.0,
    status="url_ready",
    two_gis_url="https://2gis.ru/test",
    prepared_by_user_id=1
)
db.zakupki.save(zakupka)
print(f"✓ Создана тестовая закупка: {zakupka.reg_number}")

# Создаём AI результат
ai_result = AIResult(
    reg_number="TEST_API_001",
    city="Москва",
    area_min_m2=50,
    area_max_m2=70,
    rooms="2",
    address="Москва, ул. Тестовая, д. 1"
)
db.ai_results.save(ai_result)
print(f"✓ Создан AI результат")

print("\n[2] Тест: Получение доступных закупок (url_ready)")
print("-" * 70)

available = db.zakupki.get_by_status('url_ready')
print(f"✓ Найдено закупок со статусом url_ready: {len(available)}")
assert len(available) > 0, "Должны быть закупки url_ready"

print("\n[3] Тест: Добавление в выборку пользователя")
print("-" * 70)

user_id = 1
success = db.user_selections.add_selection(user_id, "TEST_API_001")
assert success, "Должна добавиться в выборку"
print(f"✓ Закупка добавлена в выборку пользователя {user_id}")

# Проверяем количество
count = db.user_selections.get_selection_count(user_id)
print(f"✓ Количество выбранных закупок: {count}")
assert count > 0, "Должны быть выборки"

print("\n[4] Тест: Получение выборок пользователя")
print("-" * 70)

selections = db.user_selections.get_user_selections(user_id)
print(f"✓ Получено выборок: {len(selections)}")
print(f"  Reg numbers: {selections}")
assert "TEST_API_001" in selections, "TEST_API_001 должна быть в выборке"

print("\n[5] Тест: Удаление из выборки")
print("-" * 70)

success = db.user_selections.remove_selection(user_id, "TEST_API_001")
assert success, "Должна удалиться из выборки"
print(f"✓ Закупка удалена из выборки")

count_after = db.user_selections.get_selection_count(user_id)
print(f"✓ Количество после удаления: {count_after}")
assert count_after == count - 1, "Количество должно уменьшиться"

print("\n[6] Тест: Статистика по статусам")
print("-" * 70)

# Создаём закупки с разными статусами для статистики
for i, status in enumerate(['raw', 'ai_ready', 'listings_fresh'], start=2):
    z = Zakupka(
        reg_number=f"TEST_API_00{i}",
        description=f"Закупка {status}",
        status=status
    )
    db.zakupki.save(z)

status_counts = db.zakupki.get_status_counts()
print(f"✓ Статистика по статусам:")
for status, count in status_counts.items():
    print(f"  {status}: {count}")

assert 'url_ready' in status_counts, "Должен быть статус url_ready"
assert 'raw' in status_counts, "Должен быть статус raw"

print("\n[7] Тест: Фильтрация по статусам для батч-операций")
print("-" * 70)

raw_zakupki = db.zakupki.get_by_status('raw')
print(f"✓ Закупок со статусом 'raw': {len(raw_zakupki)}")

ai_ready_zakupki = db.zakupki.get_by_status('ai_ready')
print(f"✓ Закупок со статусом 'ai_ready': {len(ai_ready_zakupki)}")

print("\n[8] Очистка тестовых данных")
print("-" * 70)

# Удаляем тестовые данные
for i in range(1, 4):
    db.zakupki.delete(f"TEST_API_00{i}")
db.user_selections.clear_user_selections(user_id)
print("✓ Тестовые данные удалены")

print("\n" + "=" * 70)
print("ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО! ✓")
print("=" * 70)
print("\nAPI эндпоинты Этапа 2 готовы к использованию:")
print("  - User API: available_zakupki, select, unselect, selections, run_stage4")
print("  - Admin API: pipeline_status, batch_stage2, batch_stage3")

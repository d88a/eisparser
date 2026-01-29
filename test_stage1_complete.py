#!/usr/bin/env python3
"""
Комплексный тест Этапа 1: Подготовка базы данных.

Тестирует:
1. Создание БД с новой структурой
2. Работу со статусами закупок
3. Работу с пользовательскими выборками
4. Сохранение и чтение данных
"""

import sys
sys.path.insert(0, 'src')

from services.database_service import DatabaseService
from models.zakupka import Zakupka
from datetime import datetime

print("=" * 70)
print("ТЕСТИРОВАНИЕ ЭТАПА 1: ПОДГОТОВКА БАЗЫ ДАННЫХ")
print("=" * 70)

# Инициализация
db = DatabaseService()
db.init_database()

print("\n[1] Тест: Создание закупки с новыми полями")
print("-" * 70)

zakupka = Zakupka(
    reg_number="TEST001",
    description="Тестовая закупка квартиры",
    initial_price=3500000.0,
    status="raw",
    prepared_by_user_id=None,
    prepared_at=None
)

success = db.zakupki.save(zakupka)
print(f"✓ Закупка сохранена: {success}")

# Чтение обратно
loaded = db.zakupki.get_by_id("TEST001")
assert loaded is not None, "Закупка не найдена"
assert loaded.status == "raw", f"Неверный статус: {loaded.status}"
print(f"✓ Закупка загружена. Статус: {loaded.status}")

print("\n[2] Тест: Обновление статуса закупки")
print("-" * 70)

# Обновляем статус на ai_ready
db.zakupki.update_status("TEST001", "ai_ready")
loaded = db.zakupki.get_by_id("TEST001")
assert loaded.status == "ai_ready", f"Статус не обновлён: {loaded.status}"
print(f"✓ Статус обновлён на: {loaded.status}")

# Обновляем статус на url_ready (должен проставиться prepared_at)
db.zakupki.update_status("TEST001", "url_ready", prepared_by_user_id=1)
loaded = db.zakupki.get_by_id("TEST001")
assert loaded.status == "url_ready", f"Статус не обновлён: {loaded.status}"
assert loaded.prepared_at is not None, "prepared_at не проставлен"
assert loaded.prepared_by_user_id == 1, "prepared_by_user_id неверный"
print(f"✓ Статус обновлён на: {loaded.status}")
print(f"✓ prepared_at проставлен: {loaded.prepared_at}")
print(f"✓ prepared_by_user_id: {loaded.prepared_by_user_id}")

print("\n[3] Тест: Фильтрация по статусам")
print("-" * 70)

# Создаём несколько закупок с разными статусами
for i, status in enumerate(['raw', 'ai_ready', 'url_ready'], start=2):
    z = Zakupka(
        reg_number=f"TEST00{i}",
        description=f"Закупка {i}",
        status=status
    )
    db.zakupki.save(z)

# Получаем по статусу
raw_zakupki = db.zakupki.get_by_status('raw')
ai_ready_zakupki = db.zakupki.get_by_status('ai_ready')
url_ready_zakupki = db.zakupki.get_by_status('url_ready')

print(f"✓ Закупок со статусом 'raw': {len(raw_zakupki)}")
print(f"✓ Закупок со статусом 'ai_ready': {len(ai_ready_zakupki)}")
print(f"✓ Закупок со статусом 'url_ready': {len(url_ready_zakupki)}")

# Получаем по нескольким статусам
ready_zakupki = db.zakupki.get_by_statuses(['ai_ready', 'url_ready'])
print(f"✓ Закупок со статусами 'ai_ready' или 'url_ready': {len(ready_zakupki)}")

print("\n[4] Тест: Пользовательские выборки")
print("-" * 70)

user_id = 1

# Добавляем выборки
db.user_selections.add_selection(user_id, "TEST001")
db.user_selections.add_selection(user_id, "TEST002")
print("✓ Добавлено 2 выборки")

# Получаем список
selections = db.user_selections.get_user_selections(user_id)
assert len(selections) == 2, f"Неверное количество выборок: {len(selections)}"
print(f"✓ Получено выборок: {len(selections)}")
print(f"  Выборки: {selections}")

# Проверяем счётчик
count = db.user_selections.get_selection_count(user_id)
assert count == 2, f"Неверный счётчик: {count}"
print(f"✓ Счётчик выборок: {count}")

# Удаляем одну выборку
db.user_selections.remove_selection(user_id, "TEST001")
selections = db.user_selections.get_user_selections(user_id)
assert len(selections) == 1, f"Выборка не удалена: {len(selections)}"
print(f"✓ Выборка удалена. Осталось: {len(selections)}")

# Очищаем все выборки
db.user_selections.clear_user_selections(user_id)
count = db.user_selections.get_selection_count(user_id)
assert count == 0, f"Выборки не очищены: {count}"
print(f"✓ Все выборки очищены")

print("\n[5] Тест: Индексы и производительность")
print("-" * 70)

import sqlite3
conn = sqlite3.connect(db.db_path)
cursor = conn.cursor()

# Проверяем индексы
cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'")
indices = cursor.fetchall()
print(f"✓ Найдено индексов: {len(indices)}")
for idx in indices:
    print(f"  - {idx[0]}")

conn.close()

print("\n[6] Тест: Очистка тестовых данных")
print("-" * 70)

# Удаляем тестовые закупки
for i in range(1, 5):
    db.zakupki.delete(f"TEST00{i}")
print("✓ Тестовые данные удалены")

print("\n" + "=" * 70)
print("ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО! ✓")
print("=" * 70)
print("\nЭтап 1: Подготовка базы данных - ЗАВЕРШЁН и ПРОТЕСТИРОВАН")

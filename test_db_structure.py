#!/usr/bin/env python3
"""Тест новой структуры БД."""

import sys
sys.path.insert(0, 'src')

from services.database_service import DatabaseService

# Создаём БД
db = DatabaseService()
success = db.init_database()

if success:
    print("✓ БД инициализирована успешно")
    
    # Проверяем структуру zakupki
    import sqlite3
    conn = sqlite3.connect(db.db_path)
    cursor = conn.cursor()
    
    cursor.execute("PRAGMA table_info(zakupki)")
    columns = cursor.fetchall()
    
    print("\nСтруктура таблицы zakupki:")
    for col in columns:
        print(f"  - {col[1]} ({col[2]})")
    
    # Проверяем наличие новых полей
    col_names = [col[1] for col in columns]
    
    required_fields = ['status', 'prepared_by_user_id', 'prepared_at']
    missing = [f for f in required_fields if f not in col_names]
    
    if not missing:
        print("\n✓ Все новые поля присутствуют!")
    else:
        print(f"\n✗ Отсутствуют поля: {missing}")
    
    # Проверяем таблицу user_selections
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_selections'")
    if cursor.fetchone():
        print("✓ Таблица user_selections создана")
    else:
        print("✗ Таблица user_selections не найдена")
    
    conn.close()
    
    print("\n" + "=" * 60)
    print("Этап 1: Подготовка БД - ЗАВЕРШЁН! ✓")
    print("=" * 60)
else:
    print("✗ Ошибка инициализации БД")

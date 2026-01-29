#!/usr/bin/env python3
"""
Миграционный скрипт для обновления БД до версии с системой статусов.

Изменения:
1. Добавляет колонки status, prepared_by_user_id, prepared_at в таблицу zakupki
2. Создаёт индексы для оптимизации запросов
3. Мигрирует существующие данные (проставляет статусы на основе текущего состояния)
4. Создаёт таблицу user_selections

Использование:
    python migrate_db_to_v2.py
"""

import sqlite3
import sys
from pathlib import Path


def check_column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    """Проверяет существование колонки в таблице."""
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cursor.fetchall()]
    return column in columns


def migrate_database():
    """Выполняет миграцию базы данных."""
    # Определяем путь к БД
    db_path = Path("results") / "eis_data.db"
    
    if not db_path.exists():
        print(f"БД не найдена: {db_path}. Миграция не требуется.")
        return True
    
    print(f"Начинаем миграцию БД: {db_path}")
    print("=" * 60)
    
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 1. Проверяем и добавляем колонку status
        if not check_column_exists(conn, 'zakupki', 'status'):
            print("Добавляем колонку 'status' в таблицу zakupki...")
            cursor.execute("ALTER TABLE zakupki ADD COLUMN status TEXT DEFAULT 'raw'")
            conn.commit()
            print("✓ Колонка 'status' добавлена")
        else:
            print("✓ Колонка 'status' уже существует")
        
        # 2. Проверяем и добавляем колонку prepared_by_user_id
        if not check_column_exists(conn, 'zakupki', 'prepared_by_user_id'):
            print("Добавляем колонку 'prepared_by_user_id' в таблицу zakupki...")
            cursor.execute("ALTER TABLE zakupki ADD COLUMN prepared_by_user_id INTEGER")
            conn.commit()
            print("✓ Колонка 'prepared_by_user_id' добавлена")
        else:
            print("✓ Колонка 'prepared_by_user_id' уже существует")
        
        # 3. Проверяем и добавляем колонку prepared_at
        if not check_column_exists(conn, 'zakupki', 'prepared_at'):
            print("Добавляем колонку 'prepared_at' в таблицу zakupki...")
            cursor.execute("ALTER TABLE zakupki ADD COLUMN prepared_at TIMESTAMP")
            conn.commit()
            print("✓ Колонка 'prepared_at' добавлена")
        else:
            print("✓ Колонка 'prepared_at' уже существует")
        
        # 4. Мигрируем существующие данные (проставляем статусы)
        print("Мигрируем существующие данные...")
        
        # Закупки с two_gis_url и ai_results → url_ready
        cursor.execute("""
            UPDATE zakupki 
            SET status = 'url_ready', 
                prepared_at = processed_at,
                prepared_by_user_id = 1
            WHERE two_gis_url IS NOT NULL 
                AND two_gis_url != ''
                AND status = 'raw'
                AND EXISTS (
                    SELECT 1 FROM ai_results 
                    WHERE ai_results.reg_number = zakupki.reg_number
                )
        """)
        url_ready_count = cursor.rowcount
        
        # Закупки с ai_results но без two_gis_url → ai_ready
        cursor.execute("""
            UPDATE zakupki 
            SET status = 'ai_ready'
            WHERE status = 'raw'
                AND EXISTS (
                    SELECT 1 FROM ai_results 
                    WHERE ai_results.reg_number = zakupki.reg_number
                )
                AND (two_gis_url IS NULL OR two_gis_url = '')
        """)
        ai_ready_count = cursor.rowcount
        
        # Остальные → raw
        cursor.execute("""
            UPDATE zakupki 
            SET status = 'raw'
            WHERE status = 'raw'
        """)
        raw_count = cursor.rowcount
        
        conn.commit()
        print(f"✓ Мигрировано: {url_ready_count} url_ready, {ai_ready_count} ai_ready, {raw_count} raw")
        
        # 5. Создаём индексы
        print("Создаём индексы...")
        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_zakupki_status ON zakupki(status)")
            print("✓ Индекс idx_zakupki_status создан")
        except sqlite3.OperationalError:
            print("✓ Индекс idx_zakupki_status уже существует")
        
        conn.commit()
        
        # 6. Создаём таблицу user_selections
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_selections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                reg_number TEXT NOT NULL,
                selected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (reg_number) REFERENCES zakupki(reg_number),
                UNIQUE(user_id, reg_number)
            )
        """)
        print("✓ Таблица user_selections создана")
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_user_selections_user_id 
            ON user_selections(user_id)
        """)
        print("✓ Индекс idx_user_selections_user_id создан")
        
        conn.commit()
        conn.close()
        
        print("=" * 60)
        print("Миграция завершена успешно! ✓")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print(f"Ошибка при миграции БД: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = migrate_database()
    exit(0 if success else 1)

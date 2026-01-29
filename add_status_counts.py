#!/usr/bin/env python3
"""Добавление метода get_status_counts в ZakupkaRepository."""

# Читаем файл
with open('src/repositories/zakupka_repo.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Удаляем пустые строки в конце
while lines and lines[-1].strip() == '':
    lines.pop()

# Добавляем новый метод
new_method = '''
    
    def get_status_counts(self) -> dict:
        """Возвращает количество закупок по каждому статусу."""
        def _count():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT status, COUNT(*) as count 
                    FROM zakupki 
                    GROUP BY status
                """)
                rows = cursor.fetchall()
                return {row['status']: row['count'] for row in rows}
        
        return self.execute_with_retry(_count) or {}
'''

lines.append(new_method)
lines.append('\n')

# Записываем обратно
with open('src/repositories/zakupka_repo.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("✓ Метод get_status_counts добавлен в ZakupkaRepository")

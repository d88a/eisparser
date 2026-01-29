#!/usr/bin/env python3
"""Пересоздание БД с новой структурой."""

import os
from pathlib import Path

# Удаляем старую БД
db_path = Path("results") / "eis_data.db"
db_shm = Path("results") / "eis_data.db-shm"
db_wal = Path("results") / "eis_data.db-wal"

for f in [db_path, db_shm, db_wal]:
    if f.exists():
        try:
            os.remove(f)
            print(f"✓ Удалён: {f}")
        except Exception as e:
            print(f"✗ Ошибка удаления {f}: {e}")

print("\nБД удалена. Теперь запустите приложение - БД создастся автоматически с новой структурой!")

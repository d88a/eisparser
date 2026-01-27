# realty_scraper/storage.py
"""
Модуль для сохранения результатов сбора объявлений.
"""
import json
import os
from datetime import datetime
from typing import List, Optional

from .models import Listing, ListingResult


def save_results_json(
    result: ListingResult,
    output_dir: str = "results",
    filename_prefix: str = "2gis_top"
) -> str:
    """
    Сохраняет результаты в JSON файл.
    
    Returns:
        Путь к созданному файлу
    """
    os.makedirs(output_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{filename_prefix}_{result.top_n}_{timestamp}.json"
    filepath = os.path.join(output_dir, filename)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)
    
    return filepath


def load_stage3_results(filepath: str) -> List[dict]:
    """
    Загружает результаты stage3 из JSON файла.
    
    Returns:
        Список закупок с полем '2gis_link'
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    if isinstance(data, list):
        return data
    
    return []


def get_latest_stage3_file(results_dir: str = "results") -> Optional[str]:
    """
    Находит последний файл stage3 results.
    
    Returns:
        Путь к файлу или None
    """
    import glob
    
    pattern = os.path.join(results_dir, "zakupki_2gis_links_*.json")
    files = glob.glob(pattern)
    
    if not files:
        return None
    
    # Сортируем по имени (содержит timestamp)
    files.sort(reverse=True)
    return files[0]

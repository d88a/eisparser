"""
Настройка логирования для проекта.
"""
import logging
import sys
from pathlib import Path


def setup_logger(
    name: str = "eisparser",
    level: int = logging.INFO,
    log_file: Path = None
) -> logging.Logger:
    """
    Создаёт и настраивает логгер.
    
    Args:
        name: Имя логгера
        level: Уровень логирования
        log_file: Путь к файлу лога (опционально)
    
    Returns:
        Настроенный логгер
    """
    logger = logging.getLogger(name)
    
    # Если уже настроен — возвращаем
    if logger.handlers:
        return logger
    
    logger.setLevel(level)
    
    # Формат сообщений
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Вывод в консоль
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Вывод в файл (опционально)
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger


def get_logger(name: str = None) -> logging.Logger:
    """
    Получает логгер по имени.
    Если не существует — создаёт с настройками по умолчанию.
    """
    full_name = f"eisparser.{name}" if name else "eisparser"
    logger = logging.getLogger(full_name)
    
    # Если корневой логгер не настроен — настраиваем
    root = logging.getLogger("eisparser")
    if not root.handlers:
        setup_logger()
    
    return logger

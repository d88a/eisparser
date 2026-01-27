# config/__init__.py
from .settings import (
    settings,
    BASE_ZAKUPKI_SEARCH_URL,
    DEFAULT_HEADERS,
    ZAKUPKI_DIR,
    RESULTS_DIR,
    OPENROUTER_API_KEY_ENV,
    OPENROUTER_API_URL,
    OPENROUTER_MODEL,
)

# Для совместимости — экспортируем STAGE4 настройки
STAGE4_HEADLESS = settings.stage4_headless
STAGE4_USE_REAL_CHROME = settings.stage4_use_real_chrome
STAGE4_PAGE_TIMEOUT_S = settings.stage4_page_timeout_s
STAGE4_RATE_LIMIT_S = settings.stage4_rate_limit_s
STAGE4_MAX_RETRIES = settings.stage4_max_retries
STAGE4_SCROLL_TIMEOUT_S = settings.stage4_scroll_timeout_s

__all__ = [
    'settings',
    'BASE_ZAKUPKI_SEARCH_URL',
    'DEFAULT_HEADERS',
    'ZAKUPKI_DIR',
    'RESULTS_DIR',
    'OPENROUTER_API_KEY_ENV',
    'OPENROUTER_API_URL',
    'OPENROUTER_MODEL',
    'STAGE4_HEADLESS',
    'STAGE4_USE_REAL_CHROME',
    'STAGE4_PAGE_TIMEOUT_S',
    'STAGE4_RATE_LIMIT_S',
    'STAGE4_MAX_RETRIES',
    'STAGE4_SCROLL_TIMEOUT_S',
]


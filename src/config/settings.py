"""
Конфигурация проекта через переменные окружения.
Использует pydantic-settings для типизации и валидации.
"""
import os
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field


@dataclass
class Settings:
    """Настройки приложения."""
    
    # Пути
    base_dir: Path = field(default_factory=lambda: Path(__file__).parent.parent.parent)
    
    # Gemini AI
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash-exp"
    
    # Database
    database_path: str = ""
    
    # Scraper
    stage4_headless: bool = True
    stage4_use_real_chrome: bool = True
    stage4_page_timeout_s: int = 60
    stage4_rate_limit_s: float = 2.0
    stage4_max_retries: int = 3
    stage4_scroll_timeout_s: int = 30
    
    # Proxy
    proxy_url: Optional[str] = None
    
    # Coordinates
    coordinates_csv_path: str = ""
    
    def __post_init__(self):
        """Загружает значения из .env или переменных окружения."""
        # Загружаем .env если есть
        self._load_dotenv()
        
        # Gemini
        self.gemini_api_key = os.getenv("GEMINI_API_KEY", self.gemini_api_key)
        
        # Database - относительный путь от src/
        default_db = str(self.base_dir / "results" / "eis_data.db")
        self.database_path = os.getenv("DATABASE_PATH", default_db)
        
        # Coordinates CSV
        default_csv = str(self.base_dir / "map" / "ru_localities_geoapify.csv")
        self.coordinates_csv_path = os.getenv("COORDINATES_CSV_PATH", default_csv)
        
        # Scraper settings
        self.stage4_headless = os.getenv("STAGE4_HEADLESS", "true").lower() == "true"
        self.stage4_use_real_chrome = os.getenv("STAGE4_USE_REAL_CHROME", "true").lower() == "true"
        self.stage4_page_timeout_s = int(os.getenv("STAGE4_PAGE_TIMEOUT_S", "60"))
        
        # Proxy
        self.proxy_url = os.getenv("PROXY_URL")
    
    def _load_dotenv(self):
        """Загружает .env файл если существует."""
        env_path = Path(__file__).parent.parent / ".env"
        if env_path.exists():
            try:
                with open(env_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, value = line.split('=', 1)
                            os.environ.setdefault(key.strip(), value.strip())
            except Exception:
                pass
    
    @property
    def results_dir(self) -> Path:
        """Директория для результатов."""
        return self.base_dir / "results"
    
    @property
    def zakupki_dir(self) -> Path:
        """Директория для закупок."""
        return self.base_dir / "zakupki"


# Глобальный экземпляр настроек
settings = Settings()

# Константы для совместимости со старым кодом (eis_downloader.py)
BASE_ZAKUPKI_SEARCH_URL = (
    "https://zakupki.gov.ru/epz/order/extendedsearch/results.html?"
    "searchString=%D0%BA%D0%B2%D0%B0%D1%80%D1%82%D0%B8%D1%80%D0%B0"
    "&morphology=on"
    "&search-filter=Дате+размещения"
    "&pageNumber=1"
    "&sortDirection=false"
    "&recordsPerPage=_10"
    "&showLotsInfoHidden=false"
    "&sortBy=UPDATE_DATE"
    "&fz44=on"
    "&pc=on"
    "&currencyIdGen498085=true"
    "&publishDateFrom=01.01.2025"
)

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
}

ZAKUPKI_DIR = str(settings.zakupki_dir)
RESULTS_DIR = str(settings.results_dir)

# Константы для OpenRouter (ai_extractor.py)
OPENROUTER_API_KEY_ENV = "OPENROUTER_API_KEY"
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = "google/gemini-2.0-flash-001"

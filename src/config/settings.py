"""Application settings loaded from environment variables."""

import os
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Settings:
    """Application settings."""

    # Paths
    base_dir: Path = field(default_factory=lambda: Path(__file__).parent.parent.parent)

    # AI (Cerebras OpenAI-compatible)
    cerebras_api_key: str = ""
    cerebras_base_url: str = "https://api.cerebras.ai/v1"
    cerebras_model: str = "gpt-oss-120b"

    # Admin Auth
    admin_password: str = "admin"
    admin_token_secret: str = ""
    admin_token_secret_explicit: bool = False
    admin_token_ttl_seconds: int = 8 * 60 * 60
    user_access_mode: str = "PUBLIC"

    # Database
    database_path: str = ""
    database_url: Optional[str] = None

    # Scraper
    stage4_headless: bool = True
    stage4_use_real_chrome: bool = True
    stage4_page_timeout_s: int = 60
    stage4_rate_limit_s: float = 2.0
    stage4_max_retries: int = 3
    stage4_scroll_timeout_s: int = 30
    worker_enable_stage4: bool = True
    reservation_ttl_hours: int = 72

    # AI
    ai_stage2_delay_s: float = 2.0

    # Proxy
    proxy_url: Optional[str] = None
    server_reload: bool = False
    eis_retry_count: int = 3
    eis_retry_backoff_s: float = 2.0
    eis_request_timeout_s: int = 30

    # Coordinates
    coordinates_csv_path: str = ""

    def __post_init__(self):
        """Loads values from .env and environment."""
        self._load_dotenv()

        # Cerebras
        self.cerebras_api_key = os.getenv("CEREBRAS_API_KEY", self.cerebras_api_key)
        self.cerebras_base_url = os.getenv("CEREBRAS_BASE_URL", self.cerebras_base_url)
        self.cerebras_model = os.getenv("CEREBRAS_MODEL", self.cerebras_model)

        # Admin
        self.admin_password = os.getenv("ADMIN_PASSWORD", self.admin_password)
        raw_token_secret = (os.getenv("ADMIN_TOKEN_SECRET", "") or "").strip()
        self.admin_token_secret_explicit = bool(raw_token_secret)
        self.admin_token_secret = raw_token_secret or self.admin_password
        self.admin_token_ttl_seconds = int(
            os.getenv("ADMIN_TOKEN_TTL_SECONDS", str(self.admin_token_ttl_seconds))
        )
        self.user_access_mode = (os.getenv("USER_ACCESS_MODE", self.user_access_mode) or "PUBLIC").strip().upper()
        if self.user_access_mode not in {"PUBLIC", "AUTH_REQUIRED"}:
            self.user_access_mode = "PUBLIC"

        # Database
        db_url = (os.getenv("DATABASE_URL", "") or "").strip()
        if not db_url:
            db_url = (os.getenv("DB_CONNECTION_STRING", "") or "").strip()
        self.database_url = db_url or None
        default_db = str(self.base_dir / "results" / "eis_data.db")
        self.database_path = os.getenv("DATABASE_PATH", default_db)

        # Coordinates CSV
        default_csv = str(self.base_dir / "map" / "ru_localities_geoapify.csv")
        self.coordinates_csv_path = os.getenv("COORDINATES_CSV_PATH", default_csv)

        # Scraper settings
        self.stage4_headless = os.getenv("STAGE4_HEADLESS", "true").lower() == "true"
        self.stage4_use_real_chrome = os.getenv("STAGE4_USE_REAL_CHROME", "true").lower() == "true"
        self.stage4_page_timeout_s = int(os.getenv("STAGE4_PAGE_TIMEOUT_S", "60"))
        self.worker_enable_stage4 = os.getenv("WORKER_ENABLE_STAGE4", "true").lower() == "true"
        self.reservation_ttl_hours = max(1, int(os.getenv("RESERVATION_TTL_HOURS", "72")))

        # AI delay between Stage 2 requests
        self.ai_stage2_delay_s = float(os.getenv("AI_STAGE2_DELAY_S", "2.0"))

        # Proxy
        self.proxy_url = os.getenv("PROXY_URL")
        self.server_reload = os.getenv("SERVER_RELOAD", "false").strip().lower() == "true"
        self.eis_retry_count = max(1, int(os.getenv("EIS_RETRY_COUNT", str(self.eis_retry_count))))
        self.eis_retry_backoff_s = max(0.0, float(os.getenv("EIS_RETRY_BACKOFF_S", str(self.eis_retry_backoff_s))))
        self.eis_request_timeout_s = max(1, int(os.getenv("EIS_REQUEST_TIMEOUT_S", str(self.eis_request_timeout_s))))

    def _load_dotenv(self):
        """Loads src/.env if present."""
        env_path = Path(__file__).parent.parent / ".env"
        if env_path.exists():
            try:
                with open(env_path, "r", encoding="utf-8-sig") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            key, value = line.split("=", 1)
                            normalized_key = self._normalize_env_key(key)
                            if normalized_key:
                                os.environ.setdefault(normalized_key, value.strip())
            except Exception:
                pass

    @staticmethod
    def _normalize_env_key(key: str) -> str:
        """Strips BOM and invisible control chars from env keys."""
        if not key:
            return ""
        cleaned = key.replace("\ufeff", "")
        cleaned = "".join(ch for ch in cleaned if ch.isprintable())
        return cleaned.strip()

    @property
    def results_dir(self) -> Path:
        """Results directory."""
        return self.base_dir / "results"

    @property
    def zakupki_dir(self) -> Path:
        """Downloaded purchases directory."""
        return self.base_dir / "zakupki"

    def get_admin_security_issues(self) -> list[str]:
        """Return insecure admin-auth configuration issues."""
        issues: list[str] = []
        if (self.admin_password or "").strip() == "admin":
            issues.append("ADMIN_PASSWORD is set to insecure default value 'admin'")
        if not self.admin_token_secret_explicit:
            issues.append("ADMIN_TOKEN_SECRET is not set explicitly")
        if (self.admin_token_secret or "").strip() == (self.admin_password or "").strip():
            issues.append("ADMIN_TOKEN_SECRET must not be equal to ADMIN_PASSWORD")
        return issues

    def validate_admin_security(self, fail_fast: bool = False):
        """
        Log insecure admin-auth config; optionally stop startup.

        fail_fast=True should be enabled in production environments.
        """
        logger = logging.getLogger("config.security")
        issues = self.get_admin_security_issues()
        if not issues:
            logger.info("Admin auth configuration check passed")
            return

        for issue in issues:
            logger.error("SECURITY_RISK: %s", issue)

        if fail_fast:
            raise RuntimeError("Unsafe admin auth configuration detected")


settings = Settings()

# Compatibility constants for legacy modules
BASE_ZAKUPKI_SEARCH_URL = (
    "https://zakupki.gov.ru/epz/order/extendedsearch/results.html?"
    "searchString=%D0%BA%D0%B2%D0%B0%D1%80%D1%82%D0%B8%D1%80%D0%B0"
    "&morphology=on"
    "&search-filter=\u0414\u0430\u0442\u0435+\u0440\u0430\u0437\u043c\u0435\u0449\u0435\u043d\u0438\u044f"
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

# Cerebras constants
CEREBRAS_API_KEY_ENV = "CEREBRAS_API_KEY"
CEREBRAS_API_URL = "https://api.cerebras.ai/v1/chat/completions"
CEREBRAS_MODEL = "gpt-oss-120b"

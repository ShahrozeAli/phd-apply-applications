from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_APP_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _APP_DIR.parent
_CANDIDATE_ROOT = _BACKEND_DIR.parent
ROOT = _CANDIDATE_ROOT if (_CANDIDATE_ROOT / "config" / "profile.yaml").exists() else _BACKEND_DIR


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(ROOT / ".env"), extra="ignore")

    app_env: str = "development"
    secret_key: str = "change-me"
    database_url: str = f"sqlite:///{(ROOT / 'data' / 'phd_bot.db').as_posix()}"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    discovery_user_agent: str = "PhDApplyBot/0.1 (personal academic search; local instance)"
    discovery_max_pages: int = 3
    discovery_max_detail_pages: int = 25
    discovery_request_delay_seconds: float = 1.2

    llm_provider: str = "none"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    notify_from: str = ""
    notify_to: str = ""

    daily_discovery_hour: int = 6
    daily_discovery_minute: int = 0

    profile_yaml: Path = ROOT / "config" / "profile.yaml"
    data_dir: Path = ROOT / "data"
    packages_dir: Path = ROOT / "application_packages"

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


settings = Settings()
settings.data_dir.mkdir(parents=True, exist_ok=True)
settings.packages_dir.mkdir(parents=True, exist_ok=True)

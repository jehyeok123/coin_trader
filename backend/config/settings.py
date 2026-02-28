import json
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # Upbit API
    upbit_access_key: str = Field(default="", alias="UPBIT_ACCESS_KEY")
    upbit_secret_key: str = Field(default="", alias="UPBIT_SECRET_KEY")

    # Gemini API
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")

    # Korea Investment Securities (TODO)
    kis_app_key: str = Field(default="", alias="KIS_APP_KEY")
    kis_app_secret: str = Field(default="", alias="KIS_APP_SECRET")
    kis_account_no: str = Field(default="", alias="KIS_ACCOUNT_NO")

    # Twitter Monitoring
    twitter_monitor_accounts: str = Field(
        default="elonmusk,VitalikButerin",
        alias="TWITTER_MONITOR_ACCOUNTS",
    )
    nitter_instance_url: str = Field(
        default="https://nitter.net",
        alias="NITTER_INSTANCE_URL",
    )

    # Application
    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    db_url: str = Field(
        default="sqlite+aiosqlite:///./coin_trader.db",
        alias="DB_URL",
    )

    # Signal Monitoring Intervals
    news_check_interval_minutes: int = Field(
        default=5,
        alias="NEWS_CHECK_INTERVAL_MINUTES",
    )
    twitter_check_interval_seconds: int = Field(
        default=60,
        alias="TWITTER_CHECK_INTERVAL_SECONDS",
    )

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    @property
    def twitter_accounts(self) -> list[str]:
        return [a.strip() for a in self.twitter_monitor_accounts.split(",") if a.strip()]


# Trading rules 파일 경로
RULES_FILE = Path(__file__).parent / "default_rules.json"
USER_RULES_FILE = Path(__file__).parent.parent.parent / "trading_rules.json"


def load_trading_rules() -> dict:
    """사용자 규칙이 있으면 사용, 없으면 기본 규칙 로드"""
    if USER_RULES_FILE.exists():
        with open(USER_RULES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    with open(RULES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_trading_rules(rules: dict) -> None:
    """사용자 규칙을 파일에 저장"""
    with open(USER_RULES_FILE, "w", encoding="utf-8") as f:
        json.dump(rules, f, indent=2, ensure_ascii=False)


settings = Settings()

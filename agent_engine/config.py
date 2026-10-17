from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from agent_engine.errors import ConfigError


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mode: Literal["lite", "full"] = "lite"
    workers: int = Field(8, ge=1, le=8)
    soft_cap_requests: int = Field(1700, ge=1)
    brake_requests: int = Field(1950, ge=1, le=2000)
    per_company_cap: int = Field(14, ge=1, le=14)

    llm_base_url: str | None = None
    llm_model: str | None = None
    llm_api_key: SecretStr | None = None
    llm_rpm: int = Field(30, ge=1, le=40)

    website_timeout_s: float = Field(8, gt=0, le=8)
    website_retries: int = Field(2, ge=0, le=2)
    website_max_pages: int = Field(3, ge=1, le=3)
    website_text_chars: int = Field(6000, ge=500, le=20000)

    plan_b_enabled: bool = False
    playwright_enabled: bool = False

    conf_threshold: Decimal = Field(Decimal("0.80"), ge=Decimal("0.80"), le=Decimal("1"))
    q_threshold: Decimal = Field(Decimal("0.95"), gt=Decimal("0"), le=Decimal("1"))
    identity_threshold: Decimal = Field(Decimal("0.6"), ge=Decimal("0"), le=Decimal("1"))

    store_mode: Literal["jsonl", "mongo"] = "jsonl"
    data_dir: Path = Path("data")
    output_dir: Path = Path("output")

    @field_validator("mode")
    @classmethod
    def lite_only(cls, value: str) -> str:
        if value != "lite":
            raise ValueError("Full mode is not built; use MODE=lite")
        return value

    @field_validator("playwright_enabled")
    @classmethod
    def no_playwright(cls, value: bool) -> bool:
        if value:
            raise ValueError("Playwright is not built; use PLAYWRIGHT_ENABLED=false")
        return value

    @model_validator(mode="after")
    def caps_in_order(self):
        if self.soft_cap_requests >= self.brake_requests:
            raise ValueError(
                f"SOFT_CAP_REQUESTS ({self.soft_cap_requests}) must be below "
                f"BRAKE_REQUESTS ({self.brake_requests})"
            )
        return self

    def require_llm(self) -> tuple[str, str, str]:
        """Return (base_url, model, api_key); only code that calls the LLM asks for these."""
        api_key = self.llm_api_key.get_secret_value() if self.llm_api_key else ""
        values = {
            "LLM_BASE_URL": self.llm_base_url,
            "LLM_MODEL": self.llm_model,
            "LLM_API_KEY": api_key,
        }
        missing = [name for name, value in values.items() if not value]
        if missing:
            raise ConfigError("Missing LLM settings: " + ", ".join(missing))
        return self.llm_base_url, self.llm_model, api_key


def load_settings(**overrides) -> Settings:
    try:
        return Settings(**overrides)
    except ValidationError as exc:
        lines = []
        for error in exc.errors():
            name = ".".join(str(part) for part in error["loc"]).upper()
            message = error["msg"].removeprefix("Value error, ")
            lines.append(f"{name}: {message}" if name else message)
        raise ConfigError("Invalid configuration:\n  " + "\n  ".join(lines)) from None


@lru_cache
def get_settings() -> Settings:
    return load_settings()

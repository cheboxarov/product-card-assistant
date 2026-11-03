from __future__ import annotations

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PRODUCT_CARD_",
        env_file=".env",
        extra="ignore",
    )

    openrouter_api_key: SecretStr = Field(min_length=1)
    openrouter_model: str = Field(
        default="meta/muse-spark-1.3-contributor",
        min_length=1,
    )
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1",
        min_length=1,
    )

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PMC_", case_sensitive=False)

    app_version: str = "0.1.0"
    database_url: str = Field(
        default="postgresql+pg8000://pmcloud_dev@postgres:5432/pmcloud_dev",
        repr=False,
    )
    s3_endpoint: str = "http://seaweedfs:8333"
    s3_access_key: str = Field(default="", repr=False)
    s3_secret_key: str = Field(default="", repr=False)
    s3_region: str = "us-east-1"


@lru_cache
def get_settings() -> Settings:
    return Settings()

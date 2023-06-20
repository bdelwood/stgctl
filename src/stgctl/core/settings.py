from re import Pattern

from pydantic import BaseSettings


class Settings(BaseSettings):
    """Read settings from env."""

    VMX_DEVICE_PORT: str = ""
    VMX_DEVICE_REGEX: str | Pattern[str] = "Test Serial Device"
    LOGURU_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        fields = {"LOGURU_LEVEL": {"env": ["STCTL_LOG_LEVEL"]}}


settings = Settings()

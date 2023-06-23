from datetime import datetime
from re import Pattern

from loguru import logger
from pydantic import BaseSettings


logger.add(f'stgctl_{datetime.now().strftime("%Y-%m-%d_%H-%M-%S")}.log')


class Settings(BaseSettings):
    """Read settings from env."""

    VMX_DEVICE_PORT: str = ""
    VMX_DEVICE_REGEX: str | Pattern[str] = "USB-to-Serial"
    LOGURU_LEVEL: str = "DEBUG"
    GRID_SIZE: tuple[int, int] = (60, 60)
    STEP_SIZE: tuple[int, int] | None = None
    OBSERVE_TIME: int = 15
    SIGNAL_HOST: str = "localhost"
    SIGNAL_USER: str = ""
    START_AQ_CMD: str = "hostname"
    END_AQ_CMD: str = "hostname"

    class Config:
        env_prefix = "STGCTL_"
        validate_assignment = True
        validate_all = True
        env_file = ".env"
        env_file_encoding = "utf-8"
        fields = {"LOGURU_LEVEL": {"env": ["STGCTL_LOG_LEVEL"]}}


settings = Settings()

"""Global settings for stgctl, including logs."""

import atexit
import functools
from datetime import datetime
from pathlib import Path
from re import Pattern

from loguru import logger
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Logger that logs to file
log_path = Path("./logs") / Path(
    f"stgctl_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log"
)

# add a file handler
logger.add(log_path.absolute(), enqueue=True)


def delete_empty_logs(log_file: Path) -> None:
    """If an empty logfile is created, delete it.

    Used as a work around for loguru creating an empty logfile when the cli is run.

    Args:
        log_file (Path): Path to logfile created this run.
    """
    if log_file.stat().st_size == 0:
        log_file.unlink()


# Run above function at exit
# register accepts a function, so we need partial to pass its argument.
atexit.register(functools.partial(delete_empty_logs, log_file=log_path))


class Settings(BaseSettings):
    """Read settings from env."""

    model_config = SettingsConfigDict(
        env_prefix="STGCTL_",
        validate_assignment=True,
        validate_default=True,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    VMX_DEVICE_PORT: str = ""
    VMX_DEVICE_REGEX: str | Pattern[str] = "USB-to-Serial"
    # We use LOGURU_LEVEL internally, but STGCTL_LOG_LEVEL in the .env
    LOGURU_LEVEL: str = Field(
        default="DEBUG",
        validation_alias=AliasChoices("STGCTL_LOG_LEVEL"),
    )
    GRID_SIZE: tuple[int, int] = (60, 60)
    STEP_SIZE: tuple[int, int] | None = None
    OBSERVE_TIME: int = 15
    SIGNAL_HOST: str = "localhost"
    SIGNAL_USER: str = ""
    START_AQ_CMD: str = "hostname"
    END_AQ_CMD: str = "hostname"
    CONTINUE_AQ_CMD: str = "hostname"


settings = Settings()

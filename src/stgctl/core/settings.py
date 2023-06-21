from re import Pattern

from pydantic import BaseSettings


class Settings(BaseSettings):
    """Read settings from env."""

    VMX_DEVICE_PORT: str = ""
    VMX_DEVICE_REGEX: str | Pattern[str] = "Test Serial Device"
    LOGURU_LEVEL: str = "INFO"
    GRID_SIZE: tuple[int, int] = (60, 60)
    STEP_SIZE: tuple[int, int] | None = None
    OBSERVE_TIME: int = 15
    SIGNAL_HOST: str = "localhost"
    SIGNAL_USER: str = ""
    START_AQ_CMD: str = '$GCP_DIR/scripts/controlSystem command "signal/send start"'
    END_AQ_CMD: str = '$GCP_DIR/scripts/controlSystem command "signal/send stop"'

    class Config:
        validate_assignment = True
        validate_all = True
        env_file = ".env"
        env_file_encoding = "utf-8"
        fields = {"LOGURU_LEVEL": {"env": ["STCTL_LOG_LEVEL"]}}


settings = Settings()

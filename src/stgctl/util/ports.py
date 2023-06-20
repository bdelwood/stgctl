from re import Pattern

from loguru import logger
from serial.tools.list_ports import grep


def grep_serial_ports(regex: str | Pattern[str]) -> list:
    logger.debug(f"Using regex {regex}")

    return [*grep(regex)]

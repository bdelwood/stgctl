"""Helper functions for dealing with serial ports."""

from re import Pattern

from loguru import logger
from serial.tools.list_ports import grep


def grep_serial_ports(regex: str | Pattern[str]) -> list:
    """_summary_.

    Args:
        regex (str | Pattern[str]): regex to grep serial port name, description, and hwid/

    Returns:
        list: list of ListPortInfo objects that match regex
    """
    logger.debug(f"Using regex {regex}")

    return [*grep(regex)]

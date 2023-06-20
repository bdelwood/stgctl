"""Module config for pytest."""

import pytest


mp = pytest.MonkeyPatch()
mp.setenv("VMX_DEVICE_PORT", "/dev/ttyUSB0")
mp.setenv("VMX_DEVICE_REGEX", "USB-to-Serial")
mp.setenv("LOGURU_LEVEL", "DEBUG")

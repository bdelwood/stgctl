"""Module config for pytest."""

import pytest

mp = pytest.MonkeyPatch()
mp.setenv("STGCTL_VMX_DEVICE_PORT", "/dev/ttyUSB0")
mp.setenv("STGCTL_VMX_DEVICE_REGEX", "USB-to-Serial")
mp.setenv("STCTL_LOG_LEVEL", "DEBUG")

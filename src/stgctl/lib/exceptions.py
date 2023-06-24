"""Exceptions for stgctl."""


class UnsupportedVmxCommandError(Exception):
    """Raised when the attempted command is not supported by the VMX library (yet0)."""

    pass


class VmxNotReadyError(Exception):
    """Raised when the VMX indicates it is not ready."""

    pass


class InvalidVMXCommandError(Exception):
    """Raised when a command is invalid."""

    pass

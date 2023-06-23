"""Class for VMX motor controller."""
import functools
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import IntEnum
from pprint import pformat
from typing import Any
from typing import Self
from typing import TypeVar
from warnings import warn

import serial
from loguru import logger
from stgctl.core.settings import settings
from stgctl.lib.exceptions import InvalidVMXCommandError
from stgctl.lib.exceptions import UnsupportedVmxCommandError
from stgctl.lib.exceptions import VmxNotReadyError
from stgctl.util.ports import grep_serial_ports


class Motor(IntEnum):
    X = 1
    Y = 2
    Z = 3


T = TypeVar("T", bound="VMX")


class MandateImmediate:
    def __init__(self, immediate: bool = True) -> None:
        self.immediate = immediate

    def __call__(self, func: Callable[..., T]) -> Callable[..., T]:
        if self.immediate:

            @functools.wraps(func)
            def wrapper(instance, *args: Any, **kwargs: Any) -> T | None:
                instance._reset()
                instance._serial.reset_input_buffer()
                func(instance, *args, **kwargs)
                instance.send()
                return instance._readall()

            return wrapper
        else:

            @functools.wraps(func)
            def wrapper(
                instance, now: bool = False, *args: Any, **kwargs: Any
            ) -> T | None:
                if now:
                    instance._reset()
                    instance._serial.reset_input_buffer()
                    func(instance, *args, **kwargs)
                    instance.send()

                    return instance._readall()
                else:
                    return func(instance, *args, **kwargs)

            return wrapper


class Command:
    def __init__(self, cmd_type: str) -> None:
        self.cmd_type = cmd_type

    def __call__(self, func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(instance: Any, *args: Any, **kwargs: Any) -> T:
            allowed_cmds = getattr(VMX, self.cmd_type)
            cmd = args[0]
            if cmd in allowed_cmds:
                instance._cmd.append(cmd)
            else:
                raise UnsupportedVmxCommandError(f"{cmd} is not a supported command.")
            return func(instance, *args, **kwargs)

        return wrapper


class SerialCommand(list):
    """Container for Velmex."""

    def ___init__(self, iterable: list[str] = []):
        super().__init__(str(item) for item in iterable)

    def __setitem__(self, index, item):
        super().__setitem__(index, str(item))

    def __repr__(self) -> str:
        return ",".join(self)

    def insert(self, index, item):
        super().insert(index, str(item))

    def append(self, item):
        super().append(str(item))

    def extend(self, other):
        if isinstance(other, type(self)):
            super().extend(other)
        else:
            super().extend(str(item) for item in other)

    def encode(self):
        joined = ",".join(self)
        return joined.encode()

    @property
    def encoded(self):
        return self.encode()


@dataclass
class VMXResponse:
    pass


class VMX:
    """Class for VMX motor controller."""

    # ImMx
    # x pos or neg
    IDX_INCR: str = "I{m}M{x}"
    # IAmMx
    IDX_ABS: str = "IA{m}M{x}"
    # IAmM0
    IDX_ABS_ZERO: str = "IA{m}M0"
    # IAmM-0
    SET_ABS_ZERO: str = "IA{m}M-0"
    # ImM0
    IDX_POS_LIMIT: str = "I{m}M0"
    # ImM-0
    IDX_NEG_LIMIT: str = "I{m}M-0"
    # SmMx
    SET_SPEED: str = "S{m}M{x}"
    # Px
    # x in tenths of a second
    # -x tenths of a millisecond
    SET_PAUSE: str = "P{x}"

    # Operation commands
    OP_CMDS: tuple[str, ...] = (
        "Q",
        "R",
        "N",
        "K",
        "C",
        "D",
        "E",
        "F",
        "rsm",
        "res",
        "!",
        "J",
    )

    # Status request commands
    STATUS_CMDS: tuple[str, ...] = ("V", "X", "Y", "M", "lst", "x", "y")
    GET_MOTOR: str = "getM{m}M"

    PROG_COMPLETE: str = "^"

    def __init__(self, port=None) -> None:
        logger.debug(f"Using settings:\n{pformat(settings.dict())}")
        if not port:
            matched_serial_ports = grep_serial_ports(settings.VMX_DEVICE_REGEX)
            logger.debug(f"Matched serial ports: {matched_serial_ports}")
            if settings.VMX_DEVICE_PORT:
                port = settings.VMX_DEVICE_PORT
            elif matched_serial_ports:
                port = matched_serial_ports[0].device
                if len(matched_serial_ports) > 1:
                    warn(
                        "Multiple serial ports matched, selecting first one.",
                        stacklevel=2,
                    )
            else:
                raise VmxNotReadyError(
                    "Could not find serial port. Please specify the port."
                )
        logger.debug(f"Using serial port '{port}'")
        self._serial = serial.Serial(port, timeout=0)
        self._cmd = SerialCommand()
        self.startup()

    def __enter__(self) -> Self:
        return self

    def __exit__(self) -> None:
        self.close()

    def __del__(self) -> None:
        self.close()

    def startup(self) -> None:
        self.jog()
        self.reset()
        time.sleep(1)
        self.echo(echo_state=True)
        wait_time = 0.1
        timeout = 5
        start_time = time.time()
        while not self.isready():
            time.sleep(wait_time)
            if abs(start_time - time.time()) > timeout:
                raise VmxNotReadyError("Connecting to the VMX has timed out.")

    def close(self) -> None:
        if hasattr(self, "_serial"):
            logger.debug("Closing serial connection to VMX.")
            self._serial.close()

    def _write(self, cmd: SerialCommand) -> None:
        logger.debug(f"Writing command: {cmd}")
        self._serial.write(cmd.encode())

    def _readall(self) -> bytes:
        time.sleep(0.1)
        readout = self._serial.readall()
        logger.debug(f"Serial readall: {readout}")
        return readout

    def _read(self) -> bytes:
        readout = self._serial.read()
        return readout

    def _reset(self) -> None:
        self._cmd = SerialCommand()

    def wait_for_complete(self, timeout: float = 60.0) -> None:
        start = time.time()
        self._serial.reset_input_buffer()
        while abs(time.time() - start) < timeout:
            data = self._serial.read(1)
            if data.decode() == "^":
                return
        raise TimeoutError("Waiting for program to complete timed out.")

    def send(self) -> None:
        """Send current command string to VMX serial port.

        Note that sending commands just appends it to the current "program."
        The VMX chains calls itself unless cleared.
        Programs won't run until R is sent.
        """
        self._write(self._cmd)
        self._reset()

    # Start of op commands

    @Command("OP_CMDS")
    def op_cmd(self, cmd: str) -> Self:
        return self

    @MandateImmediate()
    def reset(self) -> bytes:
        self.op_cmd("res")

    @MandateImmediate(False)
    def run(self) -> Self:
        """Runs whatever is currently in the program.

        Raises:
            InvalidVMXCommandError:  Anything after a first R will be ignored.

        Returns:
            Self: VMX instance
        """
        if "R" in self._cmd:
            raise InvalidVMXCommandError("Everything after the first R is ignored.")
        return self.op_cmd("R")

    @MandateImmediate(False)
    def clear(self) -> Self:
        """C immediately clears the program in VMX memory.

        Note that inserting clear into the middle of a command has no real effect.

        Clear does not stop the current program. It only clears it in VMX memory.
        You need to use kill or decelerate to immediately stop current program.

        Returns:
            Self: VMX instance
        """
        return self.op_cmd("C")

    # Only the first `N` is run in a program (others are effectively ignored.)
    @MandateImmediate(False)
    def origin(self) -> Self:
        """Set the current position/index as the zero point for all motors.

        Raises:
            InvalidVMXCommandError: Only the first `N` is run in a program (others are effectively ignored.)

        Returns:
            Self: VMX instance
        """
        if "N" in self._cmd:
            raise InvalidVMXCommandError("Everything after the first N is ignored.")
        return self.op_cmd("N")

    @MandateImmediate()
    def echo(self, echo_state: bool = False) -> bytes:
        if echo_state:
            self.op_cmd("F")
        else:
            self.op_cmd("E")

    @MandateImmediate()
    def jog(self) -> bytes:
        self.op_cmd("J")

    # `D`, `K`, or `!` are ignored in the middle of a command.
    # Sending `D` or `K` to an active program decelerates/kills the program immediately.
    # These methods thus only support the "now" mode and cannot be chained.
    @MandateImmediate()
    def kill(self) -> bytes:
        self.op_cmd("K")

    @MandateImmediate()
    def decel(self) -> bytes:
        self.op_cmd("D")

    @MandateImmediate()
    def record_posn(self) -> bytes:
        """Records current positions in FIFO buffer.

        Only works when the VMX is actively indexing.
        """
        self.op_cmd("!")

    # Start of status commands

    @Command("STATUS_CMDS")
    def status_cmd(self, status_cmd: str) -> Self:
        return self

    @MandateImmediate()
    def verify(self) -> bytes:
        self.status_cmd("V")

    def isready(self) -> bool:
        state = self.verify()
        logger.debug(f"isready state is {state}")
        if state == b"R":
            return True
        return False

    @MandateImmediate()
    def posn(self, axis: Motor = Motor.X, recorded=False) -> bytes:
        cmd = axis.name.lower() if recorded else axis.name
        if recorded:
            cmd = axis.name.lower()
        self.status_cmd(cmd)

    # `lst` will list out current program.
    #  Anything outside of motor commands is not stored in a program.
    @MandateImmediate()
    def lst(self) -> bytes:
        self.status_cmd("lst")

    # Start of motor commands

    @MandateImmediate(False)
    def move(self, idx: int, motor: Motor = Motor.X, relative: bool = True) -> Self:
        if relative:
            self._cmd.append(VMX.IDX_INCR.format(m=motor, x=idx))
        else:
            self._cmd.append(VMX.IDX_ABS.format(m=motor, x=idx))

        return self

    @MandateImmediate(False)
    def to_limit(self, motor: Motor = Motor.X, pos: bool = True) -> Self:
        if pos:
            self._cmd.append(VMX.IDX_POS_LIMIT.format(m=motor))
        else:
            self._cmd.append(VMX.IDX_NEG_LIMIT.format(m=motor))
        return self

    @MandateImmediate(False)
    def to_zero(self, motor: Motor = Motor.X) -> Self:
        self._cmd.append(VMX.IDX_ABS_ZERO.format(m=motor))
        return self

    @MandateImmediate(False)
    def zero_posn(self, motor: Motor = Motor.X) -> Self:
        self._cmd.append(VMX.SET_ABS_ZERO.format(m=motor))
        return self

    @MandateImmediate(False)
    def speed(self, speed: int, motor: Motor = Motor.X) -> Self:
        self._cmd.append(VMX.SET_SPEED.format(m=motor, x=speed))
        return self

    @MandateImmediate(False)
    def pause(self, time: float) -> Self:
        time = round(time, 2) * 10
        self._cmd.append(VMX.SET_PAUSE.format(x=time))
        return self

    @property
    def command_que(self) -> SerialCommand:
        return self._cmd

    @command_que.setter
    def command_que(self, value: SerialCommand) -> None:
        if not isinstance(value, SerialCommand):
            raise TypeError(
                "Value assigned to command_que must be of type SerialCommand."
            )
        self._cmd = value

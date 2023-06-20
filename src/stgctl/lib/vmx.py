"""Class for VMX motor controller."""
import functools
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import IntEnum
from typing import Any
from typing import Self
from typing import TypeVar
from warnings import warn

import serial
from loguru import logger
from stgctl.core.settings import settings
from stgctl.util.ports import grep_serial_ports


class UnsupportedVmxCommandError(Exception):
    """Raised when the attempted command is not supported by the Velmex controller."""

    pass


class VmxNotReadyError(Exception):
    """Raised when the VMX indicates it is not ready."""

    pass


class InvalidVMXCommandError(Exception):
    """Raised when the VMX indicates it is not ready."""

    pass


class Motor(IntEnum):
    X = 1
    Y = 2
    Z = 3


T = TypeVar("T", bound="VMX")


class AllowNow:
    def __init__(self, func: Callable[..., T]) -> None:
        self.func = func

    def __get__(self, instance: T, owner: type[T]) -> Callable:
        @functools.wraps(self.func)
        def wrapper(now: bool = False, *args: Any, **kwargs: Any) -> T | None:
            if now:
                instance._reset()
                instance._read()
                set_method = getattr(instance, self.func.__name__)
                set_method(*args, **kwargs)
                instance.send()

                return None
            return self.func(instance, *args, **kwargs)

        return wrapper


class Command:
    def __init__(self, param_name: str) -> None:
        self.param_name = param_name

    def __call__(self, func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(instance: Any, *args: Any, **kwargs: Any) -> T:
            cmds = getattr(VMX, self.param_name)
            cmd = args[0]
            if cmd in cmds:
                instance._cmd.append(cmd)
            else:
                raise UnsupportedVmxCommandError(f"{cmd} is not a supported command.")
            return func(instance, *args, **kwargs)

        return wrapper


# @dataclass
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
    OP_CMDS: tuple[str, ...] = ("Q", "R", "N", "K", "C", "D", "E", "F", "rsm", "res")

    # Status request commands
    STATUS_CMDS: tuple[str, ...] = ("V", "X", "Y", "M", "lst")
    GET_MOTOR: str = "getM{m}M"

    def __init__(self, port=None) -> None:
        logger.info(f"{settings}")
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

    def startup(self) -> None:
        self.reset(now=True)
        time.sleep(1)
        self.echo(now=True, echo_state=True)
        wait_time = 0.1
        timeout = 5
        start_time = time.time()
        while not self.isready():
            time.sleep(wait_time)
            if abs(start_time - time.time()) > timeout:
                raise VmxNotReadyError("Connecting to the VMX has timed out.")

    def _write(self, cmd: SerialCommand) -> None:
        logger.debug(f"Writing command: {cmd}")
        self._serial.write(cmd.encode())

    def _read(self) -> bytes:
        time.sleep(0.1)
        readout = self._serial.readall()
        logger.debug(f"Serial has read out: {readout}")
        return readout

    def _reset(self) -> None:
        self._cmd = SerialCommand()

    def send(self) -> None:
        """Write to VMX serial port.

        Note that sending commands just appends it to the current "program." The VMX chains calls itself unless cleared.
        Programs won't run until R is sent.
        """
        self._write(self._cmd)
        self._reset()

    # Start of op commands

    @Command("OP_CMDS")
    def op_cmd(self, cmd: str) -> Self:
        return self

    @AllowNow
    def reset(self) -> Self:
        return self.op_cmd("res")

    # C immediately clears the command, and R immediately runs whatever is currently in the program.
    # Anything after a first R will be ignored.
    @AllowNow
    def run(self) -> Self:
        if "R" in self._cmd:
            raise InvalidVMXCommandError("Everything after the first R is ignored.")
        return self.op_cmd("R")

    @AllowNow
    def clear(self) -> Self:
        """Note that inserting clear into the middle of a command has no real effect.

        Clear does not stop the current program. It only clear it in memory.
        You need to use kill or decelerate to immediately stop current program.

        Returns:
            Self: VMX instance
        """
        return self.op_cmd("C")

    # Only the first `N` is run in a program (others are effectively ignored.)
    @AllowNow
    def origin(self) -> Self:
        return self.op_cmd("N")

    @AllowNow
    def echo(self, echo_state: bool = False) -> Self:
        if echo_state:
            self.op_cmd("F")
        else:
            self.op_cmd("E")
        return self

    # `D` or `K` are ignored in the middle of a command.
    # Sending `D` or `K` to an active program decelerates/kills the program immediately.
    # These methods thus only support the "now" mode and cannot be chained.
    def kill(self) -> Self:
        self._reset()
        self._read()
        self.op_cmd("K").send()

    def decel(self) -> Self:
        self._reset()
        self._read()
        self.op_cmd("D").send()

    # Start of status commands

    @Command("STATUS_CMDS")
    def status_cmd(self, status_cmd: str) -> Self:
        return self

    @AllowNow
    def verify(self) -> Self:
        return self.status_cmd("V")

    def isready(self) -> bool:
        self.verify(now=True)
        state = self._read()
        logger.debug(f"isready state is {state}")
        if state == b"R":
            return True
        return False

    @AllowNow
    def posn(self, axis: Motor = Motor.X) -> Self:
        return self.status_cmd(axis.name)

    # `lst` will list out current program.
    #  Anything outside of motor commands is not stored in a program.
    def lst(self) -> str:
        self.status_cmd("lst").send()
        return self._read()

    # Start of motor commands

    @AllowNow
    def move(self, steps: int, motor: Motor = Motor.X, relative: bool = True) -> Self:
        if relative:
            self._cmd.append(VMX.IDX_INCR.format(m=motor, x=steps))
        else:
            self._cmd.append(VMX.IDX_ABS.format(m=motor, x=steps))

        return self

    @AllowNow
    def to_limit(self, motor: Motor = Motor.X, pos: bool = True) -> Self:
        if pos:
            self._cmd.append(VMX.IDX_POS_LIMIT.format(m=motor))
        else:
            self._cmd.append(VMX.IDX_NEG_LIMIT.format(m=motor))
        return self

    def to_zero(self, motor: Motor = Motor.X) -> Self:
        self._cmd.append(VMX.IDX_ABS_ZERO.format(m=motor))
        return self

    @AllowNow
    def zero_posn(self, motor: Motor = Motor.X) -> Self:
        self._cmd.append(VMX.SET_ABS_ZERO.format(m=motor))
        return self

    @AllowNow
    def speed(self, speed: int, motor: Motor = Motor.X) -> Self:
        self._cmd.append(VMX.SET_SPEED.format(m=motor, x=speed))
        return self

    @AllowNow
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


# Notes on how old code behaved:
# data_taking_wait_time is at every step
# However, "if already there" (eg at start or turnaround), only data_taking_wait_time is waited, step_wait_time is skipped!
class XYStages:
    def __init__(self):
        self.VMX = VMX()

    def set_trajectory(self, relative=False):
        self._trajectory = get_trajectory()

    @property
    def trajectory(self):
        return self._trajectory


def get_trajectory():
    """Get array of coordinates giving trajectory."""
    raise NotImplementedError

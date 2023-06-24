"""Class for VMX motor controller."""
import functools
import time
from collections.abc import Callable
from enum import IntEnum
from pprint import pformat
from typing import Any
from typing import Self
from typing import TypeVar

import serial
from loguru import logger
from stgctl.core.settings import settings
from stgctl.lib.exceptions import InvalidVMXCommandError
from stgctl.lib.exceptions import UnsupportedVmxCommandError
from stgctl.lib.exceptions import VmxNotReadyError
from stgctl.util.ports import grep_serial_ports


class Motor(IntEnum):
    """Enum to abstract away motor numbers."""

    X = 1
    Y = 2
    Z = 3


# A generic used to represent the return type of the VMX class
T = TypeVar("T", bound="VMX")


class MandateImmediate:
    """Decorator class for commands that should be executed immediately."""

    def __init__(self, immediate: bool = True) -> None:
        """Initialize MandateImmediate.

        Args:
            immediate (bool, optional):
                If True, the command must be executed immediately,
                if False, the command can be queued for later send. (default: True).
        """
        self.immediate: bool = immediate

    def __call__(self, func: Callable[..., T]) -> Callable[..., T]:
        """Allows the MandateImmediate to accept parameters.

        Args:
            func (Callable[..., T]): The function to be wrapped.

        Returns:
            Callable[..., T]: The wrapped function.
        """
        # argument of decorator
        # If True, use the function wrapper that corresponds to immediately sending a command and reading out.
        if self.immediate:

            @functools.wraps(func)
            def wrapper(instance: Any, *args: Any, **kwargs: Any) -> T | None:
                # Take the VMX instance and reset it
                instance._reset()
                # Reset serial buffer so we don't get any old VMX responses
                instance._serial.reset_input_buffer()
                # call the decorated method, which adds single command to queue
                func(instance, *args, **kwargs)
                # send command
                instance.send()
                # return readout
                return instance._readall()

            return wrapper
        else:
            # When immediate=False, use this wrapper
            # which corresponds to methods that can be queued (and method chained)
            # these methods also support sending "now", which behaves similarly to above
            @functools.wraps(func)
            def wrapper(
                instance: Any, now: bool = False, *args: Any, **kwargs: Any
            ) -> T | None:
                if now:
                    # see above wrapper comments.
                    instance._reset()
                    instance._serial.reset_input_buffer()
                    func(instance, *args, **kwargs)
                    instance.send()

                    return instance._readall()
                else:
                    # if not now, just return the called method (ie self)
                    return func(instance, *args, **kwargs)

            return wrapper


class Command:
    """A decorator class to create factory method for categorizing commands."""

    def __init__(self, cmd_type: str) -> None:
        """Initialize Command instance.

        Args:
            cmd_type (str): category of command that method falls under
        """
        self.cmd_type = cmd_type

    def __call__(self, func: Callable[..., T]) -> Callable[..., T]:
        """Makes the Command instance callable and uses it as a decorator to wrap a function that will execute a command.

        Args:
            func (Callable[..., T]): The function to wrap that executes a command.

        Returns:
            Callable[..., T]: The wrapped function that executes a command only if it's supported.
        """

        @functools.wraps(func)
        def wrapper(instance: T, *args: Any, **kwargs: Any) -> T:
            # get allowed list of commands from class variable for command type passed to decorator
            allowed_cmds = getattr(instance, self.cmd_type)
            # the factory method's invoked command
            cmd = args[0]
            #  check if command is valid
            if cmd in allowed_cmds:
                instance._cmd.append(cmd)
            else:
                raise UnsupportedVmxCommandError(f"{cmd} is not a supported command.")
            return func(instance, *args, **kwargs)

        return wrapper


class SerialCommand(list):
    """A custom list class specifically for storing Velmex program commands as strings."""

    def ___init__(self, iterable: list[str] = []):
        """Initializes an instance of the SerialCommand class.

        Args:
            iterable (list[str], optional): A list of command strings to initialize the SerialCommand with. Defaults to an empty list.
        """
        # Call the parent list's init function to populate it with the provided iterable,
        # converting each item into a string
        super().__init__(str(item) for item in iterable)

    def __setitem__(self, index, item):
        """Overloaded method to set an item at a specific position in the list, ensuring that the item is converted to a string."""
        # Convert the item to string and then call the parent list's setitem function
        super().__setitem__(index, str(item))

    def __repr__(self) -> str:
        """Overrides the default representation of the SerialCommand list to be a comma-separated string of its items.

        Returns:
            str: A string representation of the SerialCommand list.
        """
        # Join all items in the list into a single string, separated by commas
        return ",".join(self)

    def insert(self, index, item):
        """Overloaded method to insert an item at a specific position in the list, ensuring that the item is converted to a string."""
        # Convert the item to string and then call the parent list's insert function
        super().insert(index, str(item))

    def append(self, item):
        """Overloaded method to append an item to the end of the list, ensuring that the item is converted to a string."""
        # Convert the item to string and then call the parent list's append function
        super().append(str(item))

    def extend(self, other):
        """Overloaded method to extend the list with items from another list or iterable, ensuring that each new item is converted to a string."""
        # Check if the other object is of the same type (SerialCommand)
        if isinstance(other, type(self)):
            super().extend(other)
        else:
            # If other object is not of the same type, convert each item to string before extending the list
            super().extend(str(item) for item in other)

    def encode(self):
        """Encodes the comma-separated string representation of the list into bytes.

        Returns:
            bytes: The byte-encoded string representation of the SerialCommand list.
        """
        # Join all items in the list into a single string, separated by commas, and then encode it into bytes
        joined = ",".join(self)
        return joined.encode()

    @property
    def encoded(self):
        """Property that provides the byte-encoded string representation of the SerialCommand list.

        Returns:
            bytes: The byte-encoded string representation of the SerialCommand list.
        """
        # Use the encode method to get the byte-encoded string representation of the list
        return self.encode()


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
        """Initialize a VMX instance.

        Args:
            port (str, optional): The port on which the motor controller is connected.
            If not provided, the port will be determined automatically.
        """
        logger.debug(f"Using settings:\n{pformat(settings.dict())}")
        if not port:
            # grep for serial ports using regex provided in settings
            matched_serial_ports = grep_serial_ports(settings.VMX_DEVICE_REGEX)
            logger.debug(f"Matched serial ports: {matched_serial_ports}")
            if settings.VMX_DEVICE_PORT:
                # if the port is explicitly given, use it
                port = settings.VMX_DEVICE_PORT
            elif matched_serial_ports:
                # Take first port if multiple are matched.
                port = matched_serial_ports[0].device
                logger.success(
                    f"Found serial device matching regex {settings.VMX_DEVICE_REGEX}: {matched_serial_ports[0].name}"
                )
                if len(matched_serial_ports) > 1:
                    logger.warning(
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
        # start startup sequence.
        self.startup()

    def __enter__(self) -> Self:
        return self

    def __exit__(self) -> None:
        self.close()

    def __del__(self) -> None:
        self.close()

    def startup(self) -> None:
        """Initialize VMX.

        Puts it in jog mode, resetting it to power on state,
        and waiting for "R" response.


        Raises:
            VmxNotReadyError: Returns error if VMX does not send ready response
        """
        # If VMX receives reset command while in on-line (E or F) mode,
        # it will error out (eg respond to V status request with B)
        # Put into jogging mode first.
        self.jog()
        # Reset, returns to powered-on state
        self.reset()
        # Give it time to restart
        time.sleep(1)
        # Set state to online with echo on
        self.echo(echo_state=True)
        wait_time = 0.1
        timeout = 5
        # After activating online state, may delay returning ready state
        start_time = time.time()
        while not self.isready():
            time.sleep(wait_time)
            if abs(start_time - time.time()) > timeout:
                raise VmxNotReadyError("Connecting to the VMX has timed out.")

    def close(self) -> None:
        """Close VMX by closing out serial connection."""
        # Account for case where object is closed before serial port is initialized
        # eg when port finding fails
        if hasattr(self, "_serial"):
            logger.debug("Closing serial connection to VMX.")
            self._serial.close()

    def _write(self, cmd: SerialCommand) -> None:
        """Private method for writing commands to VMX.

        Args:
            cmd (SerialCommand): Serial command to send to VMX
        """
        logger.debug(f"Writing command: {cmd}")
        self._serial.write(cmd.encode())

    def _readall(self) -> bytes:
        """Private readall method for reading out entire serial buffer.

        Returns all bytes from serial buffer

        Returns:
            bytes: Returned bytes from serial buffer.
        """
        # Since most commands using read write first, need to always wait for response
        time.sleep(0.1)
        readout = self._serial.readall()
        logger.debug(f"Serial readall: {readout}")
        return readout

    def _read(self) -> bytes:
        """Private method wrapping reading last entry in serial buffer.

        Returns:
            bytes: Returned bytes from serial buffer
        """
        readout = self._serial.read()
        return readout

    def _reset(self) -> None:
        """Private method for resetting command que."""
        self._cmd = SerialCommand()

    def wait_for_complete(self, timeout: float = 60.0) -> None:
        """_Wait until VMX program returns program-complete response.

        Typically used in try-except-finally block.

        Args:
            timeout (float, optional): Time to wait until program considered a failure. Defaults to 60.0.

        Raises:
            TimeoutError: Raised when program takes longer than timeout.
        """
        start = time.time()
        # We want to clear anything int he buffer so we do not
        # accidentally pick up old program complete responses
        self._serial.reset_input_buffer()
        while abs(time.time() - start) < timeout:
            data = self._serial.read(1)
            # VMX returns ^ when program completes
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
        # clear command que
        self._reset()

    # Start of op commands

    @Command("OP_CMDS")
    def op_cmd(self, cmd: str) -> Self:
        """Operation command decorator. Appends the operation command to the current command sequence.

        Args:
            cmd (str): The operation command to be appended.

        Returns:
            Self: The VMX instance.
        """
        return self

    @MandateImmediate()
    def reset(self) -> bytes:
        """Reset the VMX to power-on state."""
        self.op_cmd("res")

    @MandateImmediate(False)
    def run(self) -> Self:
        """Runs whatever is currently in the program memory.

        Appends R to the command queue.

        Supports running with `now`.

        Raises:
            InvalidVMXCommandError:  Anything after a first R will be ignored.

        Returns:
            Self: VMX instance
        """
        # check if R already in queue
        if "R" in self._cmd:
            raise InvalidVMXCommandError("Everything after the first R is ignored.")
        return self.op_cmd("R")

    @MandateImmediate(False)
    def clear(self) -> Self:
        """C immediately clears the program in VMX memory.

        Appends C to the command queue.

        Supports running with `now`.

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

        Appends N to the commamd queue

        Supports running with `now`

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
        """Set the echo mode.

        Args:
            echo_state (bool, optional): The state to set the echo mode to. Defaults to False.
            False is no-echo, or F. The VMX does not send the command written to serial to the serial buffer.

        Returns:
            bytes: The current echo mode setting if echo_state is not given, or an acknowledgement of setting echo mode if it is.
        """
        if echo_state:
            self.op_cmd("F")
        else:
            self.op_cmd("E")

    @MandateImmediate()
    def jog(self) -> bytes:
        """Set VMX to jog mode (the default when powered on).

        Returns:
            bytes: VMX response
        """
        self.op_cmd("J")

    # `D`, `K`, or `!` are ignored in the middle of a command.
    # Sending `D` or `K` to an active program decelerates/kills the program immediately.
    # These methods thus only support the "now" mode and cannot be chained.
    @MandateImmediate()
    def kill(self) -> bytes:
        """_Immediately stop the current program.

        Decel should be highly favored over kill, as kill immediately cuts power to the motors,
        and can cause the motor to lose its position.

        Returns:
            bytes: VMX response
        """
        self.op_cmd("K")

    @MandateImmediate()
    def decel(self) -> bytes:
        """Immediately end current program and stop the motors, safely.

        Returns:
            bytes: VMX response.
        """
        self.op_cmd("D")

    @MandateImmediate()
    def record_posn(self) -> bytes:
        """Records current positions in FIFO buffer.

        Only works when the VMX is actively indexing.

        Returns:
            bytes: VMX response
        """
        self.op_cmd("!")

    # Start of status commands

    @Command("STATUS_CMDS")
    def status_cmd(self, status_cmd: str) -> Self:
        """Status command decorator. Appends the operation command to the current command sequence.

        Args:
            status_cmd (str): The status command to be appended.

        Returns:
            Self: The VMX instance.
        """
        return self

    @MandateImmediate()
    def verify(self) -> bytes:
        """Query the VMX state.

        Returns:
            bytes: VMX state: "J" jog, "R" ready, or "B" bad
        """
        self.status_cmd("V")

    def isready(self) -> bool:
        """Checks for VMX ready response.

        Returns:
            bool: If the VMX returns R, returns True.
        """
        # query state of VMX
        state = self.verify()
        logger.debug(f"isready state is {state}")
        if state == b"R":
            return True
        return False

    @MandateImmediate()
    def posn(self, axis: Motor = Motor.X, recorded=False) -> bytes:
        """Queries motor position for a particular axis.

        Args:
            axis (Motor, optional): Which motor to query index. Defaults to Motor.X.
            recorded (bool, optional): Whether to query recorded indexes. Defaults to False.

        Returns:
            bytes: If recorded, gives last 4 indexes where; these are cleared at the start of every program
                   Otherwise, current index of selected motor.
        """
        # command to query recorded positions is just lower case of current
        cmd = axis.name.lower() if recorded else axis.name
        self.status_cmd(cmd)

    @MandateImmediate()
    def lst(self) -> bytes:
        """`lst` will list out current program.

        Anything outside of motor commands is not stored in a program.

        Returns:
            bytes: Current program command string
        """
        self.status_cmd("lst")

    # Start of motor commands

    @MandateImmediate(False)
    def move(self, idx: int, motor: Motor = Motor.X, relative: bool = True) -> Self:
        """Index motor specific number of steps, or to a particular index.

        Supports absolute and relative indexing.

        Args:
            idx (int): where to index, in steps
            motor (Motor, optional): Motor to index. Defaults to Motor.X.
            relative (bool, optional): Whether position is relative to current position. Defaults to True.

        Returns:
            Self: VMX instance with appended commands.
        """
        if relative:
            self._cmd.append(VMX.IDX_INCR.format(m=motor, x=idx))
        else:
            self._cmd.append(VMX.IDX_ABS.format(m=motor, x=idx))

        return self

    @MandateImmediate(False)
    def to_limit(self, motor: Motor = Motor.X, pos: bool = True) -> Self:
        """Index until reaching a limit switch.

        Appends command to index to limit switch to command queue.

        Supports running with `now`.

        Args:
            motor (Motor, optional): . Which motor to index to Motor.X.
            pos (bool, optional): Index to the positive limit switch. Defaults to True.

        Returns:
            Self: VMX instance with appended commands.
        """
        if pos:
            self._cmd.append(VMX.IDX_POS_LIMIT.format(m=motor))
        else:
            self._cmd.append(VMX.IDX_NEG_LIMIT.format(m=motor))
        return self

    @MandateImmediate(False)
    def to_zero(self, motor: Motor = Motor.X) -> Self:
        """Index to motor zero point.

        Appends command to index to limit switch to command queue.

        Supports running with `now`.

        Args:
            motor (Motor, optional): Which motor to index to its zero point. Defaults to Motor.X.

        Returns:
            Self: VMX instance with appended commands.
        """
        self._cmd.append(VMX.IDX_ABS_ZERO.format(m=motor))
        return self

    @MandateImmediate(False)
    def zero_posn(self, motor: Motor = Motor.X) -> Self:
        """Set current position as zero index for motor.

        Behaves similarly to origin, but only for one motor.

        Supports running with `now`.

        Args:
            motor (Motor, optional): Motor to zero index. Defaults to Motor.X.

        Returns:
            Self: VMX wirh appended command.
        """
        self._cmd.append(VMX.SET_ABS_ZERO.format(m=motor))
        return self

    @MandateImmediate(False)
    def speed(self, speed: int, motor: Motor = Motor.X) -> Self:
        """Set speed in idx/sec for motor.

        This setting is saved across programs if not explicitly set.

        Supports running with `now`.

        Args:
            speed (int): speed in idx/sec
            motor (Motor, optional): Motor to set speed for. Defaults to Motor.X.

        Returns:
            Self: VMX with appended commands.
        """
        self._cmd.append(VMX.SET_SPEED.format(m=motor, x=speed))
        return self

    @MandateImmediate(False)
    def pause(self, time: float) -> Self:
        """Pause program for _time_ seconds.

        Args:
            time (float): Time, in seconds, to pause

        Returns:
            Self: VMX instance with appended commands.
        """
        time = round(time, 2) * 10
        self._cmd.append(VMX.SET_PAUSE.format(x=time))
        return self

    @property
    def command_queue(self) -> SerialCommand:
        """Current SerialCommand list containing commands to be sent on next call to send.

        Returns:
            SerialCommand: list of serial commands
        """
        return self._cmd

    @command_queue.setter
    def command_queue(self, value: SerialCommand) -> None:
        """Retrieve currently queued commands.

        Args:
            value (SerialCommand): SerialCommand list of the VMX program that will be sent on next call to send.

        Raises:
            TypeError: Raises error when type is other than SerialCommand.
        """
        if not isinstance(value, SerialCommand):
            raise TypeError(
                "Value assigned to command_que must be of type SerialCommand."
            )
        self._cmd = value

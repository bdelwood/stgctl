"""Abstraction class over Fabric for running discrete remote commands."""

from enum import StrEnum

from fabric import Connection, Result

from stgctl.core.settings import settings


class SignalCommand(StrEnum):
    """Enum to hold command strings."""

    START_AQ = settings.START_AQ_CMD
    END_AQ = settings.END_AQ_CMD
    CONT_AQ = settings.CONTINUE_AQ_CMD


class Signaller:
    """Communicate with a remote host for controlling the data acquisition process.

    Args:
        host (str): remote host to execute commands on
        user (str | None, optional): User for remote connection. Defaults to None.
    """

    def __init__(self, host: str, user: str | None = None) -> None:
        self.connection = Connection(host, user)

    def start_aq(self) -> Result:
        """Send start acquisition signal.

        Start signal is defined by START_AQ_CMD

        Returns:
            Result: result of remote command
        """
        return self.signal(SignalCommand.START_AQ)

    def end_aq(self) -> Result:
        """Send end acquisition signal.

        Returns:
            Result: result of remote command.
        """
        return self.signal(SignalCommand.END_AQ)

    def cont_aq(self) -> Result:
        """Send continue acquisition signal.

        Returns:
            Result: result of remote command.
        """
        return self.signal(SignalCommand.CONT_AQ)

    def signal(self, cmd: str) -> Result:
        """Thin wrapper around Fabric Connection.

        Args:
            cmd (str): remote command to run

        Returns:
            Result: result of remote command
        """
        return self.connection.run(cmd, hide=True)

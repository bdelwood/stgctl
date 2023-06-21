from enum import StrEnum

from fabric import Connection
from fabric import Result
from stgctl.core.settings import settings


class SignalCommand(StrEnum):
    START_AQ = settings.START_AQ_CMD
    END_AQ = settings.END_AQ_CMD


class Signaller:
    def __init__(self, gcp_host: str, gcp_user: str | None = None) -> None:
        self.gcp_connection = Connection(gcp_host, gcp_user)

    def start_aq(self) -> Result:
        return self.signal(SignalCommand.END_AQ)

    def end_aq(self) -> Result:
        return self.signal(SignalCommand.START_AQ)

    def signal(self, cmd: str) -> Result:
        return self.gcp_connection.run(cmd, hide=True)

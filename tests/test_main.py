"""Test cases for the __main__ module."""

import pytest
from typer.testing import CliRunner

from stgctl.cli import cli


@pytest.fixture
def runner() -> CliRunner:
    """Fixture for invoking command-line interfaces."""
    return CliRunner()


def test_main_succeeds(runner: CliRunner) -> None:
    """It exits with a status code of zero."""
    result = runner.invoke(cli, ["stages"])
    assert result.exit_code == 0

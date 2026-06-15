"""Test cases for the cli module."""

from importlib import metadata

import pytest
from rich.console import Console

from stgctl.cli import cli


@pytest.fixture
def console() -> Console:
    """Deterministic console so cyclopts output is stable to assert against."""
    return Console(width=80, force_terminal=True, highlight=False, color_system=None)


def test_stages_group_shows_help() -> None:
    """Invoking the 'stages' group with no subcommand shows help and exits 0."""
    with pytest.raises(SystemExit) as exc_info:
        cli(["stages"])
    assert exc_info.value.code == 0


def test_version_flag(capsys: pytest.CaptureFixture[str], console: Console) -> None:
    """'--version' prints the installed package version and exits 0."""
    with pytest.raises(SystemExit) as exc_info:
        cli(["--version"], console=console)
    assert exc_info.value.code == 0
    assert metadata.version("stgctl") in capsys.readouterr().out


def test_run_rejects_incompatible_options(
    capsys: pytest.CaptureFixture[str], console: Console
) -> None:
    """Cross-option validation rejects --no-signal outside the 'raster' sequence."""
    with pytest.raises(SystemExit) as exc_info:
        cli(["stages", "run", "startup", "--no-signal"], console=console)
    assert exc_info.value.code != 0
    captured = capsys.readouterr()
    assert "raster" in captured.out + captured.err

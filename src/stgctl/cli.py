"""Command line interface for stgctl."""

from importlib import metadata
from typing import Annotated
from typing import Optional

import typer
from loguru import logger as logger

from stgctl.lib.stage import XYStage


cli = typer.Typer()


__version__ = metadata.version(__package__)


def version_callback(value: bool):
    """Print version information.

    Args:
        value (bool): typer expects callback to accept bool
    """
    if value:
        typer.echo(f"{__version__}")


@cli.command()
def stages(
    raster: Annotated[
        bool, typer.Option("--raster", help="Run stage raster sequence.")
    ] = False,
    home: Annotated[
        bool, typer.Option("--home", help="Run stage homing sequence.")
    ] = False,
    test_signal: Annotated[
        bool, typer.Option("--test-signal", help="Run signal testing sequence")
    ] = False,
    no_signal: bool = typer.Option(
        False, "--no-signal", help="Run raster without signal."
    ),
):
    """Subcommand for controlling XY stage."""
    # We want to make --raster and --home mutually exclusive.
    # raster runs home, so running both together is redundant.
    # Then there is the question of what order they should be run in.
    if sum([home, raster, test_signal]) >= 2:
        raise typer.BadParameter(
            "Raster runs homing sequence. Options are mutually exclusive."
        )
    if no_signal and not raster:
        raise typer.BadParameter("--no-signal option is only applicable with --raster.")
    if raster or home or test_signal:
        logger.info("Initializing stages.")
        stg = XYStage()
        if raster:
            logger.info("Entering rastering mode.")
            stg.startup()
            stg.raster()
            stg.raster(signal=not no_signal)
        elif home:
            logger.info("Entering homing mode.")
            stg.home()
        elif test_signal:
            logger.info("Running signal test sequence.")
            stg.test_signal_setup()


@cli.command()
def vmx():
    """Subcommand for controlling VMX directly."""
    raise NotImplementedError("VMX command line interface not implemented yet.")


@cli.callback(invoke_without_command=True)
def main(
    version: Annotated[
        Optional[bool],
        typer.Option("--version", callback=version_callback, is_eager=True),
    ] = None,
):
    """Callback for main function to allow --version option without any subcommands."""
    pass


# click object for docs
typer_click_object = typer.main.get_command(cli)

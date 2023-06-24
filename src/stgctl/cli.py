"""Command line interface for stgctl."""

from typing import Annotated

import typer
from loguru import logger as logger

from stgctl.lib.stage import XYStage


cli = typer.Typer()


@cli.command()
def stages(
    raster: Annotated[
        bool, typer.Option("--raster", help="Run stage raster sequence.")
    ] = False,
    home: Annotated[
        bool, typer.Option("--home", help="Run stage homing sequence.")
    ] = False,
):
    """Subcommand for controlling XY stage."""
    # We want to make --raster and --home mutually exclusive.
    # raster runs home, so running both together is redundant.
    # Then there is the question of what order they should be run in.
    if raster and home:
        raise typer.BadParameter(
            "Raster runs homing sequence. Options are mutually exclusive."
        )
    if raster or home:
        logger.info("Initializing stages.")
        stg = XYStage()
        if raster:
            logger.info("Entering rastering mode.")
            stg.startup()
            stg.raster()
        elif home:
            logger.info("Entering homing mode.")
            stg.home()


@cli.command()
def vmx():
    """Subcommand for controlling VMX directly."""
    raise NotImplementedError("VMX command line interface not implemented yet.")


# click object for docs
typer_click_object = typer.main.get_command(cli)

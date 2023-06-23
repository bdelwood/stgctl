"""Command line interface for stgctl."""

from typing import Annotated

import typer
from loguru import logger

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
    logger.info("Initializing stages.")

    logger.debug(f"{raster and home}")
    if raster and home:
        raise typer.BadParameter(
            "Raster runs homing sequence. Options are mutually exclusive."
        )

    stg = XYStage()
    if raster:
        logger.info("Entering rastering mode.")
        stg.startup()
        stg.raster()
    if home:
        logger.info("Entering homing mode.")
        stg.home()


@cli.command()
def vmx():
    """Subcommand for controlling VMX directly."""
    raise NotImplementedError("VMX command line interface not implemented yet.")

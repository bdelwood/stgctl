from typing import Optional

import typer
from loguru import logger

from stgctl.lib.stage import XYStage


cli = typer.Typer()


@cli.command()
def stages(
    raster: bool | None = False,
    home: bool | None = False,
):
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
    raise NotImplementedError("VMX command line interface not implemented yet.")

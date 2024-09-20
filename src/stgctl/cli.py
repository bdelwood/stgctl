"""Command line interface for stgctl."""

import json
from importlib import metadata
from typing import Annotated, Optional

import typer
from loguru import logger as logger

from stgctl.lib.stage import XYStage
from stgctl.schema.models import Size

cli = typer.Typer()

stages_cli = typer.Typer()


__version__ = metadata.version(__package__)


def version_callback(value: bool):
    """Print version information.

    Args:
        value (bool): typer expects callback to accept bool
    """
    if value:
        typer.echo(f"{__version__}")


@stages_cli.command()
def run(
    sequence: str = typer.Argument(
        ..., help="The sequence to run: 'startup', 'raster', 'home', or 'test-signal'."
    ),
    no_signal: bool = typer.Option(
        False, "--no-signal", help="Run raster without signal."
    ),
    save_ls_posns: bool = typer.Option(
        False, "--save-ls-posns", help="Save limit switch positions after startup."
    ),
    use_saved: bool = typer.Option(
        False,
        "--use-saved",
        help="Use saved limit switch positions. Must be in proper format.",
    ),
):
    """Run stage sequences.

    Valid sequences: 'startup', 'raster', 'home', or 'test-signal'."
    """
    if sequence not in ["startup", "raster", "home", "test-signal"]:
        raise typer.BadParameter(
            "Invalid sequence. Must be one of 'startup', 'raster', 'home', or 'test-signal'."
        )

    if no_signal and sequence != "raster":
        raise typer.BadParameter(
            "--no-signal option is only applicable with 'raster' sequence."
        )

    if save_ls_posns and sequence != "startup":
        raise typer.BadParameter(
            "--save-ls-posns option is only applicable with 'startup' sequence."
        )

    if use_saved and sequence != "raster":
        raise typer.BadParameter(
            "--use-saved option is only applicable with 'raster' sequence."
        )

    typer.echo(f"Running {sequence} sequence.")

    logger.info("Initializing stages.")
    stg = XYStage()

    # switch based on sequence argument
    match sequence:
        case "startup":
            # startup logic
            logger.info("Running startup squence.")
            stg.startup(save=save_ls_posns)
        case "raster":
            # rastering logic
            logger.info("Entering rastering mode.")
            if use_saved:
                logger.info("Loading limit switch positions.")
                with open("limit_switch_positions.json") as f:
                    stg.limit_switch_positions = json.load(f)
                stg.home()
            else:
                stg.startup()
            stg.raster(signal=not no_signal)
        case "home":
            # homing logic
            logger.info("Entering homing mode.")
            stg.home()
        case "test-signal":
            # test signal logic
            logger.info("Running signal test sequence.")
            stg.test_signal_setup()


@stages_cli.command()
def goto(
    x: int = typer.Argument(..., help="The X index to move to."),
    y: int = typer.Argument(..., help="The Y index to move to."),
    relative: bool = typer.Option(
        False, "--relative", "-r", help="Move relative to the current position."
    ),
    speed: int = typer.Option(1500, "--speed", "-s", help="Stage speed in idx/s."),
):
    """Move the stages to the specified X and Y indices."""
    typer.echo(
        f"Moving stages to X: {x}, Y: {y}, relative: {relative}, speed: {speed} idx/s"
    )

    # Initialize the XYStage instance
    stg = XYStage()

    # Call the goto method with the passed coordinates
    coord = Size(X=x, Y=y)
    stg.goto(coord=coord, relative=relative, speed=speed)


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


# adding subcommand under stages
cli.add_typer(stages_cli, name="stages", help="Run sequences.")

# click object for docs
typer_click_object = typer.main.get_command(cli)

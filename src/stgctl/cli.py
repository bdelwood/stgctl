"""Command line interface for stgctl."""

import json
from typing import Annotated, Literal

from cyclopts import App, Parameter
from loguru import logger

from stgctl.lib.stage import XYStage
from stgctl.schema.models import Size

cli = App(
    name="stgctl",
    help="Control software for a pair of Velmex XY stages.",
)

stages_cli = App(name="stages", help="Run sequences.")
cli.command(stages_cli)


def validate_run(**kwargs: object) -> None:
    """Reject option/sequence combinations that don't make sense together."""
    sequence = kwargs["sequence"]
    if kwargs.get("no_signal") and sequence != "raster":
        raise ValueError("--no-signal is only applicable with the 'raster' sequence.")
    if kwargs.get("save_ls_posns") and sequence != "startup":
        raise ValueError(
            "--save-ls-posns is only applicable with the 'startup' sequence."
        )
    if kwargs.get("use_saved") and sequence != "raster":
        raise ValueError("--use-saved is only applicable with the 'raster' sequence.")


@stages_cli.command(validator=validate_run)
def run(
    sequence: Annotated[
        Literal["startup", "raster", "home", "test-signal"],
        Parameter(help="The sequence to run."),
    ],
    *,
    no_signal: Annotated[
        bool, Parameter(help="Run raster without signal.", negative=())
    ] = False,
    save_ls_posns: Annotated[
        bool,
        Parameter(help="Save limit switch positions after startup.", negative=()),
    ] = False,
    use_saved: Annotated[
        bool,
        Parameter(
            help="Use saved limit switch positions. Must be in proper format.",
            negative=(),
        ),
    ] = False,
) -> None:
    """Run stage sequences."""
    cli.console.print(f"Running {sequence} sequence.")

    logger.info("Initializing stages.")
    stg = XYStage()

    # switch based on sequence argument
    match sequence:
        case "startup":
            # startup logic
            logger.info("Running startup sequence.")
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


@stages_cli.command
def goto(
    x: Annotated[int, Parameter(help="The X index to move to.")],
    y: Annotated[int, Parameter(help="The Y index to move to.")],
    *,
    relative: Annotated[
        bool,
        Parameter(
            name=["--relative", "-r"],
            help="Move relative to the current position.",
            negative=(),
        ),
    ] = False,
    speed: Annotated[
        int, Parameter(name=["--speed", "-s"], help="Stage speed in idx/s.")
    ] = 1500,
) -> None:
    """Move the stages to the specified X and Y indices."""
    cli.console.print(
        f"Moving stages to X: {x}, Y: {y}, relative: {relative}, speed: {speed} idx/s"
    )

    # Initialize the XYStage instance
    stg = XYStage()

    # Call the goto method with the passed coordinates
    coord = Size(X=x, Y=y)
    stg.goto(coord=coord, relative=relative, speed=speed)


@cli.command
def vmx() -> None:
    """Subcommand for controlling VMX directly."""
    raise NotImplementedError("VMX command line interface not implemented yet.")

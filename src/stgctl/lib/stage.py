"""Class to provide quick API for controlling two Velmex stages."""

import json
import time

import numpy
from loguru import logger

from stgctl.core.settings import settings
from stgctl.lib.signal import Signaller
from stgctl.lib.vmx import VMX, Motor, SerialCommand
from stgctl.schema.models import Size
from stgctl.util.trajectory import (
    gen_2d_trajectory,
    interleaved_row_order,
    plot_trajectory,
)


class XYStage:
    """Abstraction over VMX class. Useful for controlling XY stages.

    On initialization, sets up the VMX, grid size, step size, observing time, and
    signaller based on the values specified in the .env settings.

    The VMX provides an interface for controlling Velmex stepper motors, and is used
    here to control the motion of the XY stage. The grid size and step size define the
    motion parameters for the stage, and the observing time defines the time the stage
    spends at each grid point.

    The signaller is used to communicate with a remote host for controlling the data
    acquisition process.

    Args:
        dry_run (bool): Plot raster trajectories without initializing hardware or
            signaling. Defaults to False.
    """

    DRY_RUN_LIMIT_SWITCH_POSITIONS = (
        (0, 0),
        (0, -10_000),
        (-10_000, -10_000),
        (-10_000, 0),
        (0, 0),
    )

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        if not dry_run:
            # Initialize VMX device
            self.VMX = VMX(port=settings.VMX_DEVICE_PORT)
        self._limit_switch_positions = (
            list(self.DRY_RUN_LIMIT_SWITCH_POSITIONS) if dry_run else None
        )
        # Grab settings for rastering, gather into Size enum
        self.grid_size = Size(*settings.GRID_SIZE)
        self.step_size = (
            Size(*settings.STEP_SIZE) if settings.STEP_SIZE else settings.STEP_SIZE
        )
        self.observing_time = settings.OBSERVE_TIME
        self.continuous_raster_interleave = settings.CONTINUOUS_RASTER_INTERLEAVE
        if not dry_run:
            # Set up remote command execution
            self.signaller = Signaller(settings.SIGNAL_HOST, settings.SIGNAL_USER)

    def _require_hardware(self) -> None:
        """Reject hardware-only operations during a dry run."""
        if self.dry_run:
            raise RuntimeError("This operation is unavailable in dry-run mode.")

    def startup(self, save: bool = False):
        """Run startup sequence.

        Homes the stages to +X,+Y limit switches.
        Records locations of limit switches.
        """
        self._require_hardware()
        logger.info(
            "Sending stages to the four limit switches to get index counts for raster."
        )

        # Go to +X, +Y limit switches, set origin
        self.home()
        # +X,+Y is (0,0) by definition
        limit_switch_positions = [(0, 0)]

        # +X,+Y > +X,-Y > -X,-Y > -X,+Y > +X,+Y
        switch_values = [(True, False), (False, False), (False, True), (True, True)]
        for switch_value in switch_values:
            #  Go to -X, -Y limit switches then record position

            self.VMX.clear().speed(motor=Motor.X, speed=settings.MAX_SPEED).speed(
                motor=Motor.Y, speed=settings.MAX_SPEED
            ).to_limit(motor=Motor.X, pos=switch_value[0]).to_limit(
                motor=Motor.Y, pos=switch_value[1]
            ).run().send()
            # VMX.wait_for_complete can timeout
            # Timeout needs to be reasonably longer than individual commands.
            try:
                self.VMX.wait_for_complete(timeout=600)
                logger.info(
                    f"Stages have finished indexing to \
                    ({'+' if switch_value[0] else '-'}X,{'+' if switch_value[1] else '-'}Y) \
                    limit switches."
                )
                # Get motor positions after
                x_motor_idx = int(self.VMX.posn(axis=Motor.X).decode().strip())
                y_motor_idx = int(self.VMX.posn(axis=Motor.Y).decode().strip())
                logger.debug(
                    f"VMX reports stage position ({x_motor_idx},{y_motor_idx})."
                )
                limit_switch_positions.append((x_motor_idx, y_motor_idx))
            except TimeoutError:
                logger.debug("Waiting for VMX program to complete timed out.")
                return

        logger.info("Stages have recorded limit switch positions.")
        self.limit_switch_positions = limit_switch_positions

        if save:
            save_path = "limit_switch_positions.json"
            with open(save_path, "w") as f:
                json.dump(self.limit_switch_positions, f)
            logger.info(f"Saved limit switch positions to {save_path}")

    def load_limit_switch_positions(self) -> None:
        """Load limit switch positions from ``limit_switch_positions.json``."""
        load_path = "limit_switch_positions.json"
        with open(load_path) as f:
            self.limit_switch_positions = json.load(f)
        logger.info(f"Loaded limit switch positions from {load_path}")

    def home(self) -> None:
        """Run homing sequence.

        Indexes to positive limit switches. Once there, sets it as the origin.
        """
        self._require_hardware()
        logger.info("Sending stages to positive limit switches.")
        self.VMX.clear().speed(motor=Motor.X, speed=settings.MAX_SPEED).speed(
            motor=Motor.Y, speed=settings.MAX_SPEED
        ).to_limit(motor=Motor.X, pos=True).to_limit(
            motor=Motor.Y, pos=True
        ).run().send()
        # VMX.wait_for_complete can timeout
        # Timeout needs to be reasonably longer than individual commands.
        try:
            self.VMX.wait_for_complete(timeout=600)
            logger.info("Stages have finished indexing to the positive limit switches.")
            # Set origin to current location (should be +X,+Y limit switches)
            self.VMX.clear().origin().send()
            logger.info("Origin set.")
            return
        except TimeoutError:
            logger.warning(
                "Waiting for VMX program to complete timed out. The stages could be anywhere."
            )

    def raster(self, signal: bool = True) -> None:
        """Perform a grid raster.

        If step size omitted, calculates stage side lengths in idx in order to compute
        trajectory for raster.

        Args:
            signal (bool): Whether to execute aq signal remote commands. Defaults to True.
        """
        # Use gen_trajectory to get a trajectory (X(t), Y(t))
        self.gen_trajectory()
        if self.dry_run:
            plot_trajectory(self._trajectory, title="Discrete raster trajectory")
            return
        # May want to fine-tune
        raster_idx_speed = settings.MAX_SPEED

        logger.debug(f"Setting motor speed to {raster_idx_speed} for both motors.")

        self.VMX.clear().speed(motor=Motor.X, speed=raster_idx_speed).speed(
            motor=Motor.Y, speed=raster_idx_speed
        ).run().send()
        self.VMX.wait_for_complete(timeout=600)

        if signal:
            logger.info("Sending start signal.")
            # Send start signal over ssh
            msg = self.signaller.start_aq()
            logger.debug(f"Signal returned\n {msg.stdout}")

        self.VMX.clear(now=True)

        logger.info(f"Starting a raster with {len(self._trajectory)} points.")
        # Since any wait_for_complete can time out, wrap whole loop in try-finally
        # We want the timeouterror to be raised and crash the script
        try:
            for i, coord in enumerate(self._trajectory):
                logger.info(f"Now indexing to {coord}.")
                self.VMX.clear()
                self.VMX.move(motor=Motor.X, idx=coord[0], relative=False)
                self.VMX.move(motor=Motor.Y, idx=coord[1], relative=False)
                # self.VMX.pause(time=self.observing_time)
                self.VMX.run().send()
                logger.info(
                    f"Starting move to (now/total rows, now/total columns).\n \
                      ({divmod(i, self.grid_size.X)[1] + 1}/{self.grid_size.X},{divmod(i, self.grid_size.X)[0] + 1}/{self.grid_size.Y})"
                )
                self.VMX.wait_for_complete(timeout=600)

                if signal:
                    # Signal ready for start of mark
                    logger.info("Sending start signal.")
                    msg = self.signaller.start_aq()
                    logger.info(f"Signal returned\n {msg.stdout}")

                    logger.debug(f"Pausing for {settings.OBSERVE_TIME}s")
                    time.sleep(settings.OBSERVE_TIME)

                    # Signal continue
                    logger.info("Sending continue signal.")
                    msg = self.signaller.cont_aq()
                    logger.info(f"Signal returned\n {msg.stdout}")
                    logger.debug("Sending ready signal")
                    # msg = self.signaller.cont_aq()
                else:
                    time.sleep(settings.OBSERVE_TIME)
                logger.info("Program complete, moving to next position.")
        # Even if the rastering fails, send end signal
        finally:
            if signal:
                logger.info("Sending end signal.")
                msg = self.signaller.end_aq()
                logger.debug(f"Signal returned\n {msg.stdout}")

        logger.info(f"Completed {self.grid_size} raster.")

    def continuous_raster(self, signal: bool = True) -> None:
        """Raster continuously across each row of the configured grid.

        Acquisition runs for the entire raster. Each row traverses between the
        first and last X coordinates generated for that row, and the Y stage
        advances between rows.

        Args:
            signal (bool): Whether to execute acquisition signal remote commands.
                Defaults to True.

        """
        self.gen_trajectory()
        rows = self._trajectory.reshape(self.grid_size.Y, self.grid_size.X, 2)
        row_order = interleaved_row_order(len(rows), self.continuous_raster_interleave)
        continuous_trajectory = numpy.empty(
            (len(rows) * 2, 2), dtype=self._trajectory.dtype
        )
        x_edges = (rows[0, 0, 0], rows[0, -1, 0])
        for execution_index, row_index in enumerate(row_order):
            y_position = rows[row_index, 0, 1]
            start_edge = execution_index % 2
            continuous_trajectory[execution_index * 2] = (
                x_edges[start_edge],
                y_position,
            )
            continuous_trajectory[execution_index * 2 + 1] = (
                x_edges[1 - start_edge],
                y_position,
            )
        if self.dry_run:
            title = (
                "Continuous raster trajectory"
                if self.continuous_raster_interleave == 1
                else "Interleaved continuous raster trajectory"
            )
            plot_trajectory(continuous_trajectory, title=title)
            return
        raster_idx_speed = settings.CONTINUOUS_RASTER_SPEED

        logger.debug(
            f"Setting continuous raster speed to {raster_idx_speed} for both motors."
        )
        self.VMX.clear().speed(motor=Motor.X, speed=raster_idx_speed).speed(
            motor=Motor.Y, speed=raster_idx_speed
        ).run().send()
        self.VMX.wait_for_complete(timeout=600)

        scan_rows = continuous_trajectory.reshape(len(rows), 2, 2)
        first_coord = scan_rows[0, 0]
        logger.info(f"Indexing to continuous raster start at {first_coord}.")
        self.VMX.clear().move(motor=Motor.X, idx=first_coord[0], relative=False).move(
            motor=Motor.Y, idx=first_coord[1], relative=False
        ).run().send()
        self.VMX.wait_for_complete(timeout=600)

        acquisition_started = False
        try:
            if signal:
                logger.info("Sending start signal.")
                msg = self.signaller.start_aq()
                acquisition_started = True
                logger.debug(f"Signal returned\n {msg.stdout}")

            logger.info(f"Starting a continuous raster with {len(rows)} rows.")
            for execution_index, (row_index, coordinates) in enumerate(
                zip(row_order, scan_rows, strict=True)
            ):
                destination = coordinates[-1]
                logger.info(
                    f"Scanning grid row {row_index + 1}/{len(rows)} to {destination}."
                )
                self.VMX.clear().move(
                    motor=Motor.X, idx=destination[0], relative=False
                ).run().send()
                self.VMX.wait_for_complete(timeout=600)

                if execution_index + 1 < len(scan_rows):
                    next_coord = scan_rows[execution_index + 1, 0]
                    logger.info(f"Advancing to next row at {next_coord}.")
                    self.VMX.clear().move(
                        motor=Motor.X, idx=next_coord[0], relative=False
                    ).move(
                        motor=Motor.Y, idx=next_coord[1], relative=False
                    ).run().send()
                    self.VMX.wait_for_complete(timeout=600)
        finally:
            if signal and acquisition_started:
                logger.info("Sending end signal.")
                msg = self.signaller.end_aq()
                logger.debug(f"Signal returned\n {msg.stdout}")

        logger.info(f"Completed continuous raster with {len(rows)} rows.")

    def test_signal_setup(self) -> None:
        """Moves stages to home, signals start, moves back to home, then signals end.

        Useful for ensuring signalling behaves as expected.
        """
        self._require_hardware()
        self.home()

        # set motor speed
        test_idx_speed = settings.MAX_SPEED
        self.VMX.clear().speed(motor=Motor.X, speed=test_idx_speed).speed(
            motor=Motor.Y, speed=test_idx_speed
        ).run().send()
        self.VMX.wait_for_complete(timeout=600)
        logger.info(f"Set motor speed to {test_idx_speed} idx/s")

        # Signal start
        logger.info("Sending start signal.")
        msg = self.signaller.start_aq()
        logger.info(f"Signal returned\n {msg.stdout}")

        # Move index -5000,-5000
        test_idx = -5000
        logger.info(f"Moving to {test_idx}.")
        self.VMX.clear()
        self.VMX.move(motor=Motor.X, idx=test_idx, relative=True)
        self.VMX.move(motor=Motor.Y, idx=test_idx, relative=True)
        self.VMX.run().send()

        # Since any wait_for_complete can time out, wrap whole loop in try-finally
        # We want the timeouterror to be raised and crash the script
        try:
            self.VMX.wait_for_complete(timeout=600)
            # Signal ready to mark start of raster point
            logger.info("Sending start signal.")
            msg = self.signaller.start_aq()
            logger.info(f"Signal returned\n {msg.stdout}")

            logger.debug(f"Pausing for {settings.OBSERVE_TIME} s")
            time.sleep(settings.OBSERVE_TIME)

            # Signal end
            logger.info("Sending continue signal.")
            msg = self.signaller.cont_aq()
            logger.info(f"Signal returned\n {msg.stdout}")

        finally:
            # Signal end
            logger.info("Sending end signal.")
            msg = self.signaller.end_aq()
            logger.info(f"Signal returned\n {msg.stdout}")

            logger.info("Testing signalling complete.")

        # home again
        self.home()

    def scotland_the_brave(self) -> None:
        """Play Scotland the Brave using the X-axis motor."""
        self._require_hardware()
        commands = SerialCommand(
            (
                "C","S1M260","I1M260","I1M-195","I1M65","S1M325","I1M-162",
                "S1M260","I1M130","S1M325","I1M-162","S1M390","I1M195",
                "S1M520","I1M520","I1M-390","I1M130","I1M-260","S1M390",
                "I1M195","S1M325","I1M-162","S1M260","I1M260","R",
            )
        )
        self.VMX.command_queue = commands
        self.VMX.send()
        self.VMX.wait_for_complete(timeout=600)

    def e1m1(self) -> None:
        """Play the opening E1M1 guitar riff using the X-axis motor."""
        self._require_hardware()
        # E E E'  E E D'  E E C'  E E Bb  E E B C
        # E E E'  E E D'  E E C'  E E Bb----
        commands = SerialCommand(
            (
                "C","S1M325","I1M72","I1M-72","S1M650","I1M-143","S1M325",
                "I1M72","I1M72","S1M587","I1M129","S1M325","I1M-72","I1M-72",
                "S1M520","I1M114","S1M325","I1M-72","I1M-72","S1M463",
                "I1M102","S1M325","I1M-72","I1M-72","S1M491","I1M108",
                "S1M520","I1M114","S1M325","I1M-72","I1M-72","S1M650",
                "I1M143","S1M325","I1M-72","I1M72","S1M587","I1M-129",
                "S1M325","I1M72","I1M72","S1M520","I1M114","S1M325",
                "I1M72","I1M72","S1M463","I1M-408","R",
            )
        )

        self.VMX.command_queue = commands
        self.VMX.send()
        self.VMX.wait_for_complete(timeout=600)

    def gen_trajectory(self) -> None:
        """Generate grid raster trajectory."""
        # GRID_SIZE is required/has a default. If step size given,
        # we do not use the values from homing
        if settings.GRID_SIZE and settings.STEP_SIZE:
            logger.info("Using grid and step size from settings.")

        elif hasattr(self, "limit_switch_positions"):
            logger.info(
                "Using grid and step size generated from limit switch positions."
            )
            # gather positions into array where each row is a coordinate
            lsp = numpy.array(self.limit_switch_positions)
            logger.debug(f"Using this array of limit switch positions:\n {lsp}")
            # diff sequential rows to get coordinate distance between points
            stg_len = numpy.abs(numpy.diff(lsp, axis=0))
            # Since we traveled on each side twice, might as well average them.
            # Sometimes the VMX reports a 1-10 index difference at the limit switches.
            # Just ignore anything below the mean, should catch these small glitches
            x_total_idx = numpy.mean(
                stg_len[:, 0][stg_len[:, 0] > numpy.mean(numpy.abs(stg_len[:, 0]))]
            )
            y_total_idx = numpy.mean(
                stg_len[:, 1][stg_len[:, 1] > numpy.mean(numpy.abs(stg_len[:, 1]))]
            )
            # To not hit the limit switches in normal operation, we offset by an inch
            logger.debug(f"Number of indexes in (x,y):\n ({x_total_idx},{y_total_idx}")
            x_reduced_idx = x_total_idx - x_total_idx * (2 * 1 / 30)
            y_reduced_idx = y_total_idx - y_total_idx * (2 * 1 / 30)
            # We now split each dimension
            self.step_size = Size(
                x_reduced_idx / self.grid_size.X, y_reduced_idx / self.grid_size.Y
            )

        else:
            logger.warning("Either set raster parameters manually or run startup.")
            return

        logger.debug(
            f"Generating 2D raster trajectory with grid size {self.grid_size} and step size {self.step_size}."
        )
        self._trajectory = gen_2d_trajectory(self.grid_size, self.step_size)
        # Need to offset from limit switches
        offset = [
            numpy.array(x_total_idx * (1 * 1 / 30)).astype(int),
            numpy.array(y_total_idx * (1 * 1 / 30)).astype(int),
        ]
        self._trajectory += offset
        # Since the origin is at +X,+Y limit switches, we can only index to negative numbers
        self._trajectory = -self._trajectory

    def goto(self, coord: Size, relative: bool = False, speed: int = 1500):
        """Go to a commanded coordinate, in (X,Y) indexes.

        Args:
            coord (Size): Coordinates, in index count, to jog to.
            relative (bool, optional): If the coordinates are relative. Defaults to False.
            speed (int, optional): stage speed in idx/s
        """
        self._require_hardware()
        # set motor speed, enforcing the MAX_SPEED setting
        if speed > settings.MAX_SPEED:
            logger.info(
                f"Requested speed {speed} exceeds MAX_SPEED {settings.MAX_SPEED}; speed will be capped to {settings.MAX_SPEED}"
            )
            speed = settings.MAX_SPEED
        self.VMX.clear().speed(motor=Motor.X, speed=speed).speed(
            motor=Motor.Y, speed=speed
        ).run().send()
        self.VMX.wait_for_complete(timeout=600)
        logger.info(f"Set motor speed to {speed} idx/s")

        # Go to index
        logger.info(f"Moving to {coord}.")
        self.VMX.clear()
        self.VMX.move(motor=Motor.X, idx=coord.X, relative=relative)
        self.VMX.move(motor=Motor.Y, idx=coord.Y, relative=relative)
        self.VMX.run().send()
        # Since any wait_for_complete can time out, wrap whole loop in try-finally
        # We want the timeouterror to be raised and crash the script
        try:
            self.VMX.wait_for_complete(timeout=600)
        except TimeoutError:
            logger.warning(
                "Waiting for VMX program to complete timed out. The stages could be anywhere."
            )

    @property
    def limit_switch_positions(self) -> list:
        """Get list of limit switch positions.

        Returns:
            list: limit switch positions
        """
        return self._limit_switch_positions

    @limit_switch_positions.setter
    def limit_switch_positions(self, value: list):
        """Set limit switch positions.

        Args:
            value (list): List of limit switch positions as (x, y) tuples

        """
        self._limit_switch_positions = value

    @property
    def trajectory(self) -> numpy.ndarray:
        """Get currently computed trajectory.

        Returns:
            numpy.ndarray: array of grid trajectory (x,y)
        """
        return self._trajectory

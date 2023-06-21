import numpy
from loguru import logger
from stgctl.core.settings import settings
from stgctl.lib.signal import Signaller
from stgctl.lib.vmx import VMX
from stgctl.lib.vmx import Motor
from stgctl.schema.models import Size
from stgctl.util.trajectory import gen_2d_trajectory


# Notes on how old code behaved:
# data_taking_wait_time is at every step
# However, "if already there" (eg at start or turnaround), only data_taking_wait_time is waited, step_wait_time is skipped!
class XYStage:
    def __init__(self):
        self.VMX = VMX(port=settings.VMX_DEVICE_PORT)
        self.grid_size = Size(*settings.GRID_SIZE)
        self.step_size = (
            Size(*settings.STEP_SIZE) if settings.STEP_SIZE else settings.STEP_SIZE
        )
        self.observing_time = settings.OBSERVE_TIME
        self.gcp_signal = Signaller(settings.SIGNAL_HOST, settings.SIGNAL_USER)

    def startup(self):
        logger.info(
            "Sending stages to the four limit switches to get index counts for raster."
        )

        # Go to +X, +Y limit switches, set origin
        self.home()
        # +X,+Y is (0,0) by definition
        limit_switch_positions = [(0, 0)]
        # Set speed again, just in case.
        self.VMX.clear().speed(motor=Motor.X, speed=2000).speed(
            motor=Motor.Y, speed=2000
        )
        # +X,+Y > +X,-Y > -X,-Y > -X,+Y > +X,+Y
        switch_values = [(True, False), (False, False), (False, True), (True, True)]
        for switch_value in switch_values:
            #  Go to -X, -Y limit switches then record position
            self.VMX.clear().to_limit(motor=Motor.X, pos=switch_value[0]).to_limit(
                motor=Motor.Y, pos=switch_value[1]
            ).run().send()

            try:
                self.VMX.wait_for_complete(timeout=600)
                logger.info(
                    f"Stages have finished indexing to \
                    ({'+' if switch_value[0] else '-'}X,{'+' if switch_value[1] else '-'}Y) \
                    limit switches."
                )
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

    def home(self) -> None:
        logger.info("Sending stages to positive limit switches.")
        self.VMX.clear().speed(motor=Motor.X, speed=2000).speed(
            motor=Motor.Y, speed=2000
        ).to_limit(motor=Motor.X, pos=True).to_limit(
            motor=Motor.Y, pos=True
        ).run().send()

        try:
            self.VMX.wait_for_complete(timeout=600)
            logger.info("Stages have finished indexing to the positive limit switches.")
            self.VMX.clear().origin().send()
            logger.info("Origin set.")
            return
        except TimeoutError:
            logger.warning(
                "Waiting for VMX program to complete timed out. The stages could be anywhere."
            )

    def raster(self, signal: bool = True) -> None:
        self.gen_trajectory()
        raster_idx_speed = 1500

        logger.debug(f"Setting motor speed to {raster_idx_speed} for both motors.")

        self.VMX.clear().speed(motor=Motor.X, speed=raster_idx_speed).speed(
            motor=Motor.Y, speed=raster_idx_speed
        ).run().send()

        if signal:
            logger.info("Sending start signal.")
            self.gcp_signal.start_aq()

        logger.info(f"Starting a raster with {self._trajectory.size} points.")
        try:
            for i, coord in enumerate(self._trajectory):
                logger.info(f"Now indexing to {coord}.")
                self.VMX.clear()
                self.VMX.move(motor=Motor.X, idx=coord[0], relative=False)
                self.VMX.move(motor=Motor.Y, idx=coord[1], relative=False)
                self.VMX.pause(time=self.observing_time)
                self.VMX.run().send()
                logger.info(
                    f"Starting (now/total rows, now/total columns).\n \
                            ({divmod(i,self.grid_size.X)[1]}/{self.grid_size.X},{divmod(i,self.grid_size.X)[0]}/{self.grid_size.Y})"
                )
                self.VMX.wait_for_complete(timeout=600)
                logger.info("Program complete, moving to next position.")
        finally:
            if signal:
                logger.info("Sending stop signal.")
                self.gcp_signal.stop_aq()

        logger.info(f"Completed {self.grid_size} raster.")

    def gen_trajectory(self):
        if settings.GRID_SIZE and settings.STEP_SIZE:
            logger.info("Using grid and step size from settings.")

        elif hasattr(self, "limit_switch_positions"):
            logger.info(
                "Using grid and step size generated from limit switch positions."
            )
            # gather positions into array where each row is a coordinate
            lsp = numpy.array(self.limit_switch_positions)
            # diff sequential rows to get coordinate distance between points
            stg_len = numpy.diff(lsp)
            # total index for each direction is dependent on the startup strategy.
            # This assumes the origin is at the +X,+Y limit switches, and the
            # startup trajectory is > +X,-Y > -X,-Y > -X,+Y > +X,+Y
            x_total_idx = numpy.mean(stg_len[1, 1], stg_len[2, 1])
            y_total_idx = numpy.mean(stg_len[0, 1], stg_len[-1, 1])
            # To not hit the limit switches in normal operation, we offset by an inch
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
            f"Generating 2D raster trajectory with grid size {self.grid_size} and {self.step_size}."
        )
        self._trajectory = gen_2d_trajectory(self.grid_size, self.step_size)

    @property
    def trajectory(self):
        return self._trajectory

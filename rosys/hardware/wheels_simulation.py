from typing import Optional

from ..actors.odometer import Odometer
from ..runtime import runtime
from ..world import Pose, PoseStep
from .wheels import Wheels


class WheelsSimulation(Wheels):

    def __init__(self, odometer: Odometer) -> None:
        super().__init__(odometer)

        self.pose: Pose = Pose()
        self.linear_velocity: float = 0
        self.angular_velocity: float = 0

        runtime.on_repeat(self.step, 0.01)
        self._last_step: Optional[float] = None

    async def drive(self, linear: float, angular: float) -> None:
        self.linear_velocity = linear
        self.angular_velocity = angular

    async def stop(self) -> None:
        self.linear_velocity = 0
        self.angular_velocity = 0

    async def step(self) -> None:
        if self._last_step is not None:
            dt = runtime.time - self._last_step
            self.pose += PoseStep(linear=dt*self.linear_velocity, angular=dt*self.angular_velocity, time=runtime.time)
        self._last_step = runtime.time

        self.odometer.add_odometry(self.linear_velocity, self.angular_velocity, runtime.time)
        self.odometer.process_odometry()
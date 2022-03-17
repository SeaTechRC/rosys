import asyncio
from multiprocessing import Pipe
import time
from typing import Any, Optional

from .. import run
from ..world import PathSegment, Point, Pose, Spline
from . import Actor
from .pathplanning import PlannerCommand, PlannerProcess, PlannerState, \
    PlannerGetStateCommand, PlannerGrowMapCommand, PlannerSearchCommand, PlannerTestCommand


class PathPlanner(Actor):

    def __init__(self):
        super().__init__()
        self.connection, process_connection = Pipe()
        self.process = PlannerProcess(process_connection, self.world.robot.shape.outline)

    async def startup(self):
        await super().startup()
        self.process.start()

    async def tear_down(self):
        await super().tear_down()
        if self.process.is_alive():
            self.process.kill()

    async def get_state(self, timeout: float = 3.0) -> PlannerState:
        return await self._call(PlannerGetStateCommand(timeout=timeout))

    async def grow_map(self, points: list[Point], timeout: float = 3.0) -> None:
        return await self._call(PlannerGrowMapCommand(
            points=points,
            timeout=timeout,
        ))

    async def search(self, *,
                     goal: Pose,
                     start: Optional[Pose] = None,
                     backward: bool = False,
                     timeout: float = 3.0) -> list[PathSegment]:
        return await self._call(PlannerSearchCommand(
            areas=list(self.world.areas.values()),
            obstacles=list(self.world.obstacles.values()),
            start=start or self.world.robot.prediction,
            goal=goal,
            backward=backward,
            timeout=timeout,
        ))

    async def test_spline(self, spline: Spline, timeout: float = 3.0):
        return await self._call(PlannerTestCommand(
            areas=list(self.world.areas.values()),
            obstacles=list(self.world.obstacles.values()),
            spline=spline,
            timeout=timeout,
        ))

    async def _call(self, command: PlannerCommand) -> Any:
        with run.cpu():
            self.connection.send(command)
            t = time.time()
            while not self.connection.poll():
                if time.time() - t > command.timeout:
                    raise TimeoutError(f'process call with a {type(command)} took too long')
                await asyncio.sleep(0.01)
            result = self.connection.recv()
            if isinstance(result, Exception):
                raise result
            return result
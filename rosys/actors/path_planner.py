import asyncio
import logging
import os
import signal
import time
from multiprocessing import Pipe
from typing import Any

import psutil

from .. import persistence, run
from ..runtime import runtime
from ..world import Area, Obstacle, PathSegment, Point, Pose, RobotShape, Spline
from .pathplanning import (PlannerCommand, PlannerGrowMapCommand, PlannerObstacleDistanceCommand, PlannerProcess,
                           PlannerResponse, PlannerSearchCommand, PlannerTestCommand)


class PathPlanner:

    def __init__(self, robot_shape: RobotShape) -> None:
        self.log = logging.getLogger('rosys.path_planner')

        self.connection, process_connection = Pipe()
        self.process = PlannerProcess(process_connection, robot_shape.outline)
        self.responses: dict[str, Any] = {}

        self.obstacles: dict[str, Obstacle] = {}
        self.areas: dict[str, Area] = {}

        runtime.on_startup(self.startup)
        runtime.on_shutdown(self.shutdown)
        runtime.on_repeat(self.step, 0.1)
        persistence.register(self)

    def backup(self) -> dict:
        return {
            'obstacles': {id: obstacle.dict() for id, obstacle in self.obstacles.items()},
            'areas': {id: area.dict() for id, area in self.areas.items()},
        }

    def restore(self, data: dict[str, Any]) -> None:
        self.obstacles |= {id: Obstacle.parse_obj(obstacle) for id, obstacle in data.get('obstacles', {}).items()}
        self.areas |= {id: Area.parse_obj(area) for id, area in data.get('areas', {}).items()}

    def startup(self) -> None:
        self.process.start()

    async def shutdown(self) -> None:
        self.log.info('stopping planner process...')
        pid = self.process.pid
        if self.process.is_alive():
            self.process.kill()
        # to really make sure it's gone (see https://trello.com/c/M9IvOg1c/698-reload-klappt-nicht-immer#comment-62aaeb74672e6759fba37b40)
        if not runtime.is_test:
            while pid is not None and psutil.pid_exists(pid):
                self.log.info(f'{pid} still exists; killing again')
                os.kill(pid, signal.SIGKILL)
                await runtime.sleep(1)
        self.log.info(f'teardown of {self.process} completed ({self.process.is_alive()})')

        self.connection.close()
        self.process.connection.close()

    async def step(self) -> None:
        if self.connection.poll():
            response = self.connection.recv()
            assert isinstance(response, PlannerResponse)
            if time.time() < response.deadline:
                self.responses[response.id] = response.content

    async def grow_map(self, points: list[Point], timeout: float = 3.0) -> None:
        return await self._call(PlannerGrowMapCommand(
            points=points,
            deadline=time.time()+timeout,
        ))

    async def search(self, *,
                     start: Pose,
                     goal: Pose,
                     timeout: float = 3.0) -> list[PathSegment]:
        return await self._call(PlannerSearchCommand(
            areas=list(self.areas.values()),
            obstacles=list(self.obstacles.values()),
            start=start,
            goal=goal,
            deadline=time.time()+timeout,
        ))

    async def test_spline(self, spline: Spline, timeout: float = 3.0) -> bool:
        return await self._call(PlannerTestCommand(
            areas=list(self.areas.values()),
            obstacles=list(self.obstacles.values()),
            spline=spline,
            deadline=time.time()+timeout,
        ))

    async def get_obstacle_distance(self, pose: Pose, timeout: float = 3.0) -> float:
        return await self._call(PlannerObstacleDistanceCommand(
            areas=list(self.areas.values()),
            obstacles=list(self.obstacles.values()),
            pose=pose,
            deadline=time.time()+timeout,
        ))

    async def _call(self, command: PlannerCommand, check_interval: float = 0.1) -> Any:
        with run.cpu():
            self.connection.send(command)
            while command.id not in self.responses:
                if time.time() > command.deadline:
                    raise TimeoutError(f'process call {command.id} did not respond in time')
                if runtime.is_test:
                    await self.step()  # NOTE: otherwise step() is not called while awaiting response
                await asyncio.sleep(check_interval)
            result = self.responses.pop(command.id)
            if isinstance(result, Exception):
                raise result
            return result

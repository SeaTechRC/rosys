import asyncio
import logging

from ..world import World
from .. import event


class Actor:
    world: World
    interval: float = None

    def __init__(self) -> None:
        self.name = __name__[:-5] + self.__class__.__name__
        self.log = logging.getLogger(self.name)

    async def step(self):
        pass

    async def tear_down(self):
        pass

    async def sleep(self, seconds: float):
        '''delay execution; in tests this method will be replaced'''
        await asyncio.sleep(seconds)

    async def pause_automations(self, *, because: str):
        await event.call(event.Id.PAUSE_AUTOMATIONS, because)

    async def notify(self, message: str):
        await event.call(event.Id.NEW_NOTIFICATION, message)

    def __str__(self) -> str:
        return type(self).__name__

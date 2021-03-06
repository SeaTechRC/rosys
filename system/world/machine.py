from typing import Any, Optional
from world.velocity import Velocity
from pydantic.main import BaseModel
import aioserial


class Machine(BaseModel):

    port: str
    aioserial_instance: Any

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.aioserial_instance = aioserial.AioSerial(self.port, baudrate=115200)

    async def read(self) -> Optional[Velocity]:

        line = (await self.aioserial_instance.readline_async()).decode().strip()
        if '^' in line:
            line, check = line.split('^')
            checksum = 0
            for c in line:
                checksum ^= ord(c)
            if checksum != int(check):
                return

        words = line.split()
        return Velocity(linear=float(words[1]), angular=float(words[2]))
from navigation.spline import Spline
from navigation.carrot import Carrot

from actors.esp import Esp
from world.world import World
from world.pose import Pose
from actors.actor import Actor


class SplineDriver(Actor):

    async def once(self, world: World, esp: Esp):
        spline = Spline(Pose(x=0, y=0, yaw=0), Pose(x=2, y=1, yaw=0))
        carrot = Carrot(spline)

        while carrot.move(world.robot.pose):
            local_spline = Spline(world.robot.pose, carrot.pose)
            curvature = local_spline.max_curvature(0.0, 0.25)
            linear = 0.5
            angular = linear * curvature
            await esp.drive(linear, angular)
            await self.time_increment(0.01)
        await esp.drive(0, 0)

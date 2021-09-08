from nicegui.elements.scene_object3d import Object3D
from nicegui.elements.scene_objects import Extrusion
from rosys.world.obstacle import Obstacle


class ObstaclesObject(Object3D):

    def __init__(self, obstacles: dict[str, Obstacle]):
        super().__init__('group')
        self.obstacles = obstacles

        self.update()

    def update(self):
        [obj.delete() for obj in list(self.view.objects.values()) if (obj.name or '').startswith('obstacle_')]
        for obstacle in self.obstacles.values():
            outline = [[point.x, point.y] for point in obstacle.outline]
            Extrusion(outline, 0.1).with_name(f'obstacle_{obstacle.id}')
from __future__ import annotations

import io
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Protocol

import humanize
from PIL import Image, ImageDraw, ImageFont

from .. import rosys
from ..vision import Camera

STORAGE_PATH = Path('~/.rosys/timelapse').expanduser()
VIDEO_PATH = STORAGE_PATH / 'videos'
FONT = str(Path(__file__).parent / 'assets' / 'RobotoMono-Medium.ttf')
IMAGE_FONT = ImageFont.truetype(FONT, 16)
BIG_COVER_FONT = ImageFont.truetype(FONT, 50)
SMALL_COVER_FONT = ImageFont.truetype(FONT, 30)


class RosysImage(Protocol):
    camera_id: str
    time: float
    data: Optional[bytes] = None


class TimelapseRecorder:

    def __init__(self, *, width: int = 800, height: int = 600, capture_rate=1) -> None:
        """Creates a timelapse recorder to capture images from a camera and creates a video of the sequence afterwards.

        param: width: width of the images to capture (default 800)
        param: height: height of the images to capture (default 600)
        param: capture_rate: images per second to capture (default 1)
        """
        self.log = logging.getLogger('rosys.timelapse_recorder')
        self.width = width
        self.height = height
        self.capture_rate = capture_rate
        self.last_capture_time = rosys.time()
        self._notifications: list[list[str]] = []
        self.camera: Optional[Camera] = None
        VIDEO_PATH.mkdir(parents=True, exist_ok=True)
        rosys.on_repeat(self.capture, 0.01)

    async def capture(self) -> None:
        if self.camera is None:
            return
        if rosys.time() - self.last_capture_time < 1 / self.capture_rate:
            return
        images = self.camera.get_recent_images()
        if images:
            self.last_capture_time = rosys.time()
            await self.save(images[-1])

    async def save(self, image: RosysImage) -> None:
        await rosys.run.cpu_bound(_save_image,
                                  image,
                                  STORAGE_PATH,
                                  (self.width, self.height),
                                  self._notifications.pop(0) if self._notifications else [])

    async def compress_video(self) -> None:
        jpgs = sorted(STORAGE_PATH.glob('*.jpg'))
        if len(jpgs) < 20:
            self.log.info(f'very few images ({len(jpgs)}); not creating video')
            self.discard_video()
            return
        start_unix = int(jpgs[0].stem[:-4])
        start = datetime.fromtimestamp(start_unix)
        end = datetime.fromtimestamp(int(Path(jpgs[-1]).stem[:-4]))
        self.log.info(f'creating video from {start} to {end}')
        duration = humanize.naturaldelta(end-start)
        await self.create_info(start.strftime('%d.%m.%Y %H:%M:%S'), duration, time=start_unix - 1)
        id_ = start.strftime(r'%Y%m%d_%H-%M-%S_' + duration.replace(' ', '_'))
        target_dir = STORAGE_PATH / id_
        target_dir.mkdir(parents=True, exist_ok=True)
        await rosys.run.sh(f'mv {STORAGE_PATH}/*.jpg {target_dir}', shell=True)
        source_file = target_dir / 'source.txt'
        with source_file.open('w') as f:
            for jpg in sorted(target_dir.glob('*.jpg')):
                f.write(f"file '{jpg}'\n")
        absolute_niceness = 10 - os.nice(0)
        cmd = f'nice -n {absolute_niceness} ffmpeg -hide_banner -threads 1 -f concat -safe 0 -i "{source_file}" ' \
            f'-s {self.width}x{self.height} -vcodec libx264 -crf 18 -preset slow -pix_fmt yuv420p -y {target_dir}/{id_}.mp4;' \
            f'mv {target_dir}/*mp4 {STORAGE_PATH}/videos;' \
            f'rm -r {target_dir};'
        self.log.info(f'starting {cmd}')
        rosys.background_tasks.create(rosys.run.sh(cmd, timeout=None, shell=True), name='timelapse ffmpeg')

    def discard_video(self) -> None:
        for jpg in STORAGE_PATH.glob('*.jpg'):
            jpg.unlink()

    async def create_info(self, title: str, subtitle: str, frames: int = 20, time: Optional[float] = None) -> None:
        await rosys.run.cpu_bound(save_info, title, subtitle, rosys.time() if time is None else time, frames)

    def notify(self, message: str, frames: int = 10):
        '''Place message in the next n frames'''
        while len(self._notifications) < frames:
            self._notifications.append([])
        for i in range(frames):
            self._notifications[i].append(message)


def _save_image(image: RosysImage, path: Path, size: tuple[int, int], notifications: list[str]) -> None:
    assert image.data is not None
    img = Image.open(io.BytesIO(image.data))
    img = img.resize(size)
    draw = ImageDraw.Draw(img)
    x = y = 20
    write(f'{datetime.fromtimestamp(image.time).strftime(r"%Y-%m-%d %H:%M:%S")}, cam {image.camera_id}', draw, x, y)
    for message in notifications:
        y += 30
        write(message, draw, x, y)
    img.save(path / f'{int(image.time* 10000)}.jpg', 'JPEG')


def write(text: str, draw: ImageDraw.Draw, x: int, y: int):
    # shadow
    draw.text((x - 1, y - 1), text, font=IMAGE_FONT, fill=(0, 0, 0))
    draw.text((x + 1, y - 1), text, font=IMAGE_FONT, fill=(0, 0, 0))
    draw.text((x - 1, y + 1), text, font=IMAGE_FONT, fill=(0, 0, 0))
    draw.text((x + 1, y + 1), text, font=IMAGE_FONT, fill=(0, 0, 0))
    # actual text
    draw.text((x, y), text, font=IMAGE_FONT, fill=(255, 255, 255))


def save_info(title: str, subtitle: str, time: float, frames: int) -> None:
    for i in range(frames):
        img = Image.new('RGB', (1600, 1200), 'black')
        draw = ImageDraw.Draw(img)
        font = BIG_COVER_FONT if len(subtitle) < 25 and len(title) < 25 else SMALL_COVER_FONT

        title_box = draw.textbbox((0, 0), title, font=font)
        title_x = (img.width - title_box[2]) / 2
        title_y = (img.height / 2) - 200 - (title_box[3] / 2)
        draw.text((title_x, title_y), title, font=font, fill='white')

        subtitle_box = draw.textbbox((0, 0), subtitle, font=font)
        subtitle_x = (img.width - subtitle_box[2]) / 2
        subtitle_y = (img.height / 2) + 100 - (subtitle_box[3] / 2)
        draw.text((subtitle_x, subtitle_y), subtitle, font=font, fill='white')

        img.save(STORAGE_PATH / f'{time:.0f}{i:04}.jpg')

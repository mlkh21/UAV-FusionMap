"""Check owned Gazebo/RViz render targets and scene-backed IR contrast."""
import argparse
import json
from pathlib import Path

from PIL import Image, ImageStat


def validate(directory):
    directory = Path(directory)
    rows = []
    patterns = ('gazebo-scene-*.png', 'rviz-sensors-*-viewport-0.png', 'rviz-sensors-*-viewport-1.png',
                'infrared-fixture.png', 'infrared-fixture-moved.png')
    for pattern in patterns:
        paths = sorted(directory.glob(pattern))
        if not paths:raise ValueError('missing render: ' + pattern)
        for path in paths:
            image = Image.open(path).convert('RGB')
            stats = ImageStat.Stat(image)
            if image.width < 300 or image.height < 200 or max(stats.stddev) < 15:
                raise ValueError('blank/small render: ' + str(path))
            rows.append(dict(name=path.name, size=list(image.size), stddev=stats.stddev))
    radar_view = Image.open(next(directory.glob('rviz-sensors-*-viewport-0.png'))).convert('RGB')
    pixels = list(radar_view.getdata())
    colorful = sum(max(r,g,b) - min(r,g,b) > 70 and max(r,g,b) > 130 for r,g,b in pixels)
    if colorful < 300:raise ValueError('missing Radar/map colors')
    full = [p for p in directory.glob('rviz-sensors-*.png') if 'viewport' not in p.name]
    if not full or any(Image.open(p).width < 1000 for p in full):raise ValueError('missing full RViz capture')
    result = dict(passed=True, figures=rows, radar_map_color_pixels=colorful,
                  scope='owned native scene/render targets; functional sensor fixture')
    (directory / 'pixel-validation.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    print(json.dumps(validate(parser.parse_args().directory)))

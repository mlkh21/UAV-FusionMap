"""Verify actual RViz render readbacks contain map colors and preserve figure provenance."""
import argparse
import json
from pathlib import Path
from PIL import Image


def validate_figures(directory):
    directory = Path(directory)
    result = json.loads((directory / 'ui-validation.json').read_text())
    if not result['passed']:raise ValueError('native UI validation failed')
    rows = []
    for index, name in enumerate(result['captures']):
        path = Path(name)
        metadata = json.loads(path.with_suffix('.json').read_text())
        viewport = Image.open(metadata['viewport']).convert('RGB')
        pixels = list(viewport.getdata())
        red = sum(r > 140 and r > g * 1.6 and r > b * 1.4 for r, g, b in pixels)
        green = sum(g > 90 and g > r * 1.5 and b > r * 1.2 for r, g, b in pixels)
        dark = sum(max(r, g, b) < 100 for r, g, b in pixels)
        purple = sum(r > 90 and b > r * 1.1 and b > g * 1.1 for r, g, b in pixels)
        gray = sum(50 < r < 130 and 0 <= g - r < 30 and 0 <= b - g < 20 for r, g, b in pixels)
        if dark < 1000:raise ValueError('blank render in ' + str(path))
        if index < 3 and red < 500:raise ValueError('missing occupancy in ' + str(path))
        if index == 3 and purple < 500:raise ValueError('missing stale geometry')
        if index == 4 and gray < 500:raise ValueError('missing unavailable history')
        if index == 0 and green < 500:raise ValueError('free layer missing from main figure')
        frame = metadata['frame']
        if frame['sources'] != ['fixture'] or frame['header']['frame_id'] != 'map':
            raise ValueError('report fixture provenance missing')
        full = Image.open(path)
        if full.width < 1000 or full.height < 700:raise ValueError('report figure too small')
        x, y, width, height = metadata['viewport_rect']
        if not (0 <= x < x + width <= full.width and 0 <= y < y + height <= full.height):
            raise ValueError('viewport exceeds window')
        rows.append(dict(path=str(path), size=list(full.size), viewport_size=list(viewport.size),
                         occupied_pixels=red, free_pixels=green, stale_pixels=purple,
                         unavailable_pixels=gray, dark_pixels=dark))
    report = dict(passed=True, figures=rows, scope='actual RViz render pixels, not model quality')
    (directory / 'pixel-validation.json').write_text(json.dumps(report, indent=2))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    print(json.dumps(validate_figures(parser.parse_args().directory), indent=2))

from pathlib import Path
import sys
import numpy as np
from PIL import Image

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent / 'vector-deps'))
import vtracer

source = root / 'rhino-urbanism-logo-v1.png'
pixels = np.asarray(Image.open(source).convert('RGB'))
palette = np.array([[255,255,255],[40,70,79],[44,95,124],[19,120,138],[122,173,172]], dtype=np.int32)
mask = pixels.min(axis=2) < 210
flat = np.full_like(pixels, 255)
height, width = mask.shape
for y in range(height):
    for x in range(width):
        if not mask[y,x]:
            continue
        stack = [(y,x)]
        mask[y,x] = False
        component = []
        while stack:
            cy,cx = stack.pop()
            component.append((cy,cx))
            for ny,nx in ((cy-1,cx),(cy+1,cx),(cy,cx-1),(cy,cx+1)):
                if 0 <= ny < height and 0 <= nx < width and mask[ny,nx]:
                    mask[ny,nx] = False
                    stack.append((ny,nx))
        if len(component) < 50:
            continue
        ys,xs = np.array(component).T
        median = np.median(pixels[ys,xs],axis=0)
        color = palette[1:][((palette[1:]-median)**2).sum(axis=1).argmin()]
        flat[ys,xs] = color
trace_input = Path(__file__).parent / 'v1-trace-input.png'
Image.fromarray(flat).save(trace_input)
vtracer.convert_image_to_svg_py(str(trace_input), str(root / 'rhino-urbanism-logo-v1.svg'), colormode='color', hierarchical='stacked', mode='spline', filter_speckle=12, color_precision=6, layer_difference=16, corner_threshold=60, length_threshold=4.0, max_iterations=10, splice_threshold=45, path_precision=2)
print('SVG vector export complete')

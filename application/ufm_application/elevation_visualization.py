"""Display an explicit static elevation export; no connection to occupancy or live terrain."""
import numpy as np
from matplotlib import colormaps


def surface_triangles(east, north, heights, valid, *, display_height_origin_m):
    if east.shape!=north.shape or east.shape!=heights.shape or east.shape!=valid.shape:
        raise ValueError('elevation_display_shape')
    if heights.ndim!=2 or max(heights.shape)>501:
        raise ValueError('elevation_display_bound')
    low,high=float(np.nanmin(heights)),float(np.nanmax(heights))
    # Retain all source values for queries; decimate only this display to every second sample.
    east,north,heights,valid=[v[::2,::2] for v in (east,north,heights,valid)]
    colours=colormaps['terrain']((heights-low)/max(1.,high-low))
    points=[];rgba=[]
    for row in range(heights.shape[0]-1):
        for col in range(heights.shape[1]-1):
            for tri in (((row,col),(row,col+1),(row+1,col)),((row,col+1),(row+1,col+1),(row+1,col))):
                if not all(valid[r,c] for r,c in tri):continue
                for r,c in tri:
                    points.append((float(east[r,c]),float(north[r,c]),float(heights[r,c]-display_height_origin_m)))
                    rgba.append(tuple(float(v) for v in colours[r,c]))
    return points,rgba

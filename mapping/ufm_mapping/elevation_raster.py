"""Bounded real elevation raster reader; separate from the synthetic M5 provider."""
from pathlib import Path
import math

import numpy as np
import rasterio
from rasterio.windows import Window
from pyproj import Transformer


class ElevationRaster:
    def __init__(self, path, *, center_lon, center_lat, product_kind, vertical_datum, half_cells=100):
        if (type(half_cells) is not int or not 1 <= half_cells <= 250 or
                not all(math.isfinite(x) for x in (center_lon, center_lat)) or
                not -180 <= center_lon <= 180 or not -80 <= center_lat <= 84):
            raise ValueError('elevation_window_or_coordinate')
        if product_kind not in ('DSM','DTM') or type(vertical_datum) is not str or not 1 <= len(vertical_datum) <= 128:
            raise ValueError('elevation_source_product_metadata')
        self.product_kind,self.vertical_datum=product_kind,vertical_datum
        self.path = Path(path).resolve()
        with rasterio.open(self.path) as src:
            if src.count != 1 or src.crs is None:
                raise ValueError('single_band_georeferenced_raster_required')
            to_source = Transformer.from_crs('EPSG:4326', src.crs, always_xy=True)
            x, y = to_source.transform(center_lon, center_lat)
            row, col = src.index(x, y)
            if not (half_cells <= row < src.height-half_cells and half_cells <= col < src.width-half_cells):
                raise ValueError('elevation_window_outside_source')
            self.window = Window(col-half_cells, row-half_cells, 2*half_cells+1, 2*half_cells+1)
            values = src.read(1, window=self.window, masked=True).astype('float64')
            self.valid = ~np.ma.getmaskarray(values) & np.isfinite(values.data)
            self.heights = values.filled(np.nan)
            self.heights[~self.valid] = np.nan
            self.affine = src.window_transform(self.window)
            self.source_crs = src.crs.to_string()
            self.source_shape = (src.height, src.width)
        zone = min(60, int((center_lon+180)//6)+1)
        self.projected_crs = 'EPSG:%d' % ((32600 if center_lat >= 0 else 32700)+zone)
        self.to_projected = Transformer.from_crs(self.source_crs, self.projected_crs, always_xy=True)
        self.from_projected = Transformer.from_crs(self.projected_crs, self.source_crs, always_xy=True)
        self.origin = Transformer.from_crs('EPSG:4326', self.projected_crs, always_xy=True).transform(center_lon, center_lat)
        rr, cc = np.indices(self.heights.shape)
        xx, yy = self.affine * (cc+.5, rr+.5)
        east, north = self.to_projected.transform(xx, yy)
        self.east = np.asarray(east)-self.origin[0]
        self.north = np.asarray(north)-self.origin[1]
        if not np.any(self.valid):
            raise ValueError('elevation_window_all_nodata')

    def query(self, east_m, north_m):
        if not all(type(v) in (int, float) and math.isfinite(v) for v in (east_m, north_m)):
            raise ValueError('elevation_query_nonfinite')
        if not (self.east.min()-100 <= east_m <= self.east.max()+100 and
                self.north.min()-100 <= north_m <= self.north.max()+100):
            return dict(status='outside', height_m=None, source_index=None)
        x, y = self.from_projected.transform(east_m+self.origin[0], north_m+self.origin[1])
        if not all(math.isfinite(v) for v in (x, y)):
            return dict(status='outside', height_m=None, source_index=None)
        col, row = ~self.affine * (x, y)
        row, col = math.floor(row), math.floor(col)
        if not (0 <= row < self.heights.shape[0] and 0 <= col < self.heights.shape[1]):
            return dict(status='outside', height_m=None, source_index=None)
        index = [row+int(self.window.row_off), col+int(self.window.col_off)]
        if not self.valid[row, col]:
            return dict(status='no_data', height_m=None, source_index=index)
        return dict(status='valid', height_m=float(self.heights[row, col]), source_index=index)

    def metadata(self):
        return dict(schema_version='ufm.elevation.preview.v1',source_path=str(self.path), source_crs=self.source_crs, projected_crs=self.projected_crs,
            local_frame='terrain_utm_local', axes=['UTM easting offset', 'UTM northing offset', self.vertical_datum+' height'],
            projected_origin_m=list(self.origin), affine=list(self.affine)[:6],
            source_shape=list(self.source_shape), window=[int(self.window.col_off), int(self.window.row_off),
                int(self.window.width), int(self.window.height)],
            product_kind=self.product_kind, vertical_datum=self.vertical_datum, height_unit='m',
            height_min_m=float(np.nanmin(self.heights)), height_max_m=float(np.nanmax(self.heights)),
            valid_cells=int(self.valid.sum()), no_data_cells=int((~self.valid).sum()),
            sampling='nearest source pixel; no interpolation or filled holes',
            registered_to_gazebo=False, occupancy_fusion=False)

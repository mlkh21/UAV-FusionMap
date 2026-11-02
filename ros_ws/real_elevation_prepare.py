"""Crop a real Copernicus tile and verify local queries against independent source reads."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import sys

import numpy as np
import rasterio
from ufm_mapping.elevation_raster import ElevationRaster


def main():
    if sys.executable != '/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':
        raise RuntimeError('Radar-Diffusion Python required')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--longitude', type=float, default=103.25)
    parser.add_argument('--latitude', type=float, default=30.75)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    run = root/'.runtime/runs'/('real-elevation-'+datetime.now().strftime('%Y%m%dT%H%M%S%f'))
    run.mkdir(parents=True)
    terrain = ElevationRaster(args.source, center_lon=args.longitude, center_lat=args.latitude,
        product_kind='DSM',vertical_datum='EGM2008')
    meta = terrain.metadata()
    meta.update(source_url='https://copernicus-dem-30m.s3.eu-central-1.amazonaws.com/'
        'Copernicus_DSM_COG_10_N30_00_E103_00_DEM/Copernicus_DSM_COG_10_N30_00_E103_00_DEM.tif',
        source_title='Copernicus DEM GLO-30 Public, 2021 release',
        attribution='Copernicus DEM GLO-30; European Union / Airbus',
        center_lon=args.longitude, center_lat=args.latitude, python=sys.executable)
    checks = []
    with rasterio.open(args.source) as src:
        for row in (0, 25, 75, 100, 150, 175, 200):
            for col in (0, 25, 75, 100, 150, 175, 200):
                result = terrain.query(float(terrain.east[row,col]), float(terrain.north[row,col]))
                source_row, source_col = row+int(terrain.window.row_off), col+int(terrain.window.col_off)
                expected = src.read(1, window=rasterio.windows.Window(source_col, source_row, 1, 1), masked=True)[0,0]
                if np.ma.is_masked(expected):
                    assert result['status']=='no_data' and result['height_m'] is None
                else:
                    assert result['status']=='valid' and result['height_m']==float(expected)
                assert result['source_index']==[source_row,source_col]
                checks.append(dict(local_xy=[float(terrain.east[row,col]),float(terrain.north[row,col])],result=result))
        profile=src.profile.copy()
        profile.update(width=201, height=201, transform=terrain.affine, compress='deflate')
        with rasterio.open(run/'crop.tif', 'w', **profile) as cropped:
            cropped.write(src.read(1, window=terrain.window),1)
    assert terrain.query(1e8,1e8)['status']=='outside'
    np.savez_compressed(run/'terrain.npz',east=terrain.east,north=terrain.north,height=terrain.heights,valid=terrain.valid)
    (run/'metadata.json').write_text(json.dumps(meta,indent=2,allow_nan=False)+'\n')
    (run/'query-checks.json').write_text(json.dumps(dict(passed=True,source_checks=len(checks),queries=checks,
        outside_returns_no_height=True),indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(run=str(run),metadata=meta,source_query_checks=len(checks)),indent=2))


if __name__=='__main__':
    main()

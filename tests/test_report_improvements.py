"""Real raster coordinates/no-data and actual C++ Radar parameterization behavior."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.runtime/terrain-tools'))
sys.path.insert(0,str(ROOT/'application'))
import numpy as np
import rasterio
from rasterio.transform import from_origin
from ufm_mapping.elevation_raster import ElevationRaster
from ufm_sensors.scene_stream import validate_scene_profile
from ufm_application.elevation_visualization import surface_triangles
import yaml


class ReportImprovementsTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.path=Path(self.temp.name)/'terrain.tif'
        values=np.arange(25,dtype='float32').reshape(5,5)
        values[1,1]=0;values[2,2]=-3;values[3,3]=-9999
        with rasterio.open(self.path,'w',driver='GTiff',width=5,height=5,count=1,dtype='float32',
                crs='EPSG:4326',transform=from_origin(103,31,.001,.001),nodata=-9999) as ds:
            ds.write(values,1)
        self.reader=ElevationRaster(self.path,center_lon=103.0025,center_lat=30.9975,
            half_cells=1,product_kind='DSM',vertical_datum='test_height_datum')

    def tearDown(self):self.temp.cleanup()

    def query_cell(self,row,col):
        return self.reader.query(float(self.reader.east[row,col]),float(self.reader.north[row,col]))

    def test_zero_negative_and_nodata_remain_distinct(self):
        self.assertEqual(self.query_cell(0,0)['height_m'],0.)
        self.assertEqual(self.query_cell(1,1)['height_m'],-3.)
        self.assertEqual(self.query_cell(2,2),dict(status='no_data',height_m=None,source_index=[3,3]))

    def test_row_axis_projection_roundtrip_preserves_source_indices(self):
        self.assertGreater(self.reader.north[0,1],self.reader.north[2,1])
        for row in range(3):
            for col in range(3):self.assertEqual(self.query_cell(row,col)['source_index'],[row+1,col+1])

    def test_outside_and_invalid_coordinates_do_not_produce_height(self):
        self.assertEqual(self.reader.query(1e8,1e8)['status'],'outside')
        for x in (float('nan'),float('inf'),True):
            with self.assertRaises(ValueError):self.reader.query(x,0.)

    def test_window_bound_and_product_metadata_are_explicit(self):
        self.assertEqual(self.reader.metadata()['vertical_datum'],'test_height_datum')
        for extra in ({'half_cells':251},{'half_cells':True},{'product_kind':'unknown'},{'vertical_datum':''}):
            args=dict(center_lon=103.0025,center_lat=30.9975,half_cells=1,product_kind='DSM',vertical_datum='test')
            args.update(extra)
            with self.assertRaises(ValueError):ElevationRaster(self.path,**args)

    def test_nodata_hole_does_not_create_display_triangles(self):
        y,x=np.indices((5,5));z=np.ones((5,5))*10;valid=np.ones((5,5),dtype=bool)
        full,_=surface_triangles(x,y,z,valid,display_height_origin_m=10)
        valid[2,2]=False
        hole,_=surface_triangles(x,y,z,valid,display_height_origin_m=10)
        self.assertLess(len(hole),len(full))
        self.assertTrue(all(p[2]==0 for p in hole))

    def test_parameter_profile_rejects_nonfinite_bool_and_bad_model(self):
        profile=yaml.safe_load((ROOT/'configs/report_sensor_scene.yaml').read_text())
        validate_scene_profile(profile)
        for key,value in [('range_std_m',float('nan')),('detection_probability',1.1),
                ('noise_seed',True),('max_points',0),('measurement_model','unknown')]:
            bad=copy.deepcopy(profile);bad['radar'][key]=value
            with self.assertRaises(ValueError):validate_scene_profile(bad)

    def test_actual_cpp_measurements_repeat_seed_and_have_noise_distance_dropout_and_budget(self):
        binary=Path(self.temp.name)/'radar-probe'
        subprocess.run(['g++','-std=c++17','-O1','-I'+str(ROOT/'sensors'),
            str(ROOT/'tests/report_radar_probe.cpp'),'-o',str(binary)],check=True,timeout=30)
        result=json.loads(subprocess.check_output([str(binary)],text=True,timeout=5))
        self.assertTrue(result['passed']);self.assertEqual(result['point_budget'],256)
        self.assertGreater(result['near'],result['far']*3)


if __name__=='__main__':unittest.main()

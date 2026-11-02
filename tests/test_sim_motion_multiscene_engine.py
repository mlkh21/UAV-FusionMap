"""SW-04B scene assembly and independent actual-wire rejection checks."""
import copy
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

import numpy as np
import yaml

from sim_motion_fixture import ROOT
from sim_motion_multiscene_fixture import expected
from sim_motion_multiscene_live import compare_scan,proper_rotation,scan_oracle
from sim_motion_multiscene_oracle import ray_direction,rotation_from_ic,rotation_estimate
from ufm_simulation.motion_suite import case_spec,load_suite
from ufm_simulation.multiscene_world import assemble_scene,create_suite_ic,create_suite_world
from ufm_simulation.scene_motion_world import create_motion_world


class MultisceneEngineTests(unittest.TestCase):
    def setUp(self):
        self.suite=load_suite(ROOT/'configs/sim_motion_multiscene_fixture.json')
        self.scene=yaml.safe_load((ROOT/'configs/sensor_scene.yaml').read_text())

    def test_empty_world_removes_ground_without_altering_legacy_world(self):
        original=copy.deepcopy(self.scene)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'scene.world'
            spec=case_spec(self.suite,'S06')
            scene=assemble_scene(self.scene,spec)
            create_suite_world(scene,spec,ROOT,path)
            world=ET.parse(path).find('world')
            self.assertEqual([m.attrib['name'] for m in world.findall('model')],['sensor_aircraft'])
            self.assertEqual(world.findall('model/link/collision'),[])
            self.assertEqual(len(world.findall('model/link/sensor')),2)
            create_motion_world(self.scene,ROOT,path)
            self.assertIsNotNone(ET.parse(path).find("world/model[@name='ground']"))
        self.assertEqual(self.scene,original)

    def test_suite_world_installs_same_collision_visual_boxes_and_preserves_mount(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'scene.world';spec=case_spec(self.suite,'S07')
            scene=assemble_scene(self.scene,spec)
            create_suite_world(scene,spec,ROOT,path)
            world=ET.parse(path).find('world')
            model=world.find("model[@name='obstacle_wall']")
            self.assertEqual(model.find('link/collision/geometry/box/size').text,'1 12 12')
            self.assertEqual(model.find('link/visual/geometry/box/size').text,'1 12 12')
            pose=world.find("model[@name='sensor_aircraft']/link/sensor[@name='functional_radar']/pose").text
            self.assertEqual([float(v) for v in pose.split()],[.8,0,0,0,0,0])
            scene['objects']=[]
            with self.assertRaises(ValueError):create_suite_world(scene,spec,ROOT,path)

    def test_ic_only_changes_approved_fields_and_keeps_original_units(self):
        source=ROOT/'.runtime/src/px4-v1.13.3/Tools/jsbsim_bridge/scene/LSZH.xml'
        before=ET.parse(source).getroot()
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'initial.xml'
            create_suite_ic(source,path,[10,5,90],5.)
            after=ET.parse(path).getroot()
            for child in before:
                if child.tag=='gamma':
                    self.assertIsNone(after.find('gamma'))
                    continue
                self.assertEqual(child.attrib,after.find(child.tag).attrib)
                if child.tag not in ('altitude','vt','phi','theta','psi'):
                    self.assertEqual(child.text,after.find(child.tag).text)
            self.assertEqual([float(after.find(k).text) for k in ('phi','theta','psi')],[10,5,90])
            self.assertEqual(float(after.find('altitude').text),8.)
            self.assertAlmostEqual(float(after.find('vt').text)*.3048,5.)
            create_suite_ic(source,path,[0,0,90],5.)
            self.assertEqual(ET.parse(path).find('gamma').text,before.find('gamma').text)

    def test_nonzero_heading_scan_oracle_rotates_mount_and_first_hit(self):
        literals=expected()
        for case_id in ('S02','S03'):
            case=next(c for c in literals['cases'] if c['case_id']==case_id)
            boxes=literals['geometry'][case['geometry_id']]['objects']
            wanted,_=scan_oracle([0,0,8],rotation_from_ic(case['ic_degrees']),boxes)
            self.assertAlmostEqual(wanted[12*96+48],10.7/ray_direction(48,12)[0],places=12)

    def test_compare_scan_rejects_missing_duplicate_and_wrong_range(self):
        distance=7.201029212956173
        point=[x*distance for x in ray_direction(48,12)]+[0.,1/(1+distance**2)]
        wanted={12*96+48:distance}
        self.assertLess(compare_scan(np.array([point],dtype=np.float32),wanted)['maximum_range_error_m'],.00001)
        for points in ([],[point,point]):
            with self.assertRaises(ValueError):compare_scan(points,wanted)
        bad=copy.deepcopy(point)
        for axis in range(3):bad[axis]*=(distance+.02)/distance
        with self.assertRaisesRegex(ValueError,'range'):compare_scan([bad],wanted)

    def test_compare_scan_rejects_nonfinite_and_wrong_grid_direction(self):
        with self.assertRaises(ValueError):compare_scan([[float('nan'),0,0,0,0]],{})
        with self.assertRaisesRegex(ValueError,'angle'):
            compare_scan([[7.2,0.,0.,0.,0.]],{12*96+48:7.2})

    def test_zero_exemption_policy_checks_every_ray_even_when_many_are_near_edges(self):
        ids=list(range(63));wanted={i:5. for i in ids}
        points=[[x*5 for x in ray_direction(i%96,i//96)]+[0.,1/26] for i in ids]
        self.assertEqual(compare_scan(points,wanted)['points'],63)
        with self.assertRaises(ValueError):compare_scan(points[:-1],wanted)
        points[-1][0]+=.1
        with self.assertRaises(ValueError):compare_scan(points,wanted)

    def test_empty_scan_oracle_and_comparison_do_not_seed_evidence(self):
        wanted,boundary=scan_oracle([0,0,8],rotation_from_ic([0,0,90]),[])
        self.assertEqual((wanted,boundary),({},[]))
        self.assertEqual(compare_scan([],wanted),dict(points=0,maximum_range_error_m=0.))

    def test_occlusion_geometry_does_not_guarantee_echo_after_view_rotates_away(self):
        boxes=expected()['geometry']['occlusion_boxes']['objects']
        visible,_=scan_oracle([0,0,8],rotation_from_ic([0,0,90]),boxes)
        departed,_=scan_oracle([5,0,4.6],rotation_from_ic([0,-80,90]),boxes)
        self.assertTrue(visible)
        self.assertEqual(departed,{})

    def test_raw_rotation_contract_and_independent_unit_rotation_are_distinct(self):
        rotation=np.array(rotation_from_ic([10,5,90]))
        raw=rotation@np.diag([1+1e-10,1-1e-10,1.])
        before=raw.copy()
        np.testing.assert_allclose(proper_rotation(raw),rotation,rtol=0,atol=1e-12)
        np.testing.assert_array_equal(raw,before)
        with self.assertRaises(ValueError):proper_rotation(rotation@np.diag([1.0001,1,1]))

    def test_scalar_quaternion_estimate_preserves_the_declared_conversion_method(self):
        from scipy.spatial.transform import Rotation
        for angles in ([0,0,0],[10,5,90],[0,0,180],[170,0,0],[0,170,0]):
            raw=np.array(rotation_from_ic(angles))@np.diag([1+1e-10,1-1e-10,1.])
            before=raw.copy()
            estimate=rotation_estimate(raw.tolist())
            np.testing.assert_allclose(estimate,Rotation.from_matrix(raw).as_matrix(),rtol=0,atol=1e-12)
            np.testing.assert_array_equal(raw,before)
        raw=np.array(rotation_from_ic([0,0,0]))*(1+1e-10)
        self.assertGreater(np.max(np.abs(np.array(rotation_estimate(raw.tolist()))-proper_rotation(raw))),1e-12)

    def test_geometry_rpc_message_names_one_obstacle_and_has_zero_twist(self):
        from sim_motion_multiscene_delivery import MultisceneDelivery
        epoch=case_spec(self.suite,'S07')['epochs'][0]
        message=MultisceneDelivery.epoch_message(epoch)
        self.assertEqual((message.model_name,message.reference_frame),('obstacle_wall','world'))
        self.assertEqual((message.pose.position.x,message.pose.position.y,message.pose.position.z),(100,0,8))
        self.assertEqual(message.pose.orientation.w,1.)
        self.assertEqual(message.twist.linear.x+message.twist.angular.z,0.)

    def test_native_suite_uses_one_image_range_sample_without_changing_static_config(self):
        from sim_motion_multiscene_delivery import MultisceneDelivery
        instance=object.__new__(MultisceneDelivery);instance.root=ROOT
        instance.profile=yaml.safe_load((ROOT/'configs/sensor_scene.yaml').read_text())
        baseline=(ROOT/'configs/sensor_scene.rviz').read_text()
        value=yaml.safe_load(instance.native_config())
        display=next(d for d in value['Visualization Manager']['Displays'] if d['Class']=='rviz/Image')
        self.assertEqual(display['Median window'],1)
        self.assertTrue(display['Normalize Range'])
        self.assertEqual((ROOT/'configs/sensor_scene.rviz').read_text(),baseline)

    def test_new_cli_is_explicit_and_old_cli_does_not_accept_suite_case(self):
        for name in ('sim_motion_gate_run.py','sim_motion_multiscene_ros_run.py'):
            result=subprocess.run([sys.executable,'-B',str(ROOT/'ros_ws'/name),'--help'],capture_output=True,text=True,timeout=10.)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual('--case' in result.stdout,name=='sim_motion_multiscene_ros_run.py')
            self.assertEqual('--fault-step' in result.stdout,name=='sim_motion_gate_run.py')
        result=subprocess.run([sys.executable,'-B',str(ROOT/'ros_ws/sim_motion_multiscene_ros_run.py'),
            '--case','S08','--fault-step','250'],capture_output=True,text=True,timeout=10.)
        self.assertEqual(result.returncode,2)


if __name__=='__main__':unittest.main()

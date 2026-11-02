"""Inspect owned native renders together with clock and display-state receipts."""
import json
from pathlib import Path

import numpy as np
from PIL import Image


def verify_figures(run, case_id, rows=None):
    from sensor_msgs.msg import Image as RosImage
    directory=Path(run)/'figures'
    if rows is None:rows=json.loads((Path(run)/'receipts.json').read_text())['rows']
    stages={'before':100000000,'after':1000000000,'history':1000000000}
    if case_id=='S07':stages['empty']=900000000
    elif case_id!='S05':raise ValueError('undeclared_native_case')
    images={}
    views=[]

    def read(path):
        path=Path(path)
        if path.parent.resolve()!=directory.resolve():raise ValueError('native_capture_directory')
        with Image.open(path) as value:pixels=np.array(value.convert('RGB'))
        if min(pixels.shape[:2])<200:raise ValueError('native_capture_small')
        return pixels

    for stage,stamp in stages.items():
        for view in ('gazebo','rviz'):
            receipt=json.loads((directory/('%s-%s.json'%(view,stage))).read_text())
            pixels=read(receipt['file'])
            if min(pixels.shape[:2])<400 or pixels.std()<5:raise ValueError('native_capture_blank')
            images[view,stage]=pixels
            row=dict(view=view,stage=stage,file=Path(receipt['file']).name,
                size=[pixels.shape[1],pixels.shape[0]],standard_deviation=float(pixels.std()))
            if view=='rviz':
                history=stage=='history'
                if (receipt['history']!=history or int(receipt['clock_ns'])!=stamp or
                        receipt['radar_enabled']==history or receipt['infrared_enabled']==history or
                        receipt['raw_displays_enabled']==history):
                    raise ValueError('native_clock_or_display_state')
                targets=receipt['render_targets']
                ir=[read(t['file']) for t in targets if t['role']=='infrared']
                scene=[read(t['file']) for t in targets if t['role']=='scene']
                if len(scene)!=1 or len(ir)!=(0 if history else 1):
                    raise ValueError('native_owned_targets_missing')
                if scene[0].std()<4:raise ValueError('native_scene_target_blank')
                if ir:
                    row['infrared_stddev']=float(ir[0].std())
                    raw=next(r for r in rows['infrared'] if r['timestamp']==stamp)
                    message=RosImage().deserialize((Path(run)/raw['wire']).read_bytes())
                    values=np.frombuffer(message.data,dtype='<f4')
                    row['actual_infrared_span']=float(np.ptp(values))
                    # A uniform actual Camera background is legitimate, including S05 after.
                    if np.ptp(values)>0 and ir[0].std()<4:raise ValueError('native_ir_target_blank')
            views.append(row)
    changes={}
    for view in ('gazebo','rviz'):
        a,b=images[view,'before'],images[view,'after']
        if a.shape!=b.shape:raise ValueError('native_capture_size_changed')
        changed=int(np.count_nonzero(np.max(np.abs(a.astype(int)-b.astype(int)),axis=2)>20))
        if changed<200:raise ValueError('native_motion_not_visible')
        changes[view]=changed
    return dict(passed=True,case_id=case_id,views=views,changed_pixels=changes,
        actual_render_targets=True,history_raw_disabled=True,uniform_ir_checked_against_actual_wire=True)

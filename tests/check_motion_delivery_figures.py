"""Validate the actual owned native render targets, not desktop screenshots."""
import json
from pathlib import Path

import numpy as np
from PIL import Image


def verify_figures(directory):
    directory=Path(directory)
    result=dict(passed=True,views=[])
    images={}
    for stage in ('before','after','history'):
        for view in ('gazebo','rviz'):
            receipt=json.loads((directory/('%s-%s.json'%(view,stage))).read_text())
            path=Path(receipt['file'])
            if path.parent.resolve()!=directory.resolve():raise ValueError('native_capture_directory')
            pixels=np.array(Image.open(path).convert('RGB'))
            if min(pixels.shape[:2])<400 or pixels.std()<5:raise ValueError('native_capture_blank')
            images[(view,stage)]=pixels
            result['views'].append(dict(view=view,stage=stage,file=path.name,
                size=list(Image.open(path).size),standard_deviation=float(pixels.std())))
            if view=='rviz' and (receipt['history']!=(stage=='history') or
                    receipt['raw_displays_enabled']!=(stage!='history')):
                raise ValueError('native_raw_history_not_cleared')
    for view in ('gazebo','rviz'):
        before,after=images[(view,'before')],images[(view,'after')]
        if before.shape!=after.shape:raise ValueError('native_capture_size_changed')
        changed=int(np.count_nonzero(np.max(np.abs(before.astype(int)-after),axis=2)>20))
        if changed<200:raise ValueError('native_motion_not_visible')
        result[view+'_changed_pixels']=changed
    for stage in ('before','after'):
        receipt=json.loads((directory/('rviz-'+stage+'.json')).read_text())
        base=Path(receipt['file']).stem
        targets=list(directory.glob(base+'-viewport-*.png'))
        if len(targets)<2:raise ValueError('native_ir_render_target_missing')
        for path in targets:
            if np.array(Image.open(path)).std()<4:raise ValueError('native_sensor_render_target_blank')
    return result

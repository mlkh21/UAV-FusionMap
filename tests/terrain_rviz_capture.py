"""Capture only the owned RViz render target, driven by explicit fixture commands."""
import argparse
import ctypes
import json
import os
from pathlib import Path
import signal
import sys

if sys.executable != '/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':
    raise RuntimeError('Radar-Diffusion Python required')
sys.path.insert(0, '/usr/lib/python3/dist-packages')
from PyQt5 import QtCore, QtWidgets
from rviz import bindings as rviz
import sip
sys.path.remove('/usr/lib/python3/dist-packages')
import rospy


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('run',type=Path)
    parser.add_argument('--library',type=Path,required=True)
    parser.add_argument('--config',type=Path)
    args=parser.parse_args()
    rospy.init_node('terrain_capture',disable_signals=True)
    app=QtWidgets.QApplication(['UAV-FusionMap Terrain'])
    frame=rviz.VisualizationFrame()
    frame.setSplashPath('')
    frame.initialize()
    config=rviz.Config()
    rviz.YamlConfigReader().readFile(config,str(args.config or Path(__file__).resolve().parents[1]/'configs/terrain.rviz'))
    frame.load(config)
    frame.resize(1200,800)
    frame.show()
    library=ctypes.CDLL(str(args.library))
    capture=library.ufm_capture_rviz
    capture.argtypes=[ctypes.c_void_p,ctypes.c_char_p]
    capture.restype=ctypes.c_char_p
    seen=set()
    def tick():
        command=args.run/'capture-request.json'
        if not command.exists():return
        value=json.loads(command.read_text())
        label=value['label']
        if label in seen:return
        seen.add(label)
        root=frame.getManager().getRootDisplayGroup()
        for index in range(root.numDisplays()):
            display=root.getDisplayAt(index)
            if display.getClassId()=='rviz/MarkerArray':
                display.subProp('Marker Topic').setValue(value.get('topic','/uav/terrain/v1/markers'))
        def save():
            path=args.run/'figures'/(label+'.png')
            error=capture(sip.unwrapinstance(frame),os.fsencode(path))
            if error:raise RuntimeError(error.decode())
            (args.run/('capture-'+label+'.json')).write_text(json.dumps(dict(path=str(path),label=label)))
        QtCore.QTimer.singleShot(600,save)
    timer=QtCore.QTimer()
    timer.timeout.connect(tick)
    timer.start(100)
    rospy.set_param('/terrain_capture/ready',True)
    signal.signal(signal.SIGINT,lambda *_:app.quit())
    result=app.exec_()
    rospy.signal_shutdown('capture closed')
    return result


if __name__=='__main__':sys.exit(main())

"""Run unchanged legacy entrypoints with build outputs explicitly confined to .runtime/ros."""
from pathlib import Path
import sys


def main():
    if sys.executable!='/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':
        raise RuntimeError('Radar-Diffusion Python required')
    if len(sys.argv)!=2 or sys.argv[1] not in ('motion','static'):
        raise ValueError('choose motion or static compatibility')
    case=sys.argv[1]
    if case=='motion':
        import sim_motion_gate_run as entry
        original=entry.build
        def build(root,run,manifest,**kwargs):
            return original(root,run,manifest,output_directory=root/'.runtime/ros/flight-compat-v1-build')
        entry.build=build
        sys.argv=[str(Path(entry.__file__)),'--no-native']
        return entry.main(delivery_mode=True)
    import sensor_scene_run as entry
    original=entry.build_tools
    def build(root,run,manifest,**kwargs):
        return original(root,run,manifest,output_directory=root/'.runtime/ros/flight-compat-static-build')
    entry.build_tools=build
    sys.argv=[str(Path(entry.__file__)),'--check']
    return entry.main()


if __name__=='__main__':sys.exit(main())

"""Audit named completed runs and execute independent public replay, without new physics."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys

from sim_flight_scene_checks import audit_run

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('runs',nargs='+',type=Path)
    args=parser.parse_args()
    if sys.executable!='/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':raise RuntimeError('Radar-Diffusion Python required')
    output=ROOT/'.runtime/runs'/('flight-scene-audit-'+datetime.now().strftime('%Y%m%dT%H%M%S%f'))
    output.mkdir();print(output,flush=True)
    results=[]
    for item in args.runs:
        run=item.resolve()
        if run.parent!=ROOT/'.runtime/runs':raise ValueError('audit outside owned runs')
        result=audit_run(run)
        recording=run/'public-recording.json'
        public=json.loads(recording.read_text())
        if public['observations']:
            command=[sys.executable,'-B',str(ROOT/'ros_ws/local_map_replay.py'),'--input',str(recording),
                '--run-id',run.name,'--map-config',str(run/'map.yaml'),'--free-threshold','0.3','--occupied-threshold','0.7']
            with (output/(run.name+'-replay.log')).open('x') as stream:
                child=subprocess.run(command,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,timeout=30)
            if child.returncode:raise ValueError('independent flight public replay failed')
            result['independent_replay_process']=True
        result['directory']=str(run)
        with (output/(run.name+'.json')).open('x') as stream:json.dump(result,stream,indent=2)
        results.append(result)
        print(run.name+': verified',flush=True)
    with (output/'report.json').open('x') as stream:
        json.dump(dict(passed=True,python=sys.executable,cases=results,
            binding_status='unverified',control_gate_accepted=False),stream,indent=2)
    return 0


if __name__=='__main__':sys.exit(main())

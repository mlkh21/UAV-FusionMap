"""SW-03 explicit end-to-end motion handoff; defaults to native Gazebo/RViz."""
from sim_motion_gate_run import main

if __name__ == '__main__':
    raise SystemExit(main(delivery_mode=True))

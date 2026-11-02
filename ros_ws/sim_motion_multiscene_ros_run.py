"""Explicit SW-04B ROS case gate; distinct from the SW-04A offline entry."""
from sim_motion_gate_run import main

if __name__ == '__main__':
    raise SystemExit(main(delivery_mode=True,suite_mode=True))

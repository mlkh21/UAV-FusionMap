#!/usr/bin/env python
"""Explicit optional terrain entry; use the isolated Radar-Diffusion environment."""
import sys


def main():
    if sys.executable != '/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':
        raise RuntimeError('Radar-Diffusion Python required')
    import rospy
    from terrain_ros import TerrainNode
    rospy.init_node('terrain_provider')
    node = TerrainNode(rospy)
    node.run()


if __name__ == '__main__':
    main()

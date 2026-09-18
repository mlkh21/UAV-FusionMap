"""Conda启动原生Noetic播放器；exec使监督器获取C++真实退出码。"""
import os
import sys
from roslib.packages import find_node


if __name__ == '__main__':
    players = find_node('rosbag', 'play')
    if not players:
        raise RuntimeError('找不到已验证的Noetic原生rosbag/play')
    os.execv(players[0], [players[0]] + sys.argv[1:])

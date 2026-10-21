# SIM-01默认Python环境为用户指定的Radar-Diffusion；不修改调用终端。
UFM_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
export UFM_ROOT
export UFM_CONDA_PREFIX="${UFM_CONDA_PREFIX:-/home/zxj/anaconda3/envs/Radar-Diffusion}"
export UFM_PYTHON="$UFM_CONDA_PREFIX/bin/python"
if [[ ! -x "$UFM_PYTHON" ]]; then
    printf '%s\n' "Radar-Diffusion Python不存在：$UFM_PYTHON" >&2
    return 1
fi
# 只在独立子进程激活；保留既有系统Noetic为ROS库来源。
source /home/zxj/anaconda3/etc/profile.d/conda.sh
conda activate "$UFM_CONDA_PREFIX"
# 固定Noetic源码运行环境：元变量来自/opt/ros/noetic/etc/catkin/profile.d。
# 不调用setup的系统Python helper，也不继承任意ROS工作区的环境hook。
export ROS_VERSION=1
export ROS_PYTHON_VERSION=3
export ROS_DISTRO=noetic
export ROS_ROOT=/opt/ros/noetic/share/ros
export ROS_ETC_DIR=/opt/ros/noetic/etc/ros
export UFM_RUNTIME="$UFM_ROOT/.runtime"
export UFM_ROS_PREFIX="$UFM_RUNTIME/deps/ros-noetic/opt/ros/noetic"
export PATH="$UFM_ROOT/ros_ws/bin:$UFM_CONDA_PREFIX/bin:$UFM_RUNTIME/ros/devel/bin:$UFM_ROS_PREFIX/bin:/opt/ros/noetic/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export CMAKE_PREFIX_PATH="$UFM_RUNTIME/ros/devel:$UFM_ROS_PREFIX:/opt/ros/noetic"
export PKG_CONFIG_PATH="$UFM_RUNTIME/ros/devel/lib/pkgconfig:$UFM_ROS_PREFIX/lib/pkgconfig:/opt/ros/noetic/lib/pkgconfig"
export ROS_PACKAGE_PATH="$UFM_ROOT/ros_ws/src:$UFM_ROS_PREFIX/share:/opt/ros/noetic/share"
export LD_LIBRARY_PATH="$UFM_RUNTIME/ros/devel/lib:$UFM_ROS_PREFIX/lib:$UFM_RUNTIME/deps/ros-noetic/usr/lib/x86_64-linux-gnu:/opt/ros/noetic/lib"
export PYTHONPATH="$UFM_RUNTIME/ros/devel/lib/python3/dist-packages:$UFM_ROOT/simulation:$UFM_ROOT/sensors:$UFM_ROOT/perception:$UFM_ROOT/mapping:$UFM_ROOT/ros_ws:$UFM_RUNTIME/deps/python-radar:$UFM_ROS_PREFIX/lib/python3/dist-packages:/opt/ros/noetic/lib/python3/dist-packages"
export ROS_HOME="$UFM_RUNTIME/ros/home"
export ROS_LOG_DIR="$UFM_RUNTIME/ros/logs"
export GEOGRAPHICLIB_GEOID_PATH="$UFM_RUNTIME/deps/geographiclib/share/GeographicLib/geoids"
export PYTHONDONTWRITEBYTECODE=1
export PYTHONNOUSERSITE=1
export CCACHE_DISABLE=1

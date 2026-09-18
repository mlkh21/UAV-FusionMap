# SIM-00A项目前缀；由simulation/sim00a_env.sh在独立Bash子进程中加载。
# 版本及验证边界见simulation/BUILD_SIM00A.md。
UFM_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
export UFM_ROOT
export UFM_RUNTIME="$UFM_ROOT/.runtime"
export UFM_ROS_PREFIX="$UFM_RUNTIME/deps/ros-noetic/opt/ros/noetic"
export UFM_JSBSIM_PREFIX="$UFM_RUNTIME/deps/jsbsim-1.1.13/usr"

source /opt/ros/noetic/setup.bash
export PATH="$UFM_ROS_PREFIX/bin:/opt/ros/noetic/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export ROS_PACKAGE_PATH="$UFM_ROS_PREFIX/share:/opt/ros/noetic/share"
export CMAKE_PREFIX_PATH="$UFM_ROS_PREFIX:/opt/ros/noetic"
export LD_LIBRARY_PATH="$UFM_ROS_PREFIX/lib:$UFM_RUNTIME/deps/ros-noetic/usr/lib/x86_64-linux-gnu:/opt/ros/noetic/lib"
export PYTHONPATH="$UFM_ROS_PREFIX/lib/python3/dist-packages:/opt/ros/noetic/lib/python3/dist-packages"
export ROS_HOME="$UFM_RUNTIME/ros/home"
export ROS_LOG_DIR="$UFM_RUNTIME/ros/logs"
export GEOGRAPHICLIB_GEOID_PATH="$UFM_RUNTIME/deps/geographiclib/share/GeographicLib/geoids"
export PYTHONDONTWRITEBYTECODE=1
export CCACHE_DISABLE=1

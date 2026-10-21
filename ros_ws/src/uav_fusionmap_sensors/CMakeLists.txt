cmake_minimum_required(VERSION 3.0.2)
project(uav_fusionmap_sensors)
find_package(catkin REQUIRED COMPONENTS rospy rosgraph_msgs diagnostic_msgs std_msgs geometry_msgs nav_msgs tf2_ros uav_fusionmap_msgs)
catkin_package()
catkin_install_python(PROGRAMS scripts/state_adapter_node.py scripts/perf01a_sensor_node.py
                      scripts/perf01a_async_common.py scripts/perf01a_async_producer_node.py
                      scripts/perf01a_async_matcher_node.py
                      scripts/sens_train_01_fake_lidar_node.py scripts/sens_train_01_recorder_node.py
                      DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION})

cmake_minimum_required(VERSION 3.0.2)
project(uav_fusionmap_simulation)
find_package(catkin REQUIRED COMPONENTS rospy rosgraph_msgs mavros_msgs diagnostic_msgs uav_fusionmap_msgs)
catkin_package()
catkin_install_python(PROGRAMS scripts/state_clock_node.py scripts/perf01a_source_node.py
                      scripts/perf01a_async_source_node.py
                      scripts/sens_train_01_source_node.py
                      DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION})

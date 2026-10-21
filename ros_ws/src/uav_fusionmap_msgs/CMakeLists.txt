cmake_minimum_required(VERSION 3.0.2)
project(uav_fusionmap_msgs)
find_package(catkin REQUIRED COMPONENTS message_generation)
catkin_python_setup()
add_message_files(FILES
  ObservationHeader.msg Uncertainty.msg Quality.msg AircraftState.msg
  RadarPoint.msg RadarFrame.msg InfraredFrame.msg SpatialContext.msg SensorBundle.msg
  OccupancyVoxel.msg OccupancyObservation.msg MapCell.msg MapSnapshot.msg PerfEvent.msg
  MapQueryResult.msg)
add_service_files(FILES MapQuery.srv)
generate_messages()
catkin_package(CATKIN_DEPENDS message_runtime)

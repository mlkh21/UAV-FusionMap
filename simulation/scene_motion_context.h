#pragma once
#include <mutex>
#include <functional>
#include <uav_fusionmap_sim_scene_msgs/SceneFrame.h>

// One in-process typed infrastructure mailbox shared by the three new-mode plugins.
// It removes metadata callback races; raw payloads and completion ACKs still use ROS.
namespace ufm_scene {
struct Context {
  std::mutex mutex;
  bool initialized = false;
  bool radar_ready = false, infrared_ready = false;
  std::function<void()> radar_capture;
  uav_fusionmap_sim_scene_msgs::SceneFrame frame;
};
Context& context();
bool frame(uav_fusionmap_sim_scene_msgs::SceneFrame& result);
}

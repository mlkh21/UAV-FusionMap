#include "scene_motion_context.h"
namespace ufm_scene {
Context& context() { static Context value; return value; }
bool frame(uav_fusionmap_sim_scene_msgs::SceneFrame& result) {
  auto& value = context();
  std::lock_guard<std::mutex> lock(value.mutex);
  if (!value.initialized) return false;
  result = value.frame;
  return true;
}
}

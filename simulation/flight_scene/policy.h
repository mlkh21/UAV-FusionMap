#pragma once
#include <cmath>
#include <uav_fusionmap_sim_scene_msgs/SceneFrame.h>

namespace ufm_flight {
constexpr unsigned version=2, max_steps=10000, capture_after=7500, first_capture=7525;
inline bool capture(uint64_t step) {return step>capture_after && step<=max_steps && step%25==0;}
inline bool geometry(const uav_fusionmap_sim_scene_msgs::SceneFrame& f) {
  const auto& p=f.state.position;
  return p[2]>.2 && std::hypot(std::hypot(p[0],p[1]),p[2]-.5)<=250.
    && (f.step_index!=0 || (p[0]==0 && p[1]==0 && p[2]==.5));
}
}

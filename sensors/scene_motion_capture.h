#pragma once
#include "../simulation/scene_motion_context.h"
#include <ros/ros.h>
#include <uav_fusionmap_sim_scene_msgs/SceneCaptureAck.h>
#ifdef UFM_FLIGHT_SCENE
#include "../simulation/flight_scene/policy.h"
#endif

namespace ufm_scene {
class Capture {
 public:
  void load(ros::NodeHandle& node, int kind) {
    kind_ = kind;
#ifdef UFM_FLIGHT_SCENE
    ack_ = node.advertise<uav_fusionmap_sim_scene_msgs::SceneCaptureAck>("/uav/flight/scene/capture_ack", 4);
#else
    ack_ = node.advertise<uav_fusionmap_sim_scene_msgs::SceneCaptureAck>("/uav/scene/capture_ack", 4);
#endif
    auto& c = context();
    std::lock_guard<std::mutex> lock(c.mutex);
    (kind == 1 ? c.radar_ready : c.infrared_ready) = true;
  }
  bool begin(int64_t timestamp, uav_fusionmap_sim_scene_msgs::SceneFrame& f) {
    if (!frame(f) ||
#ifdef UFM_FLIGHT_SCENE
        f.protocol_version != 2 || !ufm_flight::capture(f.step_index) ||
#else
        f.step_index == 0 || f.step_index % 25 ||
#endif
        timestamp < f.state.header.timestamp || last_step_ == f.step_index) return false;
    if (timestamp != f.state.header.timestamp) {
      finish(f, timestamp, false, "scene_capture_time_mismatch");
      return false;
    }
    return true;
  }
  void finish(const uav_fusionmap_sim_scene_msgs::SceneFrame& f, int64_t stamp,
              bool published=true, const std::string& reason="") {
    uav_fusionmap_sim_scene_msgs::SceneCaptureAck a;
    a.protocol_version =
#ifdef UFM_FLIGHT_SCENE
        2;
#else
        1;
#endif
    a.run_id = f.state.header.run_id; a.clock_id = f.state.header.clock_id;
    a.step_index = f.step_index; a.measurement_timestamp = stamp; a.sensor_kind = kind_;
    a.published = published; a.reason = reason;
    ack_.publish(a); last_step_ = f.step_index;
  }
 private:
  ros::Publisher ack_; int kind_ = 0; uint64_t last_step_ = 0;
};
}

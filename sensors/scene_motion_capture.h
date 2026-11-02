#pragma once
#include "../simulation/scene_motion_context.h"
#include <ros/ros.h>
#include <uav_fusionmap_sim_scene_msgs/SceneCaptureAck.h>

namespace ufm_scene {
class Capture {
 public:
  void load(ros::NodeHandle& node, int kind) {
    kind_ = kind;
    ack_ = node.advertise<uav_fusionmap_sim_scene_msgs::SceneCaptureAck>("/uav/scene/capture_ack", 4);
    auto& c = context();
    std::lock_guard<std::mutex> lock(c.mutex);
    (kind == 1 ? c.radar_ready : c.infrared_ready) = true;
  }
  bool begin(int64_t timestamp, uav_fusionmap_sim_scene_msgs::SceneFrame& f) {
    if (!frame(f) || f.step_index == 0 || f.step_index % 25 ||
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
    a.protocol_version = 1; a.run_id = f.state.header.run_id; a.clock_id = f.state.header.clock_id;
    a.step_index = f.step_index; a.measurement_timestamp = stamp; a.sensor_kind = kind_;
    a.published = published; a.reason = reason;
    ack_.publish(a); last_step_ = f.step_index;
  }
 private:
  ros::Publisher ack_; int kind_ = 0; uint64_t last_step_ = 0;
};
}

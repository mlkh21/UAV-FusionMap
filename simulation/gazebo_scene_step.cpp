// Paused geometry proxy. JSBSim owns dynamics; ROS callbacks never run on the world thread.
#include <gazebo/gazebo.hh>
#include <gazebo/physics/physics.hh>
#include <ros/ros.h>
#include <ros/serialization.h>
#include <gazebo_msgs/SetModelState.h>
#include <uav_fusionmap_sim_scene_msgs/SceneStep.h>
#include <uav_fusionmap_sim_scene_msgs/SceneCaptureAck.h>
#include "scene_motion_context.h"
#include <chrono>
#include <condition_variable>
#include <cmath>
#include <vector>
#include <sstream>
#include <iomanip>

namespace gazebo {
using Frame = uav_fusionmap_sim_scene_msgs::SceneFrame;
using Ack = uav_fusionmap_sim_scene_msgs::SceneCaptureAck;
using Step = uav_fusionmap_sim_scene_msgs::SceneStep;
class FusionSceneStep : public ModelPlugin {
 public:
  void Load(physics::ModelPtr model, sdf::ElementPtr) override {
    if (!ros::isInitialized()) throw std::runtime_error("Gazebo ROS API required");
    model_ = model; world_ = model_->GetWorld(); world_->SetPaused(true);
    node_.reset(new ros::NodeHandle());
    node_->getParam("/ufm_scene_motion/run_id", run_);
    if (run_.empty() || run_.size() > 110) throw std::runtime_error("motion run required");
    node_->param("/ufm_scene_motion/drop_ack_kind", drop_, 0);
    node_->param("/ufm_scene_motion/drop_ack_step", drop_step_, 250);
    applied_ = node_->advertise<Frame>("/uav/scene/frame_applied", 1, true);
    ack_ = node_->subscribe("/uav/scene/capture_ack", 4, &FusionSceneStep::AckReceived, this);
    service_ = node_->advertiseService("/uav/scene/step", &FusionSceneStep::StepReceived, this);
    std::string geometry_case;
    node_->param<std::string>("/ufm_scene_motion/geometry_case", geometry_case, "");
    if (!geometry_case.empty()) {
      if (geometry_case != "S07") throw std::runtime_error("unsupported geometry case");
      geometry_service_ = node_->advertiseService("/uav/scene/geometry_epoch", &FusionSceneStep::GeometryEpoch, this);
    }
  }
 private:
  static int64_t ns(const common::Time& t) { return int64_t(t.sec)*1000000000 + t.nsec; }
  static std::vector<uint8_t> bytes(const Frame& frame) {
    const auto length = ros::serialization::serializationLength(frame);
    if (length > 4096) throw std::runtime_error("scene_wire_limit");
    std::vector<uint8_t> data(length);
    ros::serialization::OStream stream(data.data(), length);
    ros::serialization::serialize(stream, frame);
    return data;
  }
  bool Valid(const Frame& f) {
    const auto& s = f.state; const auto& h = s.header; const auto& u = s.quality.uncertainty;
    if (f.protocol_version != 1 || f.step_index > 250 || f.registration_id != "jsbsim_cg_to_scene_enu_v1" ||
        h.run_id != run_ || h.clock_id != "sim:" + run_ || h.schema_version != "0.1" ||
        h.timestamp != int64_t(f.step_index)*4000000 || h.frame_id != "scene_world" ||
        h.sample_id != "scene.frame:"+run_+":"+std::to_string(f.step_index) ||
        h.source_type != 0 || h.status != 0 || !h.reason.empty() || s.state_source != 0 ||
        s.body_frame_id != "base_link" || s.velocity_frame_id != "base_link" ||
        s.quality.confidence_available || s.quality.confidence != 0 || std::signbit(s.quality.confidence) ||
        u.status != 0 || !u.kind.empty() || !u.value.empty() || !u.unit.empty() ||
        u.source != "jsbsim_scene_truth_no_covariance_v1") return false;
    double norm = 0.;
    for (auto v : s.orientation_xyzw) { if (!std::isfinite(v)) return false; norm += v*v; }
    if (std::abs(std::sqrt(norm)-1.) > 1e-12) return false;
    for (const auto* vector : {&s.position, &s.linear_velocity, &f.angular_velocity_flu})
      for (auto v : *vector) if (!std::isfinite(v)) return false;
    if (s.position[2] <= .5 || std::hypot(std::hypot(s.position[0],s.position[1]),s.position[2]-8.) > 200.)
      return false;
    return true;
  }
  void AckReceived(const ros::MessageEvent<Ack const>& event) {
    std::lock_guard<std::mutex> lock(mutex_);
    const auto& a = *event.getMessage();
    if (!waiting_ || locked_) return;
    if (event.getPublisherName() != ros::this_node::getName() || a.protocol_version != 1 ||
        a.run_id != run_ || a.clock_id != "sim:"+run_ || a.step_index != pending_step_ ||
        (a.sensor_kind != 1 && a.sensor_kind != 2)) {
      error_ = "scene_ack_identity_or_source";
    } else if (a.sensor_kind == drop_ && a.step_index == uint64_t(drop_step_)) return;
    else if (!a.published || !a.reason.empty() || a.measurement_timestamp != int64_t(pending_step_)*4000000)
      error_ = "scene_ack_measurement_failed";
    else {
      (a.sensor_kind == 1 ? radar_ : infrared_) = true;
    }
    condition_.notify_all();
  }
  bool StepReceived(Step::Request& request, Step::Response& response) {
    const auto started = std::chrono::steady_clock::now();
    std::unique_lock<std::mutex> serial(serial_, std::try_to_lock);
    auto fail = [&](const std::string& reason, bool terminal=false) {
      response.accepted = false; response.reason = reason;
      if (terminal) { std::lock_guard<std::mutex> lock(mutex_); locked_ = true; waiting_ = false; }
      return true;
    };
    if (!serial.owns_lock()) return fail("scene_transaction_pending");
    if (locked_) return fail("scene_run_locked");
    std::vector<uint8_t> data;
    try { data = bytes(request.frame); } catch (...) { return fail("scene_wire_limit"); }
    const auto& f = request.frame;
    if (!Valid(f)) return fail("scene_invalid_frame");
    if (completed_ && f.step_index == last_step_) {
      if (data != last_bytes_) return fail("scene_step_conflict", true);
      response = last_response_; return true;
    }
    if (f.step_index != (completed_ ? last_step_+1 : 0)) return fail("scene_step_sequence");
    auto& context = ufm_scene::context();
    std::function<void()> ray_capture;
    {
      std::lock_guard<std::mutex> lock(context.mutex);
      if (!context.radar_ready || !context.infrared_ready || !context.radar_capture)
        return fail("scene_sensors_not_ready");
      context.frame = f; context.initialized = true;
      ray_capture = context.radar_capture;
    }
    if (!world_->IsPaused() || ns(world_->SimTime()) != int64_t(completed_ ? last_step_ : 0)*4000000)
      return fail("scene_world_not_paused_or_time", true);
    const auto& p = f.state.position; const auto& q = f.state.orientation_xyzw;
    model_->SetWorldPose(ignition::math::Pose3d(ignition::math::Vector3d(p[0],p[1],p[2]),
        ignition::math::Quaterniond(q[3],q[0],q[1],q[2])));
    applied_.publish(f);
    const bool capture = f.step_index > 0 && f.step_index % 25 == 0;
    {
      std::lock_guard<std::mutex> lock(mutex_);
      waiting_ = capture; pending_step_ = f.step_index; radar_ = infrared_ = false; error_.clear();
    }
    if (f.step_index > 0) world_->Step(4);
    if (capture) ray_capture();
    response.has_applied_frame = true; response.applied_frame = f;
    const auto readback = model_->WorldPose();
    response.applied_frame.state.position = {readback.Pos().X(), readback.Pos().Y(), readback.Pos().Z()};
    response.applied_frame.state.orientation_xyzw = {
        readback.Rot().X(),readback.Rot().Y(),readback.Rot().Z(),readback.Rot().W()};
    if (ns(world_->SimTime()) != f.state.header.timestamp || !world_->IsPaused())
      return fail("scene_world_step_time", true);
    if (capture) {
      std::unique_lock<std::mutex> lock(mutex_);
      const bool ready = condition_.wait_until(lock, started + std::chrono::seconds(f.step_index == 25 ? 3 : 1),
          [&]{ return !error_.empty() || (radar_ && infrared_); });
      waiting_ = false;
      response.radar_captured = radar_; response.infrared_captured = infrared_;
      response.radar_timestamp = radar_ ? f.state.header.timestamp : 0;
      response.infrared_timestamp = infrared_ ? f.state.header.timestamp : 0;
      if (!ready || !error_.empty()) {
        locked_ = true;
        response.reason = !error_.empty() ? error_ : !radar_ ? "scene_radar_timeout" : "scene_ir_timeout";
        return true;
      }
    }
    if (std::chrono::steady_clock::now() > started + std::chrono::seconds(f.step_index == 25 ? 3 : 1))
      return fail("scene_transaction_deadline", true);
    response.accepted = true;
    last_step_ = f.step_index; completed_ = true; last_bytes_ = data; last_response_ = response;
    return true;
  }
  bool GeometryEpoch(gazebo_msgs::SetModelState::Request& request,
                     gazebo_msgs::SetModelState::Response& response) {
    std::unique_lock<std::mutex> serial(serial_, std::try_to_lock);
    auto reject = [&](const std::string& reason) { response.success = false; response.status_message = reason; return true; };
    if (!serial.owns_lock()) return reject("scene_transaction_pending");
    if (locked_) return reject("scene_run_locked");
    if (!completed_ || waiting_ || geometry_epoch_ >= 2 || last_step_ != (geometry_epoch_ == 0 ? 100u : 225u) ||
        !world_->IsPaused() || ns(world_->SimTime()) != int64_t(last_step_)*4000000)
      return reject("scene_geometry_boundary");
    const auto& s = request.model_state; const auto& p = s.pose.position; const auto& q = s.pose.orientation;
    const auto& v = s.twist.linear; const auto& w = s.twist.angular;
    const double x = geometry_epoch_ == 0 ? 100. : 12.;
    if (s.model_name != "obstacle_wall" || s.reference_frame != "world" ||
        p.x != x || p.y != 0. || p.z != 8. || q.x != 0. || q.y != 0. || q.z != 0. || q.w != 1. ||
        v.x != 0. || v.y != 0. || v.z != 0. || w.x != 0. || w.y != 0. || w.z != 0.)
      return reject("scene_geometry_request");
    auto obstacle = world_->ModelByName("obstacle_wall");
    auto link = obstacle ? obstacle->GetLink("body") : physics::LinkPtr();
    if (!obstacle || !obstacle->IsStatic() || !link || link->GetCollisions().size() != 1)
      return reject("scene_geometry_model");
    const int64_t before = ns(world_->SimTime());
    obstacle->SetWorldPose(ignition::math::Pose3d(x, 0., 8., 0., 0., 0.));
    const auto pose = obstacle->WorldPose();
    const auto collision = link->GetCollision(0u);
    const auto cp = collision->WorldPose();
    msgs::Collision cm; collision->FillMsg(cm);
    msgs::Link lm; link->FillMsg(lm);
    const msgs::Visual* obstacle_visual = nullptr;
    for (int i = 0; i < lm.visual_size(); ++i) {
      if (lm.visual(i).name() == link->GetScopedName() + "::visual") {
        if (obstacle_visual) { locked_ = true; return reject("scene_geometry_duplicate_visual"); }
        obstacle_visual = &lm.visual(i);
      }
    }
    if (!obstacle_visual || !obstacle_visual->geometry().has_box() || !cm.geometry().has_box()) {
      locked_ = true; return reject("scene_geometry_shape_readback");
    }
    const auto& visual = *obstacle_visual;
    const auto& cs = cm.geometry().box().size(); const auto& vs = visual.geometry().box().size();
    const auto vp = visual.pose().position();
    const auto vq = visual.pose().orientation();
    if (pose.Pos().Distance(ignition::math::Vector3d(x,0,8)) > 1e-9 || cp.Pos().Distance(pose.Pos()) > 1e-9 ||
        pose.Rot().Euler().Length() > 1e-12 || cp.Rot().Euler().Length() > 1e-12 ||
        std::abs(vp.x())+std::abs(vp.y())+std::abs(vp.z()) > 1e-12 ||
        std::abs(vq.x())+std::abs(vq.y())+std::abs(vq.z())+std::abs(vq.w()-1.) > 1e-12 ||
        cs.x()!=1. || cs.y()!=12. || cs.z()!=12. || vs.x()!=1. || vs.y()!=12. || vs.z()!=12. ||
        !world_->IsPaused() || ns(world_->SimTime()) != before) {
      locked_ = true; return reject("scene_geometry_readback");
    }
    std::ostringstream out; out << std::setprecision(17)
      << "{\"schema_version\":\"scene_geometry_epoch.v1\",\"run_id\":\"" << run_
      << "\",\"epoch_index\":" << geometry_epoch_ << ",\"step_index\":" << last_step_
      << ",\"world_before_ns\":" << before << ",\"world_after_ns\":" << ns(world_->SimTime())
      << ",\"paused\":true,\"model_position\":[" << pose.Pos().X() << "," << pose.Pos().Y() << ","
      << pose.Pos().Z() << "],\"collision_position\":["
      << cp.Pos().X() << "," << cp.Pos().Y() << "," << cp.Pos().Z()
      << "],\"visual_local_position\":[" << vp.x() << "," << vp.y() << "," << vp.z()
      << "],\"collision_size\":[" << cs.x() << "," << cs.y() << "," << cs.z()
      << "],\"visual_size\":[" << vs.x() << "," << vs.y() << "," << vs.z()
      << "],\"visual_records\":" << lm.visual_size() << ",\"visual_name\":\"" << visual.name() << "\"}";
    response.success = true; response.status_message = out.str(); ++geometry_epoch_;
    return true;
  }
  physics::ModelPtr model_; physics::WorldPtr world_;
  std::unique_ptr<ros::NodeHandle> node_;
  ros::ServiceServer service_, geometry_service_; ros::Subscriber ack_; ros::Publisher applied_;
  std::mutex serial_, mutex_; std::condition_variable condition_;
  std::string run_, error_; int drop_ = 0, drop_step_ = 250;
  bool completed_ = false, locked_ = false, waiting_ = false, radar_ = false, infrared_ = false;
  uint64_t last_step_ = 0, pending_step_ = 0;
  unsigned int geometry_epoch_ = 0;
  std::vector<uint8_t> last_bytes_; Step::Response last_response_;
};
GZ_REGISTER_MODEL_PLUGIN(FusionSceneStep)
}

// Sensor geometry approximation for static radar targets. No LiDAR ROS data is used.
#include <gazebo/gazebo.hh>
#include <gazebo/sensors/RaySensor.hh>
#include <gazebo/physics/physics.hh>
#include <ros/ros.h>
#include <sensor_msgs/PointCloud2.h>
#include <sensor_msgs/point_cloud2_iterator.h>
#include <array>
#include <cmath>
#include <memory>
#include <vector>
#include "radar_measurement_model.h"
#ifdef UFM_SCENE_MOTION
#include "scene_motion_capture.h"
#endif

namespace gazebo {
class FusionSceneRadar : public SensorPlugin {
 public:
  void Load(sensors::SensorPtr sensor, sdf::ElementPtr sdf) override {
    if (!ros::isInitialized()) throw std::runtime_error("Gazebo ROS API plugin required");
    sensor_ = std::dynamic_pointer_cast<sensors::RaySensor>(sensor);
    if (!sensor_) throw std::runtime_error("Radar requires a geometric ray sampler");
    auto world = physics::get_world(sensor_->WorldName());
    link_ = boost::dynamic_pointer_cast<physics::Link>(world->EntityByName(sensor_->ParentName()));
    if (!link_) throw std::runtime_error("Radar parent link unavailable");
    node_.reset(new ros::NodeHandle());
    publisher_ = node_->advertise<sensor_msgs::PointCloud2>("/uav/sensors/radar/raw", 2);
    controlled_ = sdf->HasElement("controlled_motion") && sdf->Get<bool>("controlled_motion");
    parameterized_ = sdf->HasElement("measurement_model");
    if (parameterized_) {
      if (sdf->Get<std::string>("measurement_model") != "parameterized_v1")
        throw std::runtime_error("unknown Radar measurement model");
      parameters_.detection_probability = sdf->Get<double>("detection_probability");
      parameters_.detection_distance_m = sdf->Get<double>("detection_distance_m");
      parameters_.range_std_m = sdf->Get<double>("range_std_m");
      parameters_.angle_std_rad = sdf->Get<double>("angle_std_rad");
      parameters_.doppler_std_mps = sdf->Get<double>("doppler_std_mps");
      parameters_.seed = sdf->Get<unsigned>("noise_seed");
      parameters_.max_points = sdf->Get<unsigned>("max_points");
      parameters_.validate();
    }
#ifdef UFM_SCENE_MOTION
    if (controlled_) {
      auto& context = ufm_scene::context();
      {
        std::lock_guard<std::mutex> lock(context.mutex);
        context.radar_capture = [this]{ sensor_->Update(true); };
      }
      capture_.load(*node_, 1);
    }
#else
    if (controlled_) throw std::runtime_error("motion build required");
#endif
    connection_ = sensor_->ConnectUpdated(std::bind(&FusionSceneRadar::Update, this));
    sensor_->SetActive(!controlled_);
  }
 private:
  void Update() {
    const auto stamp = sensor_->LastMeasurementTime();
#ifdef UFM_SCENE_MOTION
    uav_fusionmap_sim_scene_msgs::SceneFrame frame;
    if (controlled_ && !capture_.begin(int64_t(stamp.sec)*1000000000 + stamp.nsec, frame)) return;
#endif
    std::vector<double> ranges;
    sensor_->Ranges(ranges);
    const int horizontal = sensor_->RangeCount(), vertical = sensor_->VerticalRangeCount();
    if (horizontal < 2 || vertical < 2 || ranges.size() != size_t(horizontal * vertical)) return;
    const auto world_pose = link_->WorldPose() * sensor_->Pose();
    auto velocity = link_->WorldLinearVel() + link_->WorldAngularVel().Cross(
        link_->WorldPose().Rot().RotateVector(sensor_->Pose().Pos()));
#ifdef UFM_SCENE_MOTION
    if (controlled_) {
      const auto& v = frame.state.linear_velocity; const auto& w = frame.angular_velocity_flu;
      velocity = link_->WorldPose().Rot().RotateVector(ignition::math::Vector3d(v[0],v[1],v[2]) +
          ignition::math::Vector3d(w[0],w[1],w[2]).Cross(sensor_->Pose().Pos()));
    }
#endif
    std::vector<std::array<float, 5>> points;
    ufm_radar::Measurements measurement(parameters_, uint64_t(stamp.sec)*1000000000 + stamp.nsec);
    for (int v = 0; v < vertical; ++v) {
      const double elevation = sensor_->VerticalAngleMin().Radian() +
          v * (sensor_->VerticalAngleMax().Radian() - sensor_->VerticalAngleMin().Radian()) / (vertical - 1);
      for (int h = 0; h < horizontal; ++h) {
        double range = ranges[v * horizontal + h];
        if (!std::isfinite(range) || range <= sensor_->RangeMin() || range >= sensor_->RangeMax()) continue;
        double azimuth = sensor_->AngleMin().Radian() +
            h * (sensor_->AngleMax().Radian() - sensor_->AngleMin().Radian()) / (horizontal - 1);
        const ignition::math::Vector3d direction(std::cos(elevation) * std::cos(azimuth),
                                               std::cos(elevation) * std::sin(azimuth), std::sin(elevation));
        double doppler = -velocity.Dot(world_pose.Rot().RotateVector(direction));
        double measured_elevation = elevation;
        if (parameterized_ && !measurement.sample(range, azimuth, measured_elevation, doppler,
                                                  sensor_->RangeMin(), sensor_->RangeMax())) continue;
        const ignition::math::Vector3d measured(std::cos(measured_elevation)*std::cos(azimuth),
            std::cos(measured_elevation)*std::sin(azimuth), std::sin(measured_elevation));
        const auto& output_direction = parameterized_ ? measured : direction;
        points.push_back({float(range * output_direction.X()), float(range * output_direction.Y()),
                          float(range * output_direction.Z()), float(doppler), float(1. / (1. + range * range))});
      }
    }
    if (parameterized_) measurement.limit(points);
    sensor_msgs::PointCloud2 message;
    message.header.stamp = ros::Time(stamp.sec, stamp.nsec);
    message.header.frame_id = "radar";
    sensor_msgs::PointCloud2Modifier modifier(message);
    modifier.setPointCloud2Fields(5, "x", 1, sensor_msgs::PointField::FLOAT32,
        "y", 1, sensor_msgs::PointField::FLOAT32, "z", 1, sensor_msgs::PointField::FLOAT32,
        "doppler", 1, sensor_msgs::PointField::FLOAT32, "power", 1, sensor_msgs::PointField::FLOAT32);
    modifier.resize(points.size());
    sensor_msgs::PointCloud2Iterator<float> x(message, "x"), y(message, "y"), z(message, "z"),
        doppler(message, "doppler"), power(message, "power");
    for (const auto& point : points) {
      *x = point[0]; *y = point[1]; *z = point[2]; *doppler = point[3]; *power = point[4];
      ++x; ++y; ++z; ++doppler; ++power;
    }
    message.is_dense = true;
    publisher_.publish(message);
#ifdef UFM_SCENE_MOTION
    if (controlled_) capture_.finish(frame, int64_t(stamp.sec)*1000000000 + stamp.nsec);
#endif
  }
  sensors::RaySensorPtr sensor_;
  physics::LinkPtr link_;
  event::ConnectionPtr connection_;
  std::unique_ptr<ros::NodeHandle> node_;
  ros::Publisher publisher_;
  bool controlled_ = false;
  bool parameterized_ = false;
  ufm_radar::Parameters parameters_;
#ifdef UFM_SCENE_MOTION
  ufm_scene::Capture capture_;
#endif
};
GZ_REGISTER_SENSOR_PLUGIN(FusionSceneRadar)
}

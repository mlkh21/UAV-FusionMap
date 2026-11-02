// Sensor renderer for separate thermal-intensity materials, not radiometric temperature.
#include <gazebo/gazebo.hh>
#include <gazebo/plugins/CameraPlugin.hh>
#include <gazebo/rendering/Camera.hh>
#include <OGRE/OgreCamera.h>
#include <OGRE/OgreViewport.h>
#include <ros/ros.h>
#include <sensor_msgs/Image.h>
#include <sensor_msgs/CameraInfo.h>
#include <cmath>
#include <cstring>
#include <memory>
#ifdef UFM_SCENE_MOTION
#include "scene_motion_capture.h"
#endif

namespace gazebo {
class FusionSceneInfrared : public CameraPlugin {
 public:
  void Load(sensors::SensorPtr sensor, sdf::ElementPtr sdf) override {
    if (!ros::isInitialized()) throw std::runtime_error("Gazebo ROS API plugin required");
    CameraPlugin::Load(sensor, sdf);
    node_.reset(new ros::NodeHandle());
    image_ = node_->advertise<sensor_msgs::Image>("/uav/sensors/infrared/raw", 2);
    info_ = node_->advertise<sensor_msgs::CameraInfo>("/uav/sensors/infrared/camera_info", 2, true);
    controlled_ = sdf->HasElement("controlled_motion") && sdf->Get<bool>("controlled_motion");
#ifdef UFM_SCENE_MOTION
    if (controlled_) capture_.load(*node_, 2);
#else
    if (controlled_) throw std::runtime_error("motion build required");
#endif
    parentSensor->SetActive(true);
  }
  void OnNewFrame(const unsigned char* pixels, unsigned int width, unsigned int height,
                  unsigned int depth, const std::string&) override {
    if (!node_ || depth != 3) return;
    if (!thermal_ready_) {
      auto* viewport = camera->OgreCamera()->getViewport();
      if (!viewport) return;
      viewport->setMaterialScheme("FusionThermal");
      thermal_ready_ = true;
      return;  // First buffer preceded material selection; do not publish it as IR.
    }
    const auto stamp = parentSensor->LastMeasurementTime();
#ifdef UFM_SCENE_MOTION
    uav_fusionmap_sim_scene_msgs::SceneFrame frame;
    if (controlled_ && !capture_.begin(int64_t(stamp.sec)*1000000000 + stamp.nsec, frame)) return;
#endif
    if (published_ && stamp <= last_published_) return;
    last_published_ = stamp;
    published_ = true;
    sensor_msgs::Image message;
    message.header.stamp = ros::Time(stamp.sec, stamp.nsec);
    message.header.frame_id = "thermal_optical";
    message.width = width; message.height = height;
    message.encoding = "32FC1"; message.is_bigendian = false; message.step = width * sizeof(float);
    message.data.resize(width * height * sizeof(float));
    for (size_t i = 0; i < size_t(width) * height; ++i) {
      const float intensity = (pixels[3*i] + pixels[3*i+1] + pixels[3*i+2]) / (3.f * 255.f);
      std::memcpy(message.data.data() + i * sizeof(float), &intensity, sizeof(float));
    }
    image_.publish(message);
    sensor_msgs::CameraInfo info;
    info.header = message.header; info.width = width; info.height = height;
    const double focal = width / (2. * std::tan(camera->HFOV().Radian() / 2.));
    info.K = {focal, 0, width/2., 0, focal, height/2., 0, 0, 1};
    info.R = {1,0,0,0,1,0,0,0,1};
    info.P = {focal,0,width/2.,0,0,focal,height/2.,0,0,0,1,0};
    info.distortion_model = "plumb_bob";
    info.D = {0,0,0,0,0};
    info_.publish(info);
#ifdef UFM_SCENE_MOTION
    if (controlled_) capture_.finish(frame, int64_t(stamp.sec)*1000000000 + stamp.nsec);
#endif
  }
 private:
  bool thermal_ready_ = false;
  bool published_ = false;
  common::Time last_published_;
  std::unique_ptr<ros::NodeHandle> node_;
  ros::Publisher image_, info_;
  bool controlled_ = false;
#ifdef UFM_SCENE_MOTION
  ufm_scene::Capture capture_;
#endif
};
GZ_REGISTER_SENSOR_PLUGIN(FusionSceneInfrared)
}

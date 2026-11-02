// Explicit ground-truth source for the independent sensor scene, not a PX4 estimator replacement.
#include <gazebo/gazebo.hh>
#include <gazebo/physics/physics.hh>
#include <ros/ros.h>
#include <nav_msgs/Odometry.h>
#include <memory>

namespace gazebo {
class FusionScenePose : public ModelPlugin {
 public:
  void Load(physics::ModelPtr model, sdf::ElementPtr) override {
    if (!ros::isInitialized()) throw std::runtime_error("Gazebo ROS API plugin required");
    model_ = model;
    node_.reset(new ros::NodeHandle());
    publisher_ = node_->advertise<nav_msgs::Odometry>("/uav/scene/body_odometry", 10);
    connection_ = event::Events::ConnectWorldUpdateBegin(std::bind(&FusionScenePose::Update, this));
  }
 private:
  void Update() {
    const auto stamp = model_->GetWorld()->SimTime();
    if ((stamp - last_).Double() < .01) return;
    last_ = stamp;
    const auto pose = model_->WorldPose();
    const auto velocity = pose.Rot().RotateVectorReverse(model_->WorldLinearVel());
    nav_msgs::Odometry message;
    message.header.stamp = ros::Time(stamp.sec, stamp.nsec);
    message.header.frame_id = "scene_world";
    message.child_frame_id = "base_link";
    message.pose.pose.position.x = pose.Pos().X(); message.pose.pose.position.y = pose.Pos().Y();
    message.pose.pose.position.z = pose.Pos().Z();
    message.pose.pose.orientation.x = pose.Rot().X(); message.pose.pose.orientation.y = pose.Rot().Y();
    message.pose.pose.orientation.z = pose.Rot().Z(); message.pose.pose.orientation.w = pose.Rot().W();
    message.twist.twist.linear.x = velocity.X(); message.twist.twist.linear.y = velocity.Y();
    message.twist.twist.linear.z = velocity.Z();
    publisher_.publish(message);
  }
  physics::ModelPtr model_;
  common::Time last_;
  event::ConnectionPtr connection_;
  std::unique_ptr<ros::NodeHandle> node_;
  ros::Publisher publisher_;
};
GZ_REGISTER_MODEL_PLUGIN(FusionScenePose)
}

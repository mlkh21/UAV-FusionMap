// SIM00B-INIT-01：实际构造和消息编码回归；网络系统调用由链接包装捕获。
#include "mavlink_interface.h"
#include <cstdio>
#include <cstring>
#include <new>
#include <type_traits>
#include <vector>
#include <cstdlib>
static std::vector<mavlink_message_t> captured;
extern "C" int __wrap_poll(struct pollfd *fds, nfds_t count, int) {
  for (nfds_t i=0;i<count;++i) fds[i].revents=POLLOUT;
  return 1;
}
extern "C" ssize_t __wrap_sendto(int, const void *data, size_t size, int, const struct sockaddr *, socklen_t) {
  mavlink_message_t message{}; mavlink_status_t status{};
  auto bytes=static_cast<const uint8_t *>(data);
  for(size_t i=0;i<size;++i)
    if(mavlink_parse_char(MAVLINK_COMM_1,bytes[i],&message,&status)==MAVLINK_FRAMING_OK) captured.push_back(message);
  return size;
}
static void require(bool ok,const char *reason) { if(!ok){std::fprintf(stderr,"FAIL: %s\n",reason);std::exit(1);} }
int main() {
  using Storage=std::aligned_storage<sizeof(MavlinkInterface),alignof(MavlinkInterface)>::type;
  for(unsigned char pattern:{static_cast<unsigned char>(0),static_cast<unsigned char>(0xa5)}) {
    auto *storage=new Storage; std::memset(storage,pattern,sizeof(Storage));
    auto *object=new(storage) MavlinkInterface;
    auto raw=[](const bool *p){return *reinterpret_cast<const unsigned char *>(p);};
    require(raw(&object->hil_mode_)==0 && raw(&object->hil_state_level_)==0 && raw(&object->imu_updated_)==0,"constructor initial state");
  }
  // 仅替换网络边界；不调用Load、不创建socket、不启动仿真。
  auto *object=new MavlinkInterface;
  std::memset(object->fds_,0,sizeof(object->fds_)); object->fds_[1].fd=42;
  object->remote_simulator_addr_={}; object->remote_simulator_addr_len_=sizeof(sockaddr_in);
  SensorData::Imu imu; imu.accel_b=Eigen::Vector3d(1,2,3);imu.gyro_b=Eigen::Vector3d(4,5,6);
  SensorData::Magnetometer mag;mag.mag_b=Eigen::Vector3d(7,8,9);
  object->UpdateIMU(imu);object->UpdateMag(mag);
  object->UpdateBarometer(SensorData::Barometer{20,1000,100});
  object->UpdateAirspeed(SensorData::Airspeed{10});object->SendSensorMessages(10000);
  require(captured.size()==1,"first packet CRC/framing");
  mavlink_hil_sensor_t first{};mavlink_msg_hil_sensor_decode(&captured.back(),&first);
  require(first.time_usec==10000 && first.id==0 && first.fields_updated==8191,"full sensor identity/time/mask");
  require(first.xacc==1 && first.zgyro==6 && first.zmag==9 && first.temperature==20 && first.diff_pressure==10,"full sensor values");
  object->UpdateIMU(imu);object->SendSensorMessages(20000);
  require(captured.size()==2,"second packet CRC/framing");
  mavlink_hil_sensor_t second{};mavlink_msg_hil_sensor_decode(&captured.back(),&second);
  require(second.time_usec==20000 && second.id==0 && second.fields_updated==63,"IMU-only mask does not mark old sensors valid");
  require(second.xmag==0 && second.abs_pressure==0 && second.diff_pressure==0 && second.temperature==0,"unused payload deterministic");
  SensorData::Gps gps{};gps.time_utc_usec=30000;gps.fix_type=3;gps.latitude_deg=470000000;gps.longitude_deg=80000000;gps.altitude=420000;gps.satellites_visible=10;gps.id=0;
  object->SendGpsMessages(gps);
  require(captured.size()==3,"GPS packet CRC/framing");
  mavlink_hil_gps_t result{};mavlink_msg_hil_gps_decode(&captured.back(),&result);
  require(result.time_usec==30000 && result.lat==470000000 && result.id==0 && result.yaw==0,"GPS fields and unavailable yaw");
  std::puts("PASS: constructor patterns; full/IMU-only masks; payload CRC/decode; GPS unavailable yaw");
  // 测试进程退出释放资源；不调用生产析构，避免关闭未Load的默认文件描述符。
  return 0;
}

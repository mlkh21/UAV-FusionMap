#include "time_grid.h"
#include <common/mavlink.h>
#include <iomanip>
#include <iostream>
#include <limits>
#include <string>

void packet_hex(const mavlink_message_t& message) {
  uint8_t bytes[MAVLINK_MAX_PACKET_LEN];
  unsigned length=mavlink_msg_to_send_buffer(bytes,&message);
  const char* hex="0123456789abcdef";
  std::cout<<'"';
  for (unsigned i=0;i<length;++i) std::cout<<hex[bytes[i]>>4]<<hex[bytes[i]&15];
  std::cout<<'"';
}

void emit(double seconds, unsigned step) {
  try {
    uint64_t stamp=ufm_time::grid_time_us(seconds,step);
    mavlink_message_t sensor_message{},gps_message{};
    mavlink_hil_sensor_t sensor{};sensor.time_usec=stamp;
    mavlink_hil_gps_t gps{};gps.time_usec=stamp;
    mavlink_msg_hil_sensor_encode(1,200,&sensor_message,&sensor);
    mavlink_msg_hil_gps_encode(1,200,&gps_message,&gps);
    std::cout<<"{\"accepted\":true,\"source_step\":"<<step<<",\"time_usec\":"<<stamp<<",\"sensor_hex\":";
    packet_hex(sensor_message);std::cout<<",\"gps_hex\":";packet_hex(gps_message);std::cout<<"}"<<std::endl;
  } catch (const std::exception&) {std::cout<<"{\"accepted\":false}"<<std::endl;}
}

int main(int argc,char** argv) {
  if (argc==2 && std::string(argv[1])=="--trajectory") {
    double time=0;
    for(unsigned step=0;step<=2500;++step,time+=.004) emit(time,step);
    return 0;
  }
  std::string token;unsigned step;
  while(std::cin>>token>>step) emit(std::stod(token),step);
  return 0;
}

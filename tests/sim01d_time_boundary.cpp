// SIM-01D：验证HIL_SENSOR/HIL_GPS微秒时间在32位边界附近保持64位。
#include "mavlink_interface.h"

#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <type_traits>
#include <utility>
#include <vector>

static std::vector<mavlink_message_t> captured;

extern "C" int __wrap_poll(struct pollfd *fds, nfds_t count, int) {
  for (nfds_t i = 0; i < count; ++i) fds[i].revents = POLLOUT;
  return 1;
}

extern "C" ssize_t __wrap_sendto(int, const void *data, size_t size, int,
                                  const struct sockaddr *, socklen_t) {
  mavlink_message_t message{};
  mavlink_status_t status{};
  const auto *bytes = static_cast<const uint8_t *>(data);
  for (size_t i = 0; i < size; ++i) {
    if (mavlink_parse_char(MAVLINK_COMM_1, bytes[i], &message, &status) ==
        MAVLINK_FRAMING_OK) {
      captured.push_back(message);
    }
  }
  return static_cast<ssize_t>(size);
}

static void require(bool ok, const char *reason) {
  if (!ok) {
    std::fprintf(stderr, "FAIL: %s\n", reason);
    std::exit(1);
  }
}

int main() {
  using SensorArgument = uint64_t;
  static_assert(std::is_same<decltype(&MavlinkInterface::SendSensorMessages),
                             void (MavlinkInterface::*)(SensorArgument)>::value,
                "HIL_SENSOR API must accept uint64_t microseconds");
  static_assert(std::is_same<decltype(std::declval<SensorData::Gps>().time_utc_usec),
                             uint64_t>::value,
                "HIL_GPS intermediate timestamp must be uint64_t");

  auto *object = new MavlinkInterface;
  std::memset(object->fds_, 0, sizeof(object->fds_));
  object->fds_[1].fd = 42;
  object->remote_simulator_addr_ = {};
  object->remote_simulator_addr_len_ = sizeof(sockaddr_in);

  const uint64_t boundary_values[] = {
      2147483646ULL, 2147483647ULL, 2147483648ULL, 2400000000ULL};
  for (const uint64_t expected : boundary_values) {
    captured.clear();
    object->SendSensorMessages(expected);
    require(captured.size() == 1, "HIL_SENSOR packet framing");
    mavlink_hil_sensor_t decoded{};
    mavlink_msg_hil_sensor_decode(&captured.back(), &decoded);
    require(decoded.time_usec == expected, "HIL_SENSOR timestamp preserved");
  }

  SensorData::Gps gps{};
  gps.fix_type = 3;
  gps.latitude_deg = 470000000;
  gps.longitude_deg = 80000000;
  gps.altitude = 420000;
  gps.id = 0;
  for (const uint64_t expected : boundary_values) {
    captured.clear();
    gps.time_utc_usec = expected;
    object->SendGpsMessages(gps);
    require(captured.size() == 1, "HIL_GPS packet framing");
    mavlink_hil_gps_t decoded{};
    mavlink_msg_hil_gps_decode(&captured.back(), &decoded);
    require(decoded.time_usec == expected, "HIL_GPS timestamp preserved");
  }

  std::puts("PASS: HIL_SENSOR/HIL_GPS preserve 64-bit boundary timestamps");
  return 0;
}

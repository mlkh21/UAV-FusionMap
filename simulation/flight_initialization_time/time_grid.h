#pragma once
#include <cmath>
#include <cstdint>
#include <stdexcept>

namespace ufm_time {
inline uint64_t grid_time_us(double seconds, unsigned source_step) {
  if (!std::isfinite(seconds) || seconds < 0 || source_step > 2500)
    throw std::runtime_error("invalid_input");
  const long double error_ns = static_cast<long double>(seconds) * 1000000000.L
    - static_cast<long double>(source_step) * 4000000.L;
  if (std::abs(error_ns) > 1.L) throw std::runtime_error("invalid_input");
  return static_cast<uint64_t>(source_step) * 4000ULL;
}
}

namespace flight {
uint64_t source_time_us(double seconds, unsigned sensor_kind);
}

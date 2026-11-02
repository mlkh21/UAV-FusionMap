// Optional parameterized measurements after geometric visibility is resolved.
#pragma once
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <random>
#include <stdexcept>
#include <vector>

namespace ufm_radar {
struct Parameters {
  double detection_probability = 1., detection_distance_m = 40.;
  double range_std_m = 0., angle_std_rad = 0., doppler_std_mps = 0.;
  unsigned seed = 1, max_points = 2304;
  void validate() const {
    for (double v : {detection_probability, detection_distance_m, range_std_m, angle_std_rad, doppler_std_mps})
      if (!std::isfinite(v)) throw std::invalid_argument("nonfinite radar parameter");
    if (detection_probability < 0 || detection_probability > 1 || detection_distance_m <= 0 ||
        range_std_m < 0 || range_std_m > 2 || angle_std_rad < 0 || angle_std_rad > .05 ||
        doppler_std_mps < 0 || doppler_std_mps > 5 || max_points < 1 || max_points > 4096)
      throw std::invalid_argument("radar parameter outside declared bounds");
  }
};

class Measurements {
 public:
  Measurements(const Parameters& p, uint64_t timestamp_ns) : p_(p) {
    p_.validate();
    std::seed_seq seed{p.seed, unsigned(timestamp_ns), unsigned(timestamp_ns >> 32)};
    random_.seed(seed);
  }
  bool sample(double& range, double& azimuth, double& elevation, double& doppler,
              double minimum, double maximum) {
    const double ratio = range / p_.detection_distance_m;
    const double probability = p_.detection_probability / (1. + ratio*ratio);
    if (uniform_(random_) >= probability) return false;
    range += normal_(random_) * p_.range_std_m;
    azimuth += normal_(random_) * p_.angle_std_rad;
    elevation += normal_(random_) * p_.angle_std_rad;
    doppler += normal_(random_) * p_.doppler_std_mps;
    return range > minimum && range < maximum;
  }
  void limit(std::vector<std::array<float, 5>>& points) {
    if (points.size() > p_.max_points) {
      std::shuffle(points.begin(), points.end(), random_);
      points.resize(p_.max_points);
    }
  }
 private:
  Parameters p_;
  std::mt19937 random_;
  std::normal_distribution<double> normal_{0., 1.};
  std::uniform_real_distribution<double> uniform_{0., 1.};
};
}

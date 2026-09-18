#include "configuration_parser.h"

#include <cmath>
#include <cstdlib>
#include <iostream>
#include <type_traits>
#include <utility>

int main() {
  using ReturnType =
      decltype(std::declval<ConfigurationParser&>().getRealtimeFactor());

  bool passed = std::is_floating_point<ReturnType>::value;
  std::cout << "return_type_is_floating=" << std::boolalpha << passed
            << '\n';

  const double factors[] = {0.5, 1.0, 2.0};
  for (const double expected : factors) {
    const std::string configured = std::to_string(expected);
    if (setenv("PX4_SIM_SPEED_FACTOR", configured.c_str(), 1) != 0) {
      std::cerr << "setenv_failed factor=" << expected << '\n';
      return 2;
    }

    ConfigurationParser parser;
    if (!parser.ParseEnvironmentVariables()) {
      std::cerr << "parse_failed factor=" << expected << '\n';
      return 2;
    }

    const double actual = parser.getRealtimeFactor();
    const bool factor_passed = std::fabs(actual - expected) < 1e-6;
    passed = passed && factor_passed;
    std::cout << "configured=" << expected << " actual=" << actual
              << " preserved=" << factor_passed << '\n';
  }

  if (!passed) {
    std::cerr << "SIM-SPEED-01 getter contract FAILED\n";
    return 1;
  }

  std::cout << "SIM-SPEED-01 getter contract PASSED\n";
  return 0;
}

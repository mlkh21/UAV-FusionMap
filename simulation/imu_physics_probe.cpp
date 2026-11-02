// Standalone JSBSim observation. It does not load the PX4 bridge or its IMU noise model.
#include <FGFDMExec.h>
#include <initialization/FGInitialCondition.h>
#include <models/FGAccelerations.h>
#include <models/FGAircraft.h>
#include <models/FGAuxiliary.h>
#include <models/FGMassBalance.h>

#include <array>
#include <cmath>
#include <cstdlib>
#include <iomanip>
#include <iostream>
#include <string>

namespace {
constexpr double kFeetToMeters = 0.3048;

std::array<double, 3> readPilot(JSBSim::FGFDMExec& sim) {
  return {sim.GetPropertyValue("accelerations/a-pilot-x-ft_sec2") * kFeetToMeters,
          sim.GetPropertyValue("accelerations/a-pilot-y-ft_sec2") * kFeetToMeters,
          sim.GetPropertyValue("accelerations/a-pilot-z-ft_sec2") * kFeetToMeters};
}

void printVector(const std::array<double, 3>& values) {
  std::cout << '[' << values[0] << ',' << values[1] << ',' << values[2] << ']';
}
}  // namespace

int main(int argc, char** argv) {
  if (argc != 5) {
    std::cerr << "usage: imu_physics_probe <jsbsim_bridge_root> <roll_deg> <steps> <ground|freefall>\n";
    return 2;
  }
  char* end = nullptr;
  const double roll_deg = std::strtod(argv[2], &end);
  if (*end || !std::isfinite(roll_deg) || std::abs(roll_deg) > 45.) return 2;
  const long steps = std::strtol(argv[3], &end, 10);
  if (*end || steps < 1 || steps > 2500) return 2;
  const std::string scenario = argv[4];
  if (scenario != "ground" && scenario != "freefall") return 2;
  const std::string root = argv[1];

  JSBSim::FGFDMExec sim;
  sim.SetRootDir(SGPath(root));
  sim.SetEnginePath(SGPath("Engines"));
  sim.SetSystemsPath(SGPath("systems"));
  sim.SetAircraftPath(SGPath("models/Rascal"));
  if (!sim.LoadModel("Rascal110-JSBSim", false)) return 1;
  if (!sim.GetIC()->Load(SGPath(root + "/scene/LSZH.xml"), false)) return 1;
  sim.GetIC()->SetPhiDegIC(roll_deg);
  if (scenario == "freefall") sim.GetIC()->SetAltitudeAGLFtIC(1000.);
  sim.Setdt(0.004);
  if (!sim.RunIC()) return 1;

  std::array<double, 3> sum_pilot{}, first_pilot{}, last_pilot{}, sum_body{};
  double last_gravity = 0., roll_at_sample_deg = 0.;
  std::array<double, 3> pilot_at_sample{};
  for (long step = 0; step < steps; ++step) {
    const auto pilot = readPilot(sim);
    const auto internal = sim.GetAuxiliary()->GetPilotAccel();
    const auto body = sim.GetAccelerations()->GetBodyAccel();
    for (int axis = 0; axis < 3; ++axis) {
      if (!std::isfinite(pilot[axis]) ||
          std::abs(pilot[axis] - internal(axis + 1) * kFeetToMeters) > 1e-7) {
        std::cerr << "pilot property/internal mismatch\n";
        return 1;
      }
      sum_pilot[axis] += pilot[axis];
      sum_body[axis] += body(axis + 1) * kFeetToMeters;
    }
    if (step == 0) first_pilot = pilot;
    if (step == 50) {
      pilot_at_sample = pilot;
      roll_at_sample_deg = sim.GetPropertyValue("attitude/phi-deg");
    }
    last_pilot = pilot;
    last_gravity = sim.GetAccelerations()->GetGravAccelMagnitude() * kFeetToMeters;
    if (!sim.Run()) return 1;
  }
  for (int axis = 0; axis < 3; ++axis) {
    sum_pilot[axis] /= steps;
    sum_body[axis] /= steps;
  }
  const auto eye = sim.GetAircraft()->GetXYZep();
  const auto cg = sim.GetMassBalance()->GetXYZcg();
  std::cout << std::setprecision(9) << "IMU_PROBE_RESULT {\"scenario\":\"" << scenario
            << "\",\"roll_initial_deg\":" << roll_deg
            << ",\"steps\":" << steps << ",\"dt_s\":0.004,\"pilot_first_mps2\":";
  printVector(first_pilot);
  if (steps > 50) {
    std::cout << ",\"pilot_0p2s_mps2\":";
    printVector(pilot_at_sample);
    std::cout << ",\"roll_0p2s_deg\":" << roll_at_sample_deg;
  }
  std::cout << ",\"pilot_last_mps2\":";
  printVector(last_pilot);
  std::cout << ",\"pilot_mean_mps2\":";
  printVector(sum_pilot);
  std::cout << ",\"body_forces_mean_mps2\":";
  printVector(sum_body);
  std::cout << ",\"gravity_mps2\":" << last_gravity
            << ",\"eyepoint_struct_in\":[" << eye(1) << ',' << eye(2) << ',' << eye(3)
            << "],\"cg_struct_in\":[" << cg(1) << ',' << cg(2) << ',' << cg(3)
            << "]}" << std::endl;
  return 0;
}

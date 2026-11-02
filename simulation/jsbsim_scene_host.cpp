// Own host, linked to the existing unmodified bridge and its actual FGFDMExec.
#include "jsbsim_bridge.h"
#include <models/FGPropagate.h>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <stdexcept>

static void sample(JSBSim::FGFDMExec& fdm, uint64_t index, std::ostream& out) {
  const auto p = fdm.GetPropagate();
  out << std::setprecision(17) << "{\"step_index\":" << index
      << ",\"sim_time_s\":" << fdm.GetSimTime() << ",\"ecef_ft\":[";
  for (int i = 1; i <= 3; ++i) out << (i == 1 ? "" : ",") << p->GetLocation()(i);
  out << "],\"R_ecef_frd\":[";
  for (int i = 1; i <= 3; ++i) for (int j = 1; j <= 3; ++j)
    out << (i == 1 && j == 1 ? "" : ",") << p->GetTb2ec()(i,j);
  out << "],\"uvw_ftps\":[";
  for (int i = 1; i <= 3; ++i) out << (i == 1 ? "" : ",") << p->GetUVW()(i);
  out << "],\"pqr_radps\":[";
  for (int i = 1; i <= 3; ++i) out << (i == 1 ? "" : ",") << p->GetPQR()(i);
  out << "]}" << std::endl;
}

int main(int argc, char** argv) {
  if (argc != 6) return 2;  // configuration, IC, raw JSONL, registration JSON, command FIFO
  ConfigurationParser config;
  if (!config.ParseConfigFile(argv[1])) return 3;
  config.setHeadless(true);
  config.setInitScriptPath(argv[2]);
  config.ParseEnvironmentVariables();
  JSBSim::FGFDMExec fdm;
  JSBSimBridge bridge(&fdm, config);
  std::ofstream raw(argv[3], std::ios::out | std::ios::app);
  std::ofstream registration(argv[4]);
  if (!raw || !registration || fdm.GetSimTime() != 0.) return 4;
  registration << std::setprecision(17) << "{\"geodetic_latitude_rad\":"
      << fdm.GetPropagate()->GetGeodLatitudeRad() << ",\"longitude_rad\":"
      << fdm.GetPropagate()->GetLongitude() << "}" << std::endl;
  sample(fdm, 0, raw);
  std::ifstream commands(argv[5]);
  std::string command;
  uint64_t index = 0;
  while (std::getline(commands, command)) {
    if (command == "quit") return 0;
    if (command != "next" || index >= 250) return 5;
    bridge.Run();
    sample(fdm, ++index, raw);
  }
  return 0;
}

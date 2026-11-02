#include "jsbsim_bridge.h"
#include "diagnostics.h"
#include <filesystem>
#include <fstream>
#include <iostream>
#include <csignal>

int main(int argc, char** argv) {
  if (argc==2 && std::string(argv[1])=="--self-test") return flight::self_test();
  if (argc!=7) return 2;
  std::signal(SIGPIPE,SIG_IGN);
  if (!std::filesystem::create_directory(argv[3])) return 3;
  JSBSim::FGFDMExec fdm;
  try {
    flight::open(argv[3],argv[4],argv[6]);
    ConfigurationParser config;
    if (!config.ParseConfigFile(argv[1])) throw std::runtime_error("invalid_input");
    config.setHeadless(true);config.setInitScriptPath(argv[2]);config.ParseEnvironmentVariables();
    JSBSimBridge bridge(&fdm,config);
    flight::initial(fdm);
    std::ifstream input(argv[5]);std::string command;
    unsigned index=0;
    while (std::getline(input,command)) {
      if (command=="quit") {flight::terminal("requested_stop");return 0;}
      if (command!="next" || index>=2500) throw std::runtime_error("invalid_input");
      flight::begin(fdm,++index);
      bridge.Run();
      flight::emit(fdm);
      if (index==2500) {flight::terminal("window_complete");return 0;}
    }
    throw std::runtime_error("invalid_input");
  } catch (const std::exception& error) {
    try {flight::emit(fdm);} catch (...) {}
    flight::terminal(error.what());
    std::cerr << error.what() << std::endl;
    return 20;
  }
}

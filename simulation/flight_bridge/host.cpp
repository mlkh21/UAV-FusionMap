#include "jsbsim_bridge.h"
#include "diagnostics.h"
#include <filesystem>
#include <fstream>
#include <iostream>
#include <csignal>

int main(int argc,char** argv) {
  if(argc!=6) return 2; // bridge config, IC, exclusive output directory, run id, FIFO
  std::signal(SIGPIPE,SIG_IGN);
  const std::filesystem::path directory(argv[3]);
  if(!std::filesystem::create_directory(directory)) return 3;
  JSBSim::FGFDMExec fdm;
  try {
    flight::open(argv[3],argv[4]);
    ConfigurationParser config;
    if(!config.ParseConfigFile(argv[1])) throw std::runtime_error("bridge_config");
    config.setHeadless(true);config.setInitScriptPath(argv[2]);config.ParseEnvironmentVariables();
    JSBSimBridge bridge(&fdm,config);
    flight::initial(fdm);
    std::ifstream input(argv[5]);std::string command;
    unsigned index=0;
    while(std::getline(input,command)) {
      if(command=="quit") {flight::terminal("requested_stop");return 0;}
      if(command!="next" || index>=250) throw std::runtime_error("command_or_step_limit");
      flight::begin(fdm,++index);
      bridge.Run();
      flight::emit(fdm);
      if(index==250) {flight::terminal("diagnostic_window_complete");return 0;}
    }
    throw std::runtime_error("command_pipe_closed");
  } catch(const std::exception& error) {
    flight::emit(fdm);flight::terminal(error.what());
    std::cerr << error.what() << std::endl;
    return 20;
  }
}

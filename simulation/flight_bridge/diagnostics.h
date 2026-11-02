#pragma once
#include <FGFDMExec.h>
#include <common/mavlink.h>
#include <cstdint>
#include <string>

namespace flight {
void open(const std::string& directory, const std::string& run);
void wait_peer(int listener);
void connected(int socket);
void peer_closed();
void initial(JSBSim::FGFDMExec& fdm);
void begin(JSBSim::FGFDMExec& fdm, unsigned step);
void check_tx_id(unsigned id);
void wire_rx(const unsigned char* bytes, int length);
void wire_tx(const mavlink_message_t& message, const uint8_t* bytes, int length, ssize_t sent);
void received(const mavlink_message_t& message, const mavlink_hil_actuator_controls_t& controls);
void poll_guard();
bool allow_run();
bool has_actuator();
void requested(float value, const std::string& property);
void applied(JSBSim::FGFDMExec& fdm);
void finished(JSBSim::FGFDMExec& fdm, bool result);
void emit(JSBSim::FGFDMExec& fdm);
void terminal(const std::string& reason);
}

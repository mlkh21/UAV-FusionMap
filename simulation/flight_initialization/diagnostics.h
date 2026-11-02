#pragma once
#include <FGFDMExec.h>
#include <common/mavlink.h>
#include <cstdint>
#include <string>

namespace flight {
void open(const std::string&, const std::string&, const std::string&);
void wait_peer(int);
void connected(int);
void peer_closed();
void initial(JSBSim::FGFDMExec&);
void begin(JSBSim::FGFDMExec&, unsigned);
void check_tx_id(unsigned);
void wire_rx(const unsigned char*, int);
void wire_tx(const mavlink_message_t&, const uint8_t*, int, ssize_t);
void received(const mavlink_message_t&, const mavlink_hil_actuator_controls_t&);
void poll_guard();
bool allow_run();
bool has_actuator();
void requested(float, const std::string&);
void applied(JSBSim::FGFDMExec&);
void finished(JSBSim::FGFDMExec&, bool);
void emit(JSBSim::FGFDMExec&);
void terminal(const std::string&);
int self_test();
}

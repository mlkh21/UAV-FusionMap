"""Exact-context edits applied only to a new isolated bridge source copy."""


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('flight bridge source context mismatch: ' + old[:80])
    return text.replace(old, new, 1)


def adapt(name, text):
    if '#include "diagnostics.h"' in text:
        raise ValueError('flight bridge source already adapted')
    if name == 'jsbsim_bridge.cpp':
        text = replace_once(text, '#include "jsbsim_bridge.h"',
            '#include "jsbsim_bridge.h"\n#include "diagnostics.h"')
        text = replace_once(text, '  Eigen::VectorXd actuator_controls =',
            '  if (!flight::allow_run()) return;\n  Eigen::VectorXd actuator_controls =')
        text = replace_once(text, '  if (actuator_controls.size() >= 16) {',
            '  if (flight::has_actuator() && actuator_controls.size() >= 16) {')
        text = replace_once(text, '    _actuators->SetActuatorCommands(actuator_controls);',
            '    _actuators->SetActuatorCommands(actuator_controls);\n    flight::applied(*_fdmexec);')
        text = replace_once(text, '  _result = _fdmexec->Run();',
            '  _result = _fdmexec->Run();\n  flight::finished(*_fdmexec, _result);')
    elif name == 'mavlink_interface.cpp':
        text = replace_once(text, '#include "mavlink_interface.h"',
            '#include "mavlink_interface.h"\n#include "diagnostics.h"')
        text = replace_once(text, '      local_simulator_addr_.sin_addr.s_addr = htonl(mavlink_addr_);',
            '      local_simulator_addr_.sin_addr.s_addr = htonl(INADDR_LOOPBACK);')
        text = replace_once(text, '      fds_[LISTEN_FD].events = POLLIN;  // only listens for new connections on tcp',
            '      fds_[LISTEN_FD].events = POLLIN;  // only listens for new connections on tcp\n'
            '      flight::wait_peer(fds_[LISTEN_FD].fd);\n'
            '      acceptConnections();\n'
            '      flight::connected(fds_[CONNECTION_FD].fd);')
        text = replace_once(text, '  do {\n    int timeout_ms',
            '  do {\n    flight::poll_guard();\n    int timeout_ms')
        text = replace_once(text, '        int len = ret;',
            '        flight::wire_rx(_buf, ret);\n        int len = ret;')
        text = replace_once(text, '        if (use_tcp_ && ret == 0) {',
            '        if (use_tcp_ && ret == 0) {\n          flight::peer_closed();')
        text = replace_once(text, '      mavlink_msg_hil_actuator_controls_decode(msg, &controls);',
            '      mavlink_msg_hil_actuator_controls_decode(msg, &controls);\n'
            '      flight::received(*msg, controls);')
        text = replace_once(text, '  assert(message != nullptr);',
            '  assert(message != nullptr);\n  flight::check_tx_id(message->msgid);')
        text = replace_once(text, '      size_t len;', '      ssize_t len;')
        text = replace_once(text, '      if (len < 0) {',
            '      flight::wire_tx(*message, buffer, packetlen, len);\n      if (len < 0) {')
    elif name == 'actuator_plugin.cpp':
        text = replace_once(text, '#include "actuator_plugin.h"',
            '#include "actuator_plugin.h"\n#include "diagnostics.h"')
        text = replace_once(text, '  _sim_ptr->SetPropertyValue(property, value);',
            '  flight::requested(value, property);\n  _sim_ptr->SetPropertyValue(property, value);')
    else:
        raise ValueError('unexpected flight adaptation source')
    return text

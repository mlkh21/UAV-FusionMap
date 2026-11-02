// Private observation hooks for one host-owned FDM; no command sender.
#include "diagnostics.h"
#include <models/FGPropagate.h>
#include <models/FGAuxiliary.h>
#include <models/FGInertial.h>
#include <arpa/inet.h>
#include <poll.h>
#include <sys/socket.h>
#include <array>
#include <chrono>
#include <cmath>
#include <fstream>
#include <iomanip>
#include <stdexcept>

namespace flight {
namespace {
const std::array<std::string,4> names = {"fcs/rudder-cmd-norm", "fcs/aileron-cmd-norm",
    "fcs/elevator-cmd-norm", "fcs/throttle-cmd-norm"};
std::ofstream records, wire, metadata, final;
std::string identity;
unsigned step=0, port=0, property_count=0;
uint64_t sequence=0, hil=0, sent_ns=0, received_ns=0, applied_ns=0, ended_ns=0;
uint64_t initial_ns=0, bytes_logged=0, wire_events=0;
bool observed=false, seen=false, sent=false, ran=false, result=false;
bool emitted=true;
double before_time=0;
std::array<double,4> before{}, request{}, after{};
mavlink_hil_actuator_controls_t actuator{};
unsigned sysid=0, compid=0;

uint64_t now() {
  return std::chrono::duration_cast<std::chrono::nanoseconds>(
      std::chrono::steady_clock::now().time_since_epoch()).count();
}
void require(bool condition, const char* reason) {
  if (!condition) throw std::runtime_error(reason);
}
void number(std::ostream& out, double value) {
  if (std::isfinite(value)) out << value; else out << "null";
}
void vector(std::ostream& out, const std::array<double,4>& values) {
  out << '[';
  for (unsigned i=0;i<4;++i) { if(i) out << ','; number(out,values[i]); }
  out << ']';
}
std::array<double,4> properties(JSBSim::FGFDMExec& fdm) {
  std::array<double,4> values;
  for(unsigned i=0;i<4;++i) values[i]=fdm.GetPropertyValue(names[i]);
  return values;
}
void log_bytes(const char* direction,const uint8_t* data,unsigned length,ssize_t sent_count) {
  require(length<=65535 && wire_events<12288 && bytes_logged+length<=134217728,"wire_budget");
  ++wire_events; bytes_logged+=length;
  wire << "{\"direction\":\"" << direction << "\",\"step_index\":" << step
       << ",\"wall_ns\":" << now() << ",\"length\":" << length
       << ",\"sent\":" << sent_count << ",\"hex\":\"";
  static const char hex[]="0123456789abcdef";
  for(unsigned i=0;i<length;++i) wire << hex[data[i]>>4] << hex[data[i]&15];
  wire << "\"}" << std::endl;
  require(bool(wire),"wire_write");
}
}

void open(const std::string& directory,const std::string& run) {
  require(!run.empty() && run.size()<120 && run.find_first_not_of(
      "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.")==std::string::npos,"run_identity");
  identity=run;
  records.open(directory+"/actuators.jsonl");wire.open(directory+"/wire.jsonl");
  metadata.open(directory+"/initial.json");final.open(directory+"/terminal.json");
  require(bool(records)&&bool(wire)&&bool(metadata)&&bool(final),"diagnostic_files");
  records << std::setprecision(17);metadata << std::setprecision(17);
}
void wait_peer(int listener) {
  const auto deadline=now()+60000000000ULL;
  pollfd descriptor{listener,POLLIN,0};
  while(now()<deadline) {
    int ready=::poll(&descriptor,1,50);
    require(ready>=0,"peer_poll_error");
    if(ready>0 && (descriptor.revents&POLLIN)) return;
  }
  throw std::runtime_error("peer_startup_timeout");
}
void connected(int socket) {
  sockaddr_in peer{};socklen_t length=sizeof(peer);
  require(socket>0 && getpeername(socket,reinterpret_cast<sockaddr*>(&peer),&length)==0,"peer_readback");
  require(peer.sin_family==AF_INET && ntohl(peer.sin_addr.s_addr)==INADDR_LOOPBACK,"peer_address");
  port=ntohs(peer.sin_port);require(port>=1024,"peer_port");
}
void peer_closed() { throw std::runtime_error("peer_closed"); }
void initial(JSBSim::FGFDMExec& fdm) {
  initial_ns=now();auto p=fdm.GetPropagate();
  require(fdm.GetSimTime()==0.,"initial_time");
  before=properties(fdm);
  for(double value:before) require(value==0.,"initial_property_nonzero");
  metadata << "{\"run_id\":\"" << identity << "\",\"peer\":{\"address\":\"127.0.0.1\",\"port\":"
      << port << ",\"system_id\":1,\"component_id\":1},\"initial_wall_ns\":" << initial_ns
      << ",\"initial_properties\":";vector(metadata,before);
  metadata << ",\"sim_time_s\":" << fdm.GetSimTime() << ",\"agl_m\":" << p->GetDistanceAGL()*.3048
      << ",\"asl_m\":" << p->GetAltitudeASLmeters() << ",\"terrain_m\":" << p->GetTerrainElevation()*.3048
      << ",\"latitude_deg\":" << p->GetGeodLatitudeRad()*180/M_PI << ",\"longitude_deg\":"
      << p->GetLongitude()*180/M_PI << ",\"geodetic_altitude_m\":" << p->GetGeodeticAltitude()*.3048
      << ",\"ellipsoid_axes_m\":[" << fdm.GetInertial()->GetSemimajor()*.3048 << ','
      << fdm.GetInertial()->GetSemiminor()*.3048 << "],\"ecef_m\":[" << p->GetLocation()(1)*.3048 << ','
      << p->GetLocation()(2)*.3048 << ',' << p->GetLocation()(3)*.3048 << "],\"euler_deg\":[" << p->GetEulerDeg(1) << ','
      << p->GetEulerDeg(2) << ',' << p->GetEulerDeg(3) << "],\"vt_mps\":"
      << fdm.GetAuxiliary()->GetVtrueFPS()*.3048 << "}" << std::endl;
  require(bool(metadata),"initial_write");
}
void begin(JSBSim::FGFDMExec& fdm,unsigned index) {
  require(emitted && index==step+1 && index<=250,"step_order_or_limit");
  require(std::abs(fdm.GetSimTime()-(index-1)*.004)<=1e-9,"step_time_before");
  step=index;before=properties(fdm);after=before;request={};before_time=fdm.GetSimTime();
  observed=sent=ran=result=false;sent_ns=now();received_ns=applied_ns=ended_ns=0;
  property_count=0;emitted=false;
}
void check_tx_id(unsigned id) {
  require(id==MAVLINK_MSG_ID_HIL_SENSOR || id==MAVLINK_MSG_ID_HIL_GPS,"unexpected_tx_message");
}
void wire_tx(const mavlink_message_t& message,const uint8_t* bytes,int length,ssize_t sent_count) {
  log_bytes("tx",bytes,length,sent_count);
  require(sent_count==length,"hil_send_incomplete");
  if(message.msgid==MAVLINK_MSG_ID_HIL_SENSOR) {
    require(!sent,"multiple_hil_sensor");
    mavlink_hil_sensor_t sensor{};mavlink_msg_hil_sensor_decode(&message,&sensor);
    hil=sensor.time_usec;sent_ns=now();sent=true;
  }
}
void wire_rx(const unsigned char* bytes,int length) { log_bytes("rx",bytes,length,length); }
void received(const mavlink_message_t& message,const mavlink_hil_actuator_controls_t& controls) {
  require(!observed,"multiple_actuators_in_step");
  actuator=controls;observed=true;received_ns=now();++sequence;
  sysid=message.sysid;compid=message.compid;
  require(sysid==1 && compid==1,"actuator_identity");
  require(controls.flags<=1 && controls.mode==1,"actuator_flags_or_observe_mode");
  for(unsigned i=0;i<16;++i) {
    require(std::isfinite(controls.controls[i]) && controls.controls[i]>= (i==4?0:-1)
        && controls.controls[i]<=1,"actuator_value");
    require(controls.controls[i]==0,"disarmed_nonzero");
  }
}
void poll_guard() { require(now()-sent_ns<=1000000000ULL,"actuator_poll_deadline"); }
bool allow_run() {
  require(sent,"hil_sensor_not_sent");
  if(!observed) require(!seen && step<=500 && now()-initial_ns<=5000000000ULL,"actuator_missing_after_bootstrap");
  if(observed) seen=true;
  return true;
}
bool has_actuator() { return observed; }
void requested(float value,const std::string& property) {
  require(observed && property_count<4 && property==names[property_count],"property_request_order");
  request[property_count++]=value;
}
void applied(JSBSim::FGFDMExec& fdm) {
  after=properties(fdm);applied_ns=now();require(property_count==4,"property_request_count");
  const std::array<double,4> expected={-double(actuator.controls[2]),-double(actuator.controls[5]),
      -double(actuator.controls[7]),double(actuator.controls[4])};
  for(unsigned i=0;i<4;++i) require(request[i]==expected[i] && std::isfinite(after[i])
      && std::abs(after[i]-request[i])<=1e-6,"property_readback");
}
void finished(JSBSim::FGFDMExec& fdm,bool success) {
  ran=true;result=success;ended_ns=now();
  require(success,"fdm_run_failed");
  require(std::abs(fdm.GetSimTime()-before_time-.004)<=1e-9 &&
      std::abs(fdm.GetSimTime()-step*.004)<=1e-9,"fdm_step_time");
}
void emit(JSBSim::FGFDMExec& fdm) {
  if(emitted) return;
  if(!ended_ns) ended_ns=now();
  records << "{\"schema_version\":\"sim_flight_actuator_record.v1\",\"run_id\":\"" << identity
      << "\",\"clock_id\":\"sim:" << identity << "\",\"step_index\":" << step << ",\"source_step\":" << step-1
      << ",\"hil_sensor_time_us\":" << hil << ",\"has_actuator\":" << (observed?"true":"false") << ",\"actuator\":";
  if(observed) {
    records << "{\"receive_sequence\":" << sequence << ",\"peer\":{\"address\":\"127.0.0.1\",\"port\":" << port
        << ",\"system_id\":" << sysid << ",\"component_id\":" << compid << "},\"time_usec\":" << actuator.time_usec
        << ",\"flags\":" << actuator.flags << ",\"mode\":" << unsigned(actuator.mode)
        << ",\"armed\":" << ((actuator.mode&128)?"true":"false") << ",\"controls\":[";
    for(unsigned i=0;i<16;++i) { if(i) records << ',';number(records,actuator.controls[i]); }
    records << "]}";
  } else records << "null";
  records << ",\"binding_status\":\"unverified\",\"reason\":\"" << (observed?"":"actuator_not_received")
      << "\",\"properties\":{\"before\":";vector(records,before);
  records << ",\"requested\":";if(applied_ns) vector(records,request);else records << "null";
  records << ",\"after\":";vector(records,after);
  records << "},\"fdm\":{\"ran\":" << (ran?"true":"false") << ",\"result\":" << (ran?(result?"true":"false"):"null")
      << ",\"sim_time_before_s\":" << before_time << ",\"sim_time_after_s\":";
  number(records,fdm.GetSimTime());
  records << "},\"wall\":{\"hil_sent_ns\":" << sent_ns << ",\"actuator_received_ns\":";
  if(observed) records << received_ns;else records << "null";
  records << ",\"properties_applied_ns\":";if(applied_ns) records << applied_ns;else records << "null";
  records << ",\"fdm_finished_ns\":" << ended_ns << "}}" << std::endl;
  emitted=true;require(bool(records),"record_write");
}
void terminal(const std::string& reason) {
  const auto label=reason.find_first_not_of("abcdefghijklmnopqrstuvwxyz_0123456789")==std::string::npos
      ? reason : "host_exception";
  final << "{\"reason\":\"" << label << "\",\"last_step\":" << step << ",\"actuator_observed\":"
      << (seen?"true":"false") << ",\"binding_status\":\"unverified\",\"control_gate_accepted\":false}" << std::endl;
}
}

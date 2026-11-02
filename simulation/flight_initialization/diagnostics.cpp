// One host-owned FDM and read-only native observations. No command sender.
#include "diagnostics.h"
#include <models/FGPropagate.h>
#include <models/FGAuxiliary.h>
#include <models/FGGroundReactions.h>
#include <models/FGLGear.h>
#include <arpa/inet.h>
#include <poll.h>
#include <sys/socket.h>
#include <array>
#include <chrono>
#include <cmath>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <thread>

namespace flight {
namespace {
const std::array<std::string,4> names={"fcs/rudder-cmd-norm","fcs/aileron-cmd-norm",
  "fcs/elevator-cmd-norm","fcs/throttle-cmd-norm"};
const std::array<std::string,3> gears={"LEFT_MLG","RIGHT_MLG","TAIL_LG"};
std::ofstream records,wire,metadata,final;
std::string identity,fault,kin_before,ground_before;
std::array<double,4> before{},request{},after{};
std::array<double,3> origin{};
unsigned step=0,port=0,property_count=0;
uint64_t sequence=0,sent_ns=0,received_ns=0,applied_ns=0,ended_ns=0,initial_ns=0;
uint64_t wire_bytes=0,wire_events=0,record_bytes=0,last_actuator=0;
bool observed=false,seen=false,sent=false,ran=false,result=false,emitted=true;
double before_time=0;
mavlink_hil_sensor_t sensor{};
mavlink_hil_actuator_controls_t actuator{};
uint64_t now() {return std::chrono::duration_cast<std::chrono::nanoseconds>(
  std::chrono::steady_clock::now().time_since_epoch()).count();}
void require(bool condition,const char* reason) {if (!condition) throw std::runtime_error(reason);}
void number(std::ostream& out,double value) {
  require(std::isfinite(value),"invalid_input");out<<value;
}
template <class Getter> void vector3(std::ostream& out,Getter get,double scale=1) {
  out<<'[';for (int i=1;i<=3;++i) {if(i>1) out<<',';number(out,get(i)*scale);}out<<']';
}
void vector4(std::ostream& out,const std::array<double,4>& values) {
  out<<'[';for(unsigned i=0;i<4;++i) {if(i) out<<',';number(out,values[i]);}out<<']';
}
std::array<double,4> properties(JSBSim::FGFDMExec& fdm) {
  std::array<double,4> values{};
  for(unsigned i=0;i<4;++i) {values[i]=fdm.GetPropertyValue(names[i]);require(values[i]==0,"invalid_input");}
  return values;
}
std::string kinematics(JSBSim::FGFDMExec& fdm) {
  auto p=fdm.GetPropagate();std::ostringstream out;out<<std::setprecision(17);
  out<<"{\"sim_time_s\":";number(out,fdm.GetSimTime());
  out<<",\"agl_m\":";number(out,p->GetDistanceAGL()*.3048);
  out<<",\"asl_m\":";number(out,p->GetAltitudeASLmeters());
  out<<",\"geodetic_altitude_m\":";number(out,p->GetGeodeticAltitude()*.3048);
  out<<",\"terrain_m\":";number(out,p->GetTerrainElevation()*.3048);
  out<<",\"ecef_ft\":";vector3(out,[&](int i){return p->GetLocation()(i);});
  out<<",\"vel_ned_ftps\":";vector3(out,[&](int i){return p->GetVel(i);});
  out<<",\"vel_ned_mps\":";vector3(out,[&](int i){return p->GetVel(i);},.3048);
  out<<",\"euler_deg\":";vector3(out,[&](int i){return p->GetEulerDeg(i);});
  out<<",\"pqr_radps\":";vector3(out,[&](int i){return p->GetPQR(i);});
  auto accel=[&](int i){return fdm.GetPropertyValue(std::string("accelerations/a-pilot-")+"xyz"[i-1]+"-ft_sec2");};
  out<<",\"pilot_accel_ftps2\":";vector3(out,accel);
  out<<",\"pilot_accel_mps2\":";vector3(out,accel,.3048);
  out<<",\"true_airspeed_mps\":";number(out,fdm.GetAuxiliary()->GetVtrueFPS()*.3048);out<<'}';
  return out.str();
}
std::string ground(JSBSim::FGFDMExec& fdm) {
  auto reactions=fdm.GetGroundReactions();require(reactions->GetNumGearUnits()==3,"invalid_input");
  std::ostringstream out;out<<std::setprecision(17)<<'[';
  for(unsigned i=0;i<3;++i) {
    auto g=reactions->GetGearUnit(i);require(g->GetName()==gears[i],"invalid_input");
    if(i) out<<',';
    out<<"{\"name\":\""<<gears[i]<<"\",\"wow\":"<<(g->GetWOW()?"true":"false")<<",\"compression_lbf\":";
    number(out,g->GetCompForce());out<<",\"compression_n\":";number(out,g->GetCompForce()*4.4482216152605);out<<'}';
  }out<<']';return out.str();
}
bool safe(JSBSim::FGFDMExec& fdm) {
  auto p=fdm.GetPropagate();double agl=p->GetDistanceAGL()*.3048;
  double lat=47.458159*M_PI/180,lon=8.548004*M_PI/180;
  std::array<double,3> d{};for(unsigned i=0;i<3;++i) d[i]=(p->GetLocation()(i+1)-origin[i])*.3048;
  double n=-sin(lat)*cos(lon)*d[0]-sin(lat)*sin(lon)*d[1]+cos(lat)*d[2];
  double e=-sin(lon)*d[0]+cos(lon)*d[1];
  double a=0,r=0;for(int i=1;i<=3;++i) {
    double acc=fdm.GetPropertyValue(std::string("accelerations/a-pilot-")+"xyz"[i-1]+"-ft_sec2")*.3048;
    a+=acc*acc;r+=p->GetPQR(i)*p->GetPQR(i);
  }
  return std::isfinite(agl) && agl>=-.05 && agl<=1 && std::abs(p->GetEulerDeg(1))<=30
    && std::abs(p->GetEulerDeg(2))<=25 && hypot(n,e)<=2 && fdm.GetAuxiliary()->GetVtrueFPS()*.3048<=5
    && sqrt(a)<=98.0665 && sqrt(r)<=2;
}
void valid_control(const mavlink_message_t& msg,const mavlink_hil_actuator_controls_t& c) {
  require(msg.sysid==1 && msg.compid==1,"invalid_input");
  require(c.flags<=1 && c.mode==1,"invalid_input");
  for(float v:c.controls) require(std::isfinite(v) && v==0,"invalid_input");
}
void log_bytes(const char* direction,const uint8_t* bytes,unsigned length,ssize_t count) {
  require(length<=65535 && wire_events<8192 && wire_bytes+length<=16777216,"budget_exceeded");
  wire_events++;wire_bytes+=length;
  wire<<"{\"direction\":\""<<direction<<"\",\"step_index\":"<<step<<",\"wall_ns\":"<<now()
    <<",\"length\":"<<length<<",\"sent\":"<<count<<",\"hex\":\"";
  const char* hex="0123456789abcdef";
  for(unsigned i=0;i<length;++i) wire<<hex[bytes[i]>>4]<<hex[bytes[i]&15];
  wire<<"\"}"<<std::endl;require(bool(wire),"invalid_input");
}
}
void open(const std::string& directory,const std::string& run,const std::string& selected_fault) {
  require(!run.empty() && run.size()<=120 && run.find_first_not_of(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.")==std::string::npos,"invalid_input");
  require(selected_fault=="normal" || selected_fault=="disconnect" || selected_fault=="transaction-timeout","invalid_input");
  identity=run;fault=selected_fault;
  records.open(directory+"/steps.jsonl");wire.open(directory+"/wire.jsonl");
  metadata.open(directory+"/initial.json");final.open(directory+"/terminal.json");
  require(bool(records)&&bool(wire)&&bool(metadata)&&bool(final),"invalid_input");
  records<<std::setprecision(17);metadata<<std::setprecision(17);
}
void wait_peer(int listener) {
  auto deadline=now()+60000000000ULL;pollfd fd{listener,POLLIN,0};
  while(now()<deadline) {int ready=::poll(&fd,1,50);require(ready>=0,"invalid_input");if(ready>0 && (fd.revents&POLLIN)) return;}
  throw std::runtime_error("transaction_timeout");
}
void connected(int socket) {
  sockaddr_in peer{};socklen_t length=sizeof(peer);
  require(socket>0 && getpeername(socket,reinterpret_cast<sockaddr*>(&peer),&length)==0,"invalid_input");
  require(peer.sin_family==AF_INET && ntohl(peer.sin_addr.s_addr)==INADDR_LOOPBACK,"invalid_input");
  port=ntohs(peer.sin_port);require(port>=1024,"invalid_input");
}
void peer_closed() {throw std::runtime_error("peer_closed");}
void initial(JSBSim::FGFDMExec& fdm) {
  initial_ns=now();require(fdm.GetSimTime()==0,"invalid_input");before=properties(fdm);
  for(unsigned i=0;i<3;++i) origin[i]=fdm.GetPropagate()->GetLocation()(i+1);
  metadata<<"{\"peer\":{\"address\":\"127.0.0.1\",\"port\":"<<port<<",\"system_id\":1,\"component_id\":1},"
    <<"\"initial_wall_ns\":"<<initial_ns<<",\"initial_properties\":";vector4(metadata,before);
  metadata<<",\"initial_kinematics\":"<<kinematics(fdm)<<",\"initial_ground\":"<<ground(fdm)<<'}'<<std::endl;
  require(bool(metadata),"invalid_input");
}
void begin(JSBSim::FGFDMExec& fdm,unsigned index) {
  require(emitted && index==step+1 && index<=2500,"invalid_input");
  require(now()-initial_ns<=60000000000ULL,"transaction_timeout");
  require(std::abs(fdm.GetSimTime()-(index-1)*.004)<=1e-9,"invalid_input");
  require(safe(fdm),"unsafe_state");
  step=index;before=properties(fdm);after=before;request={};before_time=fdm.GetSimTime();
  kin_before=kinematics(fdm);ground_before=ground(fdm);
  observed=sent=ran=result=false;sent_ns=now();received_ns=applied_ns=ended_ns=0;
  property_count=0;emitted=false;sensor={};
}
void check_tx_id(unsigned id) {require(id==MAVLINK_MSG_ID_HIL_SENSOR || id==MAVLINK_MSG_ID_HIL_GPS,"invalid_input");}
void wire_tx(const mavlink_message_t& msg,const uint8_t* bytes,int length,ssize_t count) {
  log_bytes("tx",bytes,length,count);require(count==length,"invalid_input");
  if(msg.msgid==MAVLINK_MSG_ID_HIL_SENSOR) {
    require(!sent,"invalid_input");mavlink_msg_hil_sensor_decode(&msg,&sensor);sent_ns=now();sent=true;
    require(sensor.time_usec==(step-1)*4000ULL,"invalid_input");
  }
}
void wire_rx(const unsigned char* bytes,int length) {log_bytes("rx",bytes,length,length);}
void received(const mavlink_message_t& msg,const mavlink_hil_actuator_controls_t& c) {
  valid_control(msg,c);require(!observed && (!seen || c.time_usec>last_actuator),"invalid_input");
  actuator=c;observed=true;received_ns=now();++sequence;last_actuator=c.time_usec;
}
void poll_guard() {require(now()-sent_ns<=1000000000ULL,"transaction_timeout");}
bool allow_run() {
  require(sent,"invalid_input");
  if(fault=="transaction-timeout" && step==126) std::this_thread::sleep_for(std::chrono::milliseconds(1010));
  poll_guard();require(now()-initial_ns<=60000000000ULL,"transaction_timeout");
  require(observed || !seen,"transaction_timeout");
  if(observed) seen=true;
  return true;
}
bool has_actuator() {return observed;}
void requested(float value,const std::string& property) {
  require(observed && property_count<4 && property==names[property_count] && value==0,"invalid_input");
  request[property_count++]=value;
}
void applied(JSBSim::FGFDMExec& fdm) {
  after=properties(fdm);applied_ns=now();require(property_count==4,"invalid_input");poll_guard();
}
void finished(JSBSim::FGFDMExec& fdm,bool success) {
  ran=true;result=success;ended_ns=now();require(success,"fdm_failed");
  require(std::abs(fdm.GetSimTime()-step*.004)<=1e-9,"invalid_input");
  require(safe(fdm),"unsafe_state");poll_guard();
}
void emit(JSBSim::FGFDMExec& fdm) {
  if(emitted) return;
  require(sent,"invalid_input");if(!ended_ns) ended_ns=now();
  std::ostringstream out;out<<std::setprecision(17);
  out<<"{\"schema_version\":\"sim_flight_initialization_step.v1\",\"run_id\":\""<<identity
    <<"\",\"clock_id\":\"sim:"<<identity<<"\",\"profile_id\":\"sim-flight-initialization-observe-v1\","
    <<"\"step_index\":"<<step<<",\"source_step\":"<<step-1<<",\"hil_sensor_time_us\":"<<sensor.time_usec
    <<",\"has_actuator\":"<<(observed?"true":"false")<<",\"actuator\":";
  if(observed) {
    out<<"{\"receive_sequence\":"<<sequence<<",\"peer\":{\"address\":\"127.0.0.1\",\"port\":"<<port
      <<",\"system_id\":1,\"component_id\":1},\"time_usec\":"<<actuator.time_usec<<",\"flags\":"<<actuator.flags
      <<",\"mode\":1,\"armed\":false,\"controls\":[";
    for(unsigned i=0;i<16;++i) {if(i) out<<',';number(out,actuator.controls[i]);}out<<"]}";
  } else out<<"null";
  out<<",\"reason\":\""<<(observed?"":"preparation_no_actuator")<<"\",\"binding_status\":\"unverified\",\"control_gate_accepted\":false,"
    <<"\"properties\":{\"before\":";vector4(out,before);out<<",\"requested\":";
  if(applied_ns) vector4(out,request);else out<<"null";out<<",\"after\":";vector4(out,after);
  out<<"},\"fdm\":{\"ran\":"<<(ran?"true":"false")<<",\"result\":"<<(ran?(result?"true":"false"):"null")
    <<",\"sim_time_before_s\":"<<before_time<<",\"sim_time_after_s\":"<<fdm.GetSimTime()
    <<",\"hil_sensor\":{\"time_usec\":"<<sensor.time_usec<<",\"accel_mps2\":[";
  number(out,sensor.xacc);out<<',';number(out,sensor.yacc);out<<',';number(out,sensor.zacc);
  out<<"],\"gyro_radps\":[";number(out,sensor.xgyro);out<<',';number(out,sensor.ygyro);out<<',';number(out,sensor.zgyro);
  out<<"]}},\"wall\":{\"hil_sent_ns\":"<<sent_ns<<",\"actuator_received_ns\":";
  if(observed) out<<received_ns;else out<<"null";out<<",\"properties_applied_ns\":";
  if(applied_ns) out<<applied_ns;else out<<"null";
  out<<",\"fdm_finished_ns\":"<<ended_ns<<"},\"kinematics_before\":"<<kin_before
    <<",\"kinematics_after\":"<<kinematics(fdm)<<",\"ground_before\":"<<ground_before
    <<",\"ground_after\":"<<ground(fdm)<<'}';
  std::string raw=out.str();require(raw.size()+1<=16384 && record_bytes+raw.size()+1<=67108864,"budget_exceeded");
  records<<raw<<std::endl;record_bytes+=raw.size()+1;emitted=true;require(bool(records),"invalid_input");
}
void terminal(const std::string& reason) {
  std::string label=reason;
  if(label!="window_complete" && label!="requested_stop" && label!="peer_closed" && label!="transaction_timeout"
      && label!="budget_exceeded" && label!="unsafe_state" && label!="fdm_failed") label="invalid_input";
  final<<"{\"schema_version\":\"sim_flight_initialization_terminal.v1\",\"run_id\":\""<<identity
    <<"\",\"clock_id\":\"sim:"<<identity<<"\",\"profile_id\":\"sim-flight-initialization-observe-v1\",\"last_step\":"
    <<step<<",\"reason\":\""<<label<<"\",\"wall_ns\":"<<now()<<",\"binding_status\":\"unverified\",\"control_gate_accepted\":false}"<<std::endl;
}
int self_test() {
  mavlink_message_t msg{};msg.sysid=msg.compid=1;mavlink_hil_actuator_controls_t c{};c.mode=1;
  valid_control(msg,c);unsigned rejected=0;
  for(unsigned i=0;i<5;++i) {
    auto bad=c;auto source=msg;
    if(i==0) bad.mode=129;if(i==1) bad.controls[5]=.25f;if(i==2) bad.flags=2;
    if(i==3) source.sysid=2;if(i==4) bad.controls[0]=NAN;
    try {valid_control(source,bad);} catch(const std::exception&) {++rejected;}
  }
  std::cout<<"{\"zero_accepted\":true,\"invalid_controls_rejected\":"<<rejected<<"}"<<std::endl;
  return rejected==5?0:1;
}
}

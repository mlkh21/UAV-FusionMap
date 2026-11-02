"""Exact time-production edits for fresh copies only; the old adapters remain unchanged."""


def replace_once(source, old, new):
    if source.count(old)!=1:
        raise ValueError('time source context mismatch: '+old[:80])
    return source.replace(old,new,1)


def adapt(name, source):
    if '#include "time_grid.h"' in source:
        raise ValueError('time source already adapted')
    if name=='jsbsim_bridge.cpp':
        source=replace_once(source,'#include "jsbsim_bridge.h"',
            '#include "jsbsim_bridge.h"\n#include "time_grid.h"')
        return replace_once(source,
            '    _mavlink_interface->SendSensorMessages(static_cast<uint64_t>(simtime * 1e6));',
            '    _mavlink_interface->SendSensorMessages(flight::source_time_us(simtime, 1));')
    if name=='sensor_gps_plugin.cpp':
        source=replace_once(source,'#include "sensor_gps_plugin.h"',
            '#include "sensor_gps_plugin.h"\n#include "time_grid.h"')
        return replace_once(source,
            '  ret.time_utc_usec = static_cast<uint64_t>(_sim_ptr->GetSimTime() * 1e6);',
            '  ret.time_utc_usec = flight::source_time_us(_sim_ptr->GetSimTime(), 2);')
    if name=='diagnostics.cpp':
        source=replace_once(source,'#include "diagnostics.h"',
            '#include "diagnostics.h"\n#include "time_grid.h"')
        source=replace_once(source,'std::ofstream records,wire,metadata,final;',
            'std::ofstream records,wire,metadata,final,time_sources;\nunsigned time_record_count=0;')
        source=replace_once(source,'  identity=run;fault=selected_fault;',
            '  identity=run;fault=selected_fault;\n'
            '  time_sources.open(directory+"/time-grid.jsonl");\n'
            '  require(bool(time_sources),"invalid_input");')
        return replace_once(source,
            'void open(const std::string& directory,const std::string& run,const std::string& selected_fault) {',
            '''uint64_t source_time_us(double seconds, unsigned sensor_kind) {
  require(!emitted && step>=1 && step<=2500 && (sensor_kind==1 || sensor_kind==2),"invalid_input");
  const uint64_t stamp=ufm_time::grid_time_us(seconds,step-1);
  require(time_record_count<5000,"budget_exceeded");
  time_sources<<std::setprecision(17)<<"{\\"sensor_kind\\":\\""<<(sensor_kind==1?"hil_sensor":"hil_gps")
    <<"\\",\\"source_step\\":"<<(step-1)<<",\\"source_time_s\\":"<<seconds
    <<",\\"time_usec\\":"<<stamp<<"}"<<std::endl;
  ++time_record_count;require(bool(time_sources),"invalid_input");
  return stamp;
}
void open(const std::string& directory,const std::string& run,const std::string& selected_fault) {''')
    raise ValueError('unexpected time adaptation source')

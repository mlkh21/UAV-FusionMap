"""Exact-context copies for the explicit flight scene host. Originals stay unchanged."""
from pathlib import Path
import importlib.util


def replace(source, old, new, count=1):
    if source.count(old) != count:
        raise ValueError('flight scene source context mismatch: '+old[:80])
    return source.replace(old, new)


def adapt(name, source):
    if name == 'host.cpp':
        source = replace(source, 'index>=2500', 'index>=10000')
        return replace(source, 'index==2500', 'index==10000')
    if name != 'diagnostics.cpp':
        raise ValueError('unexpected flight scene copy')
    spec = importlib.util.spec_from_file_location('flight_scene_integer_time_adapter',
        Path(__file__).resolve().parents[1]/'flight_initialization_time/adapt.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    source = module.adapt(name, source)
    source = replace(source, 'step<=2500', 'step<=10000')
    source = replace(source, 'index<=2500', 'index<=10000')
    source = replace(source, 'time_record_count<5000', 'time_record_count<12288')
    source = replace(source, 'wire_events<8192', 'wire_events<49152')
    source = replace(source, 'wire_bytes+length<=16777216', 'wire_bytes+length<=67108864')
    source = replace(source, 'now()-initial_ns<=60000000000ULL', 'now()-initial_ns<=240000000000ULL', 2)
    source = replace(source, 'sim_flight_initialization_step.v1', 'sim_flight_scene_step.v1')
    source = replace(source, 'sim_flight_initialization_terminal.v1', 'sim_flight_scene_terminal.v1')
    source = replace(source, 'sim-flight-initialization-observe-v1', 'sim-flight-scene-observe-v2', 2)
    source = replace(source, 'std::ofstream records,wire,metadata,final,time_sources;',
        'std::ofstream records,wire,metadata,final,time_sources,scene_samples;')
    source = replace(source, 'unsigned time_record_count=0;', '''unsigned time_record_count=0;
void sample(JSBSim::FGFDMExec& fdm, unsigned index) {
  auto p=fdm.GetPropagate();
  scene_samples<<std::setprecision(17)<<"{\\"step_index\\":"<<index<<",\\"sim_time_s\\":"<<fdm.GetSimTime()
    <<",\\"ecef_ft\\":[";
  for(int i=1;i<=3;++i) scene_samples<<(i==1?"":",")<<p->GetLocation()(i);
  scene_samples<<"],\\"R_ecef_frd\\":[";
  for(int i=1;i<=3;++i) for(int j=1;j<=3;++j)
    scene_samples<<(i==1 && j==1?"":",")<<p->GetTb2ec()(i,j);
  scene_samples<<"],\\"uvw_ftps\\":[";
  for(int i=1;i<=3;++i) scene_samples<<(i==1?"":",")<<p->GetUVW()(i);
  scene_samples<<"],\\"pqr_radps\\":[";
  for(int i=1;i<=3;++i) scene_samples<<(i==1?"":",")<<p->GetPQR()(i);
  scene_samples<<"]}"<<std::endl;
  if(!scene_samples) throw std::runtime_error("invalid_input");
}''')
    source = replace(source, '  identity=run;fault=selected_fault;',
        '  identity=run;fault=selected_fault;\n  scene_samples.open(directory+"/scene-samples.jsonl");')
    source = replace(source, '  require(bool(metadata),"invalid_input");',
        '  require(bool(metadata),"invalid_input");\n  sample(fdm,0);')
    # The initial readback is the only place geographic registration is established.
    source = replace(source, 'metadata<<",\\"initial_kinematics\\":"',
        'metadata<<",\\"geodetic_latitude_rad\\":"<<fdm.GetPropagate()->GetGeodLatitudeRad()'
        '<<",\\"longitude_rad\\":"<<fdm.GetPropagate()->GetLongitude()<<",\\"initial_kinematics\\":"')
    source = replace(source, 'records<<raw<<std::endl;record_bytes+=raw.size()+1;emitted=true;',
        'records<<raw<<std::endl;record_bytes+=raw.size()+1;emitted=true;\n  if(result) sample(fdm,step);')
    return source

// Exercise the real measurement model with known beams, independently of ROS/Gazebo.
#include "radar_measurement_model.h"
#include <cassert>
#include <iostream>
#include <limits>

int main() {
  ufm_radar::Parameters p;
  p.detection_probability=.5; p.detection_distance_m=40;
  p.range_std_m=.08; p.angle_std_rad=.003; p.doppler_std_mps=.05;
  p.max_points=256; p.seed=20261030;
  ufm_radar::Measurements a(p,100000000),b(p,100000000),c(p,200000000);
  unsigned near=0,far=0,different=0; double sum=0,squares=0;
  for (int i=0;i<20000;++i) {
    double r=10,az=0,el=0,d=2,rr=r,aa=az,ee=el,dd=d;
    bool keep=a.sample(r,az,el,d,.5,90),same=b.sample(rr,aa,ee,dd,.5,90);
    assert(keep==same && r==rr && az==aa && el==ee && d==dd);
    double cr=10,ca=0,ce=0,cd=2;
    bool other=c.sample(cr,ca,ce,cd,.5,90);
    different+=(other!=keep || cr!=r);
    if (keep) {++near;sum+=d-2;squares+=(d-2)*(d-2);}
  }
  ufm_radar::Measurements distant(p,300000000);
  for (int i=0;i<20000;++i) {
    double r=80,az=0,el=0,d=2;
    far+=distant.sample(r,az,el,d,.5,90);
  }
  // Independent seeds can both reject a beam; those unchanged input slots are expected.
  assert(near>8500 && near<10500 && far>1500 && far<2500 && different>10000);
  const double mean=sum/near,stddev=std::sqrt(squares/near-mean*mean);
  assert(std::abs(mean)<.003 && stddev>.045 && stddev<.055);
  std::vector<std::array<float,5>> points(1000,{1,2,3,4,5});a.limit(points);assert(points.size()==256);
  p.detection_probability=0;ufm_radar::Measurements none(p,0);
  double r=10,az=0,el=0,d=2;assert(!none.sample(r,az,el,d,.5,90));
  p.range_std_m=std::numeric_limits<double>::quiet_NaN();
  bool rejected=false;try {p.validate();} catch(const std::invalid_argument&) {rejected=true;}
  assert(rejected);
  std::cout << "{\"passed\":true,\"near\":" << near << ",\"far\":" << far
            << ",\"doppler_std_mps\":" << stddev << ",\"same_seed_equal\":true,\"point_budget\":256}\n";
}

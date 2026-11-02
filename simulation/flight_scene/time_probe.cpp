#include "time_grid.h"
#include <iostream>
#include <string>
int main(int argc,char** argv) {
  if(argc!=3) return 2;
  try {
    const auto value=ufm_time::grid_time_us(std::stod(argv[1]),std::stoul(argv[2]));
    std::cout<<value<<'\n';return 0;
  } catch(const std::exception&) {return 3;}
}

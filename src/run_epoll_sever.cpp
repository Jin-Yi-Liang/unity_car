#include "../include/allhead.h"
#include <cstdio>
int main(int argc,char** argv){
 if(argc>2){std::fprintf(stderr,"usage: epoll_sever_run [catalog.tsv]\n");return 2;}
 auto& manager=Manager::getManager();
 std::string error;
 if(!manager.loadBuildingCatalog(argc==2?argv[1]:"data/buildings.tsv",error)){
  std::fprintf(stderr,"[server] %s\n",error.c_str());return 1;
 }
 std::printf("[server] loaded %zu buildings\n",manager.buildings().size());
 return Sever::getSever().runSever()?0:1;
}

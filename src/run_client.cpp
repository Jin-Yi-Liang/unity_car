#include "../include/allhead.h"
#include <arpa/inet.h>
#include <cstdio>
#include <sys/socket.h>
#include <unistd.h>
int main(int argc,char** argv){
 if(argc!=7){std::fprintf(stderr,"usage: client_run pickup_x pickup_y deliver_x deliver_y food priority\n");return 2;}
 int fd=socket(AF_INET,SOCK_STREAM,0);sockaddr_in address{};address.sin_family=AF_INET;address.sin_port=htons(EPOLL_PORT);inet_pton(AF_INET,EPOLL_IP,&address.sin_addr);
 if(connect(fd,reinterpret_cast<sockaddr*>(&address),sizeof(address))<0){perror("connect");return 1;}
 std::string request="LOGIN,CLIENT\nORDER,"+std::string(argv[1])+","+argv[2]+","+argv[3]+","+argv[4]+","+argv[5]+","+argv[6]+"\n";
 send(fd,request.data(),request.size(),0);char buffer[1024];std::string pending;
 while(true){ssize_t count=recv(fd,buffer,sizeof(buffer),0);if(count<=0)break;pending.append(buffer,static_cast<size_t>(count));size_t end;
  while((end=pending.find('\n'))!=std::string::npos){std::string line=pending.substr(0,end);pending.erase(0,end+1);std::puts(line.c_str());std::fflush(stdout);
   if(line.find(",DELIVERED")!=std::string::npos){close(fd);return 0;}if(line.find(",REJECTED")!=std::string::npos||line.rfind("ERROR,",0)==0){close(fd);return 1;}
  }
 }
 close(fd);return 1;
}

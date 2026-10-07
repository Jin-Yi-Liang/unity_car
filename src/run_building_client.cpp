#include "../include/allhead.h"
#include <arpa/inet.h>
#include <cstdio>
#include <cstdlib>
#include <sys/socket.h>
#include <unistd.h>
#include <vector>

static std::vector<std::string> split(const std::string& text) {
    std::vector<std::string> result;
    size_t begin=0,end;
    while ((end=text.find(',',begin))!=std::string::npos) {
        result.push_back(text.substr(begin,end-begin));begin=end+1;
    }
    result.push_back(text.substr(begin));return result;
}

int main(int argc,char** argv) {
    if(argc!=5) {
        std::fprintf(stderr,"usage: building_client_run pickup_id delivery_id food priority\n");return 2;
    }
    int fd=socket(AF_INET,SOCK_STREAM,0);
    sockaddr_in address{};
    address.sin_family=AF_INET;address.sin_port=htons(EPOLL_PORT);
    inet_pton(AF_INET,EPOLL_IP,&address.sin_addr);
    if(connect(fd,reinterpret_cast<sockaddr*>(&address),sizeof(address))<0){perror("connect");return 1;}
    std::string request="LOGIN,CLIENT\nORDER_BUILDINGS,"+std::string(argv[1])+","+argv[2]+","+argv[3]+","+argv[4]+"\n";
    if(send(fd,request.data(),request.size(),0)<0){perror("send");close(fd);return 1;}
    char bytes[1024];std::string pending,accepted_id;bool pickup_seen=false;
    while(true){
        ssize_t count=recv(fd,bytes,sizeof(bytes),0);
        if(count<=0)break;
        pending.append(bytes,static_cast<size_t>(count));
        size_t end;
        while((end=pending.find('\n'))!=std::string::npos){
            std::string line=pending.substr(0,end);pending.erase(0,end+1);
            std::puts(line.c_str());std::fflush(stdout);
            auto f=split(line);
            if(f.size()==2&&f[0]=="ORDER_ACCEPTED")accepted_id=f[1];
            if(f.size()==4&&f[0]=="STATUS"&&f[1]==accepted_id&&f[2]=="PICKUP"){
                if(f[3]!=argv[1]){std::fprintf(stderr,"wrong pickup building ID\n");close(fd);return 1;}
                pickup_seen=true;
            }
            if(f.size()==4&&f[0]=="STATUS"&&f[1]==accepted_id&&f[2]=="DELIVERED"){
                bool okay=pickup_seen&&f[3]==argv[2];
                if(!okay)std::fprintf(stderr,"delivery sequence or building ID mismatch\n");
                close(fd);return okay?0:1;
            }
            if(!f.empty()&&f[0]=="ERROR"){close(fd);return 1;}
            if(f.size()>=3&&f[0]=="STATUS"&&f[2]=="REJECTED"){close(fd);return 1;}
        }
    }
    close(fd);return 1;
}

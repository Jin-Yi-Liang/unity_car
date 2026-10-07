#include "../include/allhead.h"
#include <arpa/inet.h>
#include <cerrno>
#include <cstdio>
#include <sys/epoll.h>
#include <sys/socket.h>
#include <unistd.h>
Sever& Sever::getSever(){ static Sever instance; return instance; }
void Sever::deletePeer(int fd){ epoll_ctl(epoll_fd_,EPOLL_CTL_DEL,fd,nullptr); Manager::getManager().removePeer(fd); close(fd); }
bool Sever::runSever(){
 listen_fd_=socket(AF_INET,SOCK_STREAM,0);
 if(listen_fd_<0){perror("socket");return false;}
 int reuse=1; setsockopt(listen_fd_,SOL_SOCKET,SO_REUSEADDR,&reuse,sizeof(reuse));
 sockaddr_in address{}; address.sin_family=AF_INET; address.sin_port=htons(EPOLL_PORT); inet_pton(AF_INET,EPOLL_IP,&address.sin_addr);
 if(bind(listen_fd_,reinterpret_cast<sockaddr*>(&address),sizeof(address))<0 || listen(listen_fd_,128)<0){perror("bind/listen");close(listen_fd_);return false;}
 epoll_fd_=epoll_create1(0); if(epoll_fd_<0){perror("epoll_create1");close(listen_fd_);return false;}
 epoll_event ev{}; ev.events=EPOLLIN; ev.data.fd=listen_fd_; epoll_ctl(epoll_fd_,EPOLL_CTL_ADD,listen_fd_,&ev);
 std::printf("[server] listening on %s:%d\n",EPOLL_IP,EPOLL_PORT); std::fflush(stdout);
 epoll_event events[128];
 while(true){
  int count=epoll_wait(epoll_fd_,events,128,-1);
  if(count<0){if(errno==EINTR)continue;perror("epoll_wait");break;}
  for(int i=0;i<count;++i){
   int fd=events[i].data.fd;
   if(fd==listen_fd_){
    int peer=accept(listen_fd_,nullptr,nullptr); if(peer<0)continue;
    epoll_event pe{};pe.events=EPOLLIN|EPOLLRDHUP;pe.data.fd=peer;
    if(epoll_ctl(epoll_fd_,EPOLL_CTL_ADD,peer,&pe)<0){close(peer);continue;}
    Manager::getManager().addPeer(peer);continue;
   }
   if(events[i].events&(EPOLLHUP|EPOLLERR|EPOLLRDHUP)){deletePeer(fd);continue;}
   char buffer[4096];ssize_t size=recv(fd,buffer,sizeof(buffer),0);
   if(size<=0){deletePeer(fd);continue;}
   Manager::getManager().receive(fd,buffer,static_cast<size_t>(size));
  }
 }
 close(epoll_fd_);close(listen_fd_);return false;
}

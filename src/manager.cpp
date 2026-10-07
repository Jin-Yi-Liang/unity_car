#include "../include/allhead.h"
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <iomanip>
#include <sstream>
#include <sys/socket.h>
#include <vector>
namespace {
std::vector<std::string> split(const std::string& line){std::vector<std::string> out;std::stringstream s(line);std::string f;while(std::getline(s,f,','))out.push_back(f);return out;}
bool number(const std::string& text,double& value){char* end=nullptr;value=std::strtod(text.c_str(),&end);return end!=text.c_str()&&*end=='\0'&&std::isfinite(value);}
bool integer(const std::string& text,int& value){char* end=nullptr;long v=std::strtol(text.c_str(),&end,10);if(end==text.c_str()||*end!='\0'||v<0||v>100000000)return false;value=static_cast<int>(v);return true;}
}
Manager& Manager::getManager(){static Manager instance;return instance;}
void Manager::addPeer(int fd){peers_[fd]=Peer{};}
bool Manager::sendLine(int fd,const std::string& line){std::string bytes=line+'\n';size_t done=0;while(done<bytes.size()){ssize_t n=send(fd,bytes.data()+done,bytes.size()-done,MSG_NOSIGNAL);if(n<=0)return false;done+=static_cast<size_t>(n);}return true;}
void Manager::removePeer(int fd){
 auto it=peers_.find(fd);if(it==peers_.end())return;
 if(it->second.role==Peer::Role::Unity&&it->second.active_order){
  int id=it->second.active_order;auto order=orders_.find(id);
  if(order!=orders_.end()){order->second.car_id=0;waiting_.push_front(id);if(peers_.count(order->second.client_fd))sendLine(order->second.client_fd,"STATUS,"+std::to_string(id)+",REQUEUED");}
 }
 peers_.erase(it);dispatch();
}
void Manager::receive(int fd,const char* bytes,size_t length){
 auto it=peers_.find(fd);if(it==peers_.end())return;
 it->second.input.append(bytes,length);
 if(it->second.input.size()>8192){Sever::getSever().deletePeer(fd);return;}
 while(true){auto p=peers_.find(fd);if(p==peers_.end())return;size_t end=p->second.input.find('\n');if(end==std::string::npos)return;
  std::string line=p->second.input.substr(0,end);p->second.input.erase(0,end+1);if(!line.empty()&&line.back()=='\r')line.pop_back();if(!line.empty())handleLine(fd,line);
 }
}
void Manager::handleLine(int fd,const std::string& line){
 auto fields=split(line);Peer& peer=peers_.at(fd);
 if(peer.role==Peer::Role::Unknown){
  if(line=="LOGIN,CLIENT"){peer.role=Peer::Role::Client;sendLine(fd,"WELCOME,CLIENT");}
  else if(line=="LOGIN,UNITY"){peer.role=Peer::Role::Unity;peer.car_id=next_car_id_++;sendLine(fd,"WELCOME,UNITY,"+std::to_string(peer.car_id));std::printf("[server] car %d connected\n",peer.car_id);dispatch();}
  else sendLine(fd,"ERROR,LOGIN_REQUIRED");std::fflush(stdout);return;
 }
 if(peer.role==Peer::Role::Client&&fields.size()==7&&fields[0]=="ORDER"){
  Order o;
  if(!number(fields[1],o.px)||!number(fields[2],o.py)||!number(fields[3],o.dx)||!number(fields[4],o.dy)||fields[5].empty()||!integer(fields[6],o.priority)||o.priority>1){sendLine(fd,"ERROR,INVALID_ORDER");return;}
  o.id=next_order_id_++;o.client_fd=fd;o.food=fields[5];orders_[o.id]=o;
  if(o.priority)waiting_.push_front(o.id);else waiting_.push_back(o.id);
  sendLine(fd,"ORDER_ACCEPTED,"+std::to_string(o.id));std::printf("[server] order %d queued\n",o.id);dispatch();
 }else if(peer.role==Peer::Role::Unity&&fields.size()==4&&fields[0]=="REPORT"){
  int car,id;
  if(!integer(fields[2],car)||!integer(fields[3],id)||car!=peer.car_id||id!=peer.active_order||!orders_.count(id)){sendLine(fd,"ERROR,INVALID_REPORT");return;}
  Order o=orders_.at(id);
  if(fields[1]=="PICKUP"){if(peers_.count(o.client_fd))sendLine(o.client_fd,"STATUS,"+std::to_string(id)+",PICKUP");std::printf("[server] order %d picked up\n",id);}
  else if(fields[1]=="ARRIVED"){if(peers_.count(o.client_fd))sendLine(o.client_fd,"STATUS,"+std::to_string(id)+",DELIVERED");std::printf("[server] order %d delivered by car %d\n",id,car);orders_.erase(id);peer.active_order=0;dispatch();}
  else if(fields[1]=="REJECTED"){if(peers_.count(o.client_fd))sendLine(o.client_fd,"STATUS,"+std::to_string(id)+",REJECTED");std::printf("[server] order %d rejected by car %d\n",id,car);orders_.erase(id);peer.active_order=0;dispatch();}
  else{sendLine(fd,"ERROR,INVALID_REPORT");return;}
 }else if(peer.role==Peer::Role::Unity&&fields.size()==4&&fields[0]=="POSITION"){
  int car;double x,y;if(integer(fields[1],car)&&car==peer.car_id&&number(fields[2],x)&&number(fields[3],y)&&peer.active_order)std::printf("[server] car %d position %.2f,%.2f\n",car,x,y);
 }else sendLine(fd,"ERROR,UNKNOWN_MESSAGE");
 std::fflush(stdout);
}
void Manager::dispatch(){
 for(auto& [fd,peer]:peers_){if(peer.role!=Peer::Role::Unity||peer.active_order||waiting_.empty())continue;
  int id=waiting_.front();waiting_.pop_front();Order& o=orders_.at(id);
  std::ostringstream task;task<<std::setprecision(10)<<"TASK,"<<o.px<<','<<o.py<<','<<o.dx<<','<<o.dy<<','<<peer.car_id<<','<<id;
  if(!sendLine(fd,task.str())){waiting_.push_front(id);continue;}
  peer.active_order=id;o.car_id=peer.car_id;
  if(peers_.count(o.client_fd))sendLine(o.client_fd,"STATUS,"+std::to_string(id)+",ASSIGNED");
  std::printf("[server] order %d assigned to car %d\n",id,peer.car_id);std::fflush(stdout);
 }
}

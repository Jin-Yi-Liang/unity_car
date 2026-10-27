#include "../include/allhead.h"
#include <cmath>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <iomanip>
#include <sstream>
#include <sys/socket.h>
#include <vector>
#include <unistd.h>
namespace {
long long nowMillis(){return std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::system_clock::now().time_since_epoch()).count();}
std::string jsonString(const std::string& value){
 std::ostringstream out;out<<'"';
 for(unsigned char c:value){
  if(c=='"'||c=='\\')out<<'\\'<<c;
  else if(c<32)out<<"\\u"<<std::hex<<std::setw(4)<<std::setfill('0')<<static_cast<int>(c)<<std::dec;
  else out<<c;
 }
 out<<'"';return out.str();
}
std::vector<std::string> split(const std::string& line){std::vector<std::string> out;std::stringstream s(line);std::string f;while(std::getline(s,f,','))out.push_back(f);return out;}
bool number(const std::string& text,double& value){char* end=nullptr;value=std::strtod(text.c_str(),&end);return end!=text.c_str()&&*end=='\0'&&std::isfinite(value);}
bool integer(const std::string& text,int& value){char* end=nullptr;long v=std::strtol(text.c_str(),&end,10);if(end==text.c_str()||*end!='\0'||v<0||v>100000000)return false;value=static_cast<int>(v);return true;}
}
Manager::Manager(){session_id_=std::to_string(nowMillis())+"-"+std::to_string(getpid());}
Manager& Manager::getManager(){static Manager instance;return instance;}
void Manager::addPeer(int fd){peers_[fd]=Peer{};}
bool Manager::sendLine(int fd,const std::string& line){std::string bytes=line+'\n';size_t done=0;while(done<bytes.size()){ssize_t n=send(fd,bytes.data()+done,bytes.size()-done,MSG_NOSIGNAL);if(n<=0)return false;done+=static_cast<size_t>(n);}return true;}
void Manager::removePeer(int fd){
 auto it=peers_.find(fd);if(it==peers_.end())return;
 if(it->second.role==Peer::Role::Client)
  for(auto& entry:orders_)if(entry.second.client_fd==fd)entry.second.client_fd=-1;
 if(it->second.role==Peer::Role::Unity&&it->second.active_order){
  int id=it->second.active_order;auto order=orders_.find(id);
  if(order!=orders_.end()){order->second.car_id=0;order->second.status="REQUEUED";order->second.updated_ms=nowMillis();waiting_.push_front(id);if(peers_.count(order->second.client_fd))sendLine(order->second.client_fd,"STATUS,"+std::to_string(id)+",REQUEUED");}
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
void Manager::queueOrder(int fd,Order order){
 order.id=next_order_id_++;
 order.client_fd=fd;
 order.created_ms=order.updated_ms=nowMillis();
 orders_[order.id]=order;
 if(order.priority)waiting_.push_front(order.id);else waiting_.push_back(order.id);
 sendLine(fd,"ORDER_ACCEPTED,"+std::to_string(order.id));
 std::printf("[server] order %d queued%s\n",order.id,order.byBuilding()?" by building ID":"");
 dispatch();
}
void Manager::handleLine(int fd,const std::string& line){
 auto fields=split(line);Peer& peer=peers_.at(fd);
 if(peer.role==Peer::Role::Unknown){
  if(line=="LOGIN,CLIENT"){peer.role=Peer::Role::Client;sendLine(fd,"WELCOME,CLIENT");}
  else if(line=="LOGIN,MONITOR"){peer.role=Peer::Role::Monitor;sendLine(fd,"WELCOME,MONITOR");}
  else if(line=="LOGIN,UNITY"){peer.role=Peer::Role::Unity;peer.car_id=next_car_id_++;sendLine(fd,"WELCOME,UNITY,"+std::to_string(peer.car_id));std::printf("[server] car %d connected\n",peer.car_id);dispatch();}
  else sendLine(fd,"ERROR,LOGIN_REQUIRED");std::fflush(stdout);return;
 }
 if(peer.role==Peer::Role::Monitor&&line=="SNAPSHOT"){sendLine(fd,snapshot());return;}
 if(peer.role==Peer::Role::Client&&fields.size()==7&&fields[0]=="ORDER"){
  Order order;
  if(!number(fields[1],order.px)||!number(fields[2],order.py)||
     !number(fields[3],order.dx)||!number(fields[4],order.dy)||
     fields[5].empty()||!integer(fields[6],order.priority)||order.priority>1){
   sendLine(fd,"ERROR,INVALID_ORDER");return;
  }
  order.food=fields[5];queueOrder(fd,order);
 }else if(peer.role==Peer::Role::Client&&fields.size()==5&&fields[0]=="ORDER_BUILDINGS"){
  int priority;
  if(fields[3].empty()||!integer(fields[4],priority)||priority>1||fields[1]==fields[2]){
   sendLine(fd,"ERROR,INVALID_BUILDING_ORDER");return;
  }
  const BuildingInfo* pickup=catalog_.findById(fields[1]);
  const BuildingInfo* delivery=catalog_.findById(fields[2]);
  if(!pickup){sendLine(fd,"ERROR,UNKNOWN_BUILDING,"+fields[1]);return;}
  if(!delivery){sendLine(fd,"ERROR,UNKNOWN_BUILDING,"+fields[2]);return;}
  if(!pickup->hasSimulationDock()){sendLine(fd,"ERROR,UNASSIGNED_BUILDING,"+pickup->stable_id);return;}
  if(!delivery->hasSimulationDock()){sendLine(fd,"ERROR,UNASSIGNED_BUILDING,"+delivery->stable_id);return;}
  Order order;
  order.priority=priority;order.food=fields[3];
  order.pickup_building_id=pickup->stable_id;order.delivery_building_id=delivery->stable_id;
  order.pickup_node_id=pickup->dock_node_id;order.delivery_node_id=delivery->dock_node_id;
  order.px=pickup->dock_x;order.py=pickup->dock_y;
  order.dx=delivery->dock_x;order.dy=delivery->dock_y;
  queueOrder(fd,order);
 }else if(peer.role==Peer::Role::Unity&&
          ((fields.size()==4&&fields[0]=="REPORT")||(fields.size()==5&&fields[0]=="REPORT_BUILDING"))){
  bool by_building=fields[0]=="REPORT_BUILDING";
  int car,id;
  if(!integer(fields[2],car)||!integer(fields[3],id)||car!=peer.car_id||
     id!=peer.active_order||!orders_.count(id)){sendLine(fd,"ERROR,INVALID_REPORT");return;}
  Order order=orders_.at(id);
  if(order.byBuilding()!=by_building){sendLine(fd,"ERROR,INVALID_REPORT_TYPE");return;}
  if(by_building){
   const std::string& expected=fields[1]=="ARRIVED"?order.delivery_building_id:order.pickup_building_id;
   if(fields[4]!=expected){sendLine(fd,"ERROR,BUILDING_ID_MISMATCH");return;}
  }
  std::string suffix=by_building?","+(fields[1]=="ARRIVED"?order.delivery_building_id:order.pickup_building_id):"";
  if(fields[1]=="PICKUP"){
   if(order.status!="ASSIGNED"){sendLine(fd,"ERROR,INVALID_REPORT_SEQUENCE");return;}
   orders_.at(id).status="PICKUP";orders_.at(id).updated_ms=nowMillis();
   if(peers_.count(order.client_fd))sendLine(order.client_fd,"STATUS,"+std::to_string(id)+",PICKUP"+suffix);
   std::printf("[server] order %d pickup %s\n",id,order.pickup_building_id.c_str());
  }else if(fields[1]=="ARRIVED"||fields[1]=="REJECTED"){
   if(fields[1]=="ARRIVED"&&order.status!="PICKUP"){sendLine(fd,"ERROR,INVALID_REPORT_SEQUENCE");return;}
   std::string status=fields[1]=="ARRIVED"?"DELIVERED":"REJECTED";
   if(peers_.count(order.client_fd))sendLine(order.client_fd,"STATUS,"+std::to_string(id)+","+status+suffix);
   std::printf("[server] order %d %s by car %d at %s\n",id,status.c_str(),car,
               order.delivery_building_id.c_str());
   orders_.at(id).status=status;orders_.at(id).updated_ms=nowMillis();peer.active_order=0;dispatch();
  }else{sendLine(fd,"ERROR,INVALID_REPORT");return;}
 }else if(peer.role==Peer::Role::Unity&&fields.size()==4&&fields[0]=="POSITION"){
  int car;double x,y;
  if(integer(fields[1],car)&&car==peer.car_id&&number(fields[2],x)&&number(fields[3],y)){
   peer.x=x;peer.y=y;peer.has_position=true;
   if(peer.active_order)std::printf("[server] car %d position %.2f,%.2f\n",car,x,y);
  }
 }else sendLine(fd,"ERROR,UNKNOWN_MESSAGE");
 std::fflush(stdout);
}
void Manager::dispatch(){
 for(auto& [fd,peer]:peers_){if(peer.role!=Peer::Role::Unity||peer.active_order||waiting_.empty())continue;
  int id=waiting_.front();waiting_.pop_front();Order& o=orders_.at(id);
  std::ostringstream task;task<<std::setprecision(10)
   <<(o.byBuilding()?"TASK_BUILDINGS,":"TASK,")
   <<o.px<<','<<o.py<<','<<o.dx<<','<<o.dy<<','<<peer.car_id<<','<<id;
  if(o.byBuilding())task<<','<<o.pickup_building_id<<','<<o.delivery_building_id
                        <<','<<o.pickup_node_id<<','<<o.delivery_node_id;
  if(!sendLine(fd,task.str())){waiting_.push_front(id);continue;}
  peer.active_order=id;o.car_id=peer.car_id;
  o.status="ASSIGNED";o.updated_ms=nowMillis();
  if(peers_.count(o.client_fd))sendLine(o.client_fd,"STATUS,"+std::to_string(id)+",ASSIGNED");
  std::printf("[server] order %d assigned to car %d %s -> %s\n",id,peer.car_id,
              o.pickup_building_id.c_str(),o.delivery_building_id.c_str());std::fflush(stdout);
 }
}
std::string Manager::snapshot() const{
 std::ostringstream out;out<<std::setprecision(12)<<"{\"session\":"<<jsonString(session_id_)<<",\"orders\":[";
 bool first=true;
 for(int id=1;id<next_order_id_;++id){
  auto it=orders_.find(id);if(it==orders_.end())continue;const Order& o=it->second;
  if(!first)out<<',';first=false;
  out<<"{\"id\":"<<id<<",\"pickup_id\":"<<jsonString(o.pickup_building_id)
     <<",\"delivery_id\":"<<jsonString(o.delivery_building_id)<<",\"food\":"<<jsonString(o.food)
     <<",\"priority\":"<<o.priority<<",\"status\":"<<jsonString(o.status)<<",\"car_id\":"<<o.car_id
     <<",\"pickup_x\":"<<o.px<<",\"pickup_y\":"<<o.py<<",\"delivery_x\":"<<o.dx<<",\"delivery_y\":"<<o.dy
     <<",\"created_ms\":"<<o.created_ms<<",\"updated_ms\":"<<o.updated_ms<<'}';
 }
 out<<"],\"cars\":[";first=true;
 for(const auto& item:peers_){const Peer& p=item.second;if(p.role!=Peer::Role::Unity)continue;
  if(!first)out<<',';first=false;
  out<<"{\"id\":"<<p.car_id<<",\"order_id\":"<<p.active_order<<",\"x\":"<<p.x<<",\"y\":"<<p.y
     <<",\"has_position\":"<<(p.has_position?"true":"false")<<'}';
 }
 out<<"]}";return out.str();
}

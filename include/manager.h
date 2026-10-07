#pragma once
#include <deque>
#include <string>
#include <unordered_map>
struct Order { int id=0, client_fd=-1, car_id=0, priority=0; double px=0, py=0, dx=0, dy=0; std::string food; };
struct Peer { enum class Role { Unknown, Client, Unity } role=Role::Unknown; std::string input; int car_id=0, active_order=0; };
class Manager {
public:
 static Manager& getManager();
 void addPeer(int fd);
 void removePeer(int fd);
 void receive(int fd, const char* data, size_t size);
private:
 Manager()=default;
 void handleLine(int fd, const std::string& line);
 void dispatch();
 bool sendLine(int fd, const std::string& line);
 std::unordered_map<int,Peer> peers_;
 std::unordered_map<int,Order> orders_;
 std::deque<int> waiting_;
 int next_order_id_=1, next_car_id_=1;
};

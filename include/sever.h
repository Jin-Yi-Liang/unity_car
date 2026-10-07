#pragma once
class Sever {
public:
 static Sever& getSever();
 bool runSever();
 void deletePeer(int fd);
private:
 Sever()=default;
 int listen_fd_=-1, epoll_fd_=-1;
};

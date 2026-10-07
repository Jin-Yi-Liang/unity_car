# Unity 校园外卖小车仿真系统

> 下方架构图描述项目目标；本分支当前可运行的范围见文末「团结前端与本机联调」。已实现本机 TCP 派单、仿真道路图寻路、车辆移动及订单状态回传；DWA/APF、C++ 动态库和服务端全局 A* 尚未实现。

## 系统架构

本系统基于**"云-边-端协同"（Cloud-Edge-End）**理念与**边缘计算**思想，采用工业级 **Fleet Management System (FMS)** 标准架构。

---

### 宏观架构概述

系统整体划分为**云端调度中心**、**边缘计算节点**与**业务交互终端**三层。云端剥离了高频的底层物理控制，专注于低频的全局状态维护与业务路由；边缘端（无人车）负责高频的局部环境感知、实时避障计算与运动学执行。此架构消除了网络延迟对车辆行驶安全性的影响，更为未来向物理实体机器人（RDK X5 + ROS2）的无缝移植奠定基础。

---

### 核心模块详述

#### 一、后端/云端调度中心 (Cloud Dispatch Center)
**技术栈：** Linux + C++11 + `epoll` 事件驱动模型

**核心职责：**
1. **高并发连接管理**：基于 `epoll` 多路复用，维护海量终端的 TCP 长连接，首包协议认证动态完成异构终端的身份鉴权与会话绑定
2. **宏观路径规划与派单 (Global Planning & Dispatch)**：接收订单后，结合车辆当前坐标矩阵，运用图论算法计算全局最优分配策略
3. **航点下发 (Waypoint Assignment)**：将配送任务降维为一系列宏观坐标点（Waypoints），下发至目标车辆，不干预车辆的点间行驶过程

#### 二、前端/边缘计算核心 (Edge Computing Core / Local Planner)
**技术栈：** 纯 C++ 算法库（编译为动态链接库 `.so` / `.dll`）

**核心职责：**

1. **局部路径规划 (Local Planning)**：接收云端下发的宏观航点，实时评估局部环境
2. **动态避障运算 (Obstacle Avoidance)**：以 60Hz 频率接收雷达点云/射线数据，运用 DWA 或 APF 进行实时矩阵运算
3. **运动学解算**：在 1 毫秒内解算下一帧线速度 ($V_x$) 与角速度 ($V_\omega$)，回传给物理表现层

#### 三、前端/仿真与感知表现层 (Simulation & Perception Layer)
**技术栈：** Unity3D + C# + 物理引擎 (Nvidia PhysX)

**核心职责：**
1. **环境感知抽象 (Perception)**：利用 Raycast 模拟多线激光雷达，对动态物体进行深度测距
2. **跨语言极速调用 (P/Invoke)**：通过 `[DllImport]` 极速调用本地 C++ 算法库，实现"感知-计算"高效闭环
3. **指令执行与渲染 (Execution)**：将速度向量转化为对刚体的物理作用力，呈现平滑行驶轨迹，到达目标后向云端发送异步报告

#### 四、业务交互终端 (Business Interaction Terminal)
**技术栈：** 任意 TCP 客户端（Python 测试脚本 / C++）

**核心职责：** 建立与调度中心的通信握手，遵循应用层协议发起异步任务请求（`ORDER,起点坐标,终点坐标`），并订阅订单状态流

---

```
┌─────────────────────────────────────────────────────────────────┐
│                    模块一：后端/服务端(Central Server)            │
│                    Linux + C++ + epoll                            │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────────┐  │
│  │ epoll 网络I/O │  │  订单队列池   │  │  调度器 (Scheduler)   │  │
│  │  连接管理     │  │  优先级排序   │  │  派单                  │  │
│  └──────┬───────┘  └──────────────┘  └───────────┬───────────┘  │
│         │                                         │              │
│         └─────────────────┬───────────────────────┘              │
│                           │                                       │
│              ┌────────────▼────────────┐                         │
│              │  下发宏观航点 (Waypoints) │                         │
│              │  NAV,x1,y1,x2,y2,...,car_id                       │
│              └─────────────────────────┘                         │
└─────────────────────────────────────────────────────────────────┘
                              │ TCP 自定义协议
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                模块二：前端/边缘端(Unity Client)                   │
│                Unity3D + C# + 物理引擎                            │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────────┐  │
│  │ TcpClient    │  │  雷达感知     │  │  运动执行              │  │
│  │ (网络收发)    │  │  (Raycast)   │  │  (NavMeshAgent /     │  │
│  │              │  │  障碍物检测    │  │   Rigidbody)         │  │
│  └──────┬───────┘  └──────────────┘  └───────────┬───────────┘  │
│         │                                         │              │
│         │  DllImport 零延迟调用                     │              │
│         ▼                                         │              │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │              模块三：边缘端"小脑" (Local Planner)              ││
│  │              纯 C++ 算法库 (.so / .dll)                      ││
│  │              DWA / APF 避障算法 · 毫秒级输出速度指令          ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
                              ▲
                              │
┌──────────────────────────────┴──────────────────────────────────┐
│                  模块四：用户终端 (End User)                       │
│                  任意 TCP 客户端（测试脚本 / Python）              │
│  例：ORDER,食堂_X,食堂_Y,目标_X,目标_Y,food,priority             │
└─────────────────────────────────────────────────────────────────┘
```

---

### 通信协议

#### 上行（Client / Unity → Server）

| 消息 | 格式 | 说明 |
|------|------|------|
| 登录 | `LOGIN,CLIENT` 或 `LOGIN,UNITY` | 首包认证 |
| 订单 | `ORDER,pickup_x,pickup_y,deliver_x,deliver_y,food,priority` | 学生下单 |
| 汇报 | `REPORT,PICKUP\|ARRIVED\|REJECTED,car_id,order_id` | Unity 取餐、送达或拒绝离路任务 |
| 位置 | `POSITION,car_id,x,y` | Unity 定期上报地图坐标 |

#### 下行（Server → Unity）

| 消息 | 格式 | 说明 |
|------|------|------|
| 任务 | `TASK,pickup_x,pickup_y,deliver_x,deliver_y,car_id,order_id` | 下发完整配送任务 |
| 状态 | `STATUS,order_id,ASSIGNED\|PICKUP\|DELIVERED\|REJECTED` | 推送给下单客户端 |

---

### 模块职责一览

```
模块                    技术栈                核心职责
─────────────────────────────────────────────────────────────
云端调度大脑 (Server)  Linux + C++ + epoll  连接管理、订单队列、调度、A* 路径规划
边缘端躯干 (Unity)    Unity3D + C#          网络收发、雷达感知、运动执行、汇报
边缘端小脑 (Local)    C++ (.so/.dll)       DWA/APF 避障算法、毫秒级速度输出
用户终端 (Client)     任意 TCP 客户端        下单、查看配送状态
```

---

## Delight Points

1. single instance : made Sever and Manager single instance,so they can use their func everywhere instead of regist recallfunc or using static func with many unnecessary args
2. epoll_wait logic :
   1. if sfd is sever_sfd(newr), we add it into epoll and wait for varify message to add to clients/unitys.and the verify part put in addressSfd func(sever.cpp) in case of newr don't send verify message and block the epoll_sever
   2. if sfd is not secer_sfd, we call addressSfd,which find whether sfd is in clients or unitys or newer need to be verify it's identify(man made protocol)

---

## 项目结构

```
.
├── include/
│   ├── allhead.h       # 全局头文件
│   ├── sever.h         # epoll 服务器（网络 I/O）
│   ├── manager.h       # 数据管理器（clients/orders/unitys）
│   └── protocol.h      # 协议解析/序列化 ⭐ 待实现
├── src/
│   ├── sever.cpp
│   ├── manager.cpp
│   └── protocol.cpp    # 协议实现 ⭐ 待实现
├── run_epoll_sever.cpp # 服务端入口
├── run_client.cpp      # 测试客户端入口
├── CMakeLists.txt
└── README.md
```

## 团结前端与本机联调

`TuanjieProject/` 是用本机团结 2022.3.62t7 创建的可打开项目；主场景是 `Assets/Scenes/CampusDelivery.unity`。场景导入 `tools/campus_builder/output/campus.fbx`，使用其中已放置的 `DeliveryRobot_ROOT` 作为小车，挂载 `CampusCarController`、刚体与碰撞体；独立 `delivery_robot.fbx` 也保存在 `Assets/Models/`，供替换与检查。建筑和道路添加了静态碰撞体，摄像机跟随小车，左上角显示 TCP 状态、订单阶段及地图坐标。导航数据来自建模分支的 `simulation_navigation_graph.json`，仅供演示仿真，不能代表现实校园通行许可。

项目启动与协议、复现命令见 [TuanjieProject/README.md](TuanjieProject/README.md)。当前服务端绑定 `127.0.0.1:10000`，前端和后端须在同一台机器上运行。后端派单并回传状态；团结小车按仿真道路图寻路、执行移动并回报取餐及送达。当前运动使用按路点匀速移动和前向 Raycast 停车，没有实现 README 架构设想中的 C++ DWA/APF 动态规划库。

## 建筑稳定编号

团结场景中的 69 栋建筑使用独立稳定编号 `B0001`～`B0069`，显示名称可在 Inspector 中修改。后端目录由场景导出并通过脚本校验导入；目前仅四栋楼有仿真停靠节点，其他楼不得将视觉中心当成可行驶目标。流程见 [tools/buildings/README.md](tools/buildings/README.md)。

# 团结校园配送演示

## 送餐小车模型与尺寸

本项目使用 Blender 5.2.2 的参数化生成器 `tools/campus_builder/scripts/build_robot.py` 生成送餐小车：封闭保温货箱、侧门餐食标识、橙色车顶识别带、前后灯、四个独立轮轴和顶部雷达外壳。造型尺寸仍为 **长 1.20 米、宽 0.80 米、高 1.10 米**，与校园道路使用同一个米制坐标，不对车体应用地图 XY 比例倍数。Blender 验证文件为 `tools/campus_builder/output/validation/delivery_robot_report.md`，独立模型可打开 `tools/campus_builder/output/delivery_robot.blend`；校园内的车已经包含在 `campus.blend` 中。

本轮两次干净构建的 ROBOT、FBX、RENDER、IDEMPOTENCY 检查通过。起点所在道路宽约 11.42 米，车体加 0.30 米安全余量的放置检查通过。校园比例尺仍缺乏充分实测证据，所以总体地图报告为 `PARTIAL`；小车尺寸是独立设计值。

## 打开项目

使用本机团结 2022.3.62t7 打开本目录，然后打开 `Assets/Scenes/CampusDelivery.unity`。先启动仓库根目录的 C++ 服务端，再按 Play。团结小车在 `DeliveryRobot_ROOT` 上挂有 `CampusCarController`；左上角的 HUD 显示连接、订单和地图坐标。服务端未启动时，小车每 3 秒重连。

Main Camera 默认使用覆盖整个校园的正交鸟瞰视角；全景中的橙色 `CAR` 标记指出小车位置。在 Game 视图按 **F** 切换近距离跟车、按 **O** 返回全景，全景下用鼠标滚轮缩放。场景保存的主相机也已设为鸟瞰；脚本会根据 Ground 网格范围重新计算适配的视野。

校园 FBX 自带一辆已定位的小车，因此场景直接控制这辆车。`Assets/Models/delivery_robot.fbx` 是同一资产的独立导入副本，不应在当前场景再次放置，否则会出现双车。地图和车辆的原始 Blender/FBX 文件仍在 `tools/campus_builder/output/`。项目内的 FBX 为快照；重生成源资产后，需要同步替换 `Assets/Models/` 中的副本并运行场景生成器。

## 后台构建与联调

在仓库根目录运行：

```bash
cmake -S . -B build
cmake --build build -j4
./build/epoll_sever_run
```

在另一终端运行团结播放器；`-batchmode -nographics` 不弹窗口：

```bash
./build/tuanjie-player/DeliveryDemo.x86_64 -batchmode -nographics -logFile "$PWD/build/player-run.log"
```

在第三终端下单，以下两点均为仿真道路图中的节点：

```bash
./build/client_run -414.2355362 45.6737498 -414.2355362 93.8849301 lunch 0
```

成功时客户端依次收到 `WELCOME,CLIENT`、`ORDER_ACCEPTED,id`、`STATUS,id,ASSIGNED`、`STATUS,id,PICKUP`、`STATUS,id,DELIVERED`。播放器日志有 `[car]` 移动、取餐和送达记录。订单坐标应位于仿真道路图节点附近 6 米以内，否则小车回报 `REJECTED`。服务端只监听本机 `127.0.0.1:10000`。

重新生成道路 TextAsset 和团结场景/播放器：

```bash
python3 tools/export_tuanjie_navigation.py
LD_LIBRARY_PATH=/home/michael/.local/opt/tuanjie-1.8.5/compat/usr/lib/x86_64-linux-gnu \
  /home/michael/.local/opt/tuanjie-1.8.5/Editor/Tuanjie \
  -batchmode -nographics -projectPath "$PWD/TuanjieProject" \
  -executeMethod SceneBuilder.BuildPlayer -quit -logFile "$PWD/build/tuanjie-build.log"
```

需要重新从 Blender 建模时，先在仓库根目录运行项目隔离环境中的流水线；Blender 可执行文件位于 `/home/michael/opt/blender-5.2.2-linux-x64/blender`：

```bash
tools/campus_builder/.venv/bin/python tools/campus_builder/run_pipeline.py \
  --verify-idempotency --blender /home/michael/opt/blender-5.2.2-linux-x64/blender
cp tools/campus_builder/output/campus.fbx TuanjieProject/Assets/Models/campus.fbx
cp tools/campus_builder/output/delivery_robot.fbx TuanjieProject/Assets/Models/delivery_robot.fbx
python3 tools/export_tuanjie_navigation.py
```

建模流水线因已有的地图比例尺证据不足而返回 `PARTIAL` 和退出码 2；应查看各阶段报告，不能把这项比例尺限制写成车辆模型失败。更新 FBX 后再运行上面的团结构建命令。

## 通信约定

每条 TCP 消息以 `\n` 结尾，字段用逗号分隔；一次 `recv` 可以包含半条或多条消息。首包 `LOGIN,UNITY` / `LOGIN,CLIENT`；服务端向车发送 `TASK,pickup_x,pickup_y,deliver_x,deliver_y,car_id,order_id`；车发送 `REPORT,PICKUP|ARRIVED|REJECTED,car_id,order_id`。车用 `POSITION,car_id,x,y` 定期汇报。取餐与送达状态会转发给下单客户端。

建筑间订单使用 `ORDER_BUILDINGS,pickup_id,deliver_id,food,priority`。服务端解析后发送 `TASK_BUILDINGS`，携带两栋楼的稳定编号、仿真停靠节点及坐标；小车回传 `REPORT_BUILDING` 时再次携带当前建筑编号，服务端核对后向客户端发送带编号的 `STATUS`。

场景道路图的 XY 米制坐标映射为团结的 `(-X, 0.045, -Y)`，这是对实际 FBX 导入位置的探针结果。小车沿图中双向仿真边用 Dijkstra 寻路并按路点匀速移动，前方建筑 Raycast 命中时暂停。它尚不是动力学或真实道路通行验证。

## 建筑编号与改名

当前场景的 69 栋建筑已各自挂有 `BuildingIdentity`，层级名称显示 `Bxxxx · 名称`。选中建筑后只修改 Inspector 中的 **Display name**；稳定编号不会跟随名称变化。保存场景后，从菜单 **Campus → Export Building Catalog for Backend** 导出，再运行 `python3 tools/buildings/import_catalog.py` 更新后端 TSV。完整字段含义、四处已有仿真停靠节点及后端查询命令见 `tools/buildings/README.md`。

当前目录的名称已作为最终初始数据导入后端。四处有仿真停靠节点的建筑可用 `./build/building_client_run B0019 B0003 lunch 0` 发起建筑间订单；团结车辆会按节点寻路并回报取餐与送达编号。其余建筑虽已编号和导入，但没有可执行的停靠目标，服务端会明确拒绝这类订单。

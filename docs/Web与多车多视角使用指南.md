# Web 下单、多车配送与多 Display 使用指南

从零启动的统一入口见 [Unity Car 完整使用与验收指南](../unity小车_使用指南.md)；本页同步更新于 2026-10-18。

本功能在本地分支 `codex/web-orders-multiview` 实现，项目根目录为 `/home/michael/workspace/project/unity_car`。本次按要求不提交、不推送。

## 1. 当前能力与边界

- Web 提供取餐地、送达地、餐品、优先级和订单数量选择；可以一次发送 1～8 笔订单。
- 页面展示当前后端的全部订单，包含 Web 和原命令行客户端创建的订单，并每秒同步状态与车辆位置。
- 团结单个场景默认生成 3 辆车，各自有独立 TCP 连接、订单和道路运动状态。空闲车可同时接单；所有车忙碌时后续订单排队。
- SQLite 历史存放于 `build/web-orders.sqlite3`。刷新浏览器或重启 Web 服务仍可查看记录。后端重启时，旧会话未完成的任务标为“服务重启中断”，不冒充送达。
- 69 栋建筑均可在建筑目录中查询；全部 69 栋均配置独立停靠点，可选择任意两个不同建筑下单（共 4692 种组合）。停靠点在附近道路上，属于仿真交接位置。
- 当前是本机/局域网演示，没有用户账号、订单取消、车辆间避让或交通调度。车辆采用独立的运动学路径跟随，交汇时可能重叠；本次验证并行派单与运动，不代表真实多车碰撞安全。

## 2. 从全部关闭状态启动

所有终端先进入根目录：

```bash
cd /home/michael/workspace/project/unity_car
```

第一次或修改 C++ 后编译并导入目录：

```bash
python3 tools/buildings/import_catalog.py
cmake -S . -B build
cmake --build build -j4
```

### 终端 A：C++ 后端

```bash
./build/epoll_sever_run data/buildings.tsv
```

应显示加载 69 栋建筑并监听 `127.0.0.1:10000`。保持终端运行。此后端必须是本分支新编译的版本，否则 Web 查询 MONITOR 协议会失败。

### 终端 B：Web 服务

```bash
python3 web/server.py
```

在浏览器打开：

```text
http://127.0.0.1:8080
```

Python Web 服务仅使用标准库，不需要 npm 安装或额外 Python 包。右上角应显示“后端已连接”；还没有启动团结时，在线车辆为 0，订单可以先进入队列。

### 终端 C：团结前端，二选一

编辑器方式：

```bash
/home/michael/.local/bin/tuanjie-1.8.5 \
  -projectPath "$PWD/TuanjieProject" \
  -executeMethod SceneBuilder.OpenForReview \
  -logFile "$PWD/build/web-editor.log"
```

等待编译完成，点击 Play，在 Game 视图观察。场景中的 `Fleet Coordinator` 在 Play 时以原有车为模板生成另外两辆车。

独立播放器方式：

```bash
./build/tuanjie-player/DeliveryDemo.x86_64 \
  -screen-fullscreen 0 -screen-width 1280 -screen-height 720 \
  -logFile "$PWD/build/web-player.log"
```

只运行一个团结前端实例；一个实例已经包含三辆车。编辑器 Play 和播放器同时开会形成额外车队。

当三辆车连接后，Web 应显示 3 张车辆卡片。程序已启用后台运行：切换到浏览器或将播放器置于后台时，小车仍会继续运动。

## 3. 在 Web 下单与观察状态

1. 在“取餐地点 / 起点 A”选择例如 `B0019 · Library west block`。
2. 在“送达地点 / 终点 B”选择例如 `B0003 · Teaching building 3`。
3. 填写餐品，优先级选择普通或优先；起终点不能相同。
4. 订单数量保持 1，点击“发送配送任务”。
5. 在订单列表中观察“排队中 → 前往取餐 → 配送中 → 已送达”。取餐和送达名称及车辆编号也会显示。
6. 在团结中观察地图上的每辆车标记；按 Tab 选择另一辆车，HUD 显示当前所选车辆的订单和最终目的地。

A 是取餐目标。车辆先从当前停车位置开到 A，随后开到 B，不会瞬移到 A。

批量测试时把订单数量改为 3 再提交。通常三辆空闲车会各接一笔并同时运动。数量改为 4 或更大时，超过空闲车辆数的订单保持排队，待有车辆完成后继续分配。为了测试不同路线，也可以连续选择不同起终点分别提交。

“配送订单”的状态筛选可查看进行中、已送达或异常订单。建筑目录可搜索稳定编号和显示名称。后端重启后订单编号会重新计数，Web 内部使用“后端会话 + 订单号”保存历史，避免不同会话记录互相覆盖。

原命令行仍可下单，任务也会出现在 Web：

```bash
./build/building_client_run B0019 B0003 lunch 0
```

## 4. Display 与观察视角

在团结 Editor 的 **Game 视图顶部 Display 下拉框**，选择：

| Display | 完整画面 | 用途 |
|---|---|---|
| Display 1 | 校园全景 + 右上角所选车近景 | 同时观察路线和三辆车的位置 |
| Display 2 | 所选车的完整近景 | 查看车身和近处道路，不再是小窗 |
| Display 3 | 所选车的中距离跟随视角 | 看车与周边道路、建筑的关系 |
| Display 4 | 所选车的高处远景 | 观察一片校园区域中的运动 |
| Display 5 | 所选车的垂直俯视 | 看道路转弯和路径方向 |
| Display 6 | 所选车的环绕视角 | 从不同方向查看车辆和场景 |

显示目标均已保存在场景各 Camera 的 `Target Display` 中。**Tab** 在三辆车之间切换，所有跟随视角都会跟到所选车。车队的服务器 ID 每次连接可能不同，不能假定总是 1、2、3。

单屏播放器通常只提供一个物理 Display。此时在 Display 1 点击 Game 画面获得焦点，使用 **数字键 1～6** 切换同一组画面；F 等同近景，O 返回全景，滚轮在全景下缩放。原有右上角车身小窗只在全景模式显示。

真实多屏播放器只会激活系统实际存在的显示器；单屏快捷键用于本机观测，不假称存在额外物理屏幕。

## 5. 让局域网的其他人访问

将终端 B 的启动命令改为：

```bash
python3 web/server.py --host 0.0.0.0 --port 8080
```

查看本机局域网地址：

```bash
hostname -I
```

同一网络的其他人通过 `http://本机局域网IP:8080` 访问，所有订单仍由本机 C++ 后端分配。后端 TCP 地址保持回环即可。这个演示 Web 没有账户或权限控制，仅在你允许访问的局域网中使用；请不要把浏览器地址写成 `0.0.0.0`。

## 6. 重建前端与场景

前端源码改动后，旧播放器不会自动更新。保存场景并关闭同一项目的编辑器后执行：

```bash
/home/michael/.local/bin/tuanjie-1.8.5 \
  -batchmode -nographics -projectPath "$PWD/TuanjieProject" \
  -executeMethod SceneBuilder.BuildPlayer -quit \
  -logFile "$PWD/build/web-player-build.log"
```

应看到 `player result=Succeeded`、`errors=0`。需要有效编辑器许可。

现有场景已升级。如从旧场景重新接入本功能，可在关闭 GUI 后运行 `-executeMethod SceneBuilder.UpgradeFleetAndDisplays`，或编辑器菜单 **Campus → Upgrade Fleet and Displays**。该操作保留已有建筑标注，并加入三车生成器与相机。

## 7. 测试与证据

协议测试需先启动新版 C++ 后端和 Web，且先不要启动真实车队：

```bash
python3 tests/test_web_orders.py -v
```

它用三条模拟车辆连接验证并发分配、第四单排队、请求去重、错误回报拒绝以及历史保留。此测试不能替代真实车辆运动验收。

`tests/browser_web_test.mjs` 使用独立的 Chrome DevTools 测试会话，在实际表单中提交 69 单，覆盖每栋建筑各作为一次取餐点和送达点；`tests/verify_unity_fleet.py` 观察真正团结播放器执行这些任务，记录并行车辆数、沿途坐标和最终状态。此组工具用于本次验收，图和协议另验证全部 4692 种组合。结果存放在忽略目录 `build/validation/`，日常使用无需运行。

用于加速全部建筑验收的播放器参数 `-qa-timescale 8` 只加快仿真时间，不是日常默认设置；默认仍为 1。`-capture-views 输出目录` 可生成六种单屏切换画面的截图，不影响正常启动命令。

## 8. 关闭与重置

先等待任务完成，退出团结 Play 或关闭播放器，再分别在 Web 和后端终端 Ctrl+C。Web 历史保留在 SQLite 中，后端运行中的订单保存在进程内存中。

如果中途重启后端，旧未完成订单会在 Web 标为“服务重启中断”；新会话可以重新下单。关闭浏览器不等于取消订单，当前没有订单取消按钮。

常见问题：

| 现象 | 处理 |
|---|---|
| Web 显示后端未连接 | 确认终端 A 正在运行新版二进制，检查 10000 端口 |
| MONITOR 协议错误 | 重新编译本分支的 C++ 并重启服务端 |
| 没有在线车辆 | 团结进入 Play 或启动新构建的播放器，等待 TCP 连接 |
| 只有一辆车 | 确认打开的是本分支已升级的 CampusDelivery 场景，且播放器已重建 |
| 订单比车多，部分排队 | 正常；车辆完成当前任务后会接下一笔 |
| 切到浏览器后车不动 | 本分支已启用 Run In Background；确认使用新播放器而非旧构建 |
| Game 下拉仍只见旧设置 | 打开正确场景并进入 Play，检查 Display 2～6 相机是否存在；单屏可先用数字键切换 |
| 名称在 Web 与场景不一致 | 保存场景并导出建筑 JSON、运行导入脚本，再重启后端与 Web |

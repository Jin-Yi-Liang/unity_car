# Unity Car 完整使用与验收指南

本文从“后端、Web、团结编辑器和播放器全部关闭”的状态开始，完成一次校园配送：启动后端 → 启动 Web → 启动团结三车场景 → 在网页选择任意两个不同建筑 → 车辆取餐、送达 → 查看订单状态。

- 更新日期：2026 年 10 月 18 日。
- 当前本地功能分支：`codex/web-orders-multiview`；功能改动尚未提交、尚未推送。不要为验收切回旧的 `main`。
- 团结版本：**1.8.5**，底层编辑器版本 **2022.3.62t7**。
- **69 栋建筑全部配置停靠点**，共支持 **69 × 68 = 4692** 种不同起终点组合。
- 一个团结实例默认运行 **3 辆车**。本指南使用 Web 下单，命令行方式作为补充。

## 1. 项目路径

| 内容 | 本机绝对路径 |
|---|---|
| 项目根目录 | `/home/michael/workspace/project/unity_car` |
| 团结项目，在 Hub 中添加此目录 | `/home/michael/workspace/project/unity_car/TuanjieProject` |
| 已配置的主场景 | `/home/michael/workspace/project/unity_car/TuanjieProject/Assets/Scenes/CampusDelivery.unity` |
| 后端建筑目录 | `/home/michael/workspace/project/unity_car/data/buildings.tsv` |
| 全部建筑停靠点与距离说明 | `/home/michael/workspace/project/unity_car/data/building-docks.json` |
| 团结启动脚本 | `/home/michael/.local/bin/tuanjie-1.8.5` |
| 编辑器程序 | `/home/michael/.local/opt/tuanjie-1.8.5/Editor/Tuanjie` |
| 团结 Hub | `/opt/tuanjiehub` |
| 独立播放器 | `/home/michael/workspace/project/unity_car/build/tuanjie-player/DeliveryDemo.x86_64` |
| 日常订单历史 | `/home/michael/workspace/project/unity_car/build/web-orders.sqlite3` |

统一使用上述普通 workspace 目录。`/home/michael/.codex/worktrees/0878/unity_car` 是另一个 Git 工作树，不能交叉使用其中的旧资源或播放器。

## 2. 首次准备：编译后端并检查目录

打开终端，执行：

```bash
cd /home/michael/workspace/project/unity_car
python3 tools/buildings/import_catalog.py
cmake -S . -B build
cmake --build build -j4
./build/catalog_lookup_run B0001
./build/catalog_lookup_run B0069
```

预期导入输出包含 `69 buildings (69 simulation docks)`，两个查询都包含 `simulation_dock` 和非空的停靠节点。

日常启动不用重新生成 Blender 模型、导航图或场景。不要重复拖入小车：校园场景已有原车，进入 Play 时自动生成另外两辆车。

## 3. 终端 A：启动 C++ 后端

```bash
cd /home/michael/workspace/project/unity_car
./build/epoll_sever_run data/buildings.tsv
```

保持终端运行。预期显示加载 69 栋建筑，监听 `127.0.0.1:10000`。

如果提示端口被占用，先检查已有进程，避免启动第二套：

```bash
ss -ltnp '( sport = :10000 or sport = :8080 )'
```

## 4. 终端 B：启动 Web

```bash
cd /home/michael/workspace/project/unity_car
python3 web/server.py
```

保持终端运行，在浏览器打开：

**http://127.0.0.1:8080**

应看到“后端已连接”。团结尚未运行时，在线车辆为 0。取餐和送达下拉框都应有 **69 个可选建筑，没有禁用项**。

Web 仅使用 Python 标准库，不需要安装 npm 或额外 Python 包。

## 5. 终端 C：启动团结前端

### 方式一：编辑器，适合验收 Display

```bash
cd /home/michael/workspace/project/unity_car
/home/michael/.local/bin/tuanjie-1.8.5 \
  -projectPath "$PWD/TuanjieProject" \
  -executeMethod SceneBuilder.OpenForReview \
  -logFile "$PWD/build/web-editor.log"
```

等待打开 `CampusDelivery` 场景，点击顶部 **Play**，切到 **Game**。Web 等待片刻后应显示 **3 辆在线车辆**。

也可以打开 Tuanjie Hub，添加上表中的 `TuanjieProject` 目录，选择已安装的 1.8.5；场景没打开时，在 Project 中双击 `Assets/Scenes/CampusDelivery.unity`，然后点击 Play。Hub 若提示缺少版本，使用上面的本机启动脚本即可调用已经安装的对应编辑器。

### 方式二：独立播放器

```bash
cd /home/michael/workspace/project/unity_car
./build/tuanjie-player/DeliveryDemo.x86_64 \
  -screen-fullscreen 0 -screen-width 1280 -screen-height 720 \
  -logFile "$PWD/build/web-player.log"
```

**只选一种前端运行方式。** 一个实例已经包含三辆车，同时开启编辑器 Play 和播放器会出现额外车队。切换到浏览器或最小化前端时，车辆会继续运动。

## 6. 在网页指定 A → B

1. 打开配送工作台，在“取餐地点 / 起点 A”选择任意建筑，例如 `B0001 · Administration`。
2. 在“送达地点 / 终点 B”选择另一栋建筑，例如 `B0069`。名称以当前目录为准。
3. 填写餐品，选择普通或优先配送。
4. 订单数量设为 **1**，点击“发送配送任务”。
5. 在订单列表观察状态：**排队中 → 前往取餐 → 配送中 → 已送达**。
6. 在 Game 中观察小车沿道路行驶。左上角显示当前观察车辆的订单和最终目的地。

车辆从自己的当前位置先开到 A 取餐，再开到 B，A 不是瞬移出生点。A 和 B 必须不同；不存在的编号会被拒绝。相同显示名称的建筑通过 Bxxxx 编号区分。

### 多订单、多车测试

- 等待三辆车空闲，把订单数量改为 **3**，提交一次，观察三个不同车辆编号同时配送。
- 数量改为 **4** 或更多，超出空闲车数的订单会排队；任一车辆完成后自动接下一单。
- 一次可提交 **1～8 单**；要测试不同路线，可连续选择不同的 A、B 提交。
- 状态筛选可查看进行中、已送达和异常订单，页面每秒刷新车辆和订单。
- 关闭浏览器不会取消任务；目前没有取消订单功能。

## 7. 六个 Display 与快捷键

在 Editor 的 **Game 视图顶部 Display 下拉框**中选择：

| Display | 视角 |
|---|---|
| Display 1 | 校园全景＋右上角所选车近景 |
| Display 2 | 所选车完整近景 |
| Display 3 | 中距离跟随 |
| Display 4 | 高处远景 |
| Display 5 | 垂直俯视 |
| Display 6 | 环绕 |

点击 Game 画面获得焦点后：

- **Tab**：切换所选车辆，所有跟随相机一起切换目标。
- **数字键 1～6**：在主画面切换上述六种视角，适合单屏播放器。
- **F**：近景；**O**：返回全景。
- **滚轮**：全景下缩放。

车队 ID 由后端在连接时分配，每次运行可能变化。多个 Display 相机已配置；独立播放器只会激活实际接入的物理显示器。单屏验收直接使用数字键即可。

场景新增 `Delivery Docks` 对象，包含 69 个青色停靠标记，名称中带建筑编号和导航节点，便于核对终点位置。

## 8. 停靠点与建筑名称的含义

每栋建筑使用固定 `stableId`（B0001～B0069），对应一个独立停靠节点。原有四处停靠点保留，新增点设置在附近可通行道路上；车辆在道路边交接，不驶入房屋中心。

这些是**仿真交接位置**，不是现场确认的真实门口。各点到建筑外墙的距离记录在 `data/building-docks.json` 中；较远的点约 43.6 米，代表附近道路交接。全部道路按仿真双向通行规则接入，真实校园通行权限尚未核实。

如需修改显示名称：

1. 在团结中选中建筑，修改 `Building Identity → Display name`，保存场景。
2. 菜单 **Campus → Export Building Catalog for Backend**。
3. 根目录执行 `python3 tools/buildings/import_catalog.py`。
4. 重启后端与 Web；需要更新独立播放器时按下一节重建。

名称不参与派单和寻路。不要修改 Stable ID、节点编号和坐标，或重新初始化建筑编号。

## 9. 重建与数据维护

仅 C++ 改动：重新执行第 2 节编译命令并重启后端。

团结脚本、资源或场景改动后，先关闭该项目编辑器，再重建独立播放器：

```bash
cd /home/michael/workspace/project/unity_car
/home/michael/.local/bin/tuanjie-1.8.5 \
  -batchmode -nographics -projectPath "$PWD/TuanjieProject" \
  -executeMethod SceneBuilder.BuildPlayer -quit \
  -logFile "$PWD/build/web-player-build.log"
```

成功日志包含 `player result=Succeeded`、`errors=0`。编辑器需要有效许可。

如重新生成了 Blender 原始导航数据，需要重新应用全部建筑停靠点；日常启动不执行这一组：

```bash
cd /home/michael/workspace/project/unity_car
tools/campus_builder/.venv/bin/python tools/buildings/assign_docks.py
python3 tools/export_tuanjie_navigation.py
/home/michael/.local/bin/tuanjie-1.8.5 \
  -batchmode -nographics -projectPath "$PWD/TuanjieProject" \
  -executeMethod SceneBuilder.UpgradeAllDocksAndBuildPlayer -quit \
  -logFile "$PWD/build/all-docks-build.log"
python3 tools/buildings/import_catalog.py
```

该流程保留场景显示名称和稳定编号，更新全部停靠数据、标记、后端导出，并检查 4692 条路线与建筑碰撞。几何生成器使用项目已有虚拟环境中的 Shapely。

## 10. 命令行下单与局域网访问

Web 是日常入口；原命令行仍可用于补充测试：

```bash
cd /home/michael/workspace/project/unity_car
./build/building_client_run B0001 B0069 lunch 0
```

该终端依次输出接单、分配、取餐、送达状态。命令行创建的订单也会显示在 Web。

如需同一局域网的其他人访问，将终端 B 命令改为：

```bash
python3 web/server.py --host 0.0.0.0 --port 8080
hostname -I
```

其他人使用 `http://本机局域网IP:8080`。TCP 后端保持回环地址。当前没有登录权限管理，仅用于你允许访问的本机或局域网演示。

## 11. 停止、历史与故障处理

正常结束：等待任务送达 → 停止编辑器 Play 或退出播放器 → Web 终端 Ctrl+C → 后端终端 Ctrl+C。

Web 历史保存在 SQLite 中，后端活动订单保存在内存中。刷新网页或重启 Web 不会丢失已保存历史；重启后端后，旧会话未完成订单显示“服务重启中断”，需要重新下单。

| 现象 | 检查 |
|---|---|
| Web 后端未连接 | 后端是否运行新版程序、10000 端口是否监听 |
| 仍然只有 4 个地点可选 | 确认使用本指南路径；导入后应输出 69 个 docks，然后重启后端与 Web并刷新页面 |
| 下单后一直排队 | 是否点击 Play、是否有空闲车辆、是否打开了新版本场景 |
| 只有一辆车 | 正确场景应有 Fleet Coordinator，vehicleCount=3；旧播放器需要重建 |
| 建筑节点/坐标不匹配 | 前后端混用了不同版本资源，重新导出、导入并重建播放器 |
| 游戏失焦后不动 | 使用本分支新播放器，Run In Background 已开启 |
| 看不到车 | 数字键 2 进入近景，Tab 切换车辆；数字键 1 返回全景 |
| 编辑器提示另一个实例 | 先检查并关闭同项目编辑器；残留进程持锁时不要直接删除锁文件 |
| 名称更改后 Web 没更新 | 保存场景、导出、导入并重启后端和 Web |

## 12. 验收与当前限制

- 69 栋均可作为起点和终点；同起终点输入被明确拒绝。
- 全部 4692 种组合已通过图寻路和协议验证；真实团结播放器运行覆盖每栋建筑作为取餐和送达点（完整覆盖采用无图形模式，另做默认速度的图形三车配送检查）。具体证据与测试倍率见验收记录：完整覆盖为无图形 8 倍测试，另已通过默认速度图形三单；138 次覆盖停车位置最大误差约 0.185 米。
- 单车全流程、多车并发、排队、后台运行、订单历史和六视角分别验收。
- 当前为运动学仿真，没有车辆间避碰、真实车辆动力学或 C++ DWA/APF 控制。交汇处或共同停靠位置可能重叠。
- 房屋材质细节还原未在本次完成；比例尺和真实门口也未实地测量。

相关文档：[Web 与多车多视角指南](docs/Web与多车多视角使用指南.md)、[验收记录](docs/本地功能验收记录.md)、[建筑目录维护](tools/buildings/README.md)、[项目说明](README.md)。

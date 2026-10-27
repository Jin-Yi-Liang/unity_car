# 建筑编号与后端目录

69 栋建筑的编号与名称已从团结场景导入 C++ 后端。建筑间订单会按稳定编号解析为仿真停靠节点，下发给团结车辆；原有坐标订单继续可用。全部 69 栋均有独立停靠点，支持任意两个不同建筑之间下单。

## 编号规则

- 每个当前建筑实例获得唯一、固定的 `stableId`：`B0001`～`B0069`。它是后端查询和将来订单的键。
- `meshId`（例如 `BLDG_003`）连接到当前 FBX 网格；`sourceTraceIds` 用于审计地图来源。后续模型重建若调整网格编号，必须显式校对注册表，不得重新运行初始化脚本覆盖编号。
- `mapLabel` 是原地图上的编号，会重复；`displayName` 是可修改的显示名称，会重复或更名。逻辑一律按 `stableId` 查找。
- `centerX/Y` 是包围盒中心，仅用于标注和粗略定位，**不是车可达的停靠点**。当前全部建筑的 `navigationStatus=simulation_dock`，停靠点为附近道路上的仿真交接点，入口并未实地确认。

只运行一次的初始注册表来自 `tools/buildings/init_registry.py`，已经存于 `TuanjieProject/Assets/Resources/building_registry.json`。脚本检测到已有文件会拒绝覆盖。

## 在团结里修改名称

1. 打开 `TuanjieProject/Assets/Scenes/CampusDelivery.unity`。Hierarchy 中每栋建筑显示 `Bxxxx · 名称`。
2. 选择建筑，在 `Building Identity` Inspector 中修改 **Display name**。Stable ID、地图号、源网格和导航节点在 Inspector 中只读。保存场景。
3. 点击菜单 **Campus → Export Building Catalog for Backend**。它从已打开场景的 69 个组件导出 `data/buildings-unity.json`。重建场景时，`SceneBuilder.BuildScene` 会按 Stable ID 保留已保存的显示名称。
4. 在仓库根目录执行 `python3 tools/buildings/import_catalog.py`。脚本校验全部编号、网格、地图号、源 ID 和停靠数据没有漂移，只允许显示名称变化，然后原子写入 `data/buildings.tsv`。
5. 重启 C++ 服务端以载入新目录。后端 `BuildingCatalog::findById` 仍使用同一 Stable ID。

也可以不打开 GUI，在仓库根目录执行下列命令读取已保存场景并导出。不要在编辑器打开同一个项目时再启动第二个团结进程。

```bash
/home/michael/.local/bin/tuanjie-1.8.5 -batchmode -nographics \
  -projectPath "$PWD/TuanjieProject" \
  -executeMethod SceneBuilder.ExportSavedSceneCatalog -quit \
  -logFile "$PWD/build/building-export.log"
python3 tools/buildings/import_catalog.py
```

## 后端验证

```bash
cmake -S . -B build
cmake --build build -j4
python3 tools/buildings/import_catalog.py
./build/catalog_lookup_run B0003
./build/catalog_lookup_run B0069
./build/epoll_sever_run data/buildings.tsv
```

`B0003` 示例有仿真停靠节点 `SIMNODE_0038`；`B0069` 有停靠节点 `DOCK_B0069`。服务端启动时加载目录并报告建筑数量；加载失败会直接报错，避免用错误的编号表运行。`catalog_lookup_run` 与服务端共用 `BuildingCatalog` C++ 解析类。

## 从建筑到建筑的订单

运行服务端和团结场景或无窗口播放器后，在仓库根目录下单：

```bash
./build/building_client_run B0019 B0003 lunch 0
```

协议为 `ORDER_BUILDINGS,取餐稳定编号,送达稳定编号,餐品,优先级`。服务端只按 Stable ID 查目录，确认两栋楼都有仿真停靠点，向车发送 `TASK_BUILDINGS`，其中包含两栋楼的稳定编号、停靠节点和地图坐标。团结端核对节点与坐标一致后寻路，到点分别发送 `REPORT_BUILDING,PICKUP/ARRIVED` 和相应建筑编号；后端核对后把 `STATUS,订单号,PICKUP/DELIVERED,建筑编号` 回传下单客户端。显示名称不参与消息解析或导航。

原有四栋的停靠节点保留。其他建筑新增 `DOCK_Bxxxx`，编号、名称与已有资产保持关联。不存在的 `B9999` 返回 `ERROR,UNKNOWN_BUILDING,B9999`；同起终点返回无效订单错误。错误建筑回报返回 `ERROR,BUILDING_ID_MISMATCH`。

## 全部停靠点的生成与验证

`tools/buildings/assign_docks.py` 在原始道路图上为 69 栋建筑分配独立停靠位置，保留四个旧站点和原 SIMNODE 编号；原始建筑中心、几何和四处候选门口数据不变。它按车体外接圆加安全余量检查道路边界，并为建筑预留 2.5 米净空，对桥外水体做排除，并检查从停靠点到建筑外墙的交接线不穿过其他建筑或水体。扩展路网为 159 个节点、180 条边，全部 4692 种组合连通。

新增点是道路交接位置，不代表真实门口已确认。到建筑外墙的距离记录在 `data/building-docks.json`，最远约 43.6 米。原始 `delivery_sites.json` 仍保存四处带来源门口及步行连接的历史资产；当前全部建筑导航使用扩展后的 `simulation_navigation_graph.json`。

关闭团结编辑器后执行以下维护流程，日常启动无需重跑：

```bash
tools/campus_builder/.venv/bin/python tools/buildings/assign_docks.py
python3 tools/export_tuanjie_navigation.py
/home/michael/.local/bin/tuanjie-1.8.5 -batchmode -nographics \
  -projectPath "$PWD/TuanjieProject" \
  -executeMethod SceneBuilder.UpgradeAllDocksAndBuildPlayer -quit \
  -logFile "$PWD/build/all-docks-build.log"
python3 tools/buildings/import_catalog.py
```

场景升级保留显示名称，并加入 69 个非碰撞青色标记。内置验证调用团结实际寻路代码检查 4692 条路线，用物理碰撞检查路段是否被建筑阻挡。服务端契约矩阵见 `tests/verify_all_building_protocol.py`；真实车辆覆盖见 `tests/browser_web_test.mjs` 和 `tests/verify_unity_fleet.py`。测试报告区别图连通、模拟回报与真实车辆运动。

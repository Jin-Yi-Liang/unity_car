# 建筑编号与后端目录

69 栋建筑的编号与名称已从团结场景导入 C++ 后端。建筑间订单会按稳定编号解析为仿真停靠节点，下发给团结车辆；原有坐标订单继续可用。只有四处已有仿真停靠点，其他建筑尚不能作为车辆终点。

## 编号规则

- 每个当前建筑实例获得唯一、固定的 `stableId`：`B0001`～`B0069`。它是后端查询和将来订单的键。
- `meshId`（例如 `BLDG_003`）连接到当前 FBX 网格；`sourceTraceIds` 用于审计地图来源。后续模型重建若调整网格编号，必须显式校对注册表，不得重新运行初始化脚本覆盖编号。
- `mapLabel` 是原地图上的编号，会重复；`displayName` 是可修改的显示名称，会重复或更名。逻辑一律按 `stableId` 查找。
- `centerX/Y` 是包围盒中心，仅用于标注和粗略定位，**不是车可达的停靠点**。`navigationStatus=simulation_dock` 的四栋楼才有仿真图节点，且入口并未实地确认。其他建筑标为 `unassigned`。

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

`B0003` 示例有仿真停靠节点 `SIMNODE_0038`；`B0069` 为 `unassigned`。服务端启动时加载目录并报告建筑数量；加载失败会直接报错，避免用错误的编号表运行。`catalog_lookup_run` 与服务端共用 `BuildingCatalog` C++ 解析类。

## 从建筑到建筑的订单

运行服务端和团结场景或无窗口播放器后，在仓库根目录下单：

```bash
./build/building_client_run B0019 B0003 lunch 0
```

协议为 `ORDER_BUILDINGS,取餐稳定编号,送达稳定编号,餐品,优先级`。服务端只按 Stable ID 查目录，确认两栋楼都有仿真停靠点，向车发送 `TASK_BUILDINGS`，其中包含两栋楼的稳定编号、停靠节点和地图坐标。团结端核对节点与坐标一致后寻路，到点分别发送 `REPORT_BUILDING,PICKUP/ARRIVED` 和相应建筑编号；后端核对后把 `STATUS,订单号,PICKUP/DELIVERED,建筑编号` 回传下单客户端。显示名称不参与消息解析或导航。

实测 `B0019 → B0003` 返回 `ORDER_ACCEPTED,1`、`STATUS,1,ASSIGNED`、`STATUS,1,PICKUP,B0019`、`STATUS,1,DELIVERED,B0003`；车从初始位置经 `SIMNODE_0037` 到 `SIMNODE_0038`，并记录沿途位置。另用协议探针发送错误的取餐建筑编号，服务端返回 `ERROR,BUILDING_ID_MISMATCH`，正确回报仍可完成订单。不存在的 `B9999` 返回 `ERROR,UNKNOWN_BUILDING,B9999`；已导入但无停靠点的 `B0001` 返回 `ERROR,UNASSIGNED_BUILDING,B0001`。这些错误在接单前返回，不会派车。其余 65 栋楼需要另行确认入口与仿真停靠节点，不能把视觉中心当作可行驶目标。

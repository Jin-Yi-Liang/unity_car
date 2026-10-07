# Campus Model V0.5 — 候选入口与配送通行几何

在 V0.2 的尺度校准、固定米制 Z、受限道路修正、独立桥面和基础导航图基础上，增加按楼栋配置的楼层/高度、平顶/坡顶/弧形屋顶、可导出的立面贴图和建筑近景验证。没有使用 Unity/团结引擎，也没有修改 C++ 服务端。

V0.4 进一步按已有照片改进展厅、体育馆、图书馆的立面。展厅下部在原占地包络内收 8%，体育馆增加金属屋面拼缝贴图，图书馆使用成组窗格与顶部窄窗带；这些细节尺寸是建模近似。窗格沿边界累计距离映射，避免弧形立面逐面错位。原高度与 XY 包络继续在源场景、FBX 重新导入后验证。

V0.5 在图书馆、3号教学楼、20号食堂和11号宿舍建立四组候选入口、门前步行连接道和道路侧交付区域。**入口不是经过确认的真实门位，通行规则也不是校园交通事实。** 原图只确定建筑相对位置，门位与连接道属于显式仿真假设。蓝色停靠标记、金色连接道和深色候选门框正式包含在校园 blend/FBX/GLB 中；入口、交付点及停车位置参考 Empty 一同导出。小车本体保持原尺寸与起始位姿。

南区、东北和东南区道路已按原图通道重新描绘；两处错误楼体改为广场并补入可见小结构，实训院落增加侧翼，支流水体改用可见蓝色边界。人工源数据修正记录在 `source_geometry_changes.json`（包括前后坐标与距离），自动调整仍限制在最多 3 px。`source_retrace_overlay.png` 显示人工修改前后；`road_correction_overlay.png` 只显示当前源数据的自动微调。`v03_baseline.json` 保存上一版对照。

```bash
# 从仓库根目录执行完整验收
python3 tools/campus_builder/run_pipeline.py --verify-idempotency

# 单次构建（不满足 clean × 2 的最终验收要求）
python3 tools/campus_builder/run_pipeline.py

# 关键规则回归测试
python3 -m unittest discover -s tools/campus_builder/tests -v
```

入口按自身文件位置解析路径；可用 `--blender /absolute/path/to/blender` 指定 Blender。退出码：0 = 全部阶段 PASS；2 = 资产已生成，但证据/源几何/导航或双次验收尚未通过，报告为 PARTIAL；其他非零值 = 执行或产物验证失败。每次运行覆盖工具所属的 `data/` 与 `output/` 生成物，保留 input、config、日志和双次构建记录。不要把人工资料放进生成目录。

需要 Blender FBX/glTF/Cycles，宿主 Python 的 Pillow 和 Shapely 2.1+。当前主机已具备。另一台主机缺依赖时使用项目虚拟环境：

```bash
python3 -m venv tools/campus_builder/.venv
tools/campus_builder/.venv/bin/python -m pip install -r tools/campus_builder/requirements.txt
tools/campus_builder/.venv/bin/python tools/campus_builder/run_pipeline.py --verify-idempotency
```

## 数据来源与当前证据限制

`input/campus_1.jpg` 是未修改的 900 × 1037 主图；`campus_2.jpg` 仅供建筑名称核对，不混用旋转后的像素坐标。原始图片仍在仓库 picture 目录。学校官网的同布局图片及页面保存在 `input/evidence/`，来源、日期和哈希见 `source_manifest.json`。

全仓库没有找到可用于测量的比例尺、CAD/GIS、控制点或实测长度。网上取得的学校规划图也没有比例尺；OSM/Overpass 原始数据访问超时或 HTTP 406，没有使用未取得的坐标。已保存 World Athletics 和 FIFA 的规范来源摘要、URL、获取日期与适用性说明。

当前四个长度锚点采用运动场外轮廓和足球场边界，分别参考标准八道跑道 176.91 × 92.52 m、FIFA 推荐场地 105 × 68 m。它们全部属于 `standard-dimension assumption`，校园设施是否符合这些尺寸尚未确认。四条线共享一个体育区域、两份规范文档，不是四次独立实测。

条件拟合结果约 1.268715272 m/px，LOW confidence。低残差只能说明这些假设彼此吻合，不能证明真实校园尺度准确。因此当前 SCALE 为 PARTIAL / INSUFFICIENT SCALE EVIDENCE。禁止把生成模型的尺寸当成实测结果。

## 可维护配置与坐标

- `config/source_geometry.json`（schema 2）是建筑边界、道路描线、水体、桥梁掩膜等几何来源。发现错位应改此文件，然后重建；不要人工编辑生成的 campus_map。
- `config/scale_anchors.json` 保存全部人工选取端点、长度、来源、类型、置信度、权重、相关组和证据文件。实测数值只应加入此文件，不在 Python 内硬编码。
- `config/campus_config.json` 保存建筑高度及各层高程/厚度，单位始终为 modeled metres。已删除 height_reference_meters_per_pixel；XY 改变不会缩放建筑高度或 0.3 m Ground 厚度。建筑的逐栋高度、立面和屋顶参数由 `config/building_profiles.json` 管理；12 m / 4.5 m 仅作为后备默认值。
- `config/v01_baseline.json` 与 `input/evidence/v01_source_geometry.json` 仅用于审计旧版尺度、复杂度和描线，没有把旧版大幅自动绕行当成新事实。

像素坐标经 `data/scale_calibration.json` 的完整 3 × 3 矩阵转换为 local metric XY，原点接近 Ground 中心。默认 X 向图右、Y 向图上，图片 Y 翻转；Z 向上。Blender Metric，1 BU = 1 modeled metre。建筑高度来源继续明确标记 `modeling default, not measured`。

## 独立尺度校准

`scripts/calibrate_scale.py` 检查端点、来源与证据哈希，计算每条候选比例；median/MAD 检测离群点，Huber IRLS 加权拟合统一比例。相关组按锚点数量归一，保留 high/medium/low 置信度权重。所有锚点的残差仍报告，高置信度冲突不能因降权而隐藏。

优先使用 uniform scale。只有独立方向证据充分、残差改善至少 3 个百分点、X/Y 比例差至少 5% 才允许 anisotropic scale。三个以上非共线、有实际来源的 metric controls 可评估 similarity transform；当前没有此类控制点，未采用 affine 或 homography。长度锚点仍需配置，可把控制点之间的实测距离作为长度锚点录入。

尺度验收单独检查证据与残差：至少三个长度锚点；加权相对 RMSE ≤ 5% 为 GOOD，5–10% 为 WARNING；至少 80% 锚点误差 ≤ 8%；可靠锚点最大误差 ≤ 10%；高置信度冲突禁止 PASS。还必须至少有一个实际校园测量/GIS 来源。只有标准设施假设始终为 LOW、证据不通过。HIGH 还需要独立实际来源与独立空间区域。

`scale_debug_overlay.png` 在原图上绘制 50 m 网格、端点和每条锚点的参考/预测/误差。网格仍随条件拟合变化，不能代替尺度证据。

## 道路与桥梁

每条路线保留 road_type、driveable、bidirectional；不能确定的权限/方向为 null，类型为 unknown。桥面范围内赋予 bridge 表面分类；表面分类不会把未知车辆权限提升为 true，桥头道路也不继承通行权限。

自动描线修正上限为 `min(max_auto_road_adjustment_px, 0.5 × width_px)`，默认最大 3 px。仅搜索小幅坐标修正，并固定原始路线共享顶点；用双向 Hausdorff 距离核对上限。需要更大绕行时保留原路线并输出 FLAG_RETRACE_REQUIRED。`road_correction_overlay.png` 中红色为原描线、紫色为接受的小修正、黄色为仍冲突段。

为了能检查其他资产，PARTIAL 构建会输出道路审阅 Mesh：裁去建筑及非桥梁水体的重叠区域。这会产生缺口，报告记录裁剪面积；不把裁剪声称为描线修复，也不允许据此让 ROADS 或 NAVIGATION 通过。最终可用于小车仿真的道路网络必须先修正 source_geometry 中报告列出的 ROUTE。

`Campus/Bridges` 下独立 `BRIDGE_*`，与道路顶面同高、位于水面上方；custom properties 为 surface_type=bridge、driveable=true、collidable=true。桥梁掩膜与道路相交处生成桥面，包含原图桥梁符号造成的水体断口，避免遗漏北侧桥梁。

## 导航基础文件

`data/navigation_graph.json` 的节点位于路线端点、实际交叉口和桥面边界；曲率描绘点保留为 edge 的 polyline_m。边记录米制长度、宽度、route_id、类型、权限及方向。生成时检查有限坐标、重复节点、长度一致、路面覆盖、建筑/水体穿越、桥面对应及共享路口；对通过验证的 driveable 连通分量执行固定随机种子的 Dijkstra 连通检查。

未知权限不提升为允许车辆行驶，未知方向不默认为双向。所有边（包括 unknown）都检查整条几何是否落在路面内；重叠来源的禁止权限优先。Dijkstra 使用 `allowed_directions` 的有向弧；连通分量统计则是无向结构连通性，两者分别报告。几何/拓扑通过不代表车辆权限已确认。当前两个显式桥梁来源没有确认方向，校园 Dijkstra 配对为零并明确记录；回归夹具验证双向、单行与禁止覆盖等规则。

## Blender、FBX 与自动验证

1. 校准 → 地图生成 → 导航数据/平面检查 → Blender factory-startup 构建。
2. 0.001 m 坐标精度与约 0.002 m 简化；约 0.003 m 向内清理处理点接触轮廓，避免侵入相邻桥面。受约束三角剖分保持凹边界和孔洞并核对面积。
3. 独立封闭建筑和地表实体，检查 manifold、法线、零面积面、正有向体积、finite 顶点、变换与 bbox。
4. 对实际 Ground Mesh 四角和校准端点进行绝对米制检查；建筑 Z 与配置直接比较。另建 ValidationOnly_ScaleReferences 下的 1/10/50 m Mesh，保留在 blend 供检查，明确排除在 FBX/GLB 之外。
5. 保存 campus.blend；导出正式 Mesh 和小车根节点/轮轴/安装参考 Empty，FBX -Z forward / Y up，记录单位设置，材质为 Principled BSDF；附加 GLB。验证相机、灯光与尺度尺排除在交换资产之外。
6. 全新空 Blender Scene 导入 FBX，保留原有 bbox、双向顶点偏差、方向和尺寸比例检查，并再次检查绝对米制锚点、建筑高度、桥梁属性及无 debug 对象泄漏。
7. bbox 自动取景，CPU Cycles 生成 top、两个 perspective 和 reimported_fbx；检查相机范围、1200 × 1200 分辨率、图像均值/方差/非背景比例以及同视角 FBX 色彩差。
8. 完整 clean rebuild 再执行一轮；比较校准、地图、导航、道路数据哈希和所有源 Mesh 验证摘要。序列化文件可含不同元数据，不以 blend/FBX 二进制相同为幂等标准。

报告分别列 GEOMETRY、SCALE、ROADS、NAVIGATION、FBX、RENDER、BUILDINGS、IDEMPOTENCY。BUILDINGS 表示建筑参数、贴图、UV 与导出一致性通过，不表示实测复刻。全部通过才 RESULT: PASS。即使 Mesh/FBX/渲染成功，尺度证据不足或道路冲突仍 RESULT: PARTIAL。

## 主要产物

```text
data/scale_calibration.json
data/campus_map.json
data/navigation_graph.json
data/road_validation.json
data/map_metadata.json
output/campus.blend
output/campus.fbx
output/campus.glb
output/previews/map_debug_overlay.png
output/previews/scale_debug_overlay.png
output/previews/road_correction_overlay.png
output/previews/top.png
output/previews/perspective_01.png
output/previews/perspective_02.png
output/previews/reimported_fbx.png
output/validation/scale_calibration_report.md
output/validation/validation_report.md
output/validation/validation_report.json
output/validation/navigation_validation.json
output/validation/source_scene.json
output/validation/reimport_scene.json
output/validation/blender_validation.json
output/validation/reimported_fbx.blend
output/idempotency_runs.json
output/logs/run_01.log
output/logs/run_02.log
```

在本机 Blender 的 File → Open 中打开本仓库下 `tools/campus_builder/output/campus.blend`。完整绝对路径见最终报告。道路中心线数量与最终道路 Mesh 数量分别报告。

## 最小额外信息与后续阶段

尺度最小补充：提供主图像素 [210,552] 到 [210,692]（田径场外轮廓北端到南端）的真实直线长度，单位米，并说明测量来源。它可替换 TRACK_OUTER_LONG 假设、检验现有比例。要提升 HIGH confidence，还需要体育区域之外、端点明确的一条独立长基线及可信来源；不能保证任意一个新数值都会与其他锚点相符。

若后续出现道路冲突，应根据地图修正报告列出的 ROUTE 描线或对应障碍边界，不能恢复 V0.1 的 46.6 px 自动绕行。

Unity/团结阶段需实际验证导入、配置 Collider/图层/水体排除和允许车辆行驶的路面。Ground 延伸在水体下方，不可把全 Ground 当道路；路顶面高于 Ground 4.5 cm，碰撞连接需考虑小台阶。本轮未开发服务器路径规划、NavMesh、小车运动、TCP、DWA/APF 或精细室内资产。

## V0.3 建筑资料与编辑方式

本轮按公开基本资料和用户接受的近似精度重建，**并非逐楼实测复刻**。来源网页、参考照片及 URL/日期/SHA256 清单保存在 `input/evidence/buildings/`。图书馆官方房间记录、行政楼官方办公室记录只提供楼层下限；照片提供外观参考；典型层高、未确认楼层、窗距和屋顶起伏都属于建模假设。2023 年新楼资料无法可靠匹配旧规划图的全部轮廓，没有直接套用到不确定楼号。

- 行政楼按 13 层、3.4 m 近似层高建模，约 44.2 m；13 层来自官方房间编号下限，44.2 m 不是测量值。
- 3–5 号教学楼按 5 层、约 18 m；6–8 号采用较低体量和坡顶。
- 图书馆约 16 m，体育馆约 13.8 m（含约 3 m 弧形屋顶起伏），展厅约 15.2 m。
- 普通宿舍暂按 6 层、约 18.6 m；11 号“小高层”暂按 9 层、约 27.9 m。楼层数均明确标注为类型估计。
- 实验/训练用房、食堂、服务用房分别使用较低的体量与不同的窗格/颜色。

`building_profiles.json` 的 `profiles` 按地图楼号选择样式；`features` 用稳定的原始 BLDG ID 保存特殊翼楼覆盖。生成时保留 `source_trace_ids`，避免合并轮廓后重新编号导致高度应用到另一栋楼。可修改 `floor_count`、`floor_height_m`、`roof_shape`、`roof_rise_m`、颜色和窗距；同时更新事实/假设的 provenance。

立面为小尺寸自行绘制的重复贴图，并未直接投影有透视和遮挡的校园照片。贴图打包进 `.blend`、内嵌在 FBX、包含在 GLB。FBX 独立重新导入时检查贴图实际加载、UV 有限、建筑高度/屋顶/来源属性保留。所有屋顶仍是封闭实体，继续经过 manifold、法线和顶点往返检查。

新增文件：

```text
config/building_profiles.json
config/source_geometry_changes.json
data/building_reconstruction.json
output/textures/facade_*.png
output/previews/building_administration.png
output/previews/building_teaching.png
output/previews/building_gym.png
output/previews/building_library.png
output/validation/building_reconstruction_report.md
```

源道路的人工修正逐项记录在 `source_geometry_changes.json`，包括修改前后坐标及原因。它们和运行时最多 3 px 的自动修正严格区分；仍冲突的道路继续 FLAG，不能直接作为已验证的车辆导航网络。

本机打开项目：

```text
/home/michael/workspace/unity/tools/campus_builder/output/campus.blend
```

文件保存了全景视角并默认使用材质预览。想检查某栋楼，在 Buildings collection 选中对象，按小键盘 `.` 聚焦；对象自定义属性中能看到地图楼号、近似层数、屋顶类型和高度依据。需要轻量浏览时可切换 Solid shading；贴图效果在 Material Preview 或 Rendered shading 下查看。

## 配送小车资产

V1.1 送餐造型在原有米制车体上增加两侧餐食图形、保温货箱顶盖识别带与后面板橙色标识。视觉部件仍保持在长 1.20 m、宽 0.80 m、高 1.10 m 的包络内，不改变根节点、四个轮轴、轮胎接地平面或校园道路放置点。团结导入与实际 TCP 订单联调记录见仓库根目录的 `TuanjieProject/README.md`。

完整入口现在同时生成一辆参数化四轮配送小车，并把它放在校园中的有效道路段。设计尺寸为 **长 1.20 m × 宽 0.80 m × 高 1.10 m**，轮半径 0.16 m、前后轴距 0.76 m、底盘离地 0.15 m；它是本项目自定义设计，并非某款实车的测量复刻。尺寸在 `config/delivery_robot.json` 中独立保存，校园 XY 比例改变不会缩放小车。

放置点在 `ROUTE_012` 的 32% 弧长位置，朝向沿路线切向。生成器要求源路线通过几何检查，整个矩形占地加 0.30 m 安全余量必须落在路面内，并避开建筑和水体。`data/delivery_robot.json` 保存实际位姿、道路宽度、边界余量、关联 graph edge、轮胎规格和碰撞体尺寸提示。道路车辆通行权限仍保持原数据的 unknown；几何放置检查不会替它做交通许可判断。

校园文件 `campus.blend / campus.fbx / campus.glb` 包含一个已摆放的小车实例，独立的 `delivery_robot.blend / delivery_robot.fbx / delivery_robot.glb` 包含同一辆放在原点的小车。若后续在引擎中使用独立小车资产，应移除或禁用校园文件中原有的 `DeliveryRobot_ROOT`，避免重复实例。所有文件都由同一个命令重新生成。

```text
DeliveryRobot_ROOT           根节点在占地中心、轮胎接地平面
  ROBOT_Chassis              底盘
  ROBOT_CargoBody            货箱
  ROBOT_Lid / Door_*         顶盖与侧舱门视觉部件
  ROBOT_*                   灯、保险杠、显示面板、雷达外壳等
  WheelPivot_FL / FR         前左 / 前右轮轴心
    ROBOT_Tire_* / Hub_*
  WheelPivot_RL / RR         后左 / 后右轮轴心
    ROBOT_Tire_* / Hub_*
  BaseLink                  位姿参考点
  ForwardAxis               朝向参考点
  LidarMount / CameraMount   传感器安装参考点
```

局部坐标为 **+X 向右、-Y 向前、+Z 向上**；轮轴沿局部 X，旋转各 `WheelPivot_*` 即可驱动视觉轮胎转动。FBX 使用 -Z forward / Y up，保留 Empty 父子节点、轴心和 custom properties；不烘焙父子层级的空间变换。实际 Unity/团结引擎中的轴向和组件仍须在导入阶段核对。

小车全部正式 Mesh 继续经过封闭性、法线、退化面和双向顶点偏差检查。新增验证分别检查地图实例与原点资产的宽长高、根节点位置、前进方向、四个车轮的轴心/旋转轴、轮胎接地、独立 `.blend` 可重开，并比较 FBX 前后近景图。两次干净构建还比较小车规格及验证报告哈希。

额外产物：

```text
config/delivery_robot.json
data/delivery_robot.json
output/delivery_robot.blend
output/delivery_robot.fbx
output/delivery_robot.glb
output/previews/delivery_robot_closeup.png
output/previews/delivery_robot_on_campus.png
output/previews/delivery_robot_reimported.png
output/previews/delivery_robot_asset.png
output/validation/delivery_robot_validation.json
output/validation/delivery_robot_report.md
```

打开 `output/delivery_robot.blend` 可单独检查小车；在校园中可通过 Outliner 找到 `DeliveryRobot` collection，选择其中全部对象后按小键盘 `.` 聚焦。根节点作为整体移动入口，不要分别移动轮胎 Mesh。

本阶段完成视觉/几何资产、放置和导航数据关联。尚未配置 Rigidbody、Collider 组件、质量/惯量、轮胎动力学、运动控制、传感器或实际导航执行；`collision_hint` 只是下一阶段使用的数据。校园 SCALE/ROADS/NAVIGATION 阶段继续单独报告，ROBOT PASS 不代表全校园车辆导航已通过。

V0.4 增加 `building_exhibition.png`、`roads_south.png`、`roads_northeast.png` 和人工源数据对照图 `source_retrace_overlay.png`。V0.5 增加四张配送点近景，共生成 19 张 Blender 验证渲染。实际验收结果以最新 `validation_report.md` 为准，尺度证据不足仍为 PARTIAL。

## V0.5 配送点与仿真路网

`config/delivery_sites.json` 是人工维护的候选入口数据：稳定原始楼体 ID、像素门位、向外法线、连接道路、地图 SHA256、来源和低置信度。原始楼体 ID 经 source_trace_ids 映射到当前建筑，避免对象重新编号造成错配。生成器验证候选点位于对应立面、法线朝外、步行道不穿建筑/水体、停车与旋转包络完全落在道路中。不会自动迁移一个错误入口以让检查通过。

`config/simulation_access.json` 明确列出八条用于演示的路线并假定双向通行。它只用于新生成的 `data/simulation_navigation_graph.json`，不会修改 `source_geometry.json` 或基础 `navigation_graph.json` 中的真实/未知权限；基础数据中的显式禁止优先。所有仿真边都标记 real_world_access_confirmed=false。

固定米制尺寸：步行连接道宽1.80m，门前交付点距立面1.10m，候选门框宽1.60m/高2.30m，交付区域宽1.40m/长1.80m。蓝色标记厚2mm、无碰撞语义，位于原0.045m路面顶上；金色连接道与道路顶面同高。入口框是非碰撞的候选位置提示，不会假装已在真实楼体上建成门洞。

车辆净空采用 `sqrt(1.20²+0.80²)/2 + 0.30 = 1.021110m` 的旋转包络半径。对整条折线使用圆端/圆角 buffer，并检查路面覆盖与障碍交集，避免只检查若干顶点漏掉中间障碍。它覆盖车身及余量，**不证明实际轮式转向、转弯半径或动力学可行**。车辆路径在道路侧交付区域结束，门前连接道标记为 pedestrian_access、driveable=false。

仿真图仅在真实交点、起始小车位置、道路投影站点和停靠点增加节点；曲率点继续保留在 polyline_m 中。执行从实际小车起点到四个停靠点的 Dijkstra 检查，保存完整节点、边与折线。长度随条件XY尺度变化；车体、步行宽度、停车尺寸和门前退让均独立使用建模米数。

新增输出：

```text
data/delivery_sites.json
data/simulation_navigation_graph.json
output/previews/delivery_sites_overlay.png
output/previews/delivery_site_LIBRARY.png
output/previews/delivery_site_TEACHING_3.png
output/previews/delivery_site_CANTEEN_20.png
output/previews/delivery_site_DORM_11.png
output/validation/delivery_sites_validation.json
output/validation/delivery_scene_validation.json
output/validation/delivery_access_report.md
```

Blender 新增 `Campus/AccessPaths`、`Campus/DeliverySites`。`ENTRY_*` 是候选立面点，`HANDOFF_*` 是门前交付点，`STOP_*` 是车身中心停靠点；位置和自定义属性在新场景FBX导入后再次检查，停车区域绝对尺寸同样重新测量。独立小车资产不包含这些校园对象。

统一入口依次生成基础图、小车、配送点与仿真图，再建模/验证/导出/渲染。两轮干净构建比较新增JSON哈希；报告新增 `DELIVERY` 阶段，代表候选几何和已声明的仿真假设验证通过。原来的 `SCALE`、道路、FBX、建筑、小车、渲染与幂等性检查继续保留。

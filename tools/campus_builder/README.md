# Campus Model V0.2 — Metric Calibration + Simulation Geometry

在 V0.1 的 CLI 建模、Mesh 验证、FBX 干净往返、渲染和双次重建基础上增加尺度校准、固定米制 Z、受限道路修正、独立桥面和基础导航图。没有使用 Unity/团结引擎，也没有修改 C++ 服务端。

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
- `config/campus_config.json` 保存建筑高度及各层高程/厚度，单位始终为 modeled metres。已删除 height_reference_meters_per_pixel；XY 改变不会缩放 12 m / 4.5 m 建筑高度或 0.3 m Ground 厚度。
- `config/v01_baseline.json` 与 `input/evidence/v01_source_geometry.json` 仅用于审计旧版尺度、复杂度和描线，没有把旧版大幅自动绕行当成新事实。

像素坐标经 `data/scale_calibration.json` 的完整 3 × 3 矩阵转换为 local metric XY，原点接近 Ground 中心。默认 X 向图右、Y 向图上，图片 Y 翻转；Z 向上。Blender Metric，1 BU = 1 modeled metre。建筑高度来源继续明确标记 `modeling default, not measured`。

## 独立尺度校准

`scripts/calibrate_scale.py` 检查端点、来源与证据哈希，计算每条候选比例；median/MAD 检测离群点，Huber IRLS 加权拟合统一比例。相关组按锚点数量归一，保留 high/medium/low 置信度权重。所有锚点的残差仍报告，高置信度冲突不能因降权而隐藏。

优先使用 uniform scale。只有独立方向证据充分、残差改善至少 3 个百分点、X/Y 比例差至少 5% 才允许 anisotropic scale。三个以上非共线、有实际来源的 metric controls 可评估 similarity transform；当前没有此类控制点，未采用 affine 或 homography。长度锚点仍需配置，可把控制点之间的实测距离作为长度锚点录入。

尺度验收单独检查证据与残差：至少三个长度锚点；加权相对 RMSE ≤ 5% 为 GOOD，5–10% 为 WARNING；至少 80% 锚点误差 ≤ 8%；可靠锚点最大误差 ≤ 10%；高置信度冲突禁止 PASS。还必须至少有一个实际校园测量/GIS 来源。只有标准设施假设始终为 LOW、证据不通过。HIGH 还需要独立实际来源与独立空间区域。

`scale_debug_overlay.png` 在原图上绘制 50 m 网格、端点和每条锚点的参考/预测/误差。网格仍随条件拟合变化，不能代替尺度证据。

## 道路与桥梁

每条路线保留 road_type、driveable、bidirectional；不能确定的权限/方向为 null，类型为 unknown。桥面范围内显式赋予 bridge 语义；桥头道路不继承已确认通行权限。

自动描线修正上限为 `min(max_auto_road_adjustment_px, 0.5 × width_px)`，默认最大 3 px。仅搜索小幅坐标修正，并固定原始路线共享顶点；用双向 Hausdorff 距离核对上限。需要更大绕行时保留原路线并输出 FLAG_RETRACE_REQUIRED。`road_correction_overlay.png` 中红色为原描线、紫色为接受的小修正、黄色为仍冲突段。

为了能检查其他资产，PARTIAL 构建会输出道路审阅 Mesh：裁去建筑及非桥梁水体的重叠区域。这会产生缺口，报告记录裁剪面积；不把裁剪声称为描线修复，也不允许据此让 ROADS 或 NAVIGATION 通过。最终可用于小车仿真的道路网络必须先修正 source_geometry 中报告列出的 ROUTE。

`Campus/Bridges` 下独立 `BRIDGE_*`，与道路顶面同高、位于水面上方；custom properties 为 surface_type=bridge、driveable=true、collidable=true。桥梁掩膜只在实际道路与水体相交处生成桥面。

## 导航基础文件

`data/navigation_graph.json` 的节点位于路线端点、实际交叉口和桥面边界；曲率描绘点保留为 edge 的 polyline_m。边记录米制长度、宽度、route_id、类型、权限及方向。生成时检查有限坐标、重复节点、长度一致、路面覆盖、建筑/水体穿越、桥面对应及共享路口；对通过验证的 driveable 连通分量执行固定随机种子的 Dijkstra 连通检查。

未知权限不提升为允许车辆行驶。当前文件包含未通过的源描线，边带 validation_pass/source_trace_valid，整体验证失败时不得直接接入小车导航。连通分量统计包含全部描线；Dijkstra 的无向结构连通检查不是交通合法性判断。

## Blender、FBX 与自动验证

1. 校准 → 地图生成 → 导航数据/平面检查 → Blender factory-startup 构建。
2. 0.001 m 坐标精度与约 0.002 m 简化；约 0.003 m 向内清理处理点接触轮廓，避免侵入相邻桥面。受约束三角剖分保持凹边界和孔洞并核对面积。
3. 独立封闭建筑和地表实体，检查 manifold、法线、零面积面、正有向体积、finite 顶点、变换与 bbox。
4. 对实际 Ground Mesh 四角和校准端点进行绝对米制检查；建筑 Z 与配置直接比较。另建 ValidationOnly_ScaleReferences 下的 1/10/50 m Mesh，保留在 blend 供检查，明确排除在 FBX/GLB 之外。
5. 保存 campus.blend；仅导出正式 Mesh，FBX -Z forward / Y up，记录单位设置，材质为 Principled BSDF；附加 GLB。
6. 全新空 Blender Scene 导入 FBX，保留原有 bbox、双向顶点偏差、方向和尺寸比例检查，并再次检查绝对米制锚点、建筑高度、桥梁属性及无 debug 对象泄漏。
7. bbox 自动取景，CPU Cycles 生成 top、两个 perspective 和 reimported_fbx；检查相机范围、1200 × 1200 分辨率、图像均值/方差/非背景比例以及同视角 FBX 色彩差。
8. 完整 clean rebuild 再执行一轮；比较校准、地图、导航、道路数据哈希和所有源 Mesh 验证摘要。序列化文件可含不同元数据，不以 blend/FBX 二进制相同为幂等标准。

报告分别列 GEOMETRY、SCALE、ROADS、NAVIGATION、FBX、RENDER、IDEMPOTENCY。全部通过才 RESULT: PASS。即使 Mesh/FBX/渲染成功，尺度证据不足或道路冲突仍 RESULT: PARTIAL。

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

道路冲突需根据地图修正报告列出的 ROUTE 描线或对应障碍边界，不能恢复 V0.1 的 46.6 px 自动绕行。

Unity/团结阶段需实际验证导入、配置 Collider/图层/水体排除和允许车辆行驶的路面。Ground 延伸在水体下方，不可把全 Ground 当道路；路顶面高于 Ground 4.5 cm，碰撞连接需考虑小台阶。本轮未开发服务器路径规划、NavMesh、小车运动、TCP、DWA/APF 或精细室内资产。

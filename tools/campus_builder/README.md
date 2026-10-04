# Campus Builder

从上海第二工业大学金海路校区二维规划图生成可导入 Unity/团结引擎的基础环境资产。整个流程在 CLI 中执行，不需要 Editor、手动 Blender 操作或修改 C++ 服务端。

```bash
# 在仓库根目录执行；本次交付的完整验收命令
python3 tools/campus_builder/run_pipeline.py --verify-idempotency

# 单次重新生成：仍执行全部建模、导出、干净 FBX 导入和四张渲染检查
python3 tools/campus_builder/run_pipeline.py
```

可用 `--blender /absolute/path/to/blender` 指定 Blender。入口按自身文件位置解析路径，从其他工作目录执行也可。

需要 Blender 的 FBX、glTF、Cycles 功能，以及宿主 Python 的 Pillow 和 Shapely 2.1+。当前主机已有依赖，无需安装。另一台主机如果缺少库，可使用本目录虚拟环境：

```bash
python3 -m venv tools/campus_builder/.venv
tools/campus_builder/.venv/bin/python -m pip install -r tools/campus_builder/requirements.txt
tools/campus_builder/.venv/bin/python tools/campus_builder/run_pipeline.py --verify-idempotency
```

## 输入与假设

- `input/campus_1.jpg`：来自原始 `picture/campus_1.jpg` 的未修改副本，900 × 1037，作为空间布局主图。
- `input/campus_2.jpg`：来自 `picture/campus_2.jpg` 的未修改副本，同一校区的名称说明参考。它的旋转、排版与主图不同，不能直接混用像素坐标。
- `config/source_geometry.json`：人工视觉描绘的建筑多边形、道路中心线、河道、桥梁掩膜、绿地区域、广场、运动设施。每个建筑保留地图编号、名称、来源和精度说明。重叠的同编号翼楼会合并，互不连接的翼楼保留独立对象。
- 地图属于带文字、树木图标和阴影的彩色规划图；不用颜色识别去假装恢复测绘边界。地图也不保证反映目前实际校园。
- **没有可靠比例尺。0.75 m/px 是 provisional scale，绝非已测量真实尺度。建筑高度 12 m / 低矮建筑 4.5 m 是建模默认值。**

`config/campus_config.json` 中 `meters_per_pixel` 是整体尺度唯一入口。调整后重新执行流水线即可。建筑高度和环境层高按照该值相对于 `height_reference_meters_per_pixel` 的比例统一缩放，避免只放大地面而高度不变。暂定宽度约 3.75–7.5 m，道路与建筑边界仍属于视觉近似值。

地图坐标只存在于描绘配置。`data/campus_map.json` 已转换为以米为单位、校园 Ground 中心为原点的独立中间结构：X 向图片右侧，Y 向图片上侧，Z 向上；图片 Y 向下在分析阶段翻转。北箭头对应 +Y。Blender Metric，1 BU = 1 modeled metre。

## 生成流程与验证

1. `scripts/analyze_map.py` 校验图片尺寸，合并同编号相接翼楼，局部修正道路完整宽度走廊，合并交叉口。建筑缓冲区和非桥梁水体不允许道路通过。绿地减去建筑、道路、水体与地标。道路的原始描绘及修正后的数据均可审计。
2. `scripts/road_geometry.py` 使用受限局部网格搜索处理描绘中心线撞到建筑的问题；这是离线几何生成工具，与项目服务端/小车规划算法无关。它不会任意为河道创建桥梁。叠加图展示最终道路与建筑边界，须将视觉近似与实测地图区分。
3. Shapely constrained triangulation 保留凹边界和孔洞，核对面积覆盖率，输出可直接创建 Mesh 的顶点、三角面与边界环。坐标使用 0.001 m 网格与 0.002 m 边界简化，避免 GEOS 双精度结果转换到 Blender 单精度顶点后出现退化面；单点接触边界用 0.02 m 的微小扩张闭合。建筑和道路边界本身的精度属于米级视觉近似。
4. `scripts/build_campus.py` 从全新场景构建封闭实体。建筑独立命名 `BLDG_*`；道路按连接面命名 `ROAD_*`。`Campus` 下包含 Ground、Roads、Buildings、Vegetation、Water、Walls、Landmarks、Plazas。没有确认的实体围墙不会凭空补造；Walls 可以为空。
5. `scripts/validate_scene.py` 校验 Ground、Building、Road、顶点/面、NaN/Inf、范围、尺度、建筑高度、道路高程、法线、零面积面及 non-manifold，并用正的有向体积检查封闭实体法线朝外。源场景要求已应用变换且没有残留 Modifier。
6. 保存 `output/campus.blend`，仅导出 Mesh 到 `output/campus.fbx`（-Z forward / Y up）和 `output/campus.glb`。材质均使用简单 Principled BSDF。相机与验证灯光不属于导出资产。
7. 源场景自动渲染 top 和两张方向不同的 perspective；然后重置到空场景，独立重新导入 FBX，复核对象、材质槽、每对象边界、世界顶点集合及尺寸比例。验证用导入场景另存于 `output/validation/reimported_fbx.blend`，并单独生成 `reimported_fbx.png`。
8. `scripts/render_validation.py` 将所有包围盒角点投影到相机基坐标，根据宽高比计算正交相机范围。CPU Cycles 提供无需 GPU 的可重复渲染。每张图片同时检查相机边界、文件大小、分辨率、均值、方差、非背景像素比例；原始与导入后同视角图片还检查平均颜色差。俯视相机额外检查 +X 向右、+Y 向上，保持与主图一致；二维数据额外排查同高程表面的面积重叠，防止局部水池等出现共面黑斑。
9. 完整验收命令清理工具所属生成物并再完整执行一轮。每轮都独立验证 FBX 和渲染；比较中间数据 SHA256 和所有 Mesh 验证摘要。`.blend`/FBX 文件可能包含不同序列化元数据，不以二进制完全一致作为几何幂等性标准。

入口只清理本工具 `data/` 和 `output/` 的生成物；保留 `input/`、`config/`、运行日志与两轮证据。不要在生成目录里存放人工文件。单次运行报告明确标记没有执行两轮验收，完整 `--verify-idempotency` 才输出最终 PASS。

## 产物

```text
data/campus_map.json                 米制中间结构与可直接建模的多边形/三角形
data/map_metadata.json               输入摘要、假设、尺度与二维几何检查
output/campus.blend                  纯校园资产场景
output/campus.fbx                    主交换格式
output/campus.glb                    辅助交换格式
output/previews/map_debug_overlay.png
output/previews/top.png
output/previews/perspective_01.png
output/previews/perspective_02.png
output/previews/reimported_fbx.png
output/validation/validation_report.json
output/validation/validation_report.md
output/validation/source_scene.json
output/validation/reimport_scene.json
output/validation/reimported_fbx.blend
output/idempotency_runs.json         两轮独立运行证据
output/logs/run_01.log               Blender 日志
output/logs/run_02.log
```

道路数量有两个含义：描绘的中心线路段数量与最终合并后连通道路 Mesh 数量。报告同时给出，不能把一个相连道路网络误读为只有一条路。

## 后续引擎接入

本次实际验证 Blender FBX 往返导入；没有 Unity/团结环境，不能宣称已在游戏引擎运行。引擎阶段需要给静态建筑、地面和道路配置 Collider 与图层，排除水体/草地等非行驶区域，再定义车辆允许行驶的表面。道路顶面在当前尺度下高于 Ground 4.5 cm，碰撞表面连接策略需考虑该小台阶。水体目前是低平面可视对象，Ground 仍延伸在其下方，不能将整个 Ground 默认判作道路。

本轮不生成 NavMesh、小车代码、Raycast、服务器航点或局部规划逻辑。建筑孔洞保留在几何中，但没有建造室内、门窗和屋顶细节；可见立面只是低多边形体块。

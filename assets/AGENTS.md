# AGENTS.md — assets/ 建模规范（Blender → GLB → Godot）

本目录下所有资产都由同目录的 Python 脚本在 Blender 里**程序化生成**，再导出 `.glb` 给 Godot 4 使用。
脚本是唯一事实来源：`.blend` / `.glb` / `*_preview.png` 都是产物，**改模型请改脚本再重新生成，不要手改产物**。

本文件的核心目的只有一个：**让所有模型保持统一的真实尺度（米）**，这样在 Godot 里摆放时不需要为每个资产单独调 `scale`。

---

## 1. 硬性尺寸约定（所有新建模必须遵守）

| 约定 | 值 | 说明 |
| --- | --- | --- |
| 单位制 | **公制** | `scene.unit_settings.system = 'METRIC'` |
| 单位比例 | **1 Blender unit = 1 米** | 不要用 `unit_settings.scale_length` 去缩放，直接按米建模 |
| 世界朝向（Blender） | **+Z 向上** | 与 Blender 默认一致 |
| 导出朝向（Godot） | **+Y 向上**（`export_yup=True`） | glTF 自动做 Z-up → Y-up；Godot 中"树往上长"= `+Y` |
| 地面基准 | **根部 / 地面 = z = 0** | 树干底、草根、假茎底必须正好落在 z=0，不许悬空或埋地 |
| 物体缩放 | **全部 apply 为 1** | 导出前 `transform_apply(scale=True, rotation=True)`，禁止用物体 scale 假装尺寸 |
| 原点 | **放在"摆放锚点"上** | 见 §4，Godot 里 `position` 直接等于落地点 |
| 网格尺寸容差 | ±2% | 与下表基准值的偏差不超过 2%，改款必须同步更新表格 |

> ⚠️ 最关键的一条：**不要让 Godot 侧的 `scale` 来救尺寸**。所有资产都必须是 1:1 米制，
> 组件脚本（如 `components/vegetation/banana_tree/banana_tree.gd`）是按真实米数做几何计算的。

---

## 1.1 关于"用约束统一大小"：能做，但不是本项目的机制

社区建议里常见的做法是加 **复制缩放（Copy Scale）** 约束，让所有模型跟随一个"标准参考物"的缩放。
本仓库实测（Blender 5.2）后确认：**这条链路能工作，但会把缩放烘焙成导出节点的 scale，和 §1 的"scale 恒为 1"冲突**，
所以本项目**不把它当作尺寸统一手段**，只保留它作为建模期的临时对齐辅助。

### 实测结论（可复现）

在 Blender 5.2 + glTF 导出（`export_apply=True, export_yup=True`）下：

| 观察 | 结果 | 含义 |
| --- | --- | --- |
| 约束是否影响 `ob.scale` | **不影响**，`ob.scale` 仍是 `(1,1,1)`，只有 `matrix_world` 变了 | 约束是求值期效果，不改属性 |
| 导出时是否生效 | **生效**，`matrix_world` 被分解进 glTF 节点 | 约束结果会被烘进 `.glb` |
| 导出到 Godot 里长什么样 | 节点带 `"scale": [0.5, 0.5, 0.5]` | **变成 Godot 侧的 `scale`，正是我们要禁止的东西** |
| 尺寸不匹配时是否被"修正" | **不会** | 见下面的"比例系数 ≠ 绝对尺寸" |

复现脚本（可直接粘进 Blender 脚本编辑器运行）：

```python
bpy.ops.mesh.primitive_cube_add(size=1.0);  REF = bpy.context.active_object
bpy.ops.mesh.primitive_cube_add(size=10.0); BIG = bpy.context.active_object
c = BIG.constraints.new('COPY_SCALE'); c.target = REF; c.use_make_uniform = True
REF.scale = (0.5, 0.5, 0.5)
# 结果：BIG.matrix_world 缩放 = 0.5 → 导出 glTF 后 BIG 节点 scale = [0.5,0.5,0.5]
# 但 BIG 的网格仍是 10 m，Godot 里读到的尺寸 = 10 × 0.5 = 5 m，与 REF 的 0.5 m 仍不一致
```

### 正确用法与边界

- ✅ **能做**：让一组物体在建模期共享同一个缩放系数（改一个参考物，全体同步缩放）。
  `use_make_uniform`（UI 里的"统一/使一致"）**只对非均匀参考缩放有意义**：参考物 `(1,2,1)` 时，
  关闭它 → 子物体也被拉成 `(1,2,1)`；开启它 → 子物体取各轴平均得到 `1.26` 等比缩放。
  参考物本身是等比缩放时，这个开关没有效果。
- ❌ **不能做**：修正"网格数据本身就差了 100 倍"。约束只是比例系数，
  1 m 的方块和 10 m 的方块都挂着 Copy Scale，永远不会因此变得一样大。
  **真实尺寸只能靠建模时按米写参数 + §2 基准表来保证**（这一点与用户意见的"重要提醒"完全一致）。
- ❌ **本仓库不用它导出**：它会往 `.glb` 节点里写非 1 的 `scale`，让 Godot 侧出现隐藏缩放，
  后续改资产时极易踩坑（改网格尺寸却没改参考物，缩放突然变化）。
- ⚠️ 约束**不做静默清理**：如果只是把模型挂在参考物下拖进场景做视觉比对，用完必须删除约束并在导出前把物体移出参考物层级，
  否则导出时对象树里会混进参考物（不是目标资产）。

### 补偿 "Child Of" 只跟随位置/旋转

若确实要建模期跟随（不参与导出），用 **子级（Child Of）** 约束并把缩放轴向关掉。注意属性默认值与直觉相反：

```python
c = ob.constraints.new('CHILD_OF'); c.target = REF
print(c.use_location_x, c.use_rotation_x, c.use_scale_x)   # True True False  ← 缩放默认就是关的
```

实测 Blender 5.2 中 `CHILD_OF` 的 `use_scale_x/y/z` **默认即为 False**，
所以"只勾位置和旋转、取消缩放"通常无需手动改；但**不要依赖默认值**，
在脚本/清单里显式置位更安全。另外 `CHILD_OF` 使用 `inverse_matrix` 做偏移补偿，
是"相对当前变换"的跟随，不是真正的父子层级。

> **一句话结论**：约束解决的是"建模期同步调比例"，基准表 + 脚本里的米制参数解决的才是"绝对尺寸一致"。
> 本项目以**后者**为准，前者只在 Blender 里做临时视觉对齐，**导出前必须清干净**。

---

## 2. 尺寸基准表（改动前先读这里）

实测值由脚本末尾的自检输出 + 对 `.glb` 的 POSITION 包围盒得到，单位米。

| 资产 | 脚本 | 实测尺寸 (X × Y × Z，Blender 轴) | 基准 | 备注 |
| --- | --- | --- | --- | --- |
| 苹果树 `low_poly_tree` | `models/apple-tree/low_poly_tree.py` | 3.53 × 4.96 × 3.28 | 树高 **5.0 m**，冠幅 3.5–4.5 m | 果树，比香蕉树略高 |
| 香蕉树·高 `low_poly_banana_tree` (tall) | `models/banana-tree-tall/…` | 2.85 × 4.85 × 3.41 | 树高 **4.77 m** | 与 `banana_tree.gd` 的 `tree_height = 4.77` 强绑定 |
| 香蕉树·矮 `low_poly_banana_tree` (short) | `models/banana-tree-short/…` | 1.98 × 2.70 × 2.18 | 树高 **2.66 m** | 与 `banana_tree.gd` 的 `tree_height = 2.66` 强绑定 |
| 香蕉 `banana` | `models/banana/banana.py` | 0.29 × 0.46 × 0.11 | 长 **0.55 m**（沿 -Z 生长，含弯曲） | 必须与香蕉树上果串里的单根同尺寸 |
| 草丛 `grass_tuft` / `grass_clump` | `models/grass/low_poly_grass.py` | 0.63×0.77×0.61 / 0.56×0.41×0.48 | 高 **0.6–0.8 m** | 造景小物，便于批量播撒 |
| 侏罗纪岛地形 `island_terrain` | `models/jurassic-island/island_terrain.py` | 199 × 56 × 150 | 长边 **≈200 m**，海平面 z=0 | 主地图地形，玩家活动区 |
| 山体洞窟岛 `low_poly_mountain_cave_island` | `models/mountain-cave-island/…` | 15.5 × 7.6 × 10.9 | 长边 **24 m**（模型常数 `SIZE=24`） | ⚠️ 实测偏小，统一时对齐到 24 m |
| 天空岛 `sky-island-basic` | `assets/island/sky-island-basic.glb` | 507 × 509 × 326 | 长边 **≈500 m**（远景，无 `apply_root_scale`） | 外部资产；如重做请按此尺度 |

主地图整体尺度：侏罗纪岛地形约 **200 m × 150 m**，海平面 `y = 0`（Godot）。
新增地形 / 大型地物请以此为参照，不要做出和地图不成比例的资产。

---

## 3. 高度 / 尺寸参考（Godot 中 +Y 为高度）

给"比例感"用的常识锚点，建模时用它们自检：

- 草 0.6–0.8 m，香蕉 0.5 m 左右（手持道具尺度）
- 香蕉树（矮）2.7 m、（高）4.8 m；苹果树 5 m
- 岛屿长边 ~200 m，海平面 0 m，最深处约 −22 m，最高峰约 +35 m
- 山体洞窟岛是"可走进的景点"，长边 24 m 量级

**新增植被 / 道具时先回答三个问题**：多高（米）？落地点是不是 z=0？在 Godot 里是否需要缩放？
如果答案里出现"到 Godot 里再缩放"，说明尺寸错了，回 Blender 改。

---

## 4. 原点（pivot）约定

原点决定 Godot 里 `position` 的含义，必须按类型统一：

| 类型 | 原点位置 | 生长 / 朝向 |
| --- | --- | --- |
| 树木、草 | **根部地面中心 (0, 0, 0)** | 沿 **+Z** 生长（导出后在 Godot 沿 +Y） |
| 悬挂物（香蕉） | **蒂（与果轴相连的一端）** | 从原点向 **−Z** 生长并弯向 +X；导出后向 −Y 垂下 |
| 地形 / 岛 | **岛屿中心，海平面 z = 0** | — |
| 道具 / 可拾取物 | 放在"被握持 / 被放置的面"的中心 | — |

导出前必须把所有对象的世界变换烘进网格并归零：

```python
bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
for ob in mesh_objects:
    ob.data.transform(ob.matrix_world)   # 世界变换烘进网格
    ob.matrix_world.identity()           # 原点回到 (0,0,0)
```

---

## 5. 新建模脚本模板（照抄这一段）

```python
import bpy

# 1) 干净起点。注意：MCP 沙箱里 read_factory_settings 会被拦截，用 homefile。
bpy.ops.wm.read_homefile(use_empty=True, use_factory_startup=True)

# 2) 公制 + 米（1 unit = 1 m），不要动 scale_length
scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'
scene.unit_settings.scale_length = 1.0

# 3) 直接按"米"写参数，名字里带 _M 或注释标明单位
TREE_HEIGHT_M = 4.77     # 米
TRUNK_RADIUS_M = 0.18    # 米

# ... 建模（z=0 为地面，+Z 向上）...

# 4) 收尾：apply 变换 + 原点归零 + flat shading
bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)

# 5) 导出：Z-up -> Y-up，应用修改器
bpy.ops.export_scene.gltf(
    filepath="...glb", export_format='GLB',
    export_apply=True, export_yup=True,
    export_vertex_color='MATERIAL',   # 顶点色资产需要
)

# 6) 自检：把尺寸打印出来，方便和 §2 表格对账
zs = [v.co.z for o in bpy.data.objects if o.type == 'MESH' for v in o.data.vertices]
xs = [v.co.x for o in bpy.data.objects if o.type == 'MESH' for v in o.data.vertices]
print("HEIGHT %.3f m  SPAN %.3f m" % (max(zs) - min(zs), max(xs) - min(xs)))
assert abs(min(zs)) < 0.02, "根部必须落在 z=0"
```

---

## 6. 自检清单（每次生成后逐条确认）

1. `min(z) ≈ 0`：根部 / 落地面贴地（±0.02 m）。
2. 尺寸落在 §2 基准的 ±2% 内；若确实要改款，**同时**更新 §2 表格与依赖它的 Godot 组件参数。
3. 所有物体 `scale == (1,1,1)`、`rotation == 0`（已 apply）。
4. `.glb` 用 `export_yup=True` 导出，Godot 导入保持 `apply_root_scale=true / root_scale=1.0`（现有 `.import` 文件已是如此）。
5. 打印的高度 / 跨度与 §2 表格一致，把实测数字留在脚本输出里。
6. 顶点色资产（草、香蕉树）颜色为**线性空间**（先做 sRGB→linear），否则 Godot 里会发白发灰。
7. **导出节点里不含非 1 的 `scale`**（见下方自动校验）；这条同时兜住"约束/参考物没清干净"的情况。

### 尺寸审计（一条命令核对全部资产）

```bash
# 1) 各资产包围盒（Blender 轴，单位米）
python3 - <<'EOF'
import json, struct, glob
for p in sorted(glob.glob("assets/**/*.glb", recursive=True)):
    d = open(p, "rb").read(); off = 12; js = None
    while off < len(d):
        clen, ctype = struct.unpack("<II", d[off:off+8])
        if ctype == 0x4E4F534A:
            js = json.loads(d[off+8:off+8+clen])
        off += 8 + clen
    idx = {pr["attributes"]["POSITION"] for m in js.get("meshes", [])
           for pr in m.get("primitives", []) if "POSITION" in pr.get("attributes", {})}
    lo = [min(js["accessors"][i]["min"][k] for i in idx) for k in range(3)]
    hi = [max(js["accessors"][i]["max"][k] for i in idx) for k in range(3)]
    print(f"{p:68s} {[round(hi[k]-lo[k], 2) for k in range(3)]}")
EOF

# 2) 非 1 缩放的节点（应输出 none；命中即说明混进了参考物或未 apply 的缩放）
python3 - <<'EOF'
import json, struct, glob
for p in sorted(glob.glob("assets/**/*.glb", recursive=True)):
    d = open(p, "rb").read(); off = 12; js = None
    while off < len(d):
        clen, ctype = struct.unpack("<II", d[off:off+8])
        if ctype == 0x4E4F534A:
            js = json.loads(d[off+8:off+8+clen])
        off += 8 + clen
    bad = [(n.get("name"), n["scale"]) for n in js.get("nodes", [])
           if n.get("scale") and any(abs(v - 1.0) > 1e-4 for v in n["scale"])]
    print(f"{p:68s} {'OK' if not bad else bad}")
EOF
```

当前实测：`assets/models/**` 全部为 `OK`；
唯一的例外是外部资产 `assets/island/sky-island-basic.glb`——它的 5 个节点自带 `scale = 0.01`
（原作者用节点缩放把模型缩到 0.01 倍）。这正是 §1.1 说的反面例子：**缩放藏在节点里，网格本身是 100 倍大小**，
后续谁改都不直观。本项目自产资产一律不这样做。

### 想要"改一处、全体同步"时怎么办

不引入约束，改用**脚本内的单一常量源 + 断言**，效果等价且不污染导出：

```python
# 在共享模块里定义唯一基准，各脚本 import 它
SIZE_REF = {"grass_m": 0.7, "banana_tree_tall_m": 4.77, "banana_m": 0.55}

# 每个脚本收尾时断言，尺寸漂了就报错，而不是悄悄变大变小
assert abs(measured_height - SIZE_REF["banana_tree_tall_m"]) < 0.02, \
    f"高度漂了：{measured_height:.3f} != {SIZE_REF['banana_tree_tall_m']}"
```

这比约束更强：约束只同步"比例系数"，这里同步的是**绝对米数**，正是本项目要的东西。

---

## 7. 与 Godot 侧的耦合（改动会破坏组件，务必同步）

- `components/vegetation/banana_tree/banana_tree.gd`：依赖香蕉树高 **4.77 m（高款）/ 2.66 m（矮款）**、
  假茎半径剖面（高款底 0.35 顶 0.24；矮款底 0.365 顶 0.26）、网格节点名 `Stalk` / `Leaves`。
- `components/vegetation/banana_bunch/`：依赖香蕉单根长 **0.55 m**、原点在蒂。
- `components/vegetation/tests/verify_banana_tree.gd`：自检里有写死的期望高度与"香蕉不插进假茎"的容差。
- 草地 / 植被摆放脚本：按 §3 的高度锚点推算密度与间距。

**规则**：改 §2 表格里任何数字前，先 grep 一遍使用方，脚本与组件一起改，并跑一次对应的 `verify_*.gd`。

---

## 8. 目录与产物约定

```
assets/
  models/<资产名>/
    <name>.py            # 生成脚本（唯一事实来源，提交）
    <name>.blend         # Blender 源文件（提交）
    <name>.glb           # Godot 用资产（提交）
    <name>_preview.png   # 预览图（提交，便于 review）
  island/                # 主地图地形与形状数据
    jurassic_island.py         # 地形生成器
    jurassic_island_shapes.py  # 烘焙的形状数据（由脚本导入，勿手改）
```

- 一个资产一个目录，脚本内路径用 `os.path.dirname(os.path.abspath(__file__))` 派生，**不要**写死绝对路径
  （`models/apple-tree/low_poly_tree.py` 里遗留的绝对 `OUT_DIR` 属于待清理项）。
- 随机造型必须固定 `random.seed(...)` / 固定噪声种子，保证可复现。
- 预览图渲染用于人眼校验比例：至少一张带地面的正视 / 3/4 视图。
- 用 Blender MCP 工作时：先 `get_scene_info` 确认场景，再用 `look` 看图核对比例；`execute_blender_code`
  里读引擎 / 枚举一律**按 type 查节点**、写进 `try/except TypeError`，不要写死本地化名称。
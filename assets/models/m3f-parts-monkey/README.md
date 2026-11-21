# 用 Python 在 Blender 里"程序化"造一只猴 —— 入门教程

> 对象：`m3f_parts_monkey.py`（1717 行）+ 两个零件库
> 产出：`m3f_parts_monkey.glb`（35 节点 / 32 网格 / 12 材质 / 8 段动画）、
> `.blend`、`_preview.png`（四视图）、`_anim.png`（6 格情绪接触表）
>
> 这份教程假设你**完全没写过 Blender 脚本**，但会一点 Python。

---

## 0. 一分钟看懂

这套脚本**不是**"用代码模拟鼠标点击去建模"。它做的是更直接的事：

> **算出每一个顶点的三维坐标，把顶点连成面，再给这些面分配颜色。**

没有"在 Blender 里拖一个顶点"这种动作。所有形状都来自三类东西：

| 你想要的形状 | 代码里的做法 | 生活比喻 |
| --- | --- | --- |
| 躯干（梨形） | **车削**：给一张"剖面表"（每个高度多宽多深），绕竖轴转一圈 | 陶艺拉坯：泥条一圈圈往上垒 |
| 手臂 / 腿 / 尾巴 | **放样**：沿一条曲线，让一个六边形截面滑过去 | 让橡皮筋沿着一条线拉伸 |
| 头（圆脸） | **参数曲面**：写一个函数 `f(方位角, 仰角) → (x,y,z)` | 用经纬网画地球仪 |

动画则更简单：**给物体的位置 / 旋转打关键帧**，然后把一堆关键帧打包成"片段"。

所以整套流程是：

```
写参数 → 跑脚本 → 得到 .blend/.glb/预览图 → 不满意就改参数再跑
```

改一个数字（比如"胳膊粗 2 毫米"），整只猴会**重新长一遍**，不会只胖一个胳膊。
这是脚本化建模最大的好处：**参数化了 = 可复用了**。

---

## 1. 为什么非要写脚本？手搓不行吗？

手搓当然行，但这个项目里脚本赢在四点：

| 手搓 Blender | 写脚本 |
| --- | --- |
| 调形状靠鼠标拖，改一处得重做一遍 | 改一个常量，重跑一遍 |
| 尺寸只能靠目测 | 参数就是米，**1 Blender 单位 = 1 米**（`assets/AGENTS.md` §1 硬规矩） |
| 加动画 = 手工 K 帧，K 到崩溃 | 一张表写完，循环片段自动接得上 |
| 改完不知道有没有"穿地""丢通道" | 脚本末尾**自己跑审计**，不合规直接报错 |

最后一条是精髓：`m3f_parts_monkey.py` 末尾那一段（第 9~11 章）是**自检**——
量尺寸、扫脚底有没有插进地面、检查每段动画是不是都带脸。
这些检查不启动 Godot，纯 Python/BVH 就能做（见 [第 8 章](#8-自检脚本自己验证自己)）。

---

## 2. 环境 & 怎么跑

### 2.1 需要什么

- **Blender**（这台机器上在 `/Applications/Blender.app`）
- Python 不用单独装 —— **Blender 自带一个 Python 环境**，
  而且里面已经带好了 `bpy`（Blender API）、`bmesh`、`mathutils`、`numpy`

### 2.2 两种跑法

**A. 命令行（headless，适合出产物）**

```bash
cd assets/models/m3f-parts-monkey
/Applications/Blender.app/Contents/MacOS/Blender -b -P m3f_parts_monkey.py
```

`-b` = background（无界面），`-P` = 跑一个 Python 文件。
脚本会自己建场景、导出 `.glb`、渲染两张 PNG，最后在终端打印 `M3F CHECK: ...`。

**B. 图形界面（适合调试）**

Blender → 切到 **Scripting** 工作区 → 新建文本 → 打开 `m3f_parts_monkey.py` →
点 **Run Script**。想看模型长什么样，切回 **Layout** 工作区按小键盘 `0` 看相机视角。

> ⚠️ **本项目的规矩**：做资产**不要启动 Godot**。
> 尺寸 / 面数 / 动画片段一律用脚本末尾的自检输出 + 直接读 `.glb` 的 JSON 来验
> （见 `assets/AGENTS.md` §0）。Godot 只在真的要改 `.tscn` 场景时才开。

### 2.3 脚本跑完会打印什么

```
M3F CHECK: tris 5338  网格 32  节点 35  材质 12
尺寸（Blender 轴 X×Y×Z）: 0.418 × 0.418 × 0.609   最低点 z = +0.0000
glb -> .../m3f_parts_monkey.glb
地面审计（每帧扫脚底真实顶点）:
  DSMonkey_Parts_Walk          脚底最低 -0.0017 m  (f1 -0.0017  f12 +0.0000 ...)
  ...
表情通道审计:
  DSMonkey_Parts_Idle              脸通道数  6      身体通道数  9   OK
  ...
```

这几行就是"验收单"。看不懂没关系，先记住：**跑完没有 `!!` 就说明过了**。

---

## 3. 核心概念一：网格 = 一张顶点表 + 一张面表

Blender 里一个网格，说到底就是两个数组：

```python
verts = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)]        # 4 个顶点
faces = [(0, 1, 2, 3)]                                        # 1 个面，用的是哪几个顶点
```

面**不存坐标**，只存**顶点的编号**。所以：

- 想移动一个顶点 → 改 `verts` 里那一项 → 所有引用它的面跟着变
- 想给某个面换颜色 → 记下它的编号 → 改它的 `material_index`

整个脚本里几乎每一段建模代码都是这个模式。最小可运行例子：

```python
me = bpy.data.meshes.new("MyCube")
me.from_pydata(verts, [], faces)      # ← 顶点、边（空）、面
me.validate()
me.update()

ob = bpy.data.objects.new("MyCube", me)
bpy.context.scene.collection.objects.link(ob)
```

两个细节：

1. **`me.validate()`** 必须调 —— 它会修掉"重复顶点""零面积面"这类脏数据，
   不调的话后面导出可能报错或者渲出黑斑。
2. **顶点索引从 1 开始**。`from_pydata` 的面用的是"第几个顶点"，
   但 Blender 内部存的是"第几个顶点 + 1"（0 号被占用了）。
   所以脚本里算索引时经常看到 `1 + j * ncols + i` 这种写法。

---

## 4. 核心概念二：三种"长出形状"的手法

这是整套脚本 80% 的内容。掌握了三种手法，你就能自己造任何低模部件了。

### 4.1 车削（Lathe / 旋转成型）

**原理**：你只需要描述"从底到顶，每一层有多宽多深"，
Blender 帮你绕竖轴转一圈。

**代码**：[`m3f_parts_monkey.py:102`](../../models/m3f-parts-monkey/m3f_parts_monkey.py) 的剖面表

```python
TORSO_PROFILE = [
    (0.108, 0.080, 0.070),    # (高度z, 半宽rx, 半深ry)
    (0.132, 0.126, 0.106),
    (0.176, 0.142, 0.120),    # 最宽（胯）
    (0.216, 0.138, 0.117),
    (0.248, 0.128, 0.110),
    (0.276, 0.116, 0.102),    # 肩
    (0.296, 0.088, 0.080),
    (0.310, 0.050, 0.048),    # 颈
    (0.322, 0.044, 0.042),
]
```

读法：这只猴的屁股宽 0.284 m（`0.142 × 2`），肩膀窄 0.232 m，中间是脖子。
**梨形**就是这么来的。

**代码**：[`build_torso()` @ 321 行](../../models/m3f-parts-monkey/m3f_parts_monkey.py)

```python
for (z, rx, ry) in densify_profile(TORSO_PROFILE, TORSO_RINGS):
    idx = []
    for k in range(cols):                       # 环向 20 段
        a = 2.0 * math.pi * k / cols
        idx.append(len(verts))
        verts.append(Vector((rx * math.sin(a), ry * math.cos(a), z)))
    rings.append(idx)
# 然后相邻两环之间连四边形
```

**三步套路**（背下来，几乎所有"圆滚滚的部件"都能套）：

1. `densify_profile()`：把稀疏的剖面表**插值**成 N 环
   （插值是为了让面块均匀；不插值的话有的面特别大、有的特别小）
2. 每环沿圆周撒 N 个点 → 得到一圈"环"
3. 环与环之间连四边形，首尾各加一个盖子

> **为什么环向顶点写的是 `(rx·sin a, ry·cos a)` 而不是 `(rx·cos a, ry·sin a)`？**
> 因为 `sin` 在前，从 +Z 往下看是**顺时针**。
> 配上面片顺序 `(r_j_k, r_j_k2, r_{j+1}_k2, r_{j+1}_k)` 之后，
> 整块壳的**法线会朝内**。Blender 渲染时会把背面法线自动翻过来凑合着照，
> 看起来"还行"，但换个角度就变味，而且**贴面壳会整个埋进身体里**。
> 所以脚本最后调 [`recalc_normals()` @ 292 行](../../models/m3f-parts-monkey/m3f_parts_monkey.py)
> 统一把法线掰回朝外。

### 4.2 放样（Loft / 扫掠）

**原理**：一条路径 + 一个截面 → 一根管子。
路径可以是弯的（胳膊肘是弯的），截面可以是变化的（胳膊越往手越细）。

**代码**：工具函数全在 [`ds_monkey_trunk.py`](../../models/ds-monkey-trunk/ds_monkey_trunk.py)

| 函数 | 作用 |
| --- | --- |
| `catmull_rom_3d(pts, n)` | 把几个控制点变成一条**平滑曲线**（Catmull-Rom 样条） |
| `resample(path, n)` | 按**弧长**重新采样成 n 个点（保证疏密均匀） |
| `frames_along(pts)` | 沿曲线给每个点配一组**正交基 (u, v)** |
| `add_tube_path(b, pts, radii, ...)` | 沿路径扫出 n 棱管 |
| `loft_rings(b, rings, slot)` | 把一圈圈的顶点连成面 |

**`frames_along` 是放样最关键的一环**，值得单独说：

沿曲线走，每一步都得知道"这一点的截面该朝哪个方向摆"。
最笨的办法是每个点都用世界坐标的 up 向量，但那样曲线一弯，管子就**拧麻花**了。
正确做法叫**平行传导标架**（parallel transport frame）：

```python
u = u - t * u.dot(t)      # 把上一帧的 u 投影到当前切线的法平面上
u.normalize()             # 这样 u 一直"贴着"曲线转，不会突然翻转
v = t.cross(u)
```

一句注释概括：**"平行传导标架：沿曲线逐点转过去，管子不会自己拧麻花。"**

**代码**：[`build_arm()` @ 476 行](../../models/m3f-parts-monkey/m3f_parts_monkey.py)

```python
def build_arm(side):
    ctrl = [Vector((p.x * side, p.y, p.z)) for p in ARM_PATH]   # 左臂 = 右臂 x 取负
    b = TR.Builder()
    TR.add_tube_path(b, smooth_path(ctrl, ARM_RINGS), ARM_RADII,
                     "fur", sides=6, round_start=True)           # 6 棱，肩那头是半球
    wrist = ctrl[-1]
    add_fist(b, wrist, wrist + Vector((0.002 * side, 0.010, -0.046)))
    return b
```

> **左半边不重新建模**，直接把右边镜像（`x` 取负 + 面绕序反转）。
> 一半的代码量，也保证了左右**绝对对称**。

### 4.3 参数曲面（f(u, v)）

**原理**：写一个函数，输入两个参数，输出一个坐标。
整个头就是一张这样的网格。

**代码**：[`skull_point(az, el)` @ `monkey_head.py:338`](../../models/_shared/monkey_head.py)

```python
def skull_point(az, el):
    zn = max(-0.999, min(0.999, math.sin(el)))     # 归一化高度
    hw = lerp_table(PROFILE, zn)                    # 查表：这个高度多宽
    fb = lerp_table(FRONT, zn)                      # 这个高度往正面凸多少
    ca, sa = math.cos(az), math.sin(az)
    x = hw * sa
    if ca >= 0.0:                                   # 正面
        y = fb * (abs(ca) ** FACE_ROUND_P)          # 圆脸截面（p<1 更鼓）
        y += MUZZLE_SCALE * mz * math.exp(-(az / MUZZLE_AZ) ** 2)   # 吻部前突
    else:
        y = bk * ca                                 # 背面
    return Vector((x, y, RZ * zn))
```

这里 `az`（方位角）和 `el`（仰角）是**球面坐标**——
和地球仪的经纬度一个意思。`build_skull()` 把它撒成 31 环 × 31 列。

> 📖 头的完整实现（四张侧影表、发际线 V 形、脸盘边界、BVH 射线贴五官……）
> 见 **[第 13 章](#13-专题头部是怎么做出来的)**。

**三种手法怎么选？**

| 你的部件 | 用哪个 |
| --- | --- |
| 上下粗细不一样、绕轴对称（躯干、脖子、桩子） | 车削 |
| 沿着弯的路径（胳膊、腿、尾巴、触手） | 放样 |
| 球面形状、脸上要贴东西（头、石头） | 参数曲面 |

---

## 5. 核心概念三：零件复用 —— 把别的脚本当库 import

这个项目里有 6 只猴，头和四肢是**共用**的。
`m3f_parts_monkey.py` 只负责"拼装 + 改脸"，不重造轮子。

### 5.1 import 顺序有讲究

```python
sys.path.insert(0, TRUNK)              # ds-monkey-trunk
import ds_monkey_trunk as TR            # ← 它开头会 read_homefile(use_empty=True) 清空场景！

sys.path.insert(0, SHARED)
sys.modules.pop("monkey_head", None)
import monkey_head as MH                # ← 这个不清场
```

**规则：先导会清场的，后导不会清场的。**
（`sys.modules.pop` 是为了强制重新加载，不然改动不生效）

### 5.2 零件脚本要加"副作用开关"

一个脚本想既能被 `import` 当库用，又能单独跑，需要把"导出 / 渲染 / 存盘"这些**副作用**关掉：

```python
STANDALONE = (__name__ == "__main__")
...
if STANDALONE:
    bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH)
```

这是 Python 的标准做法，记住就行。

### 5.3 猴子脚本怎么"改造"共用的头

共用的头只有 12 环 × 8 列，脸的侧边只有 4 列 → 头侧边只剩几个大面。
这个脚本的做法是**换掉它的采样函数**再重建：

```python
MH.ROWS[:] = ROWS_DENSE              # 环数 12 → 31
MH.NCOL_FACE = 12                     # 脸的列数 4 → 12
MH.NCOL_FUR  = 9                      # 每侧毛区 2 → 9
MH.NCOL = 2 * 9 + 12 + 1              # = 31
MH.col_az = col_az_dense              # ← 直接把模块里的函数换掉
head_root = MH.build_skull()          # 重建
```

妙处：`build_skull()` 是按**模块级函数名**调用的，
所以把 `MH.col_az` 一换，整个采样分布就变了，而表面函数一行没动。

> ⚠️ **重建颅骨后，五官要重新贴一遍**。
> 原来的眼白 / 微笑弧是按射线打在"旧颅骨"上定位的，
> 颅骨加密后曲面往外挪了 1~2 mm，旧的五官就**埋进脸里**了（微笑弧直接看不见）。
> 做法：删掉旧五官 → 重建颅骨 → 用同一个 BVH 重新调 `build_eye_parts(bvh)` 等。

---

## 6. 核心概念四：骨架 = 节点层级，不用骨骼权重

### 6.1 为什么不用 armature？

Blender 的骨骼要处理"权重"（哪些顶点跟随哪根骨头）、
骨骼命名、rest pose……这些是跨软件最容易翻车的地方。

这个项目用的是**更土但更稳**的办法：

> **每个肢体是一个独立的网格物体，物体的原点就落在关节枢轴上，按关节父子挂接。**

长出来是这样：

```
Root
└── Hips                （整体起伏 / 升降）
    ├── Torso           （绕髋俯仰：跑步前倾、坐姿后靠）
    │   ├── HeadNode    （脖子转轴）
    │   │   └── Head    （颅骨）
    │   │       └── 眼睛 / 瞳孔 / 眉毛 / 5 张嘴 / 耳朵 …
    │   ├── Arm_R / Arm_L
    │   └── Belly / BellyRim
    ├── Thigh_R / Thigh_L
    │   └── Shin_R / Shin_L
    │       └── Foot_R / Foot_L
    └── Tail
```

这就像**提线木偶**：每个零件挂在自己的关节上，父节点一动，子节点全跟着动。

### 6.2 枢轴（pivot）是关键

一个物体的**原点**就是它的旋转中心。所以想让"膝盖能弯"，
就必须让小腿的原点**正好在膝盖上**。

工具函数 [`make_part()` @ `ds_monkey_trunk.py:409`](../../models/ds-monkey-trunk/ds_monkey_trunk.py)：

```python
def make_part(name, b, anchor):
    """把世界坐标的网格烘成「锚点局部坐标」，物体摆在锚点上（scale = 1）。"""
    anchor = Vector(anchor)
    ob = build_object(name, [v - anchor for v in b.v], b.f)
    ob.location = anchor
    return ob
```

读法：**顶点全部减去锚点 → 变成"以锚点为原点"的局部坐标；
物体本身再摆到锚点上。** 这样物体的 scale 恒为 1（`assets/AGENTS.md` §1 硬规矩）。

### 6.3 ⚠️ 偏置只能加一次

这是新手最容易懵的地方。

共用头的零件是**颅骨的子物体**。颅骨要抬高 0.145 m（`HEAD_C_Z - NECK_Z`），
那这个高度**加在颅骨的顶点上**，零件的 `location` 就**不能再加一次**：

```python
off = Vector((0.0, 0.0, HEAD_C_Z - NECK_Z))
for ob in MH.MESHES:
    if ob is head_root: continue
    ob.location = off + Vector(ob.location) * HEAD_SCALE   # 位置搬过去
    for v in ob.data.vertices:
        v.co = v.co * HEAD_SCALE                          # 顶点缩放
for v in head_root.data.vertices:
    v.co += off                                           # 颅骨：只加在顶点上
head_root.location = Vector((0.0, 0.0, 0.0))
```

**加两次的后果**：头会飞到半空（实测颅心跑到 0.89 m）。

口诀：
> **网格里存"世界坐标"的东西（躯干）+ 父节点带高度 → 父节点的高度要减掉。**
> **网格里存"局部坐标"的东西（共用头的零件）+ 父节点是原点 → 直接加。**

---

## 7. 核心概念五：动画 = 关键帧 → NLA 轨 → 片段

### 7.1 打关键帧的封装

[`key_clip()` @ 1131 行](../../models/m3f-parts-monkey/m3f_parts_monkey.py) 的输入是一张"表"：

```python
WALK = [
    (1,  {ARM_R: {"rot": (-0.48, 0, 0)}, ARM_L: {"rot": (0.48, 0, 0)}, ...}),
    (13, {ARM_R: {"rot": (0.0, 0, 0)},   ARM_L: {"rot": (0.0, 0, 0)},   ...}),
    (25, {ARM_R: {"rot": (0.48, 0, 0)},  ARM_L: {"rot": (-0.48, 0, 0)}, ...}),
]
```

读法：**第 1 帧右胳膊转 -0.48 弧度（往前），第 13 帧回正，第 25 帧往后……**
走一个来回 = 半个周期。

### 7.2 为什么要用 NLA 轨？

glTF 导出器在 `NLA_TRACKS` 模式下，**按轨的名字**把所有物体的动画合成一条。
所以做法是：**每个物体挂 N 条同名 NLA 轨，轨名 = 片段名**。

```python
tr = ad.nla_tracks.new()
tr.name = name                                  # ← 片段名
st = tr.strips.new(name, 0, act)
st.frame_start = 0
st.frame_end = length                           # ⚠️ 必须显式给！
```

### 7.3 ⚠️ 三个必须记住的坑

**坑 1：strip 必须显式给帧范围。**
`tr.strips.new(name, 0, act)` 的默认 `frame_end = 0` → 片段长度是 0 →
不管 `frame_set` 到第几帧，动画永远停在第 0 帧（"动画不动"）。

**坑 2：导出器会丢掉"整段不变"的通道。**
如果一条通道从头到尾数值完全一样，glTF 导出器会**整个丢掉它**。
后果：
- 跑步时躯干前倾 0.16 rad 三帧都一样 → **根本没进 .glb** → Godot 里跑步不前倾
- 嘴一直抿着不动 → 通道被丢 → "换嘴"失效，微笑一直挂在脸上

脚本的应对：
- 嘴加 **2.2 mm 的下颌微动**（看不出来，但通道有变化了）
- 眉毛在"发力帧 / 过腿帧"给**两个不同的值**
- 坐姿别三帧一模一样，从"刚开始坐"慢慢落到"坐定"

**坑 3：撤下 action 不会把属性退回静止位。**
Blender 里上一段动画求值过的 `rotation_euler` 会**留在物体上**。
实测切到 Idle 之后腿还留着上一段的 0.69 rad，脚底离地 8 mm，**每一段都偏 8 mm**。

应对：脚本里存一份静止位快照 `REST`，`activate_clip()` 时显式写回去。

### 7.4 换表情要"瞬切"

两张嘴如果用平滑插值，过渡帧会**同时露一半**。
所以表情零件的位置通道要用 `CONSTANT` 插值：

```python
if nm in CONST_LOC:
    for fc in action_fcurves(act):
        if fc.data_path == "location":
            for kp in fc.keyframe_points:
                kp.interpolation = 'CONSTANT'
```

### 7.5 预览和导出走两套路

Blender 5.2 的 NLA strip 求值时间**不随 `scene.frame_set` 推进**（动画"不动"）。
所以脚本分两套：

- **预览 / 审计**：`activate_clip(name)` —— 直接把 action 挂回物体
- **导出**：仍然用 NLA 轨（导出器按轨名合并片段）

---

## 8. 表情系统：怎么在脸上"换表情"

这是这个脚本最巧的部分。

### 8.1 思路：所有表情都是"零件"，靠推拉切换

脸上有 **8 个可动零件**：

| 零件 | 作用 |
| --- | --- |
| `Eye_L/R` | 眼白 |
| `Pupil_L/R` | 瞳孔 |
| `EyeShut_L/R` | 开心眯眼（向上拱的弧） |
| `EyeBlink_L/R` | 眨眼（向下弯的弧） |
| `MouthSmile` | 微笑弧 |
| `MouthLaugh` / `MouthFear` / `MouthFlat` / `MouthPants` | 4 张不同的嘴 |

它们**全都长在颅骨上**，平时**藏进颅骨里**：

```python
SHOW = (0.0, 0.060, 0.0)      # 从颅骨里推到脸上
HIDE = (0.0, -0.060, 0.0)     # 推进颅骨里藏起来
```

换表情 = **把这一个推到脸上，其余全部推进去**：

```python
def mouth(which):
    p = {}
    for nm in MOUTH_PARTS:
        p[PREFIX + "_" + nm] = {"loc": HIDE}       # 先全藏
    if which == "smile":
        p[PREFIX + "_MouthSmile"] = {"loc": (0.0, 0.0, 0.0)}   # 微笑是静止位
    else:
        p[PREFIX + "_" + MOUTH_MAP[which]] = {"loc": SHOW}      # 其余推到脸上
    return p
```

> ⚠️ **每次都必须把所有眼 / 嘴零件都点名一遍**，
> 只点"要变的那个"会让上一个表情的状态**粘住**。

### 8.2 为什么重做的嘴要自己藏

共用头在自己的模块里把 `MouthLaugh / MouthFear / EyeShut` 推进颅骨藏起来（`PARK`）。
这个脚本**重做**了这几张嘴 —— 换了网格、换了名字，就**没人藏它们了** →
大笑嘴一直挂在脸上，和微笑弧叠在一起，看起来就是"嘴很奇怪、好像重叠"。

所以重做共用头的零件时，**藏的动作要自己补一遍**。

### 8.3 怎么在脸上"贴"一块橘色肚皮

橘色肚皮不是一个独立物体，而是一层**贴在躯干表面的壳**。
做法是**用射线打表面**：

```python
def surf(px, pz, off):
    loc, nor, _, _ = bvh_t.ray_cast(Vector((px, 1.0, pz)), Vector((0.0, -1.0, 0.0)))
    return loc + nor * off      # 命中点 + 沿法线抬起 off 米
```

从 +Y 方向打射线 → 命中躯干表面 → 沿法线抬起 3 mm → 得到一个"贴"上去的圈。

> ⚠️ **壳要 4 圈同心环 + 中心点，不能只画一圈**。
> 圈与圈之间是**弦**（直线），弦会切进鼓起来的曲面里 →
> 被切到的那些面从壳**底下顶出来** → 肚皮上顶出一张"鬼脸"。
> 圈多 → 每块三角形都短 → 弦切不进去。

> ⚠️ **为什么不用"逐面染色"？**
> 染色的边界只能落在**网格线上** → 边界永远是碎方块（看着像贴了张创可贴）。
> 做成独立的壳，才能是一个**干净的圆**。

---

## 9. 脚不穿地：髋高是**算**出来的

腿拆成 大腿 / 小腿 / 脚掌 三个节点之后，"脚该多高"不再是手填角度能推的。

做法（[`solve_ground()` @ 1286 行](../../models/m3f-parts-monkey/m3f_parts_monkey.py)）：

```
1. 按关键帧摆好腿
2. 量脚底**真实顶点**的最低 z
3. 髋高 = -那个 z（正好让最低点落在 0）
4. 把这个偏移打成髋部位移的关键帧
```

这样循环片段就**永远有一只脚正好踩在地上**。

> ⚠️ **必须用真实顶点，不能用 `bound_box`**。
> 腿转起来之后，轴对齐的包围盒角会比实际几何低好几毫米（盒子不跟着转），
> 会报出假的穿地。

实测结果：

| 片段 | 脚底最低 |
| --- | --- |
| Walk | −0.0017 m |
| Run | −0.0010 m |
| Idle | +0.0000 m |
| Sit | −0.0000 m |

---

## 10. 自检：脚本自己验证自己

### 10.1 脚本内置的三道审计

| 函数 | 检查什么 |
| --- | --- |
| `bbox_world()` | 整体尺寸、最低点是不是 z=0 |
| `clip_ground_audit()` | 逐帧扫脚底，找穿地 |
| `face_channel_audit()` | **每段动画都必须有脸通道**，没有就 `assert` 失败 |

```python
assert face, "%s 没有表情通道" % nm
```

### 10.2 不开 Godot 也能验 `.glb`

GLB 的格式是 `12 字节头 + JSON 块 + BIN 块`，用 Python 直接读：

```python
import json, struct
d = open('m3f_parts_monkey.glb', 'rb').read()
off = 12
while off < len(d):
    ln, ty = struct.unpack_from('<II', d, off); off += 8
    ch = d[off:off+ln]; off += ln
    if ty == 0x4E4F534A:            # 'JSON'
        js = json.loads(ch.decode('utf-8'))

for a in js['animations']:
    print(a['name'], len(a['channels']))
```

实测输出（这就是"8 段动画、每段都带脸"的证据）：

```
DSMonkey_Parts_Idle          channels= 15
DSMonkey_Parts_Sit           channels= 23
DSMonkey_Parts_Walk          channels= 25
DSMonkey_Parts_Run           channels= 15
DSMonkey_Parts_Cheer         channels= 21
DSMonkey_Parts_Startle       channels= 16
DSMonkey_Laugh               channels= 15
DSMonkey_Fear                channels= 11
```

节点数 / 网格数 / 材质数也在同一个 JSON 里（`nodes` / `meshes` / `materials`）。

---

## 11. 坑清单（速查）

按"踩到概率"排序：

| # | 坑 | 症状 | 解法 |
| --- | --- | --- | --- |
| 1 | 偏置加了两次 | 头飞到半空 | 网格存世界坐标 vs 局部坐标，要分清（§6.3） |
| 2 | `materials.clear()` | 所有面都变槽 0（拳头变棕色） | 先存 `material_index`，append 完写回（`remap_materials()`） |
| 3 | 导出丢"整段不变"的通道 | 跑步不前倾 / 换嘴失效 | 给通道加微小变化（§7.3 坑 2） |
| 4 | strip 没给帧范围 | 动画"不动" | `st.frame_start / frame_end` 显式给（§7.3 坑 1） |
| 5 | 撤下 action 不回静止位 | 每段动画都偏 8 mm | 存 `REST` 快照，显式写回（§7.3 坑 3） |
| 6 | 贴面壳只画一圈 | 肚皮/嘴巴上顶出"鬼脸" | 4 圈同心环 + 中心点（§8.3） |
| 7 | 重做的零件没人藏 | 两张嘴叠在一起 | 自己补 `EXTRA_HIDDEN` 隐藏逻辑（§8.2） |
| 8 | 车削的法线朝内 | 贴面壳整个埋进身体 | `recalc_face_normals`（§4.1） |
| 9 | 重建颅骨后没重贴五官 | 微笑弧看不见 | 用新 BVH 重新调 `build_eye_parts`（§5.3） |
| 10 | import 顺序反了 | 零件全没了 | 先导会清场的脚本（§5.1） |
| 11 | 趾头互相叠 | 脚趾像锯齿 | 间距 > 直径（0.0225 > 0.021） |
| 12 | 拳头不咬进手臂 | 手是飘着的 | 第一圈 `t = -0.018` 埋进手臂 |

---

## 12. 动手练习

按难度排。**每个练习都只改一个常量，然后重跑脚本、对比预览图。**

### 练习 1（10 分钟）：把猴改胖

改 [`m3f_parts_monkey.py:102`](../../models/m3f-parts-monkey/m3f_parts_monkey.py) 的 `TORSO_PROFILE`，
把 `0.176, 0.142, 0.120` 那一行的两个半径都改成 `0.160`。

**观察**：只有躯干变胖，手脚没变 → 理解"参数化"是**局部的**。
（要整体变胖，得每个常量都改 —— 这就是"参数化"的代价。）

### 练习 2（20 分钟）：加一个表情

1. 照着 `build_mouth_pants()` @ 960 行写一个 `build_mouth_o()`，
   轮廓用一个 8 点的小圆
2. 在 `MOUTH_MAP` 和 `MOUTH_PARTS` 里各加一项
3. 在 `EXTRA_HIDDEN` 里加上它
4. 在 `mouth()` 里加一个分支
5. 给 `Startle` 片段换成 `"o"`

**难点提示**：`build_mouth_mesh()` 里的 `slots` 列表和 `faces` 列表必须**一一对应**，
所以嘴巴的描边管子（`MH.tube` 返回的是 `(面, 槽名)` 二元组）要**摊平**再合并。

### 练习 3（30 分钟）：让猴走得更"高"

改 `WALK` 里的 `legs_pose(...)` 参数：
把 `0.42` 改成 `0.60`（抬腿更高），然后**重跑**，看脚底审计那一行变成多少。

**观察**：`solve_ground()` 会自动把髋抬高来补偿 → 脚还是踩在地上。
这个练习能让你真正理解"地面求解器"在干嘛。

### 练习 4（挑战）：给猴加一根手指

`add_fist()` 造的是一颗八棱球。想加手指，就把 `SECTIONS` 的球换成
几段沿轴放的细管（用 `TR.add_tube`）。

**思考**：为什么脚本里放弃了手指，改用拳头？
（提示：在这个大小的模型上，0.015 m 长的小棍会像毛刺 —— **低模不是"细节多"，是"读得懂"**。）

---

## 13. 专题：头部是怎么做出来的

> 对象：`assets/models/_shared/monkey_head.py`（1082 行）+ `m3f_parts_monkey.py` 第 6 章的改造
> 头是整个资产里技术密度最高的一块 —— 因为它要同时满足三件事：
> **① 形状像参考图 ② 颜色分界线干净 ③ 五官能贴在曲面上不穿模**。

### 13.0 头由哪些零件组成

头不是一个网格，而是 **16 个独立物体**，因为五官要能独立动：

| 类别 | 零件 | 数量 |
| --- | --- | --- |
| 静态 | `DSMonkeyHead`（颅骨）、`DSMonkeyTuft`（呆毛）、`DSMonkeyEar_L/R` | 4 |
| 眼 | `Eye_L/R`（眼白）、`Pupil_L/R`（瞳孔+高光）、`EyeShut_L/R`（开心眯眼弧） | 6 |
| 嘴 | `MouthSmile`（常驻微笑）、`MouthLaugh`、`MouthFear` | 3 |
| 标记 | `Brow_L/R`（眉毛）、`DSMonkeyNostrils`（鼻孔） | 3 |

全部是颅骨的**子物体**（`ob.parent = head`），
所以头一转，所有五官跟着走。

---

### 13.1 颅骨：一张网格 = 四张表 + 一个公式

#### 13.1.1 坐标系：两个角

头用的是**球面坐标**，和地球仪的经纬度一个意思：

| 符号 | 名字 | 范围 | 含义 |
| --- | --- | --- | --- |
| `az` | 方位角 | −π ~ +π | 0 = 正前方（+Y），±π = 正后方 |
| `el` | 仰角 | −π/2 ~ +π/2 | +π/2 = 头顶，−π/2 = 下巴 |

代码里先归一化成"高度" `zn = sin(el) ∈ [−1, 1]`，
这样查表就用 0.930 这样的数，而不是 76° 这种角度：

```python
zn = max(-0.999, min(0.999, math.sin(el)))
```

#### 13.1.2 四张表（全部是**量出来的**，不是手调的）

| 表 | 查什么 | 量自 | 代码 |
| --- | --- | --- | --- |
| `PROFILE` | 这个高度**多宽**（半宽） | 正面视图的轮廓 | `monkey_head.py:37` |
| `FRONT` | 这个高度中线往**前**凸多少 | 侧视图 | `monkey_head.py:54` |
| `BACK` | 这个高度后脑**多深** | 侧视图 | `monkey_head.py:97` |
| `MUZZLE` | 吻部（前突的嘴）**多突** | 侧视图 | `monkey_head.py:69` |

查表函数 `lerp_table(table, x)` 就是普通的线性插值（两端夹住）。

```python
PROFILE = [
    (1.000, 0.000),      # 头顶最尖
    (0.930, 0.052),
    (0.860, 0.049),
    (0.700, 0.118),
    (0.520, 0.129),
    (0.320, 0.146),
    (0.120, 0.149),
    (-0.080, 0.1505),    # ← 眼睛在这附近，半宽 0.15 m
    (-0.280, 0.1510),
    (-0.480, 0.1520),
    (-0.660, 0.1480),
    (-0.820, 0.1170),
    (-0.940, 0.0920),
    (-1.000, 0.0680),    # 下巴收窄
]
```

**关键理解：头不是球，是"四条侧影曲线 + 一条横截面公式"拼出来的。**
所以改形状的最快办法是**改表**（比如"后脑再鼓一点"→ 改 `BACK`），
而不是改公式。

#### 13.1.3 `skull_point()` 逐行拆

```python
def skull_point(az, el):
    zn = max(-0.999, min(0.999, math.sin(el)))
    hw = lerp_table(PROFILE, zn)      # 半宽
    fb = lerp_table(FRONT, zn)        # 正面深度
    mz = lerp_table(MUZZLE, zn)       # 吻部凸起量
    bk = lerp_table(BACK, zn)         # 后脑深度
    ca, sa = math.cos(az), math.sin(az)

    x = hw * sa                      # ← 横向位置：宽度表 × sin
    if ca >= 0.0:                    # ===== 正面 (az ∈ [-90°, +90°]) =====
        y = fb * (abs(ca) ** FACE_ROUND_P)                       # ① 圆脸截面
        la = abs(az)
        if la < FACE_LIFT_AZ:
            y += FACE_LIFT * (1.0 - (la / FACE_LIFT_AZ) ** 2)   # ② 面罩隆起
        y += MUZZLE_SCALE * mz * math.exp(-(az / MUZZLE_AZ) ** 2)  # ③ 吻部前突
    else:                            # ===== 背面 =====
        y = bk * ca
    return Vector((x, y, RZ * zn))
```

**① 圆脸截面 `fb · |cos(az)|^p`（p = 0.70）**

把 `sin(az) = x/hw` 代进去，`cos(az) = √(1−(x/hw)²)`，所以正面的横截面是

```
y = fb · (1 − (x/hw)²)^(p/2)
```

- `p = 1` → 椭圆
- `p = 0.70` → **比椭圆更鼓**（脸颊鼓出来）

为什么不能太小？曲率半径 `R = hw² / (fb · p)`：

| p | R | 后果 |
| --- | --- | --- |
| 1.00 | 0.149 m | 正圆截面，颊部偏平 |
| **0.70** | **0.210 m** | 脸颊鼓，符合参考图 |
| 0.30 | 0.49 m | 太平，退化成"平板 + 尖角" |

注释里写着："p 不能太小：p → 0 会退化成『平脸 + 尖角』，而且中心曲率半径变小后，
56 mm 的眼白贴片两边会陷进脸里"。这就是 `FACE_ROUND_P` 卡在 0.70 的原因。

**② 面罩隆起 `FACE_LIFT = 0.010`**

参考图的脸是**一块浮在毛皮上的面罩**，不是平铺上去的。
所以正面整体往外鼓 10 mm，到颞骨（|az| > 1.05 rad）收到 0，用一个抛物线过渡。

**③ 吻部前突（高斯）**

```python
y += MUZZLE_SCALE * mz * math.exp(-(az / MUZZLE_AZ) ** 2)
```

`mz` 是"这个高度吻部该突多少"（查表），`exp(-(az/0.46)²)` 是一个**高斯钟形**，
让凸起只在正前方（|az| < ~0.5 rad）出现，两边自然收掉。

`MUZZLE_SCALE = 0.66` 是"整体缩量"——参考图里的嘴没有鼓那么厉害。

#### 13.1.4 为什么正面和背面要分开算？

`ca >= 0` 是分界线（az = ±90°，也就是头的"最宽那一圈"）。
在 az = ±90° 处 `ca = 0`，两个分支都给出 `y = 0` → **连续，没有缝**。

分开算是因为**正面和侧视的深度规律完全不同**：
正面要"鼓"（超椭圆 + 面罩隆起 + 吻部），背面要"圆"（`bk · ca` 是个椭圆截面）。
用一张表管到底就做不出这张脸。

#### 13.1.5 采样：环 × 列

网格 = **若干条环（ROWS）× 若干列（col_az）**。

**列（环向）的分布**由 `col_az(i, A)` 决定，`A` 是"脸盘在这一层的边界角"：

```python
def col_az(i, A):
    if i <= NCOL_FUR:                       # 左毛区
        return -math.pi + (math.pi - A) * (i / float(NCOL_FUR))
    if i <= NCOL_FUR + NCOL_FACE:           # 脸盘
        j = i - NCOL_FUR
        return -A + 2.0 * A * (j / float(NCOL_FACE))
    j = i - NCOL_FUR - NCOL_FACE            # 右毛区
    return A + (math.pi - A) * (j / float(NCOL_FUR))
```

布局：`[左毛区 NCOL_FUR 列] [脸盘 NCOL_FACE 列] [右毛区 NCOL_FUR 列]`，
脸盘占中间，边界在 ±A。

**环（高度）的分布**由 `ROWS` 决定，每行是 `(仰角°, V 形下垂权重)`：

```python
ROWS = [
    (76.0, 0.10), (62.0, 0.30), (46.0, 0.70), (33.0, 0.95),
    None,                                   # ← 发际线环（索引必须是 4！）
    (8.0, 0.75), (-8.0, 0.45), (-17.0, 0.32), (-26.0, 0.20),
    (-46.0, 0.00), (-64.0, 0.00), (-79.0, 0.00),
]
```

`None` 是**发际线环**——它的仰角随方位角变化。

#### 13.1.6 发际线：一个高斯缺口

```python
def hairline(az):
    return HAIR_EL - HAIR_PEAK * math.exp(-(az / HAIR_W) ** 2)
```

- `HAIR_EL = 0.545` rad = 31.2° → 两侧的发际线高度
- `HAIR_PEAK = 0.155` → 正中往下压 8.9°
- `HAIR_W = 0.22` → 缺口的宽度（很窄 → 正中是**尖角**，不是 U 形）

所以正中发际线 = 0.545 − 0.155 = **0.39 rad = 22.3°**，
两侧 = **31.2°**。这就是参考图里额头上那个"V 形褐毛楔形"。

每行的仰角再按权重往发际线方向拉：

```python
def row_el(row, az):
    if row is None:                       # 发际线环自己
        return hairline(az)
    deg, w = row
    return math.radians(deg) + (hairline(az) - hairline(0.0)) * w
```

`w` 越大，这一行的仰角越**跟着发际线跑**。
所以发际线附近那几行（`w` = 0.95 / 0.75）的面会紧紧贴着发际线的 V 形走 ——
**发际线是颜色边界，它附近的面必须跟着走，边界才干净**；
再往下 `w` 递减到 0，下巴那几行就恢复成纯粹的等仰角环。

#### 13.1.7 `SIDE_LIMIT`：脸盘的侧边界

```python
SIDE_LIMIT = [
    (-1.5708, 0.88), (-1.30, 0.79), (-1.05, 0.76), (-0.96, 0.83),
    (-0.82, 0.71), (-0.66, 0.62), (-0.52, 0.76), (-0.38, 0.94),
    (-0.23, 1.00), (-0.09, 1.03), (0.05, 1.10), (0.19, 1.14),
    (0.35, 1.15), (0.49, 1.15), (0.63, 1.10), (0.75, 1.00),
]
```

查表：`仰角 → 脸盘的最大 |az|`。

**这张表是从参考图逐行量出来的**（量橘色脸盘每行的半宽，换算成该高度的颅骨半宽，
再 `asin` 回去），不是手调的。所以脸盘是**上窄下宽**的，
而且在 `el ≈ -0.5`（下巴附近）有个明显的收窄。

用法：

```python
for j, row in enumerate(ROWS):
    base_el = hairline(0.0) if row is None else math.radians(row[0])
    A = lerp_table(SIDE_LIMIT, base_el)      # ← 这一层的脸盘边界角
    for i in range(NCOL):
        az = col_az(i, A)                     # ← 列分布随 A 变
        el = row_el(row, az)
        verts.append(skull_point(az, el))
```

**A 逐层变化 → 脸盘的侧边就是一条随高度起伏的曲线，而不是一条竖直线。**

#### 13.1.8 分色：哪些面算"脸"

```python
def is_face_col(i):
    return NCOL_FUR <= i < NCOL_FUR + NCOL_FACE     # 列在不在脸盘范围
...
face_row = (j + 1) > HAIR_ROW                       # 行在不在发际线之下
slot = "face" if (face_row and is_face_col(i)) else "fur_light"
```

**两个条件同时满足**才是橘色脸盘：列在中间 + 行在发际线以下。

> ⚠️ **`HAIR_ROW = 4` 是硬约定**。`build_skull()` 用 `(j + 1) > HAIR_ROW` 判断，
> 所以发际线环（`None`）**必须待在索引 4**。
> m3f 脚本加密颅骨时把 `None` 放到了索引 7 → 整个额头被染成橘色，脸变成一张大面具。

#### 13.1.9 三角化：交替对角线

```python
if (i + j) % 2 == 0:
    faces.append(((A_, B_, C_), slot))
    faces.append(((A_, C_, D_), slot))
else:
    faces.append(((A_, B_, D_), slot))
    faces.append(((B_, C_, D_), slot))
```

四边形拆三角形时，对角线**按 `(i+j)` 的奇偶交替**。
不交替的话所有四边形都朝同一个方向切，网格会有系统性的斜纹，
平面着色下每块棱面的明暗会出现规律性的"人字纹"。

#### 13.1.10 顶点索引公式（后面要用）

```
索引 0            = 顶极点
索引 1 + j*NCOL + i = 第 j 环第 i 列
最后那个           = 底极点
```

`shade_face_edge()` 就是靠这个公式精确定位"脸盘最外一列"的顶点。

---

### 13.2 呆毛：一条脊，不是尖刺

```python
ridge = [                      # (y, 脊线 z, 基座半宽)
    (0.092, 0.1435, 0.020),
    (0.058, 0.1690, 0.030),
    ...
]
```

每行撒 3 个点（左脚 L、脊线 T、右脚 R），行与行之间连两个四边形（左侧斜面 + 右侧斜面），
最后封两端和底面。

"宽而低的脊"而不是"细尖刺"——因为参考图里那撮毛正视宽 36 px（≈0.063 m），
只比头顶高 1~2 cm。做成尖刺会读成一根天线。

---

### 13.3 核心技术：**BVH 射线** —— 脸怎么"长"出五官

这是整个头部最关键的技术。五官不是"贴"上去的贴图，
而是**真的长在颅骨曲面上**——每一个顶点都先用射线打到颅骨，
再沿法线抬起一点点。

#### 13.3.1 建 BVH

```python
def make_bvh(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.transform(ob.matrix_world)
    bvh = BVHTree.FromBMesh(bm)
    bm.free()
    return bvh
```

BVH = **包围体层次**，一种"加速空间查询"的数据结构。
Blender 自带（`mathutils.bvhtree.BVHTree`），不用自己写。

它能回答一个问题：**"从 A 沿方向 D 射一条线，第一个打到哪个面？那个面的法线是什么？"**

#### 13.3.2 `hit()` —— 射线 + 法线

```python
def hit(bvh, origin, direction):
    loc, nor, idx, dist = bvh.ray_cast(origin, direction)
    if loc is None:
        raise RuntimeError("ray miss")
    if nor.dot(direction) > 0:      # 法线背对射线 → 翻过来
        nor = -nor
    return loc, nor
```

翻法线这步很重要：不翻的话，射线从 +Y 往 −Y 打，
拿到的法线可能朝里，用它抬起顶点就会把贴片**埋进脸里**。

#### 13.3.3 `front_point()` —— "在脸的正面投影上取一点"

```python
def front_point(bvh, x, z, off):
    """正面平行投影打到颅骨上，再沿 +Y（朝镜头）抬起 off。
    ⚠️ +Y 才是"脸外面"；写成 −Y 会把细线半埋、把纯平面填充整块埋进去。"""
    loc, nor = hit(bvh, Vector((x, 1.5, z)), Vector((0.0, -1.0, 0.0)))
    return loc + Vector((0.0, 1.0, 0.0)) * off
```

用的时候是 `(x, z)` 这样的**正面平面坐标**（不是三维坐标）：
从 `(x, 1.5, z)`（脸前方 1.5 m）往 −Y 打，命中颅骨。

**`off` 为什么是负数？**

眉毛 / 微笑弧 / 眯眼弧都是 `tube()` 扫出来的**细管**，
管半径 0.0042 m。如果把管的**中心线**放在表面 +0.0022，
整根管就浮在脸前面 2 mm，看起来像贴上去的塑料条。

所以中心线要**往里压** `off = −0.0022` → 管子有 2 mm 埋进脸里，
2 mm 露在外面 → 读起来像"长在脸上的线条"。

#### 13.3.4 `shell_disc()` —— 眼白为什么是个"壳"

```python
def shell_disc(verts, faces, bvh, x, z, radius, off, slot, segs=24,
               rings=(0.42, 0.72, 1.0)):
    """正面投影的圆片（单面，法线朝 +Y）：每个顶点先打到颅骨真实棱面上、再沿法线抬起 off。
    正面轮廓严格是圆，同时贴着脸走 —— 三层用不同 off 就绝不会互相穿插。"""
    def ring_pt(px, pz):
        loc, nor = hit(bvh, Vector((px, 1.5, pz)), Vector((0.0, -1.0, 0.0)))
        return loc + nor * off
    ...
```

**每个顶点独立地**打到颅骨上，再沿**该点的法线**抬起 `off`。
结果：这张圆片在正面看是**严格的正圆**，但每个点都贴着颅骨的曲面。

用 3 圈同心环（`rings=(0.42, 0.72, 1.0)`）+ 中心点，而不是一个大 n 边形——
因为轮廓点落在曲面上**不共面**，让 Blender 自由三角化会得到乱七八糟的形状。

**眼白要抬 3.5 mm，不是 1.5 mm**：

```python
# ⚠️ 抬高量不能只有 1.5 mm：脸是**曲面**，眼白外缘（半径 28 mm）比中心
# 靠后约 1.9 mm（r²/2R，R≈0.21 m），1.5 mm 的抬高会让**外缘被脸切掉**，
# 眼睛看着比参考图小一圈、边缘发暗。抬到 3.5 mm，整片眼白才完整露出来。
shell_disc(verts, faces, bvh, x, EYE_Z, SCLERA_R, 0.0035, "sclera",
           segs=10, rings=(0.62, 1.0))
```

原理：脸是个半径 R ≈ 0.21 m 的球面（`R = hw²/(fb·p)`，眼高处 `hw ≈ 0.150`、`fb ≈ 0.152`、`p = 0.70`）。
距离中心 r 处的球面，比中心靠后 `r²/(2R)`：

| r | `r²/(2R)` |
| --- | --- |
| 0.028 m（注释里按这个算的） | 1.85 mm |
| **0.0312 m**（`SCLERA_R` 的实际值） | **2.30 mm** |

如果眼白只抬 1.5 mm，那外缘就比脸还低 0.4~0.8 mm → **被脸切掉一圈**。
抬到 3.5 mm 才整片露出来。

#### 13.3.5 `flat_disc()` —— 瞳孔为什么是"平"的

```python
def flat_disc(verts, faces, x, z, y, radius, slot, segs=20):
    """纯平圆片（朝 +Y）：瞳孔 / 高光用，轮廓是干净的正圆、不会有棱面明暗块"""
```

瞳孔和高光用**纯平面圆片**，不用壳。
理由：低模的眼睛里，瞳孔是一个**实心深色圆**，
如果它跟着脸鼓起来，平面着色下会出现难看的棱面明暗块。
做成平的 → 颜色均匀、轮廓干净。

但平片放多深？—— 这是另一个坑：

```python
def surface_front_y(bvh, x, z, r):
    """(x,z) 周围一圈里**最靠前**（+Y 最大）的颅面 y —— 平面贴片放它前面就绝不会被顶穿。"""
    best = -1e9
    for k in range(20):
        a = 2.0 * math.pi * k / 20.0
        for rr in (0.0, 0.5, 0.85, 1.0):
            loc, _ = hit(bvh, Vector((x + r*rr*math.cos(a), 1.5, z + r*rr*math.sin(a))),
                         Vector((0.0, -1.0, 0.0)))
            best = max(best, loc.y)
    return best
```

在瞳孔周围采 20×4 个点，取**最靠前**的那个 y，
平片放在 `y0 + 0.0036` → 保证整块片都在眼白前面，不会被鼓起的脸顶穿。

高光再往前 1 mm：`y0 + 0.0046`。

#### 13.3.6 `face_plane()` / `plane_frame()` / `flat_plate()`

鼻孔是一片**斜着的小方片**（不是圆）：

```python
def face_plane(bvh, x, z, r):
    """在 (x,z) 附近扫一圈，返回 (贴片中心, 平均法线)。"""
    ctr, _ = hit(bvh, Vector((x, 1.5, z)), Vector((0.0, -1.0, 0.0)))
    ns = Vector((0.0, 0.0, 0.0))
    for k in range(16):
        a = 2.0 * math.pi * k / 16.0
        for rr in (0.5, 1.0):
            _, nor = hit(...)
            ns += nor
    return ctr, ns.normalized()
```

在周围采一圈法线**求平均** → 得到这片区域的"平均朝向"。
贴片按这个平面倾斜，才贴着脸又不陷进去。

`plane_frame(n)` 在这个平面上造一组正交基，还把 u/v **拉长**到
"正面投影正好是单位长度"——这样斜着贴的圆片在正面视图里仍然是正圆。

`flat_plate()` 最后拼出一个薄盒子（内圈 4 点 + 外圈 4 点 + 4 个侧面 + 1 个内面）。

---

### 13.4 五官逐个拆

#### 13.4.1 眼白 / 瞳孔 / 高光

```python
for side in (1, -1):
    x = EYE_X * side
    # ① 眼白：壳，10 段，2 圈
    shell_disc(verts, faces, bvh, x, EYE_Z, SCLERA_R, 0.0035, "sclera",
               segs=10, rings=(0.62, 1.0))
    # ② 瞳孔：平片，向鼻梁内偏 PUPIL_IN
    px = x - PUPIL_IN * side
    y0 = surface_front_y(bvh, px, EYE_Z, PUPIL_R)
    flat_disc(verts, faces, px, EYE_Z, y0 + 0.0036, PUPIL_R, "pupil", segs=10)
    # ③ 高光：更前 1 mm，偏向 +X/+Z（屏幕左上），两只眼同向
    flat_disc(verts, faces, px + GLINT_OFF[0], EYE_Z + GLINT_OFF[1],
              y0 + 0.0046, GLINT_R, "glint", segs=6)
```

**"高光在屏幕左上"**：`GLINT_OFF = (0.0050, 0.0053)`，两只眼**同向**——
因为光源在左上，两只眼的高光当然要同向。反过来做（对称偏移）会像斗鸡眼。

#### 13.4.2 眯眼弧（笑眼）

```python
arc = [(-0.024, -0.0030), (-0.013, 0.0056), (0.0, 0.0090),
       (0.013, 0.0056), (0.024, -0.0030)]
path = [front_point(bvh, x + dx, EYE_Z + dz, -0.0022) for dx, dz in arc]
tube(verts, faces, path, 0.0042, "mark", sides=4)
```

一条**向上拱**的短弧 —— 那是"笑眯了眼"。

> ⚠️ m3f 脚本后来又补了一对 `EyeBlink_L/R`，
> 那是一条**向下弯**的弧（眨眼）。两种弧长得完全不一样，必须分开做。
> 脚本头部的注释写得很清楚：
> "共用头那对 `EyeShut` 是**向上**拱的弧 = 开心眯眼；两种要分开。"

#### 13.4.3 微笑：Catmull-Rom + 变半径

```python
path = [front_point(bvh, q.x, q.y, -0.0022) for q in catmull_rom(MOUTH_PTS, 2)]
n = len(path)
radius = [MOUTH_R * (0.70 + 0.30 * math.sin(math.pi * i / (n - 1.0))) for i in range(n)]
tube(verts, faces, path, radius, "mark", sides=4)
```

两处讲究：

**① 半径两端收细** —— `sin(π·i/(n-1))` 从 0 升到 1 再降到 0，
所以管子的**两端半径只有中间的 70%**，端盖不会在嘴角露出两个小疙瘩。

**② 控制点故意稀**：

```python
# 控制点比「够用」更稀：Catmull-Rom 会补出中间点，多写的控制点在成品里根本看不出来，
# 只是白白把笑脸那段管子拉成 50 多环（曾经 636 三角面，占整颗头预算的 3 成）。
MOUTH_PTS = [
    (0.0553, -0.0895), (0.0272, -0.1017), (-0.0009, -0.1043),
    (-0.0289, -0.0991), (-0.0500, -0.0886),
    (-0.0553, -0.0780), (-0.0605, -0.0737), (-0.0658, -0.0728),
    (-0.0705, -0.0757), (-0.0702, -0.0705),
]
```

**低模不是"细节多"，是"面块少而读得懂"。**
10 个控制点 → `catmull_rom(MOUTH_PTS, 2)` 出 19 个路径点 → 19 圈 × 4 边 ≈ **150 个三角面**。
控制点写到 20 个 → 路径点翻倍 → 面数翻倍，出来的东西**一模一样**。

#### 13.4.4 大笑 / 惊恐：`mouth_mesh()`

```python
def mouth_mesh(bvh, outline, slot_fill, slot_lip, rim, tongue=None):
    """把一张 (x, z) 轮廓做成"贴脸上的洞"：腔底 + 外圈描边 + 可选舌头。"""
    # ① 有向面积 < 0 说明是顺时针，翻过来，保证填充面朝 +Y
    area = 0.0
    for i in range(len(pts)):
        x0, z0 = pts[i]; x1, z1 = pts[(i + 1) % len(pts)]
        area += x0 * z1 - x1 * z0
    if area < 0.0:
        pts.reverse()

    # ② 腔底：每个轮廓点打到颅面，**朝镜头方向**抬一点点
    # ⚠️ 写成负的（往里压）整块暗腔会埋进脸里，渲染出来只剩一圈描边。
    for q in pts:
        loc, nor = hit(bvh, Vector((q.x, 1.5, q.y)), Vector((0.0, -1.0, 0.0)))
        fill.append(len(verts))
        verts.append(loc + nor * 0.0012)

    # ③ 填充用**中心扇形**而不是一个大 n 边形：轮廓点落在曲面上不是共面的，
    #    一个 12 边形让 Blender 自由三角化会得到乱糟糟的形状。
    for i in range(n):
        faces.append(((ci, fill[i], fill[(i + 1) % n]), slot_fill))

    # ④ 外圈描边：沿轮廓扫一根细管
    path = [front_point(bvh, q.x, q.y, -0.0016) for q in pts]
    tube(verts, faces, path, rim, slot_lip, sides=4)

    # ⑤ 舌头：比腔底浅一点
    verts.append(loc + nor * 0.0022)
```

三个必记的点：

| 做法 | 不做会怎样 |
| --- | --- |
| 有向面积判断 + 翻转 | 腔底的面朝 −Y → 背面剔除 → **嘴是个黑洞** |
| 中心扇形而不是 n 边形 | 轮廓点不共面 → 三角化乱 → 嘴像一朵"花瓣" |
| 舌头抬 0.0022 > 腔底 0.0012 | 共面 → **z-fighting** → 舌头被咬掉一半，渲染成两瓣碎粉色 |

#### 13.4.5 眉毛 / 鼻孔

```python
# 眉毛：内端高、外端低的一道斜杠
dz = math.tan(BROW_TILT) * BROW_LEN * 0.5
for i in range(5):
    u = i / 4.0
    x = BROW_X * side + (u - 0.5) * BROW_LEN * side
    z = BROW_Z + dz * (1.0 - 2.0 * u)
    arc.append(front_point(bvh, x, z, -0.0016))
tube(verts, faces, arc, BROW_THICK * 0.5, "mark", sides=4)
```

`BROW_TILT = 21°` → 眉毛是斜的（内端高、外端低），这是猴脸的关键特征。

鼻孔是**两片小扁片**，旋转 −14°（左右镜像）：

```python
flat_plate(verts, faces, c, Vector((0.0, 1.0, 0.0)),
           Vector((1.0, 0.0, 0.0)), Vector((0.0, 0.0, 1.0)),
           0.0068, 0.0028, math.radians(-14.0 * side), "mark", 0.0014)
```

---

### 13.5 耳朵：一个**碗**

```python
def build_ear(side):
    """挖了坑的盘：外圈厚毛边 + 凹进去的橘色盘底。"""
    n = Vector((EAR_N.x * side, EAR_N.y, EAR_N.z)).normalized()
    up = Vector((0.0, 0.0, 1.0))
    e2 = (up - n * up.dot(n)).normalized()      # 耳盘竖直方向
    e1 = e2.cross(n).normalized()               # 耳盘横向
    C = Vector((EAR_X * side, EAR_Y, EAR_Z))

    rings = [(1.00, 1.00, -0.014), (1.00, 1.00, 0.002), (0.95, 0.96, 0.010),
             (0.88, 0.92, 0.014), (0.76, 0.86, 0.008), (0.56, 0.80, 0.003)]
```

每环是 `(椭圆x系数, 椭圆y系数, 沿法线的深度)`：
深度从 −0.014（外缘在毛皮里）→ +0.014（毛边内唇最高）→ 往里降到 0.003（碗底），
所以耳朵是**真的凹进去**的一个碗。

**耳朵朝向是反解出来的**：

```python
# 盘面法线（右耳；左耳镜像）：离 +Y 轴 30°（正对前方偏外）。
# 由参考图两个投影量反解：正面 x 向投影 0.106 m、侧面 y 向投影 0.061 m
#   x 向投影 = 2·rx·√(1−n_x²)，y 向投影 = 2·rx·√(1−n_y²)  →  tan φ = 0.061/0.106
EAR_N = Vector((0.500, 0.866, 0.05))
```

从参考图的**两个投影量**解出法线方向 —— 这是"量参考图 → 反解参数"的典型例子。

两个细节：

- `EAR_VAR` 让轮廓半径**逐段微抖**，避免读成一个规整的多边形垫圈
- `UP_SHIFT` 让盘底整体往上偏 → 下缘的毛边比上缘厚（和参考图一致）

> ⚠️ **背面必须封口**：耳朵是个"碗"，碗口朝前。不封背面的话，
> 从脑后看进去直接看见碗底的**橘色耳窝**，耳朵正反面分不清。

---

### 13.6 组装 + 表情

```python
head = build_skull()
tuft = build_tuft()
bvh = make_bvh(head)                  # ← 颅骨建完才能建 BVH
eye_parts = build_eye_parts(bvh)
mouth_parts = build_mouth_parts(bvh)
mark_parts = build_mark_parts(bvh)
ear_l = build_ear(-1); ear_r = build_ear(+1)

MESHES = STATIC + eye_parts + mouth_parts + mark_parts
OBJ = {ob.name: ob for ob in MESHES}
for ob in MESHES:
    if ob is not head:
        ob.parent = head              # ← 全部挂成颅骨的子物体
for nm in HIDDEN:                     # 静止时藏在颅骨内部
    OBJ[nm].location = OBJ[nm].location + PARK
```

`PARK = Vector((0.0, -0.060, 0.0))` → 往脑袋里退 6 cm = 看不见。

> ⚠️ `bvh` 必须在**重建颅骨之后**再建 —— 五官要打在**新**颅骨上。

---

### 13.7 m3f 脚本对头做的 8 处改造

`m3f_parts_monkey.py` 第 6 章（578~997 行）把共用的头改了 8 处：

| # | 改造 | 为什么 |
| --- | --- | --- |
| 1 | 颅骨从 12 环 × 8 列 → **31 环 × 31 列** | 12 环时脸的侧边每列跨 28°，头侧只剩几个大面 |
| 2 | 换掉 `MH.col_az` → `col_az_dense` | 共用版的列分布不均：脸的侧边 4 列、后脑最后一条闭合边跨 57°（整个后脑只有 2 个大面） |
| 3 | `SIDE_LIMIT` 整表 **× 0.86** | 不收窄的话橘色铺满整张正脸，两侧看不到毛的轮廓 |
| 4 | **删旧五官 → 重建颅骨 → 用新 BVH 重贴** | 颅骨加密后曲面外挪 1~2 mm，旧五官埋进脸里（微笑弧直接看不见） |
| 5 | `shade_face_edge()` 染一圈**过渡色** | 共用版按对角线拆三角形 → 颜色边界落在对角线上 → 锯齿线 |
| 6 | **重做耳朵**（`build_ear()`，16 段碗形） | 共用版是 8 边扁盘，像两枚别针；新版本耳心嵌进颅骨，外沿只探出 0.045 m |
| 7 | **重做 3 张嘴**（`build_mouth_mesh()`） | 共用版是尖角多边形 → 渲染出来是一坨黑疙瘩 |
| 8 | **补 4 个表情件** | `EyeBlink_L/R`（眨眼）、`MouthFlat`（抿嘴）、`MouthPants`（跑步喘气） |

#### 13.7.1 `col_az_dense`：把列分匀

```python
NCOL_FACE_DENSE = 12
NCOL_FUR_DENSE  = 9

def col_az_dense(i, A):
    nf = MH.NCOL_FUR
    nface = MH.NCOL_FACE
    if i < nf:                                  # 左毛区（9 列，不含边界）
        return -math.pi + (math.pi - A) * ((i + 0.5) / nf)
    if i <= nf + nface:                         # 脸盘（13 列，含两端 ±A）
        return -A + 2.0 * A * ((i - nf) / float(nface))
    j = i - nf - nface - 1                      # 右毛区（9 列）
    return A + (math.pi - A) * ((j + 0.5) / nf)
```

和共用版比，只有**一处**写法不同：毛区用 `(i + 0.5) / nf` 而不是 `i / nf`。
这一处把毛区的列**居中**在各自的区间里，两端各留**半步**，
于是闭合缝正好是**一整步**、左右对称。

实测（取 A = 1.10 rad，也就是脸盘半角 63°）：

| | 共用版 (nf=2, nface=4) | dense 版 (nf=9, nface=12) |
| --- | --- | --- |
| 总列数 | 8 | **31** |
| 毛区每列跨度 | 58.5° | **13.0°** |
| 脸盘每列跨度 | 31.5° | **10.5°** |
| 毛区 ↔ 脸盘接缝 | 0°（列正好落在 ±A 上） | 6.5°（半步） |
| **闭合缝（后脑）** | **58.5°** | **13.0°**（一整步） |
| 整个后脑有几个大面 | **2 个** | 正常的一列一步 |

共用版 `i / nf` 的问题是：**最外一列正好落在边界角 ±A 上**，
闭合缝因此撑成一整个毛区跨度（58.5°）—— 整个后脑只剩两个大面。
"一转背就露"就是这么来的。

列数必须配套改：

```python
MH.NCOL = 2 * NCOL_FUR_DENSE + NCOL_FACE_DENSE + 1      # = 2×9 + 12 + 1 = 31
```

> ⚠️ **那个 `+1` 不能省**：dense 版的脸盘分支是 `i <= nf + nface`（**含**两端），
> 毛区分支是 `i < nf`（**不含**边界）→ 脸盘分支多出一个列。
> 总数得写成 `2*NCOL_FUR + NCOL_FACE + 1`。
> 共用版能写成 `NCOL_FUR + NCOL_FACE + 2*NCOL_FUR`，是因为它的毛区分支
> 用的是 `i <= NCOL_FUR`（**含**边界），左右毛区**共用**了脸盘的两个端点列。
> 照抄共用版的公式 → 列数对不上 → 环会自己叠起来，出零面积三角 / 折痕。

#### 13.7.2 `shade_face_edge()`：把锯齿线变回干净的边

问题根源：共用头是**按对角线**把每个四边形拆成两个三角形再逐面上色的，
所以"脸盘 ↔ 毛"的颜色边界落在**对角线**上 → 边界沿对角线来回跳 = 锯齿线。

解法：把边界那一圈**整个四边形**染成同一种过渡色（`tan_shadow`）。

```python
def shade_face_edge(head):
    me = head.data
    ncols = MH.NCOL
    i_last_face = MH.NCOL_FUR + MH.NCOL_FACE       # 脸盘最外一列（+A 侧）= 21
    pairs = set()
    for j in range(nrows):
        a = 1 + j * ncols + i_last_face
        pairs.add((a, a + 1))                     # +A 侧：脸盘最外一列 ↔ 毛区第一列
        b = 1 + j * ncols + (MH.NCOL_FUR - 1)      # -A 侧：毛区最后一列 ↔ 脸盘第一列
        pairs.add((b, b + 1))
    ...
    for poly in me.polygons:
        vs = list(poly.vertices)
        for a, b in pairs:
            if a in vs and b in vs:
                poly.material_index = shadow_idx   # 整个四边形的两个三角形都被染
                break
```

**为什么按顶点索引找，而不是按面心？**

因为 `build_skull()` 拆三角形时对角线是**按 `(i+j)` 奇偶交替**的，
同一个四边形的两个三角形可能各自"缺"一个边界顶点：

```
四边形 = (A_=col21_j, B_=col22_j, C_=col22_{j+1}, D_=col21_{j+1})
偶数拆法: tri1=(A_,B_,C_)   tri2=(A_,C_,D_)
奇数拆法: tri1=(A_,B_,D_)   tri2=(B_,C_,D_)
```

但 `pairs` 是**所有环一起收集**的：
一个三角形如果没命中第 j 环的那一对，它一定含有第 j+1 环的某一对
（例：奇数拆法的 `tri2=(B_,C_,D_)` 含 `col22_{j+1}` 和 `col21_{j+1}`）→ 照样被染上。

把 `build_skull` 的索引生成 + `shade_face_edge` 的匹配逻辑单独跑一遍实测：
**60 个边界四边形 / 120 个面片，命中 2/2 —— 一个都没漏。**

所以颜色边界回到了**四边形的边上**（一条干净的线）+ 一圈柔和过渡。

> ⚠️ 顶点索引公式是 `1 + j*ncols + i`（第 0 号被顶极点占了）。

#### 13.7.3 偏置只能加一次

```python
off = Vector((0.0, 0.0, HEAD_C_Z - NECK_Z))       # = 0.440 - 0.295 = 0.145
for ob in MH.MESHES:
    if ob is head_root:
        continue
    ob.location = off + Vector(ob.location) * HEAD_SCALE   # 位置搬过去
    for v in ob.data.vertices:
        v.co = v.co * HEAD_SCALE                          # 顶点缩放
for v in head_root.data.vertices:
    v.co += off                                           # 颅骨：只加在顶点上
head_root.location = Vector((0.0, 0.0, 0.0))
```

共用头的五官是**颅骨的子物体**（`parent = head`），
颅骨的"离地高度"加在**颅骨顶点**上，五官的 `location` 就**不能再加一次**。

加两次的后果：头飞到半空（实测颅心跑到 0.89 m）。

#### 13.7.4 重做的零件要自己藏

```python
EXTRA_HIDDEN = [PREFIX + "_EyeBlink_L", PREFIX + "_EyeBlink_R",
                PREFIX + "_EyeShut_L", PREFIX + "_EyeShut_R",
                PREFIX + "_MouthLaugh", PREFIX + "_MouthFear",
                PREFIX + "_MouthFlat", PREFIX + "_MouthPants"]
PARK = Vector((0.0, -0.060, 0.0))
for nm in EXTRA_HIDDEN:
    MH.OBJ[nm].location = MH.OBJ[nm].location + PARK
```

共用头在自己的模块里把 `MouthLaugh / MouthFear / EyeShut` 藏好了。
m3f **重做**了这几张嘴（换了网格、换了名字）→ **没人藏它们了** →
大笑嘴一直挂在脸上，和微笑弧叠在一起，看起来就是"嘴很奇怪、好像重叠"。

**重做共用头的零件时，藏的动作要自己补一遍。**

#### 13.7.5 重做的嘴：腔底要 2 圈

```python
outer = fill_ring(pts)                            # 外圈
inner = fill_ring([cc + (q - cc) * 0.55 for q in pts])   # 内圈（缩 55%）
ctr = len(verts)
verts.append(surf(cc.x, cc.y))                    # 中心点
for i in range(n):
    faces.append(((ctr, inner[i], inner[j])))          # 中心扇形
    faces.append(((inner[i], outer[i], outer[j])))      # 外带
    faces.append(((inner[i], outer[j], inner[j])))
```

共用版的腔底是「一圈点 + 中心点」的**单圈扇面**：
扇形的**弦**会切进鼓着的颅骨里 → 中间露出**脸色的面** → 嘴像一朵"花瓣"。

2 圈同心环 + 中心点 → 每块三角形都短 → 弦切不进去 → 口腔是一整片深色。

---

### 13.8 头部相关的坑（速查）

| # | 坑 | 症状 | 解法 |
| --- | --- | --- | --- |
| 1 | `HAIR_ROW = 4` 被破坏 | 整个额头染成橘色，脸像大面具 | 发际线环必须留在索引 4 |
| 2 | 重建颅骨后没重贴五官 | 微笑弧看不见 | 删旧五官 → 重建 → 用新 BVH 重贴 |
| 3 | `col_az` 的列分布不均 | 后脑只有 2 个大面 | 换 `col_az_dense`，列数配套改 31 |
| 4 | `NCOL` 算错（少那个 `+1`） | 环叠起来，出零面积三角 | `2*NCOL_FUR + NCOL_FACE + 1` = 31 |
| 5 | 颜色边界落在对角线上 | 脸的侧边是锯齿线 | `shade_face_edge()` 整圈染过渡色 |
| 6 | 眼白只抬 1.5 mm | 外缘被脸切掉，眼睛小一圈发暗 | 抬 3.5 mm（球面高差 `r²/2R ≈ 1.9 mm`） |
| 7 | 细线 `off` 取正 | 线浮在脸前面，像塑料条 | `off` 取负，把管子埋一半进去 |
| 8 | 腔底只 1 圈 | 弦切进颅骨，嘴像花瓣 | 2 圈 + 中心点 |
| 9 | 舌头和腔底共面 | z-fighting，舌头被咬掉一半 | 舌头抬 0.0046 > 腔底 0.0022 |
| 10 | 偏置加两次 | 头飞到半空（颅心 0.89 m） | 颅骨顶点加，五官位置只搬不加 |
| 11 | 重做的嘴没人藏 | 两张嘴同框 | 补 `EXTRA_HIDDEN` |
| 12 | 耳朵背面不封口 | 从脑后看见橘色耳窝 | 背面封一个朝 −n 的棕色扇面 |
| 13 | 顺时针轮廓 | 腔底朝 −Y，嘴是黑洞 | 有向面积判断后 `reverse()` |
| 14 | 控制点写太密 | 面数翻倍，形状一模一样 | Catmull-Rom 会补点，控制点宜稀 |

---

### 13.9 一句话总结

> **头 = 四张量出来的侧影表 × 一条横截面公式 → 撒成一张球面网格；
> 五官 = 拿 BVH 射线打到这张网格上，每个顶点沿法线抬起一点点。**

前者负责"像不像"，后者负责"贴不贴得住"。
两者合起来，才是一只既像参考图、又能做表情的 low-poly 猴头。

---

## 14. 一页速查

```
脚本 = 一堆参数 + 一堆构造函数 + 一堆断言

三个造型手法：
  车削    给剖面表 (z, rx, ry)，绕轴转一圈        → 躯干、脖子
  放样    路径 + 标架 + 截面，扫出管子            → 手臂、腿、尾巴
  参数曲面 f(az, el) → (x,y,z)                   → 头

头（见第 13 章）：
  四张侧影表 (PROFILE/FRONT/BACK/MUZZLE) × 横截面公式 → 颅骨
  BVH 射线打到颅骨 + 沿法线抬起                     → 五官

动画：
  关键帧表 → 每个物体一个 action → 同名 NLA 轨 → 导出器按轨名合成片段

坑：
  偏置只加一次 / clear() 会清槽位 / 整段不变的通道会被丢
  strip 要给帧范围 / 撤 action 不回静止位 / 贴面壳要 4 圈
  发际线环必须留在索引 4 / 眼白要抬 3.5mm 不然被脸切掉 / 细线 off 取负
```

---

**相关文档**

- `assets/AGENTS.md` §1（尺寸硬规矩）、§2.11（本资产的规格）、§2.1（带动画资产的导出套路）
- `assets/AGENTS.md` §6.8（怎么读 `.glb` 的 JSON）
- `assets/models/_shared/monkey_head.py`（共用头 —— 第 13 章逐行拆的就是它）
- `assets/models/ds-monkey-trunk/ds_monkey_trunk.py`（四肢 + 尾巴的工具库）

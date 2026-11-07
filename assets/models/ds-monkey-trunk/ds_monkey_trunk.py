# -*- coding: utf-8 -*-
"""
ds_monkey_trunk.py —— 猴子的「四肢 + 尾巴」5 件套（只做四肢和尾巴）

参考图：assets/models/ds-monkey-trunk/reference.png（2×2 四视图，与 ds-monkey-body 同一张）

产物：**5 个独立模型**，每个都是**一个网格物体**（没有关节层级、没有 armature），
结构精简、面数很低，可以直接挂到躯干（`ds-monkey-body`）的关节锚点上：

    ds_monkey_trunk_arm_r.glb   右臂：肩 → 肘 → 腕 → 手掌（3 指 + 拇指）
    ds_monkey_trunk_arm_l.glb   左臂：右臂网格 X 镜像（**手完全对称**）
    ds_monkey_trunk_leg_r.glb   右腿：胯 → 膝 → 踝 → 脚掌（3 趾）
    ds_monkey_trunk_leg_l.glb   左腿：右腿网格 X 镜像（**脚完全对称**）
    ds_monkey_trunk_tail.glb    尾巴：一条 Catmull-Rom 大钩，单段

左右不是「各建一遍」，而是**只建右边、左边由右边镜像得到**（顶点逐点取负、面绕序反转），
所以左/右手的每一个顶点都严格互补，不可能出现"两只手长得不一样"。
脚本里 `audit_symmetry()` 会逐顶点核对，并打印两边一致的结论。

坐标与尺度
----------
* 单位：米（1 Blender unit = 1 m），公制。
* 世界 +Z 向上，面朝 **+Y**（导出 glTF 后 Godot 里 −Z 向前）。
* 每个模型的**原点（pivot）就在它的关节上**，模型按"挂上去之后的位置"建：
    - 手臂 pivot = 肩关节，几何朝下、略外张
    - 腿   pivot = 髋关节，脚底正好落在世界 z = 0
    - 尾巴 pivot = 尾根（胯后）
  导出的 `.glb` 里物体位置归零，锚点坐标见下表 §「关节锚点」——
  在 Godot 里把它们摆到锚点上就是完整的一套四肢。
* 所有物体 scale = 1、rotation = 0（镜像烘进网格，**不用负缩放**）。

关节锚点（= `ds-monkey-body` 的关节位置，可直接替换它自带的四肢）
----------------------------------------------------------------
| 模型 | 锚点（Blender / 米） | Godot（+Y 向上） |
| --- | --- | --- |
| 右臂 | ( +0.090, 0.000, 0.238 ) | ( +0.090, 0.238, 0.000 ) |
| 左臂 | ( −0.090, 0.000, 0.238 ) | ( −0.090, 0.238, 0.000 ) |
| 右腿 | ( +0.044, 0.000, 0.142 ) | ( +0.044, 0.142, 0.000 ) |
| 左腿 | ( −0.044, 0.000, 0.142 ) | ( −0.044, 0.142, 0.000 ) |
| 尾巴 | ( 0.000, −0.078, 0.134 ) | ( 0.000, 0.134, +0.078 ) |

低多边形做法
------------
* ⭐ **四肢是「一根沿曲线放样的六棱管」，不是「关节球 + 锥台」**：
  肩 / 肘 / 腕是**同一条 Catmull-Rom 曲线上的三个点**，肘只是曲线上的一个弯。
  之前用球 + 管拼过一轮，两个问题：① 6 棱 × 2 环的球顶点是尖的，肩 / 胯球从
  胳膊上冒出来像根刺；② 两段锥台在肘部对撞，留下一圈生硬的折角。
  换成一根管之后：没有尖、没有折角，面数还更少。肩 / 胯那头用**半球形圆头**收口。
* **手掌 / 脚掌 = 六边形截面放样**（不是方盒子），末端挂 3 根 5 棱短指 / 短趾 +
  1 根拇指 —— 参考图的手脚都是这个结构，手和脚因此"长得一套"。
  手指的**指缝要留出来**（指距 18.5 mm > 指径 17 mm），否则糊成一块。
* **手掌的第一环要缩在前臂里面**（半厚 0.021 < 前臂半径 0.0264）：
  反过来把第一环放大到"包住前臂"，前臂六边形的两个角会**从掌背上顶出两根棕刺**。
* **尾巴 = Catmull-Rom 曲线 + 平行传导标架扫 6 棱管**（不会像逐段直线那样扭麻花），
  并且**要往侧向甩出去**（x 最大 0.114）：只在 YZ 平面里画的话，背视图里尾巴
  被脑袋整个挡住，只剩一根贴背的竖线。
* 全平直着色（`use_smooth = False`），一格四边形一个法线 = 一块干净棱面。
* 面数（三角面）：手臂 190、腿 158、尾巴 104，**五件合计 800 面**、2 个材质槽。

产物
----
ds_monkey_trunk_arm_r/l.glb      手臂模型（各自独立）
ds_monkey_trunk_leg_r/l.glb      腿模型（各自独立）
ds_monkey_trunk_tail.glb         尾巴模型
ds_monkey_trunk_parts.png        五件套并排图（同一比例，带标签）
ds_monkey_trunk_fit.png          装到 ds-monkey-body 上的四视图（核对锚点 / 比例）
ds_monkey_trunk.blend            Blender 源文件（只有这 5 件，摆在装配位置）

运行::

    blender --background --factory-startup --python ds_monkey_trunk.py
"""

import bpy
import bmesh
import math
import os

from mathutils import Vector, Matrix

HERE = os.path.dirname(os.path.abspath(__file__))
BODY_BLEND = os.path.join(HERE, "..", "ds-monkey-body", "ds_monkey_body.blend")
PARTS_PNG = os.path.join(HERE, "ds_monkey_trunk_parts.png")
FIT_PNG = os.path.join(HERE, "ds_monkey_trunk_fit.png")
BLEND_PATH = os.path.join(HERE, "ds_monkey_trunk.blend")
RENDER_DIR = os.path.join(HERE, "_render_tmp")

PREFIX = "DSMonkeyTrunk"

# 当作**零件库**被别的脚本 import 时，只建几何，不导出、不渲染
# （否则 import 会顺手覆盖自己的 .glb / 预览图，还把身体的 .blend 借进场景）
STANDALONE = (__name__ == "__main__")


# =====================================================================
# 0. 干净起点 + 公制
# =====================================================================
bpy.ops.wm.read_homefile(use_empty=True, use_factory_startup=True)
scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'
scene.unit_settings.scale_length = 1.0
scene.render.fps = 30
for act in list(bpy.data.actions):
    bpy.data.actions.remove(act)


# =====================================================================
# 1. 关节锚点（与 assets/models/ds-monkey-body 的 ARM / LEG 完全一致）
# =====================================================================
# 只写「右半边 + 中线」，左半边由镜像生成。
SHOULDER_R = Vector((0.090, 0.000, 0.238))
ELBOW_R = Vector((0.122, 0.000, 0.180))
WRIST_R = Vector((0.128, 0.014, 0.118))

HIP_R = Vector((0.044, 0.000, 0.142))
KNEE_R = Vector((0.050, 0.004, 0.078))
ANKLE_R = Vector((0.052, 0.000, 0.032))

TAIL_BASE = Vector((0.000, -0.078, 0.134))

# 手掌 / 脚掌的外形参数
HAND_END = 0.024            # 腕 → 指根的长度（沿手掌轴）
FINGER_LEN = 0.015
FINGER_R0, FINGER_R1 = 0.0085, 0.0050
THUMB_LEN = 0.014

FOOT_SPLAY = math.radians(7.0)   # 脚尖外八的角度（左右镜像自动对称）

# 尾巴：侧视图里那条「向后甩、再卷上来、最后向前下钩住」的大问号
TAIL_PTS = [
    (0.000, -0.078, 0.134),
    (0.022, -0.132, 0.138),
    (0.055, -0.185, 0.172),
    (0.090, -0.215, 0.225),
    (0.105, -0.202, 0.280),
    (0.090, -0.164, 0.310),
    (0.062, -0.128, 0.300),
]
TAIL_RADII = [0.0150, 0.0146, 0.0140, 0.0134, 0.0126,
              0.0118, 0.0108, 0.0092, 0.0078]
TAIL_RINGS = len(TAIL_RADII)    # 每环一个半径：环数和半径表一一对应
TAIL_SIDES = 6


# =====================================================================
# 2. 材质（与共用头 / 身体的调色板同一组数）
# =====================================================================
PAL = {
    "fur": (0.478, 0.271, 0.153),   # #7A4527 == ds-monkey-body / monkey_head 的 fur
    "tan": (0.788, 0.561, 0.341),   # #C98F57 手脚：比脸略深一档（同 ds-monkey-body 的 tan_deep）
}
ROUGH = {"fur": 0.72, "tan": 0.70}
MAT_NAME = {"fur": "DSMonkeyTrunk_fur", "tan": "DSMonkeyTrunk_tan"}


def srgb2lin(c):
    def f(u):
        return u / 12.92 if u <= 0.04045 else ((u + 0.055) / 1.055) ** 2.4
    return (f(c[0]), f(c[1]), f(c[2]), 1.0)


def make_materials():
    mats = {}
    for key, rgb in PAL.items():
        mat = bpy.data.materials.new(MAT_NAME[key])
        mat.use_nodes = True
        mat.use_backface_culling = False
        bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
        lin = srgb2lin(rgb)
        bsdf.inputs["Base Color"].default_value = lin
        bsdf.inputs["Roughness"].default_value = ROUGH[key]
        for prop in ("Specular IOR Level", "Specular"):
            if prop in bsdf.inputs:
                bsdf.inputs[prop].default_value = 0.20
                break
        mat.diffuse_color = lin
        mats[key] = mat
    return mats


MATS = make_materials()


# =====================================================================
# 3. 网格工具
# =====================================================================
class Builder(object):
    """攒顶点 / 面（面带材质槽名），最后一次性建物体。"""

    def __init__(self):
        self.v = []
        self.f = []

    def add(self, co):
        self.v.append(Vector(co))
        return len(self.v) - 1

    def face(self, idx, slot):
        self.f.append((tuple(idx), slot))

    def tri(self, a, b, c, slot):
        self.face((a, b, c), slot)

    def quad(self, a, b, c, d, slot):
        self.face((a, b, c, d), slot)


def build_object(name, verts, faces, recalc=True):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], [f[0] for f in faces])
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)

    used = []
    for _, key in faces:
        if key not in used:
            used.append(key)
    for key in used:
        me.materials.append(MATS[key])
    idx = {k: i for i, k in enumerate(used)}
    for poly, (_, key) in zip(me.polygons, faces):
        poly.use_smooth = False
        poly.material_index = idx[key]

    if recalc:
        bm = bmesh.new()
        bm.from_mesh(me)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(me)
        bm.free()
    me.validate(verbose=False)
    me.update()
    return ob


def circle_pts(n, phase=0.0):
    return [(math.cos(2.0 * math.pi * k / n + phase),
             math.sin(2.0 * math.pi * k / n + phase)) for k in range(n)]


def basis_along(axis):
    """给一条轴配一组正交基（u, v）—— 参考向量不能和轴平行，否则会退化。"""
    t = Vector(axis).normalized()
    ref = Vector((0.0, 0.0, 1.0))
    if abs(t.dot(ref)) > 0.9:
        ref = Vector((0.0, 1.0, 0.0))
    u = t.cross(ref).normalized()
    v = t.cross(u).normalized()
    return u, v


def loft_rings(b, rings, slot, cap0=True, cap1=True):
    """rings = [[顶点索引, ...], ...]（每环点数相同），逐带连四边形。"""
    for j in range(len(rings) - 1):
        ra, rb = rings[j], rings[j + 1]
        n = len(ra)
        for i in range(n):
            i2 = (i + 1) % n
            b.quad(ra[i], ra[i2], rb[i2], rb[i], slot)
    if cap0:
        b.face(tuple(reversed(rings[0])), slot)
    if cap1:
        b.face(tuple(rings[-1]), slot)


def add_tube(b, p0, p1, r0, r1, slot, sides=6, cap0=True, cap1=True):
    """两点之间的 n 棱锥台（手指 / 脚趾）。端盖默认保留，反正会被手掌挡住。"""
    p0, p1 = Vector(p0), Vector(p1)
    u, v = basis_along(p1 - p0)
    rings = []
    for (p, r) in ((p0, r0), (p1, r1)):
        rings.append([b.add(p + u * (r * cx) + v * (r * cy))
                      for (cx, cy) in circle_pts(sides)])
    loft_rings(b, rings, slot, cap0=cap0, cap1=cap1)


def add_tube_path(b, pts, radii, slot, sides=6, round_start=False, round_end=False):
    """沿一条折线扫 n 棱管（半径逐点给），两端可选「半球圆头」。

    四肢就用它：肩 / 肘 / 腕是**同一条曲线上的三个点**，肘只是曲线上的一个弯，
    不是两段管子对撞出来的折角，也不需要往关节里塞球。
    """
    pts = [Vector(p) for p in pts]
    frames = frames_along(pts)
    rings = []
    pole_start = pole_end = None

    if round_start:
        t0 = (pts[1] - pts[0]).normalized()
        u0, v0 = frames[0]
        r0 = radii[0]
        # 从极点往外 0.80r / 0.45r 收两环 → 半球形的肩 / 胯
        # ⚠️ 顺序必须是「离极点最近的一环先建」，否则极点扇面会跨过中间那环
        for (back, sc) in ((0.80, 0.55), (0.45, 0.86)):
            c = pts[0] - t0 * (r0 * back)
            rings.append([b.add(c + u0 * (r0 * sc * cx) + v0 * (r0 * sc * cy))
                          for (cx, cy) in circle_pts(sides)])
        pole_start = b.add(pts[0] - t0 * r0)

    for i, p in enumerate(pts):
        u, v = frames[i]
        r = radii[i]
        rings.append([b.add(p + u * (r * cx) + v * (r * cy))
                      for (cx, cy) in circle_pts(sides)])

    if round_end:
        t1 = (pts[-1] - pts[-2]).normalized()
        u1, v1 = frames[-1]
        r1 = radii[-1]
        for (fwd, sc) in ((0.45, 0.86), (0.80, 0.55)):
            c = pts[-1] + t1 * (r1 * fwd)
            rings.append([b.add(c + u1 * (r1 * sc * cx) + v1 * (r1 * sc * cy))
                          for (cx, cy) in circle_pts(sides)])
        pole_end = b.add(pts[-1] + t1 * r1)

    n_side = sides
    for j in range(len(rings) - 1):
        ra, rb = rings[j], rings[j + 1]
        for k in range(n_side):
            k2 = (k + 1) % n_side
            b.quad(ra[k], ra[k2], rb[k2], rb[k], slot)

    if pole_start is not None:
        for k in range(n_side):
            k2 = (k + 1) % n_side
            b.tri(pole_start, rings[0][k2], rings[0][k], slot)
    if pole_end is not None:
        for k in range(n_side):
            k2 = (k + 1) % n_side
            b.tri(pole_end, rings[-1][k], rings[-1][k2], slot)
    if pole_start is None:
        b.face(tuple(reversed(rings[0])), slot)
    if pole_end is None:
        b.face(tuple(rings[-1]), slot)


def catmull_rom_3d(pts, samples_per_seg=8):
    P = [Vector(p) for p in pts]
    P = [P[0]] + P + [P[-1]]
    out = []
    for i in range(len(P) - 3):
        p0, p1, p2, p3 = P[i], P[i + 1], P[i + 2], P[i + 3]
        for s in range(samples_per_seg):
            t = s / float(samples_per_seg)
            t2, t3 = t * t, t * t * t
            out.append(0.5 * ((2.0 * p1) + (-p0 + p2) * t
                              + (2.0 * p0 - 5.0 * p1 + 4.0 * p2 - p3) * t2
                              + (-p0 + 3.0 * p1 - 3.0 * p2 + p3) * t3))
    out.append(P[-2])
    return out


def resample(path, n):
    """按弧长把折线重采样成 n 个点。"""
    acc = [0.0]
    for i in range(1, len(path)):
        acc.append(acc[-1] + (path[i] - path[i - 1]).length)
    total = acc[-1]
    out = []
    for k in range(n):
        d = total * k / float(n - 1)
        for i in range(1, len(acc)):
            if acc[i] >= d - 1e-9:
                t = (d - acc[i - 1]) / max(1e-9, acc[i] - acc[i - 1])
                out.append(path[i - 1].lerp(path[i], t))
                break
        else:
            out.append(path[-1])
    return out


def frames_along(pts):
    """平行传导标架：沿曲线逐点转过去，管子不会自己拧麻花。"""
    n = len(pts)
    tangents = []
    for i in range(n):
        if i == 0:
            t = pts[1] - pts[0]
        elif i == n - 1:
            t = pts[-1] - pts[-2]
        else:
            t = pts[i + 1] - pts[i - 1]
        tangents.append(t.normalized())
    u = basis_along(tangents[0])[0]
    frames = []
    for i, t in enumerate(tangents):
        if i > 0:
            u = u - t * u.dot(t)
            if u.length < 1e-7:
                u = basis_along(t)[0]
            u.normalize()
        v = t.cross(u).normalized()
        frames.append((u, v))
    return frames


def mirror_builder(src):
    """X 镜像：顶点取负 + 每个面的绕序反转（法线仍然朝外）。"""
    b = Builder()
    b.v = [Vector((-v.x, v.y, v.z)) for v in src.v]
    b.f = [(tuple(reversed(idx)), slot) for (idx, slot) in src.f]
    return b


def mirror_pt(p):
    return Vector((-p.x, p.y, p.z))


def make_part(name, b, anchor):
    """把世界坐标的网格烘成「锚点局部坐标」，物体摆在锚点上（scale = 1）。"""
    anchor = Vector(anchor)
    ob = build_object(name, [v - anchor for v in b.v], b.f)
    ob.location = anchor
    return ob


def tri_count(ob):
    return sum(len(p.vertices) - 2 for p in ob.data.polygons)


def bbox(ob):
    pts = [ob.matrix_world @ v.co for v in ob.data.vertices]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi


# =====================================================================
# 4. 手臂：肩 → 肘 → 腕（一根连续收细的六棱管）+ 手（3 指 + 拇指）
# =====================================================================
# ⚠️ 这里**不用「关节球 + 锥台」的拼接**：一段一段接起来，肘部会是一道折角，
# 球顶还会从肩头支出一根尖。整条手臂改成**沿曲线放样的一根管**——
# 肩 / 肘 / 腕是曲线上三个点，肘只是曲线上的一个弯，管子连续、收细、没有接缝，
# 三角面反而更少（一段拼接要 2 球 + 2 管，这里只要 9 环）。
ELBOW_R = Vector((0.122, 0.000, 0.180))
WRIST_R = Vector((0.128, 0.014, 0.118))

ARM_PATH = [
    SHOULDER_R,
    SHOULDER_R.lerp(ELBOW_R, 0.5),
    ELBOW_R,
    ELBOW_R.lerp(WRIST_R, 0.5),
    WRIST_R,
]
ARM_RADII = [0.0315, 0.0304, 0.0294, 0.0288, 0.0284,
             0.0274, 0.0264, 0.0248, 0.0206]   # 末端收细：管口整个缩进手掌里

# 手的六边形截面（u = 横向 / v = 前后），比正方盒子更接近参考图的"连指手套"
HAND_PROFILE = [(1.00, 0.00), (0.50, 0.95), (-0.50, 0.95),
                (-1.00, 0.00), (-0.50, -0.95), (0.50, -0.95)]
HAND_SECTIONS = [               # (沿手掌轴的距离, 横向半宽, 前后半厚)
    # ⚠️ 第一环要**缩在前臂里面**（半厚 0.021 < 前臂半径 0.0264），
    # 手掌是从袖口一样的胳膊里"长出来"的；反过来把第一环放大到包住前臂，
    # 前臂六边形的两个角就会从掌背上顶出两根棕色的刺（实测）。
    (-0.030, 0.0240, 0.0210),
    (0.000, 0.0292, 0.0240),
    (0.014, 0.0298, 0.0238),
    (0.024, 0.0268, 0.0198),
]


def hand_frame(wrist, tip):
    d = (tip - wrist).normalized()
    u = Vector((1.0, 0.0, 0.0))
    u = (u - d * u.dot(d)).normalized()
    v = d.cross(u).normalized()
    if v.y < 0.0:            # v 固定朝前（+Y），手背 / 手心才不会翻面
        v = -v
    return d, u, v


def add_hand(b, wrist, tip):
    """腕 → 掌（六边形放样）→ 3 根短指 + 1 根拇指。整只手 tan 色。

    参考图的手是**连指手套**：手掌厚、三根指头分得开、拇指从内侧挑出来。
    """
    wrist = Vector(wrist)
    d, u, v = hand_frame(wrist, tip)

    rings = []
    for (t, hu, hv) in HAND_SECTIONS:
        c = wrist + d * t
        rings.append([b.add(c + u * (hu * px) + v * (hv * py))
                      for (px, py) in HAND_PROFILE])
    loft_rings(b, rings, "tan")

    # 3 根指头：指缝要留出来（间距 18.5 mm > 指径 17 mm），不然糊成一块
    knuckle = wrist + d * (HAND_END - 0.003)
    for off in (-0.0185, 0.0, 0.0185):
        base = knuckle + u * off
        fdir = (d + u * (off * 2.0) + v * 0.12).normalized()
        add_tube(b, base, base + fdir * FINGER_LEN,
                 FINGER_R0, FINGER_R1, "tan", sides=4)

    # 拇指：长在手掌内侧（右边 = −X），朝下前方；起点埋进掌里，别像根刺
    tbase = wrist + d * 0.014 + u * (-0.025)
    tdir = (d * 0.94 - u * 0.28 + v * 0.10).normalized()
    add_tube(b, tbase, tbase + tdir * THUMB_LEN, 0.0090, 0.0066, "tan", sides=4)


def build_arm():
    b = Builder()
    tip = WRIST_R + Vector((0.002, 0.008, -0.046))    # 手掌方向：向下、略朝前
    add_tube_path(b, ARM_PATH, ARM_RADII, "fur", sides=6, round_start=True)
    add_hand(b, WRIST_R, tip)
    return b


# =====================================================================
# 5. 腿：胯 → 膝 → 踝（一根连续收细的六棱管）+ 脚（3 趾）
# =====================================================================
def foot_frame():
    """脚掌局部坐标：x = 横向，y = 脚尖方向（外八 7°）。"""
    rot = Matrix.Rotation(FOOT_SPLAY, 3, 'Z')
    ex = rot @ Vector((1.0, 0.0, 0.0))
    ey = rot @ Vector((0.0, 1.0, 0.0))
    return ex, ey


LEG_PATH = [
    HIP_R,
    HIP_R.lerp(KNEE_R, 0.5),
    KNEE_R,
    KNEE_R.lerp(ANKLE_R, 0.5),
    ANKLE_R,
]
LEG_RADII = [0.0390, 0.0378, 0.0366, 0.0352, 0.0338,
             0.0320, 0.0300, 0.0272, 0.0245]

FOOT_SECTIONS = [               # (相对踝的 Y, 半宽, 脚背高度 z)
    (-0.030, 0.024, 0.024),
    (-0.008, 0.034, 0.040),
    (0.018, 0.033, 0.030),
    (0.036, 0.030, 0.012),
]
TOE_BASE_Y = 0.028
TOE_R0, TOE_R1 = 0.0122, 0.0094


def add_foot(b, ankle):
    """脚掌 = 平底楔形放样（脚底严格 z = 0）+ 3 根短趾。

    脚趾**从脚掌前端伸出去**（不是贴在脚底下面），正面 / 侧面都能数出三根，
    和手的三根指头是同一套做法 —— 手和脚因此"长得一套"。
    """
    a = Vector(ankle)
    ex, ey = foot_frame()

    def P(x, y, z):
        return a + ex * x + ey * y + Vector((0.0, 0.0, z - a.z))

    rings = []
    for (y, hw, top) in FOOT_SECTIONS:
        rings.append([b.add(P(-hw, y, 0.0)),
                      b.add(P(+hw, y, 0.0)),
                      b.add(P(+hw, y, top)),
                      b.add(P(-hw, y, top))])
    loft_rings(b, rings, "tan")

    # 3 根短趾：贴着地面（底面离地 ~0.5 mm，不会穿地），中间一根最长
    for (xoff, tlen) in ((-0.0195, 0.022), (0.0, 0.025), (0.0195, 0.022)):
        base = P(xoff, TOE_BASE_Y, 0.0122)
        tdir = (ey + ex * (xoff * 1.4) + Vector((0.0, 0.0, 0.010))).normalized()
        add_tube(b, base, base + tdir * tlen, TOE_R0, TOE_R1, "tan", sides=4)


def build_leg():
    b = Builder()
    add_tube_path(b, LEG_PATH, LEG_RADII, "fur", sides=6, round_start=True)
    add_foot(b, ANKLE_R)
    return b


# =====================================================================
# 6. 尾巴：Catmull-Rom 大钩 + 平行标架扫管
# =====================================================================
def build_tail():
    b = Builder()
    path = resample(catmull_rom_3d(TAIL_PTS, 8), TAIL_RINGS)
    frames = frames_along(path)
    rings = []
    for i, p in enumerate(path):
        u, v = frames[i]
        r = TAIL_RADII[i]
        rings.append([b.add(p + u * (r * cx) + v * (r * cy))
                      for (cx, cy) in circle_pts(TAIL_SIDES)])
    loft_rings(b, rings, "fur")
    return b


# =====================================================================
# 7. 建 5 件（右手 / 右腿 / 尾巴 各建一次，左手 / 左腿 镜像）
# =====================================================================
arm_b = build_arm()
leg_b = build_leg()

PART_SPECS = [
    ("arm_r", "Arm_R", arm_b, SHOULDER_R, "右臂"),
    ("arm_l", "Arm_L", mirror_builder(arm_b), mirror_pt(SHOULDER_R), "左臂"),
    ("leg_r", "Leg_R", leg_b, HIP_R, "右腿"),
    ("leg_l", "Leg_L", mirror_builder(leg_b), mirror_pt(HIP_R), "左腿"),
    ("tail", "Tail", build_tail(), TAIL_BASE, "尾巴"),
]

PARTS = []
for (fname, tag, builder, anchor, label) in PART_SPECS:
    ob = make_part(PREFIX + "_" + tag, builder, anchor)
    ob["fname"] = fname
    ob["label"] = label
    PARTS.append(ob)

bpy.ops.object.select_all(action='DESELECT')
for ob in PARTS:
    ob.select_set(True)
bpy.context.view_layer.objects.active = PARTS[0]
bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)


# =====================================================================
# 8. 自检：对称 / 贴地 / scale / 面数
# =====================================================================
def key(v):
    return (round(v.x, 6), round(v.y, 6), round(v.z, 6))


def audit_symmetry(ob_r, ob_l, label):
    vr = [v.co.copy() for v in ob_r.data.vertices]
    vl = [Vector((-v.co.x, v.co.y, v.co.z)) for v in ob_l.data.vertices]
    assert len(vr) == len(vl), (label, len(vr), len(vl))
    assert sorted(map(key, vr)) == sorted(map(key, vl)), "%s 左右顶点不互补" % label
    assert len(ob_r.data.polygons) == len(ob_l.data.polygons), label
    assert [m.name for m in ob_r.data.materials] == [m.name for m in ob_l.data.materials], label
    print("  SYMMETRY OK  %-6s  %d 顶点 / %d 面 左右逐点互补"
          % (label, len(vr), len(ob_r.data.polygons)))


def report():
    print("=" * 78)
    print("DS MONKEY TRUNK —— 四肢 + 尾巴 5 件套")
    print("=" * 78)
    total_tris = 0
    for ob in PARTS:
        lo, hi = bbox(ob)
        t = tri_count(ob)
        total_tris += t
        assert all(abs(s - 1.0) < 1e-6 for s in ob.scale), ob.name
        assert all(abs(r) < 1e-6 for r in ob.rotation_euler), ob.name
        print("  %-24s verts %4d  faces %4d  tris %4d   bbox X %+.3f..%+.3f  Y %+.3f..%+.3f  Z %+.3f..%+.3f"
              % (ob.name, len(ob.data.vertices), len(ob.data.polygons), t,
                 lo.x, hi.x, lo.y, hi.y, lo.z, hi.z))
    legs_min_z = min(bbox(ob)[0].z for ob in PARTS if "Leg" in ob.name)
    arms_min_z = min(bbox(ob)[0].z for ob in PARTS if "Arm" in ob.name)
    print("  合计三角面 %d   |  腿脚最低点 z = %+.4f m（必须是 0）  手臂最低点 z = %+.4f"
          % (total_tris, legs_min_z, arms_min_z))
    print("=" * 78)
    return total_tris, legs_min_z


audit_symmetry(bpy.data.objects[PREFIX + "_Arm_R"], bpy.data.objects[PREFIX + "_Arm_L"], "手臂")
audit_symmetry(bpy.data.objects[PREFIX + "_Leg_R"], bpy.data.objects[PREFIX + "_Leg_L"], "腿")
TOTAL_TRIS, LEG_ZMIN = report()
assert abs(LEG_ZMIN) < 0.0015, "脚底必须落在 z = 0：%.4f" % LEG_ZMIN


# =====================================================================
# 9. 预览场景（灯 / 相机 / 世界）
# =====================================================================
def setup_preview():
    world = bpy.data.worlds.new("DSTrunkWorld")
    world.use_nodes = True
    bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs[0].default_value = (0.78, 0.78, 0.78, 1.0)
    bg.inputs[1].default_value = 0.32
    scene.world = world

    def add_area(name, loc, energy, size):
        ld = bpy.data.lights.new(name, 'AREA')
        ld.energy = energy
        ld.color = (1.0, 0.97, 0.93)
        ld.size = size
        ob = bpy.data.objects.new(name, ld)
        bpy.context.collection.objects.link(ob)
        ob.location = loc
        ob.rotation_euler = (Vector((0.0, 0.0, 0.20)) - Vector(loc)) \
            .to_track_quat('-Z', 'Y').to_euler()
        return ob

    add_area("DSTrunkKey", (1.9, 2.2, 2.4), 150.0, 1.8)
    add_area("DSTrunkFill", (-2.2, 1.5, 0.6), 55.0, 2.6)
    add_area("DSTrunkRim", (0.4, -2.4, 1.4), 60.0, 1.6)

    cam_data = bpy.data.cameras.new("DSTrunkCam")
    cam_data.type = 'ORTHO'
    cam_data.ortho_scale = 0.80
    cam = bpy.data.objects.new("DSTrunkCam", cam_data)
    bpy.context.collection.objects.link(cam)
    scene.camera = cam

    try:
        scene.render.engine = 'BLENDER_EEVEE'
    except TypeError:
        try:
            scene.render.engine = 'BLENDER_EEVEE_NEXT'
        except TypeError:
            pass
    scene.render.film_transparent = False
    scene.view_settings.view_transform = 'Standard'
    scene.view_settings.look = 'None'
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    if hasattr(scene, "eevee") and hasattr(scene.eevee, "taa_render_samples"):
        scene.eevee.taa_render_samples = 48
    return cam


CAM = setup_preview()


def render_to(path):
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


def load_rgba(path, w, h):
    import numpy as np
    for im in list(bpy.data.images):
        if im.filepath == path:
            bpy.data.images.remove(im)
    img = bpy.data.images.load(path, check_existing=False)
    a = np.array(img.pixels[:], dtype=np.float32).reshape(h, w, 4)
    bpy.data.images.remove(img)
    return a[::-1]


def save_rgba(buf, path, name):
    out = bpy.data.images.new(name, buf.shape[1], buf.shape[0], alpha=False)
    out.pixels = buf[::-1].ravel().tolist()
    out.filepath_raw = path
    out.file_format = 'PNG'
    out.save()


def aim_camera(cam, target, distance, ortho_scale, az_deg):
    az = math.radians(az_deg)
    cam.data.ortho_scale = ortho_scale
    cam.location = Vector((math.sin(az) * distance, math.cos(az) * distance, target.z))
    cam.rotation_euler = (target - cam.location).to_track_quat('-Z', 'Y').to_euler()


# =====================================================================
# 10. 存 .blend（在把 ds-monkey-body 借进场景之前存，免得把别人也写进来）
# =====================================================================
if STANDALONE:
    bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH)


# =====================================================================
# 11. 导出 5 个 .glb（每个模型都只有一个网格物体；原点在关节）
# =====================================================================
EXPORTS = []
for ob in (PARTS if STANDALONE else []):
    fname = ob["fname"]
    path = os.path.join(HERE, "ds_monkey_trunk_%s.glb" % fname)
    saved = ob.location.copy()
    ob.location = (0.0, 0.0, 0.0)
    bpy.context.view_layer.update()
    bpy.ops.object.select_all(action='DESELECT')
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.export_scene.gltf(
        filepath=path,
        export_format='GLB',
        use_selection=True,
        export_apply=True,
        export_yup=True,
        export_animations=False,
        export_cameras=False,
        export_lights=False,
    )
    ob.location = saved
    bpy.context.view_layer.update()
    EXPORTS.append(path)
    print("glb -> %s" % path)


# =====================================================================
# 12. 五件套并排图（同一比例，标了名字）
# =====================================================================
if not os.path.isdir(RENDER_DIR):
    os.makedirs(RENDER_DIR)


def add_label(text, x, z, size=0.026):
    cu = bpy.data.curves.new("lbl_" + text, type='FONT')
    cu.body = text
    cu.size = size
    cu.align_x = 'CENTER'
    cu.align_y = 'CENTER'
    ob = bpy.data.objects.new("lbl_" + text, cu)
    ob.data.materials.append(MATS["fur"])
    bpy.context.collection.objects.link(ob)
    ob.location = (x, 0.40, z)
    ob.rotation_euler = (math.radians(90.0), 0.0, math.radians(180.0))
    return ob


def render_parts():
    import numpy as np
    saved = [(ob, ob.location.copy()) for ob in PARTS]
    labels = []
    SPACING = 0.26
    for k, ob in enumerate(PARTS):
        lo, hi = bbox(ob)
        center = (lo + hi) * 0.5
        target = Vector(((2 - k) * SPACING, 0.0, 0.10))
        ob.location = ob.location + (target - center)
        labels.append(add_label(ob["label"], target.x, -0.055))
    bpy.context.view_layer.update()

    W, H = 1300, 520
    scene.render.resolution_x = W
    scene.render.resolution_y = H
    aim_camera(CAM, Vector((0.0, 0.0, 0.10)), 3.0, 1.46, 0.0)
    shot = os.path.join(RENDER_DIR, "parts.png")
    render_to(shot)
    a = load_rgba(shot, W, H)
    save_rgba(a, PARTS_PNG, "ds_monkey_trunk_parts")
    print("parts preview ->", PARTS_PNG)

    for ob, loc in saved:
        ob.location = loc
    for ob in labels:
        bpy.data.objects.remove(ob, do_unlink=True)
    bpy.context.view_layer.update()


if STANDALONE:
    render_parts()


# =====================================================================
# 13. 装配核对：把 ds-monkey-body 借进场景，删掉它自带的四肢 / 尾巴，
#     只留躯干 + 头，然后看这 5 件是不是正好长在上面
# =====================================================================
def append_body():
    if not os.path.exists(BODY_BLEND):
        print("!! 找不到 ds-monkey-body.blend，跳过装配核对：", BODY_BLEND)
        return []
    with bpy.data.libraries.load(BODY_BLEND, link=False) as (df, dt):
        dt.objects = [n for n in df.objects
                      if n.startswith("DSMonkeyBody") or n.startswith("DSMonkey")]
    objs = [o for o in dt.objects if o is not None]
    for o in objs:
        scene.collection.objects.link(o)
    bpy.context.view_layer.update()
    return objs


def drop_body_limbs():
    drop = ("DSMonkeyBody_Arm_", "DSMonkeyBody_Leg_", "DSMonkeyBody_Tail_",
            "DSBody")           # 后者的灯 / 相机也一起清掉
    for ob in list(bpy.context.scene.objects):
        if ob.name.startswith(drop):
            bpy.data.objects.remove(ob, do_unlink=True)
    bpy.context.view_layer.update()


def anchor_deltas():
    """拿身体对象的世界原点当锚点，和本脚本的常量对账。"""
    pairs = [
        ("DSMonkeyBody_Arm_R_Upper", SHOULDER_R, "肩 R"),
        ("DSMonkeyBody_Arm_L_Upper", mirror_pt(SHOULDER_R), "肩 L"),
        ("DSMonkeyBody_Leg_R_Thigh", HIP_R, "髋 R"),
        ("DSMonkeyBody_Leg_L_Thigh", mirror_pt(HIP_R), "髋 L"),
    ]
    print("  装配锚点核对（身体世界原点 vs 本脚本常量）：")
    for name, want, label in pairs:
        ob = bpy.data.objects.get(name)
        if ob is None:
            print("    %-6s %s（身体里没这个节点，跳过）" % (label, name))
            continue
        got = ob.matrix_world.translation
        d = (got - want).length
        print("    %-6s 身体 %s  本脚本 %s  差 %.4f m %s"
              % (label, tuple(round(v, 4) for v in got),
                 tuple(round(v, 4) for v in want), d,
                 "OK" if d < 0.003 else "!! 锚点已经变了"))
    tail = bpy.data.objects.get("DSMonkeyBody_Tail_1")
    if tail is not None:
        got = tail.matrix_world.translation
        print("    尾根   身体 %s  本脚本 %s  差 %.4f m"
              % (tuple(round(v, 4) for v in got),
                 tuple(round(v, 4) for v in TAIL_BASE), (got - TAIL_BASE).length))


def render_fit():
    import numpy as np
    objs = append_body()
    if not objs:
        return
    anchor_deltas()
    drop_body_limbs()

    views = [("front", 0.0), ("side", -90.0), ("back", 180.0), ("q34", 35.0)]
    W, H = 480, 600
    scene.render.resolution_x = W
    scene.render.resolution_y = H
    target = Vector((0.0, 0.0, 0.315))
    paths = []
    for name, az in views:
        aim_camera(CAM, target, 3.0, 0.78, az)
        path = os.path.join(RENDER_DIR, "fit_%s.png" % name)
        render_to(path)
        paths.append(path)

    buf = np.ones((H * 2, W * 2, 4), dtype=np.float32)
    for i, path in enumerate(paths):
        a = load_rgba(path, W, H)
        r, c = divmod(i, 2)
        buf[r * H:r * H + H, c * W:(c + 1) * W] = a
    save_rgba(buf, FIT_PNG, "ds_monkey_trunk_fit")
    print("fit preview ->", FIT_PNG)


if STANDALONE:
    render_fit()


# =====================================================================
# 14. 收尾总结
# =====================================================================
print("=" * 78)
print("导出 %d 个模型：%s" % (len(EXPORTS), ", ".join(os.path.basename(p) for p in EXPORTS)))
print("合计三角面 %d；脚底 z = %+.4f m；左右手 / 左右脚逐顶点互补（见上一节 SYMMETRY OK）"
      % (TOTAL_TRIS, LEG_ZMIN))
print("=" * 78)

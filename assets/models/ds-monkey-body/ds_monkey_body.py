# -*- coding: utf-8 -*-
"""
ds_monkey_body.py —— 猴子的「身体」（只做身体，不含头）

参考图：assets/models/ds-monkey-body/reference.png（2x2 四视图：正坐 / 侧坐 / 站立 3-4 / 背坐）

和 `ds-monkey-head` 是一对：那只做头，这只做身体。**头不在本脚本里建**，而是复用
`assets/models/_shared/monkey_head.py`（= `ds-monkey-head` 的同一份几何），只在预览时
按 **1.0 倍**（不缩放！）挂到脖子节点上，用来核对「头 + 身」合体后的比例。
导出时只选身体网格，头不会进 `ds_monkey_body.glb`。

坐标与尺度
----------
* 单位：米（1 Blender unit = 1 m）。
* 面朝 **+Y**，+Z 向上（导出 glTF 后 Godot 里 −Z 向前）。
* 原点在**双脚之间的地面中心**（脚底 z = 0），可以直接摆到地形上。
* 所有物体 scale = 1、rotation = 0，动画靠改 `location` / `rotation_euler`。

比例是怎么定的
--------------
参考图的头就是 `ds-monkey-head` 那只（同一套脸 / 耳朵 / 呆毛），所以**用头当尺子**：

| 参考图（正视图像素） | 测量值 | 换算 |
| --- | --- | --- |
| 颅宽（不含耳） | 165 px | = 0.300 m  → **1 px = 1.818 mm** |
| 呆毛尖 → 下巴 | 178 px | 0.324 m |
| 站姿：呆毛尖 → 脚底 | 337 px | **全高 0.613 m** |
| 下巴 → 裆 | 88 px | 躯干 0.160 m |
| 裆 → 脚底 | 71 px | 腿 0.129 m |
| 肩宽（含上臂） | 171 px | 0.311 m → 躯干 0.200 m |
| 躯干前后深（侧视图） | 94 px | 0.171 m |
| 脚长（侧视图） | 45 px | 0.082 m |
| 耳到耳总宽 | 254 px | 0.462 m（头资产实测 0.451，差 2%） |

于是：**头占全高的 52%**——这就是参考图那只「头比身体大」的 chibi 猴。
（`ds-lowpoly-monkey` 是另一种比例：那只为了身体好看把头放大 1.2 倍、头只占 39%。
本资产不复用它的任何数字。）

低多边形做法
------------
* **躯干 / 胯 = 10 列车削**（`lathe`），橘色肚皮不是另贴一片，而是**逐面换材质**——
  `ds_lowpoly_monkey` 的肚皮是独立网格（126 三角面），这里直接画在躯干面上，0 成本。
* **四肢 = 关节球 + 从球里长出来的锥台**（6 棱），球比管粗 1.2 倍、管端埋进球里，
  所以转起来不会出现「竹节」折角。手腕 / 脚踝不放假球（手和脚本身就是圆头），
  只有肩 / 肘 / 胯 / 膝 4 对关节有球。
* **手脚 = 矩形截面放样**（`loft`），脚底严格落在 z = 0。
* **尾巴 = Catmull-Rom 大钩切成 4 段**，逐段父子挂接，段枢轴 = 切分点。
* 全平直着色（`use_smooth = False`），每格四边形一个法线 = 一块干净棱面。

产物
----
ds_monkey_body.glb              Godot 用资产（无动画，纯节点层级）
ds_monkey_body.blend            Blender 源文件（**里面带头**，方便重渲预览）
ds_monkey_body_preview.png      2x2 四视图（身体 + 头合体）
ds_monkey_body_vs_reference.png 正视轮廓与参考图逐像素叠加（红 = 参考 / 绿 = 模型）

运行::

    blender --background --factory-startup --python ds_monkey_body.py
"""

import bpy
import bmesh
import math
import os
import shutil
import sys

from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
NAME = "ds_monkey_body"
GLB_PATH = os.path.join(HERE, NAME + ".glb")
BLEND_PATH = os.path.join(HERE, NAME + ".blend")
PREVIEW_PATH = os.path.join(HERE, NAME + "_preview.png")
COMPARE_PATH = os.path.join(HERE, NAME + "_vs_reference.png")
REF_PATH = os.path.join(HERE, "reference.png")
RENDER_DIR = os.path.join(HERE, "_render_tmp")


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

PREFIX = "DSMonkeyBody"


# =====================================================================
# 1. 尺寸常量（米）—— 全部由 §「比例是怎么定的」那张表换算
# =====================================================================
PX_M = 0.300 / 165.0            # 参考图 1 px = 1.818 mm（下面所有米数都是这么换出来的）

SKULL_C_Z = 0.444               # 颅心（= ds_monkey_head 原点的落点）；下巴 = 0.293
TOTAL_H = 0.613                 # 呆毛尖（合体全高，自检里对账用）

ANKLE_Z = 0.032
KNEE_Z = 0.078
HIP_Z = 0.142                   # 髋关节
WAIST_Z = 0.170
SHOULDER_Z = 0.238              # 肩关节（往下挪：球心站在躯干侧面，不在肩上「长出角」）

# 肩枢轴必须站在躯干**外面**（躯干半宽 0.100，肩球中心 0.100），
# 否则手臂整条埋进身体里 —— 参考图正视：躯干 110 px、左右手臂各 30 px、
# 总宽 170 px（= 0.31 m），手臂中心在 ±0.109 m 处。
SHOULDER_X = 0.090
HIP_X = 0.044

# 实测（参考图正视 / 侧视）：胸 X 全宽 0.200、前后深 0.176、胯 0.196 / 0.172、
# 脚长 0.086、脚宽 0.056 —— 这些数直接落在下面 TORSO_PROFILE / HIPS_PROFILE 里。

UPPER_ARM_R = 0.030
FOREARM_R = 0.027
THIGH_R = 0.040
SHIN_R = 0.032

FOOT_LEN, FOOT_W = 0.086, 0.056     # 参考图侧视 45 px 长
TAIL_PTS = [                    # 侧视图里那条「向后甩、再卷上来」的问号大钩
    (0.000, -0.078, 0.134),
    (0.014, -0.150, 0.150),
    (0.022, -0.214, 0.212),
    (0.014, -0.226, 0.286),
    (-0.006, -0.196, 0.320),
    (-0.012, -0.156, 0.310),
]
TAIL_R0, TAIL_R1 = 0.0150, 0.0080   # 参考图侧视：尾根直径 ≈ 0.021 m，尖端 ≈ 0.014 m
TAIL_SEGS = 4


# =====================================================================
# 2. 调色板（与共用头同一组数；脚本里 assert 兜住漂移）
# =====================================================================
PAL = {
    "fur":      (0.508, 0.265, 0.145),   # == monkey_head PAL["fur"]
    "fur_dark": (0.365, 0.192, 0.110),   # == monkey_head PAL["fur_dark"]
    "tan":      (0.858, 0.652, 0.438),   # == monkey_head PAL["face"]
    "tan_deep": (0.826, 0.606, 0.392),   # 手掌 / 脚掌：比脸略深一档
}
ROUGH = {"fur": 0.72, "fur_dark": 0.74, "tan": 0.70, "tan_deep": 0.70}
MAT_NAME = {"fur": "DSBody_fur", "fur_dark": "DSBody_fur_dark",
            "tan": "DSBody_tan", "tan_deep": "DSBody_tan_deep"}


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


def rect_pts(half_u, half_v):
    return [(-half_u, -half_v), (half_u, -half_v), (half_u, half_v), (-half_u, half_v)]


def basis_along(axis):
    """给一条轴配一组正交基（u, v）—— 参考向量不能和轴平行，否则会退化。"""
    t = Vector(axis).normalized()
    ref = Vector((0.0, 0.0, 1.0))
    if abs(t.dot(ref)) > 0.9:
        ref = Vector((0.0, 1.0, 0.0))
    u = t.cross(ref).normalized()
    v = t.cross(u).normalized()
    return u, v


def loft(b, sections, slot, cap=True):
    """sections: [(center, u, v, [(a,b), ...])] —— 逐段放样，端头用 n 边形封口。"""
    rings = []
    for (ctr, u, v, prof) in sections:
        idx = []
        for (a, bb) in prof:
            idx.append(b.add(Vector(ctr) + u * a + v * bb))
        rings.append(idx)
    for j in range(len(rings) - 1):
        ra, rb = rings[j], rings[j + 1]
        n = len(ra)
        for i in range(n):
            i2 = (i + 1) % n
            b.quad(ra[i], ra[i2], rb[i2], rb[i], slot)
    if cap:
        b.face(tuple(reversed(rings[0])), slot)
        b.face(tuple(rings[-1]), slot)
    return rings


def prism(b, p0, p1, r0, r1, slot, sides=6, cap=True):
    """两点之间的 n 棱锥台（四肢）。"""
    p0, p1 = Vector(p0), Vector(p1)
    u, v = basis_along(p1 - p0)
    sect = [(p0, u, v, [(cx * r0, cy * r0) for (cx, cy) in circle_pts(sides)]),
            (p1, u, v, [(cx * r1, cy * r1) for (cx, cy) in circle_pts(sides)])]
    return loft(b, sect, slot, cap=cap)


def ball(b, ctr, r, slot, segs=6, rings=2):
    """低多边形关节球（默认 6×2 = 24 三角面）。棱数要和相邻的管一致，接缝才没有折痕。"""
    ctr = Vector(ctr)
    top = b.add(ctr + Vector((0.0, 0.0, r)))
    bot = b.add(ctr - Vector((0.0, 0.0, r)))
    ring_idx = []
    for j in range(1, rings + 1):
        el = math.pi * (j / float(rings + 1)) - math.pi * 0.5
        rr = r * math.cos(el)
        z = r * math.sin(el)
        idx = []
        for k in range(segs):
            a = 2.0 * math.pi * k / segs
            idx.append(b.add(ctr + Vector((rr * math.cos(a), rr * math.sin(a), z))))
        ring_idx.append(idx)
    for k in range(segs):
        k2 = (k + 1) % segs
        b.tri(top, ring_idx[0][k], ring_idx[0][k2], slot)
    for j in range(len(ring_idx) - 1):
        ra, rb = ring_idx[j], ring_idx[j + 1]
        for k in range(segs):
            k2 = (k + 1) % segs
            b.quad(ra[k], ra[k2], rb[k2], rb[k], slot)
    for k in range(segs):
        k2 = (k + 1) % segs
        b.tri(bot, ring_idx[-1][k2], ring_idx[-1][k], slot)


def lathe(b, profile, cols, matfn, cap_slot=None):
    """把一个 (z, rx, ry) 剖面车一圈。
    ¶ 每格四边形单独判色（`matfn(面中心) -> 槽名`）—— 肚皮就是这么「画」上去的。"""
    rings = []
    for (z, rx, ry) in profile:
        idx = []
        for i in range(cols):
            a = 2.0 * math.pi * i / cols
            idx.append(b.add(Vector((rx * math.sin(a), ry * math.cos(a), z))))
        rings.append(idx)
    for j in range(len(rings) - 1):
        ra, rb = rings[j], rings[j + 1]
        for i in range(cols):
            i2 = (i + 1) % cols
            ctr = (b.v[ra[i]] + b.v[ra[i2]] + b.v[rb[i2]] + b.v[rb[i]]) / 4.0
            b.quad(ra[i], ra[i2], rb[i2], rb[i], matfn(ctr))
    if cap_slot:
        b.face(tuple(reversed(rings[0])), cap_slot)
        b.face(tuple(rings[-1]), cap_slot)
    return rings


def catmull_rom_3d(pts, samples_per_seg=6):
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
    """按弧长把折线重采样成 n 个点（尾巴逐段等长）。"""
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


def recenter(ob, pivot):
    p = Vector(pivot)
    for v in ob.data.vertices:
        v.co -= p
    ob.location = p
    return ob


def make_part(name, b, pivot, recalc=True):
    return recenter(build_object(name, b.v, b.f, recalc=recalc), pivot)


# =====================================================================
# 4. 躯干 / 胯（车削 + 逐面画肚皮）
# =====================================================================
TORSO_PROFILE = [               # (z, rx, ry) 腰 → 肩：**蛋形**，肩线往里收
    (0.132, 0.076, 0.068),       # 收腰：手臂才在腰侧让出一条可见的缝
    (0.170, 0.094, 0.084),
    (0.200, 0.103, 0.090),       # 最宽处
    (0.232, 0.100, 0.088),
    (0.262, 0.092, 0.080),
    (0.284, 0.076, 0.068),       # 肩线一路往里收，头才不会「架在一块平板上」
    (0.300, 0.046, 0.044),       # 顶环缩进颅骨底面（下巴 0.293），头一歪也不露缝
]
HIPS_PROFILE = [                # 裆部收到 0.118，腿才「露得出来」（参考图腿长 0.129）
    (0.118, 0.058, 0.052),
    (0.132, 0.086, 0.078),
    (0.146, 0.098, 0.086),
    (0.164, 0.092, 0.082),
]
# 肚皮：参考图正视里是一块 90 px 宽的圆角六边形（≈0.164 m = 躯干宽的 8 成），
# 上窄 → 中间最宽 → 下窄，所以「方位角上限」随高度变。
# 肚皮：环向 10 列 → 面心方位角是 18° / 54° / 90°…
# 「4 列」= ±54°（弦长 0.166 m，和参考图的 90 px / 0.164 m 对得上）；
# 「2 列」= ±18°（上下两头收窄，正视图读出来是一块六边形）。
BELLY_AZ_WIDE = 1.00            # > 0.942（54°）就吃到第 4 列
BELLY_AZ_NARROW = 0.50          # 只吃正中 2 列
BELLY_WIDE_Z = (0.170, 0.262)   # 满宽的高度区间
BELLY_Z = (0.148, 0.275)        # 收窄的两头


def torso_mat(ctr):
    """躯干逐面判色：肚皮是一块**六边形**橘色面盘（参考图正视）。
    az = 0 是正前方（+Y）。"""
    az = math.atan2(ctr.x, ctr.y)
    z0, z1 = BELLY_Z
    if z0 <= ctr.z <= z1:
        w0, w1 = BELLY_WIDE_Z
        lim = BELLY_AZ_WIDE if w0 <= ctr.z <= w1 else BELLY_AZ_NARROW
        if abs(az) < lim:
            return "tan"
    return "fur"


def build_torso():
    b = Builder()
    lathe(b, TORSO_PROFILE, 10, torso_mat, cap_slot="fur")
    # 脖子：一小段藏在颅骨里的柱子，保证「头一歪也不露缝」
    prism(b, (0.0, 0.0, 0.284), (0.0, 0.0, 0.320), 0.050, 0.046, "fur", sides=6)
    return make_part(PREFIX + "_Torso", b, (0.0, 0.0, WAIST_Z))


def build_hips():
    b = Builder()
    lathe(b, HIPS_PROFILE, 10, lambda ctr: "fur", cap_slot="fur")
    return make_part(PREFIX + "_Hips", b, (0.0, 0.0, HIP_Z))


# =====================================================================
# 5. 四肢
# =====================================================================
# 手臂要**外张**：参考图正视里，手臂与躯干在腰侧之间有一块三角形空隙。
# 竖直垂下的手臂会糊在躯干上，正面看就是「一块板」。
ARM = {                         # 右臂（x > 0 是角色右）；左臂镜像
    "shoulder": Vector((SHOULDER_X, 0.000, SHOULDER_Z)),
    "elbow":    Vector((0.124, 0.004, 0.178)),
    "wrist":    Vector((0.128, 0.006, 0.116)),
    "tip":      Vector((0.130, 0.008, 0.076)),
}
LEG = {
    "hip":   Vector((HIP_X, 0.000, HIP_Z)),
    "knee":  Vector((0.050, 0.004, KNEE_Z)),
    "ankle": Vector((0.052, 0.000, ANKLE_Z)),
}


def side_pt(p, side):
    return Vector((p.x * side, p.y, p.z))


def build_arm_upper(side):
    b = Builder()
    s = side_pt(ARM["shoulder"], side)
    e = side_pt(ARM["elbow"], side)
    tag = "L" if side < 0 else "R"
    ball(b, s, UPPER_ARM_R * 1.08, "fur", segs=6, rings=2)
    prism(b, s, e, UPPER_ARM_R, UPPER_ARM_R * 0.92, "fur", sides=6)
    return make_part(PREFIX + "_Arm_%s_Upper" % tag, b, s)


def build_arm_fore(side):
    b = Builder()
    e = side_pt(ARM["elbow"], side)
    w = side_pt(ARM["wrist"], side)
    tag = "L" if side < 0 else "R"
    ball(b, e, FOREARM_R * 1.18, "fur", segs=6, rings=2)
    prism(b, e, w, FOREARM_R * 0.95, FOREARM_R * 0.86, "fur", sides=6)
    return make_part(PREFIX + "_Arm_%s_Fore" % tag, b, e)


def build_hand(side):
    """连指手套式的手：腕 → 掌 → 指端三段矩形放样，下面挂 3 根短指。"""
    b = Builder()
    w = side_pt(ARM["wrist"], side)
    tip = side_pt(ARM["tip"], side)
    tag = "L" if side < 0 else "R"
    axis = (tip - w).normalized()
    u, v = basis_along(axis)
    # u 大致是「横向」，v 是「前后」
    sect = [(w, u, v, rect_pts(0.021, 0.017)),
            (w + axis * 0.020, u, v, rect_pts(0.026, 0.019)),
            (w + axis * 0.036, u, v, rect_pts(0.024, 0.016)),
            (tip, u, v, rect_pts(0.018, 0.011))]
    loft(b, sect, "tan_deep")
    # 三根短指（从掌端往下伸一点，参考图里能看到指缝）
    for k, (dx, dy) in enumerate(((-0.011, -0.008), (0.0, -0.010), (0.011, -0.008))):
        base = tip + u * dx + v * dy - axis * 0.002
        end = base + axis * 0.012 + Vector((0.0, 0.0, -0.004))
        prism(b, base, end, 0.0075, 0.0055, "tan_deep", sides=4)
    return make_part(PREFIX + "_Arm_%s_Hand" % tag, b, w)


def build_leg_thigh(side):
    b = Builder()
    h = side_pt(LEG["hip"], side)
    k = side_pt(LEG["knee"], side)
    tag = "L" if side < 0 else "R"
    ball(b, h, THIGH_R * 1.12, "fur", segs=6, rings=2)
    prism(b, h, k, THIGH_R, THIGH_R * 0.86, "fur", sides=6)
    return make_part(PREFIX + "_Leg_%s_Thigh" % tag, b, h)


def build_leg_shin(side):
    b = Builder()
    k = side_pt(LEG["knee"], side)
    a = side_pt(LEG["ankle"], side)
    tag = "L" if side < 0 else "R"
    ball(b, k, SHIN_R * 1.18, "fur", segs=6, rings=2)
    prism(b, k, a, SHIN_R * 0.92, SHIN_R * 0.80, "fur", sides=6)
    return make_part(PREFIX + "_Leg_%s_Shin" % tag, b, k)


def build_foot(side):
    """矩形截面放样的脚：脚跟窄、脚背高、脚尖收薄，脚底严格 z = 0。"""
    b = Builder()
    a = side_pt(LEG["ankle"], side)
    tag = "L" if side < 0 else "R"
    x = a.x
    # (y, 半宽, 顶高, 底高)——底高全 0，落地是平的
    sect_def = [(-0.030, 0.022, 0.032, 0.0),
                (-0.004, 0.029, 0.040, 0.0),
                (0.032, 0.029, 0.030, 0.0),
                (0.052, 0.024, 0.019, 0.0),
                (0.062, 0.015, 0.011, 0.0)]
    sect = []
    for (y, hw, top, bot) in sect_def:
        ctr = Vector((x, y, (top + bot) * 0.5))
        u = Vector((1.0, 0.0, 0.0))
        v = Vector((0.0, 0.0, 1.0))
        sect.append((ctr, u, v, rect_pts(hw, (top - bot) * 0.5)))
    loft(b, sect, "tan_deep")
    return make_part(PREFIX + "_Leg_%s_Foot" % tag, b, a)


# =====================================================================
# 6. 尾巴（4 段圆弧链）
# =====================================================================
TAIL_SAMPLES = 48               # 整条尾巴的密采样点数（等弧长）
TAIL_RINGS_PER_SEG = 4          # 每段 4 环 = 3 带：再密就是浪费面数


def tail_chain():
    """整条尾巴先过一次 Catmull-Rom、再等弧长重采样，然后切成 4 段。

    ⚠️ 不能「先切 4 段、每段各扫一段直线」—— 那样尾巴是一条 4 折的折线，
    侧视图里能数出 3 个硬折角（第一版踩过）。段内必须走**曲线子路径**。"""
    dense = resample(catmull_rom_3d(TAIL_PTS, 10), TAIL_SAMPLES)
    bounds = [int(round(i * (TAIL_SAMPLES - 1) / float(TAIL_SEGS)))
              for i in range(TAIL_SEGS + 1)]
    segs = []
    for j in range(TAIL_SEGS):
        sub = dense[bounds[j]:bounds[j + 1] + 1]
        if len(sub) < 2:
            sub = [dense[bounds[j]], dense[min(bounds[j + 1], TAIL_SAMPLES - 1)]]
        segs.append(sub)
    return segs


def build_tail_seg(j, sub):
    b = Builder()
    pts = resample(sub, TAIL_RINGS_PER_SEG)
    n = len(pts)
    sect = []
    for k, p in enumerate(pts):
        if k == 0:
            t = pts[1] - pts[0]
        elif k == n - 1:
            t = pts[-1] - pts[-2]
        else:
            t = pts[k + 1] - pts[k - 1]
        u, v = basis_along(t)
        g = (j + k / float(n - 1)) / float(TAIL_SEGS)
        r = TAIL_R0 + (TAIL_R1 - TAIL_R0) * (g ** 0.8)
        sect.append((p, u, v, [(cx * r, cy * r) for (cx, cy) in circle_pts(5)]))
    loft(b, sect, "fur", cap=True)
    return make_part(PREFIX + "_Tail_%d" % (j + 1), b, pts[0])


# =====================================================================
# 7. 组装层级（节点层级 = 骨架，不用 armature 权重）
# =====================================================================
root = bpy.data.objects.new(PREFIX + "_Root", None)
root.empty_display_type = 'PLAIN_AXES'
root.empty_display_size = 0.06
bpy.context.collection.objects.link(root)

hips = build_hips()
torso = build_torso()


PARTS = [hips, torso]


def attach(ob, parent, local_loc):
    ob.parent = parent
    ob.location = Vector(local_loc)
    return ob


attach(hips, root, (0.0, 0.0, HIP_Z))
attach(torso, hips, (0.0, 0.0, WAIST_Z - HIP_Z))

arms = {}
for side in (-1, 1):
    tag = "L" if side < 0 else "R"
    up = build_arm_upper(side)
    fo = build_arm_fore(side)
    ha = build_hand(side)
    attach(up, torso, side_pt(ARM["shoulder"], side) - Vector((0.0, 0.0, WAIST_Z)))
    attach(fo, up, side_pt(ARM["elbow"], side) - side_pt(ARM["shoulder"], side))
    attach(ha, fo, side_pt(ARM["wrist"], side) - side_pt(ARM["elbow"], side))
    arms[tag] = (up, fo, ha)
    PARTS += [up, fo, ha]

legs = {}
for side in (-1, 1):
    tag = "L" if side < 0 else "R"
    th = build_leg_thigh(side)
    sh = build_leg_shin(side)
    ft = build_foot(side)
    attach(th, hips, side_pt(LEG["hip"], side) - Vector((0.0, 0.0, HIP_Z)))
    attach(sh, th, side_pt(LEG["knee"], side) - side_pt(LEG["hip"], side))
    attach(ft, sh, side_pt(LEG["ankle"], side) - side_pt(LEG["knee"], side))
    legs[tag] = (th, sh, ft)
    PARTS += [th, sh, ft]

tail_parts = []
segs = tail_chain()
prev = hips
prev_start = Vector((0.0, 0.0, HIP_Z))
for j, seg in enumerate(segs):
    ob = build_tail_seg(j, seg)
    attach(ob, prev, seg[0] - prev_start)
    prev, prev_start = ob, seg[0]
    tail_parts.append(ob)
PARTS += tail_parts

# 脖子节点：颅心就落在这里（= ds_monkey_head 的原点），所以**头挂进来不需要任何偏移**
neck = bpy.data.objects.new(PREFIX + "_Neck", None)
neck.empty_display_type = 'PLAIN_AXES'
neck.empty_display_size = 0.03
bpy.context.collection.objects.link(neck)
attach(neck, torso, (0.0, 0.0, SKULL_C_Z - WAIST_Z))

bpy.ops.object.select_all(action='DESELECT')
for ob in PARTS:
    ob.select_set(True)
bpy.context.view_layer.objects.active = PARTS[0]
bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)


# =====================================================================
# 8. 共用猴头（只在预览用；导出时不选它）
# =====================================================================
sys.path.insert(0, os.path.join(HERE, "..", "_shared"))
sys.modules.pop("monkey_head", None)
import monkey_head as MH          # noqa: E402  导入即在场景里建出头

for key in ("fur", "fur_dark", "tan"):
    src = {"fur": "fur", "fur_dark": "fur_dark", "tan": "face"}[key]
    assert all(abs(a - b) < 1e-9 for a, b in zip(PAL[key], MH.PAL[src])), key

MH.head.location = Vector((0.0, 0.0, SKULL_C_Z))
bpy.context.view_layer.update()      # 不刷一次 matrix_world 还是旧的（合体尺寸会算错）
HEAD_MESHES = list(MH.MESHES)


# =====================================================================
# 9. 自检
# =====================================================================
def report():
    tris = 0
    zs = []
    for ob in PARTS:
        for v in ob.data.vertices:
            zs.append((ob.matrix_world @ v.co).z)
        tris += sum(len(p.vertices) - 2 for p in ob.data.polygons)
        assert all(abs(s - 1.0) < 1e-6 for s in ob.scale), ob.name
        assert all(abs(r) < 1e-6 for r in ob.rotation_euler), ob.name
        assert all(abs(s - 1.0) < 1e-6 for s in (ob.scale)), ob.name
    head_tris = sum(len(p.vertices) - 2 for ob in HEAD_MESHES
                    for p in ob.data.polygons)
    head_z = [(ob.matrix_world @ v.co).z for ob in HEAD_MESHES
              for v in ob.data.vertices]
    print("=" * 70)
    print("DS MONKEY BODY (head from models/_shared/monkey_head.py, preview only)")
    for ob in PARTS:
        print("  %-26s verts %4d  faces %4d  %s" %
              (ob.name, len(ob.data.vertices), len(ob.data.polygons),
               [m.name for m in ob.data.materials]))
    print("  BODY tris %d   (+ head %d  = 合体 %d)" % (tris, head_tris, tris + head_tris))
    print("  合体全高 %.3f m（参考图 0.613 m，允许 ±2%%）" % (max(head_z) - min(zs)))
    print("  body z %.4f .. %.4f m   (脚底必须是 0)" % (min(zs), max(zs)))
    assert abs((max(head_z) - min(zs)) - TOTAL_H) < TOTAL_H * 0.02, "合体全高漂了"
    print("  skull centre z %.3f / 合体后 %.3f .. %.3f m（下巴 / 呆毛尖）" %
          (SKULL_C_Z, min(head_z), max(head_z)))
    print("=" * 70)
    return tris, min(zs), max(zs)


BODY_TRIS, ZMIN, ZMAX = report()
assert abs(ZMIN) < 0.0015, "脚底必须落在 z = 0：%.4f" % ZMIN


# =====================================================================
# 9.1 间隙审计（回归用：改肩位 / 躯干宽度 / 大腿粗细前后先看这里）
# =====================================================================
def audit_clearance():
    """数「手臂 / 尾巴」与「躯干 / 胯 / 腿」的相交三角面对。

    参考 `ds-lowpoly-monkey` 的 `audit_arm_clearance()`：手臂只允许在肩球那一小段
    和躯干咬合（那是「长在身上」的证据），前臂 / 手掌必须是 0 —— 否则渲染出来
    就是「手臂和身体粘在一起」或者「手掌插进大腿」。"""
    from mathutils.bvhtree import BVHTree

    def tree(objs):
        bm = bmesh.new()
        for ob in objs:
            me = ob.data.copy()
            me.transform(ob.matrix_world)
            bm.from_mesh(me)
            bpy.data.meshes.remove(me)
        t = BVHTree.FromBMesh(bm)
        bm.free()
        return t

    core = tree([torso, hips] + [legs[t][0] for t in ("L", "R")]
                + [legs[t][1] for t in ("L", "R")] + [legs[t][2] for t in ("L", "R")])
    rows = []
    for tag in ("L", "R"):
        up, fo, ha = arms[tag]
        rows.append(("%s 上臂" % tag, len(tree([up]).overlap(core))))
        rows.append(("%s 前臂" % tag, len(tree([fo]).overlap(core))))
        rows.append(("%s 手掌" % tag, len(tree([ha]).overlap(core))))
    tail = tree(tail_parts)
    rows.append(("尾巴", len(tail.overlap(core))))
    print("  间隙审计:", "  ".join("%s %d" % r for r in rows))
    return rows


CLEARANCE = audit_clearance()


# =====================================================================
# 10. 预览（2x2 四视图 + 与参考图叠加）
# =====================================================================
def setup_preview():
    world = bpy.data.worlds.new("DSBodyWorld")
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
        ob.rotation_euler = (Vector((0.0, 0.0, 0.30)) - Vector(loc)) \
            .to_track_quat('-Z', 'Y').to_euler()
        return ob

    add_area("DSBodyKey", (1.9, 2.2, 2.4), 150.0, 1.8)
    add_area("DSBodyFill", (-2.2, 1.5, 0.6), 55.0, 2.6)
    add_area("DSBodyRim", (0.4, -2.4, 1.4), 60.0, 1.6)

    cam_data = bpy.data.cameras.new("DSBodyCam")
    cam_data.type = 'ORTHO'
    cam_data.ortho_scale = 0.80
    cam = bpy.data.objects.new("DSBodyCam", cam_data)
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
    return a[::-1]              # 统一成「自上而下」（第 0 行 = 图顶）


def save_rgba(buf, path, name):
    out = bpy.data.images.new(name, buf.shape[1], buf.shape[0], alpha=False)
    out.pixels = buf[::-1].ravel().tolist()      # 缓冲区是自上而下，Blender 要自下而上
    out.filepath_raw = path
    out.file_format = 'PNG'
    out.save()


def render_views(cam):
    import numpy as np
    if not os.path.isdir(RENDER_DIR):
        os.makedirs(RENDER_DIR)
    scene.render.resolution_x = 480
    scene.render.resolution_y = 600
    views = [("front", 0.0), ("side", -90.0), ("back", 180.0), ("q34", -38.0)]
    dist, target = 3.0, Vector((0.0, 0.0, 0.315))
    paths = []
    for name, az_deg in views:
        az = math.radians(az_deg)
        cam.location = Vector((math.sin(az) * dist, math.cos(az) * dist, target.z))
        cam.rotation_euler = (target - cam.location).to_track_quat('-Z', 'Y').to_euler()
        path = os.path.join(RENDER_DIR, "view_%s.png" % name)
        render_to(path)
        paths.append(path)

    W, H = scene.render.resolution_x, scene.render.resolution_y
    buf = np.ones((H * 2, W * 2, 4), dtype=np.float32)
    for i, path in enumerate(paths):
        a = load_rgba(path, W, H)
        r, c = divmod(i, 2)
        buf[r * H:r * H + H, c * W:(c + 1) * W] = a
    save_rgba(buf, PREVIEW_PATH, "ds_monkey_body_preview")
    print("preview ->", PREVIEW_PATH)


def render_compare(cam):
    """参考图正视格 vs 模型正视（同像素密度 550 px/m），并出一张轮廓叠加。"""
    import numpy as np
    if not os.path.isdir(RENDER_DIR):
        os.makedirs(RENDER_DIR)
    W, H = 704, 384
    scene.render.resolution_x = W
    scene.render.resolution_y = H
    scene.render.film_transparent = True
    cam.data.ortho_scale = 704.0 / 550.0          # 550 px/m（= 参考图 165 px = 0.300 m）
    cam.location = Vector((0.0, 3.0, 0.320))
    cam.rotation_euler = (Vector((0.0, 0.0, 0.320)) - cam.location) \
        .to_track_quat('-Z', 'Y').to_euler()
    shot = os.path.join(RENDER_DIR, "compare_front.png")
    render_to(shot)
    scene.render.film_transparent = False

    mine = load_rgba(shot, W, H)
    ref = load_rgba(REF_PATH, 1408, 768)
    # 参考图是「自上而下」读的：load_rgba 拿到的是 Blender 的自下而上序，这里翻回去
    ref_tb = ref[0:H, 0:W]                        # 正视图格（左上）
    mine_tb = mine

    ref_fg = ref_tb[..., 3] > 0.5
    mine_fg = mine_tb[..., 3] > 0.35

    def bbox(mask):
        ys, xs = np.nonzero(mask)
        return xs.min(), xs.max(), ys.min(), ys.max()

    rx0, rx1, ry0, ry1 = bbox(ref_fg)
    mx0, mx1, my0, my1 = bbox(mine_fg)
    # 只按「高度」对齐并平移（不缩放）：比例对不上就看得出来
    sx = (mx0 + mx1) * 0.5 - (rx0 + rx1) * 0.5
    sy = (my0 + my1) * 0.5 - (ry0 + ry1) * 0.5
    sh = np.zeros_like(mine_fg)
    ys, xs = np.nonzero(mine_fg)
    ty = np.round(ys - sy).astype(int)
    tx = np.round(xs - sx).astype(int)
    ok = (ty >= 0) & (ty < H) & (tx >= 0) & (tx < W)
    sh[ty[ok], tx[ok]] = True

    # 三格：参考 / 模型 / 叠加（红=参考独有，绿=模型独有，灰=重合）
    panel = np.ones((H, W * 3, 4), dtype=np.float32)
    ref_rgb = ref_tb[..., :3] * ref_tb[..., 3:4] + 1.0 * (1.0 - ref_tb[..., 3:4])
    mine_rgb = mine_tb[..., :3] * mine_tb[..., 3:4] + 1.0 * (1.0 - mine_tb[..., 3:4])
    panel[:, 0:W, :3] = ref_rgb
    panel[:, W:2 * W, :3] = mine_rgb
    ov = np.ones((H, W, 3), dtype=np.float32)
    ov[ref_fg] = (0.90, 0.15, 0.15)
    ov[sh] = (0.15, 0.55, 0.15)
    ov[ref_fg & sh] = (0.55, 0.55, 0.55)
    panel[:, 2 * W:3 * W, :3] = ov
    save_rgba(panel, COMPARE_PATH, "ds_monkey_body_vs_reference")
    inter = (ref_fg & sh).sum()
    union = (ref_fg | sh).sum()
    print("compare -> %s   IoU %.3f   ref %d px / model %d px" %
          (COMPARE_PATH, inter / max(1, union), ref_fg.sum(), sh.sum()))
    print("  ref bbox x %d-%d y %d-%d | model bbox x %d-%d y %d-%d" %
          (rx0, rx1, ry0, ry1, mx0, mx1, my0, my1))


cam = setup_preview()
render_views(cam)
render_compare(cam)
shutil.rmtree(RENDER_DIR, ignore_errors=True)     # 单视图 / 对比渲染都是中间产物


# =====================================================================
# 11. 存 .blend / 导出 .glb（只导出身体，头留在 .blend 里方便重渲预览）
# =====================================================================
bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH)

bpy.ops.object.select_all(action='DESELECT')
root.select_set(True)
neck.select_set(True)          # 空物体也要选，否则 glb 里没有挂头的节点
for ob in PARTS:
    ob.select_set(True)
bpy.context.view_layer.objects.active = torso
bpy.ops.export_scene.gltf(
    filepath=GLB_PATH,
    export_format='GLB',
    use_selection=True,
    export_apply=False,
    export_yup=True,
    export_animations=False,
    export_cameras=False,
    export_lights=False,
)
print("glb ->", GLB_PATH)
print("BODY CHECK: tris %d  z %.4f .. %.4f  height %.3f m"
      % (BODY_TRIS, ZMIN, ZMAX, ZMAX - ZMIN))

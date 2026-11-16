# 共享库：侏罗纪园区废墟（大门 / 破墙）的公共构建代码
#
# 为什么要有这个文件：
#   大门两侧的矮墙（low_poly_jurassic_gate.py）和独立破墙模型
#   （ruined-wall/low_poly_ruined_wall.py）必须是**同一堵墙**，否则两者拼在一起时
#   基座高度、砖缝错位、压顶出挑、墙头剖面会各走各的，接缝一眼就看出是两套模型。
#   这里放唯一一份实现，两个脚本 import 它 —— 拼接自然的前提是"几何只有一份"。
#
# ---------------------------------------------------------------------------
# 拼接缝（joint）契约 —— 改墙的代码前必须先读懂这一段
# ---------------------------------------------------------------------------
# 一段墙的两个端面要能和另一段墙的端面**严丝合缝**地对上，靠四条硬约定：
#
#   1) 长度 = 整数倍的 bay_w。build_wall_segment() 内部按
#      n_bay = round(length / bay_m)、bay_w = length / n_bay 反算，
#      所以无论传多长，都不会在端头留出"半块砖"。
#   2) 接缝端强制满高。墙头剖面本来是随机的（那是破败感的来源），
#      但端头那 1 块如果也随机，两段墙接起来就会出现台阶。
#      所以 joint_ends 指定的端头一律拉回满高，破败交给中段去表达。
#   3) 压顶与基座在 X 方向**不外扩**。基座只朝前后（Y）涨 PLINTH_OUT_M，
#      压顶只朝前后涨 COPING_OUT_M；X 方向严格切成 [xa, xb]。
#      于是相邻两段的基座正好对接成一整条，压顶也连成一条脊。
#   4) **接缝端由一块"端石列"收口**（seam_column() 模板，所有墙段共用同一份、
#      固定种子）：端石逐层码砌、只是**接缝那一面被切平**，所以相邻两段的端面
#      逐点重合，接缝既没有台阶也没有缝。
#      墙身石块一律离端面 ≥ SEAM_W_M → 接缝平面上只有端石一个几何，
#      端面剖面因此可解析（verify_seams() 逐点核对）。
#
# 错缝为什么能跨缝对上：
#   端石列本身就是逐层错缝的砌法，切平面落在层与层的界上，
#   相邻两段的端石列拼起来就是连续的砌体 —— 镜像也不影响：
#   镜像只翻转 X 方向，层序不变，所以把相邻段镜像放置既增加外观变化，
#   又不会破坏接缝。
#
# 因此**换墙的尺寸（bay_m / 高度 / 压顶）时两个脚本要一起动**：
# 常量都从本文件导出，不要在各自的脚本里另写一份。
#
# ---------------------------------------------------------------------------
# 造型思路（2026-11 重做：低多边形"凿石"版）
# ---------------------------------------------------------------------------
# 旧版墙身 = 一只只**正立方体**（砖模数 0.48 × 层高 0.25 × 墙厚 0.75），
# 棱角全是直角，颜色还**逐面随机撒绿苔** —— 渲染出来是"我的世界"的积木墙：
# 没有体积感，也没有低多边形该有的"块面"。
#
# 现在换成手工凿石，四个关键：
#   1) 石块 = **切角块**（hewn_block）：棱角被削掉，边缘有倒角高光；
#      所有面都是**精确平面**（切角面本来就是平面），按棱面上色不会花。
#   2) 石头**前后深度逐块不同** → 墙面是起伏的，不是两张平板。
#   3) **颜色按整块石头给**，面与面之间只按法线做明暗 —— 低多边形的块面感
#      来自明暗差，不是来自彩色噪点。苔藓染在**朝上的整块棱面**上
#      （和 low_poly_rock 一个路子）。
#   4) 墙身背后有**暗色墙芯**：缺石处露出的是一块发暗的凹面，
#      而不是"看穿墙" —— 墙因此有厚度、有阴影。


import math
import os
import random

import bpy
import numpy as np
from mathutils import Vector

__all__ = [
    "srgb2lin", "PAL", "hash01", "lerp3", "shade",
    "MeshBuilder", "BOX_FACES", "box", "extrude_y", "extrude_x",
    "add_poly", "add_box", "hewn_block", "hewn_block_lite", "facet_shade", "seam_column",
    "stone_base", "stone_color", "build_base_rubble",
    "clear_scene", "make_material", "make_materials",
    "build_wall_segment", "build_coping_slabs", "tile_layout",
    "PreviewRig", "setup_preview_helpers", "stitch_images",
    "WALL_BAY_M", "WALL_T_M", "WALL_H_M",
    "PLINTH_M", "PLINTH_OUT_M", "WALL_ROWS", "COPING_H_M", "COPING_OUT_M",
    "TILE_N", "SEAM_W_M",
]


# ==========================================================================
# 调色板（sRGB → 线性）
# ==========================================================================
def srgb2lin(c):
    c = np.asarray(c, dtype=float)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


# 石头是**一族灰**：亮 / 中 / 暗 / 断面四档，色相基本一致。
# 旧版把苔藓当成"每块面 26% 概率撒一个绿点" —— 整面墙于是变成彩色噪点，
# 读起来是"贴了绿纸的积木"。这一版的规矩是：
#   · **颜色按整块石头给**（一块石头一个调子），面与面之间只按法线做明暗；
#   · 苔藓是**整块石头**染的（长在朝上的面、朝上的石头），不是随机撒点；
#   · 暖色（砂岩 / 风化白）只作少量点缀，避免整墙一个调子。
PAL = {
    # 石：暖土灰一族（亮 → 暗 → 断面）。偏暖才像"石头"，
    # 偏冷就变成"混凝土预制块"（旧版就是这个问题）。
    "stone_l": srgb2lin([0.640, 0.595, 0.510]),
    "stone_m": srgb2lin([0.505, 0.460, 0.390]),
    "stone_d": srgb2lin([0.355, 0.320, 0.270]),
    "stone_x": srgb2lin([0.245, 0.225, 0.190]),
    "stone_pale": srgb2lin([0.690, 0.660, 0.590]),  # 风化发白的旧石面
    "stone_warm": srgb2lin([0.505, 0.400, 0.275]),  # 偏暖的砂岩色（少量点缀）
    "wood_l": srgb2lin([0.51, 0.40, 0.28]),
    "wood_m": srgb2lin([0.39, 0.30, 0.21]),
    "wood_d": srgb2lin([0.27, 0.21, 0.15]),
    "iron_l": srgb2lin([0.40, 0.39, 0.38]),
    "iron_m": srgb2lin([0.30, 0.29, 0.29]),
    "rust": srgb2lin([0.47, 0.27, 0.14]),
    "rust_l": srgb2lin([0.60, 0.36, 0.18]),
    "rust_d": srgb2lin([0.30, 0.17, 0.10]),
    "moss_l": srgb2lin([0.370, 0.480, 0.195]),
    "moss_m": srgb2lin([0.265, 0.350, 0.140]),
    "moss_d": srgb2lin([0.145, 0.195, 0.090]),
    "leaf_l": srgb2lin([0.335, 0.515, 0.205]),
    "leaf_m": srgb2lin([0.255, 0.415, 0.185]),
    "leaf_d": srgb2lin([0.175, 0.305, 0.135]),
    "grass_m": srgb2lin([0.40, 0.50, 0.22]),
    "grass_d": srgb2lin([0.26, 0.36, 0.15]),
    "bark": srgb2lin([0.29, 0.23, 0.17]),
}


def hash01(*vals):
    h = math.sin(sum(v * k for v, k in zip(vals, (12.9898, 78.233, 37.719))) * 43758.5453)
    return h - math.floor(h)


def lerp3(a, b, t):
    return a * (1.0 - t) + b * t


def shade(base, jitter):
    """相邻棱面之间的轻微明暗差，避免整片糊成一个色块。"""
    return np.clip(np.asarray(base, dtype=float) * (0.90 + 0.20 * jitter), 0.0, 1.0)


# ==========================================================================
# 墙体尺寸（大门矮墙与独立破墙**共用**，改这里两边一起变）
# ==========================================================================
WALL_T_M = 0.75          # 墙体厚度（Y）
WALL_H_M = 2.25          # 墙高（含压顶）
PLINTH_M = 0.28          # 墙脚基座高度
PLINTH_OUT_M = 0.07      # 基座朝前后外扩（X 不外扩，见文件头"拼接缝契约"）
WALL_ROWS = 7            # 墙身砖层数
COPING_H_M = 0.20        # 压顶高度
COPING_OUT_M = 0.12      # 压顶朝前后外挑
TILE_N = 9               # 压顶瓦片数（按长度换算，见 build_wall_segment）
WALL_BAY_M = 0.48        # 单块砖长（错缝基准）


# ==========================================================================
# 网格构建
# ==========================================================================
class MeshBuilder:
    """收集多边形 + 每面材质槽 + 每面颜色，最后一次成型。

    直接 from_pydata 而不用 bmesh 布尔：本资产都是块状体，
    自己发面才能保证「一个平面 = 一块颜色」（assets/AGENTS.md §6.9）。
    """

    def __init__(self):
        self.verts = []
        self.faces = []       # [(顶点索引元组, 材质槽, (r,g,b))]
        self.slots = []

    def slot(self, name):
        if name not in self.slots:
            self.slots.append(name)
        return self.slots.index(name)

    def add(self, ve_list, slot, color):
        base = len(self.verts)
        self.verts.extend(tuple(v) for v in ve_list)
        self.faces.append((tuple(range(base, base + len(ve_list))), slot, color))

    def mirror_x(self):
        """沿 X 镜像：顶点取反，同时**反转每个面的绕序**，否则法线会翻进内部。"""
        self.verts = [(-v[0], v[1], v[2]) for v in self.verts]
        self.faces = [(f[0][::-1], f[1], f[2]) for f in self.faces]

    def build(self, name, materials):
        me = bpy.data.meshes.new(name + "Mesh")
        me.from_pydata(self.verts, [], [f[0] for f in self.faces])
        me.update()
        for slot_name in self.slots:
            me.materials.append(materials[slot_name])
        ca = me.color_attributes.new(name="Col", type='FLOAT_COLOR', domain='CORNER')
        for fi, (idx, slot, col) in enumerate(self.faces):
            poly = me.polygons[fi]
            poly.material_index = slot
            poly.use_smooth = False
            for li in poly.loop_indices:
                ca.data[li].color = (col[0], col[1], col[2], 1.0)
        me.validate(verbose=False)
        ob = bpy.data.objects.new(name, me)
        bpy.context.scene.collection.objects.link(ob)
        return ob


BOX_FACES = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]


def box(b, x0, x1, y0, y1, z0, z1, slot, color, offset=(0.0, 0.0, 0.0)):
    """轴对齐长方体；color 可以是 (r,g,b)，也可以是 {"top":…, "side":…, "bottom":…}。"""
    ox, oy, oz = offset
    V = [(x0 + ox, y0 + oy, z0 + oz), (x1 + ox, y0 + oy, z0 + oz),
         (x1 + ox, y1 + oy, z0 + oz), (x0 + ox, y1 + oy, z0 + oz),
         (x0 + ox, y0 + oy, z1 + oz), (x1 + ox, y0 + oy, z1 + oz),
         (x1 + ox, y1 + oy, z1 + oz), (x0 + ox, y1 + oy, z1 + oz)]
    if isinstance(color, dict):
        side = color["side"]
        cols = [color.get("bottom", side), color.get("top", side)] + [side] * 4
    else:
        cols = [color] * 6
    for idx, c in zip(BOX_FACES, cols):
        b.add([V[i] for i in idx], slot, c)


def extrude_y(b, y0, y1, prof_xz, slot, color_fn):
    """把 XZ 截面沿 Y 挤出（用于拱券环：截面就是拱环的扇形）。"""
    n = len(prof_xz)
    base = len(b.verts)
    for x, z in prof_xz:
        b.verts.append((x, y0, z))
    for x, z in prof_xz:
        b.verts.append((x, y1, z))
    for f in (tuple(range(n - 1, -1, -1)), tuple(range(n, 2 * n))):
        b.faces.append((tuple(base + i for i in f), slot,
                        color_fn([Vector(b.verts[base + i]) for i in f])))
    for i in range(n):
        j = (i + 1) % n
        f = (base + i, base + j, base + n + j, base + n + i)
        b.faces.append((f, slot, color_fn([Vector(b.verts[k]) for k in f])))


# ==========================================================================
# 材质 / 场景
# ==========================================================================
def clear_scene():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.cameras,
                 bpy.data.lights, bpy.data.actions):
        for d in list(coll):
            if d.users == 0:
                coll.remove(d)


def make_material(name, roughness, metallic=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    bsdf.inputs['Roughness'].default_value = roughness
    bsdf.inputs['Metallic'].default_value = metallic
    attr = nt.nodes.new('ShaderNodeVertexColor')
    attr.layer_name = "Col"
    attr.location = (-320, 200)
    nt.links.new(attr.outputs['Color'], bsdf.inputs['Base Color'])
    return mat


def make_materials(prefix):
    """四个顶点色材质槽。prefix 让不同资产的材质名在 Godot 里也分得开。"""
    return {
        "Stone": make_material(prefix + "Stone", 0.95),
        "Wood": make_material(prefix + "Wood", 0.90),
        "Iron": make_material(prefix + "Iron", 0.62, 0.35),
        "Plant": make_material(prefix + "Plant", 0.85),
    }


# ==========================================================================
# 低多边形石作：切角石块 / 沿 X 挤出 / 棱面明暗
# ==========================================================================
# 旧版墙身 = 一只只**正立方体**（砖模数 0.48 × 层高 0.25 × 墙厚 0.75），
# 棱角全是直角，颜色还逐面随机撒绿苔 —— 渲染出来是"我的世界"的积木墙：
# 没有体积感，也没有低多边形该有的"块面"。
#
# 这一版换成手工凿石：
#   · 石块 = **切角块**（棱角切掉 → 边缘有倒角高光，面块感立刻出来）；
#   · 石块**前后深度逐块不同** → 墙面是起伏的，不是两张平板；
#   · 颜色**按整块石头给**，面与面之间只按法线做明暗（朝上吃天光 / 朝下压暗）；
#   · 压顶是**一块块石板**（有缺、有厚薄、跟着墙头起伏），不是整齐的木条。
#
# ⚠️ 切角而不是"抖动顶点"：抖动会把面揉成非平面碎片，按棱面上色就花了；
#   切角得到的每一个面都是**精确平面**，棱线天然干净。
SEAM_W_M = 0.42          # 接缝端石列的进深（米）
STONE_CHAMFER_M = 0.045  # 石块切角（X / Z 方向）
STONE_CHAMFER_Y_M = 0.05  # 石块切角（Y 方向：前后棱）
FLAG_CHAMFER_M = 0.026   # 压顶石板切角
SEAM_PROFILE_SEED = 20261115


def _poly_normal(pts):
    """Newell 法求多边形法线（比三点叉乘稳，凹多边形也不会翻）。"""
    n = Vector((0.0, 0.0, 0.0))
    m = len(pts)
    for i in range(m):
        a = Vector(pts[i])
        c = Vector(pts[(i + 1) % m])
        n.x += (a.y - c.y) * (a.z + c.z)
        n.y += (a.z - c.z) * (a.x + c.x)
        n.z += (a.x - c.x) * (a.y + c.y)
    return n


def add_poly(b, pts, slot, color, ref):
    """加一个多边形面，绕序自动校正成"法线背离 ref"（即朝外）。

    color 可以是固定颜色，也可以是 color_fn(normal, center) -> color。
    """
    n = _poly_normal(pts)
    if n.length < 1e-9:
        return                       # 零面积面（退化）直接丢掉：Godot 里会变成黑斑
    n.normalize()
    c = Vector((0.0, 0.0, 0.0))
    for p in pts:
        c += Vector(p)
    c /= len(pts)
    if n.dot(c - Vector(ref)) < 0.0:
        pts = list(reversed(pts))
    b.add(pts, slot, color(n, c) if callable(color) else color)


def add_box(b, x0, x1, y0, y1, z0, z1, slot, color):
    """轴对齐盒子；color 可以是固定色，也可以是 color_fn(normal, center)。

    和 box() 的区别：box() 的颜色只能是"上/侧/底"三档固定色，
    这里每个面都能按自己的法线取色（内芯这种"整块一个暗调"的东西要这个）。
    """
    V = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
         (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    ref = ((x0 + x1) * 0.5, (y0 + y1) * 0.5, (z0 + z1) * 0.5)
    for idx in BOX_FACES:
        add_poly(b, [V[i] for i in idx], slot, color, ref)


def extrude_x(b, x0, x1, prof_yz, slot, color):
    """把 YZ 剖面沿 X 挤出（基座 / 接缝端石）。

    prof_yz 是 (y, z) 列表，绕序随便 —— add_poly 会按剖面形心自动校正朝外。
    """
    n = len(prof_yz)
    cy = sum(p[0] for p in prof_yz) / n
    cz = sum(p[1] for p in prof_yz) / n
    ref = ((x0 + x1) * 0.5, cy, cz)
    for x in (x0, x1):
        add_poly(b, [(x, p[0], p[1]) for p in prof_yz], slot, color, ref)
    for i in range(n):
        j = (i + 1) % n
        add_poly(b, [(x0, prof_yz[i][0], prof_yz[i][1]),
                     (x1, prof_yz[i][0], prof_yz[i][1]),
                     (x1, prof_yz[j][0], prof_yz[j][1]),
                     (x0, prof_yz[j][0], prof_yz[j][1])], slot, color, ref)


def facet_shade(base, n, k=1.0):
    """棱面明暗：朝上的面吃天光、朝下的面压暗。

    低多边形的"块面感"来自**明暗差**，不是来自随机色 —— 所以这里只按法线
    给一个窄区间的系数（0.86~1.10），同一块石头的面与面之间永远是同一个调子。
    """
    if n.z > 0.45:
        f = 1.10
    elif n.z > 0.10:
        f = 1.03
    elif n.z > -0.35:
        f = 0.92
    else:
        f = 0.70              # 朝下的面压得很暗：低多边形靠明暗分层，不靠噪点
    f *= 1.0 + 0.07 * n.x          # 朝 +X 的面略亮一点，两侧不要死板对称
    return np.clip(np.asarray(base, dtype=float) * f * k, 0.0, 1.0)


def _block_extents(hx, hy, hz, yaw=0.0, tilt=0.0, roll=0.0):
    """切角块旋转后在三个轴上的半包络（取 8 个角点算，精确）。

    碎石要"半埋进地里"，就得知道旋转后最低点在哪 ——
    所以这里把三个轴一起算出来，而不是只算 X。
    """
    ex = ey = ez = 0.0
    for sx in (-1, 1):
        for sy in (-1, 1):
            for sz in (-1, 1):
                px, py, pz = sx * hx, sy * hy, sz * hz
                if tilt:
                    a = math.radians(tilt)
                    ca, sa = math.cos(a), math.sin(a)
                    px, pz = px * ca + pz * sa, -px * sa + pz * ca
                if yaw:
                    a = math.radians(yaw)
                    ca, sa = math.cos(a), math.sin(a)
                    px, py = px * ca - py * sa, px * sa + py * ca
                if roll:
                    a = math.radians(roll)
                    ca, sa = math.cos(a), math.sin(a)
                    py, pz = py * ca - pz * sa, py * sa + pz * ca
                ex = max(ex, abs(px))
                ey = max(ey, abs(py))
                ez = max(ez, abs(pz))
    return ex, ey, ez


def _block_x_extent(hx, hy, hz, yaw, tilt, roll=0.0):
    """（兼容旧调用）只要 X 方向的半包络。"""
    return _block_extents(hx, hy, hz, yaw, tilt, roll)[0]


def _make_rot(cx, cy, cz, yaw=0.0, tilt=0.0, roll=0.0):
    """返回一个"绕块心旋转"的函数（hewn_block / hewn_block_lite 共用）。"""

    def rot(p):
        px, py, pz = p[0] - cx, p[1] - cy, p[2] - cz
        if tilt:
            a = math.radians(tilt)
            ca, sa = math.cos(a), math.sin(a)
            px, pz = px * ca + pz * sa, -px * sa + pz * ca
        if yaw:
            a = math.radians(yaw)
            ca, sa = math.cos(a), math.sin(a)
            px, py = px * ca - py * sa, px * sa + py * ca
        if roll:
            a = math.radians(roll)
            ca, sa = math.cos(a), math.sin(a)
            py, pz = py * ca - pz * sa, py * sa + pz * ca
        return (px + cx, py + cy, pz + cz)

    return rot


def hewn_block_lite(b, x0, x1, y0, y1, z0, z1, slot, color, bevel=0.035,
                    yaw=0.0, tilt=0.0, roll=0.0, ref=None, mode="top"):
    """轻量石块：**10 面 / 20 三角面**（切角块 hewn_block 是 26 面 / 44 三角面）。

    为什么要有"减面版"：切角块用在墙身正面的石头上是值的，但碎石、护墙石、
    接缝端石这些**又小又不起眼**的零件用它是浪费 —— 一段墙里碎石就有二三十块，
    光它们就 1300 面。

    两种减法（都是 10 面）：

    | mode | 倒角在哪 | 适合 |
    | --- | --- | --- |
    | `"top"`（默认） | **顶面一圈** | 碎石、护墙石 —— 从上往下看的零件 |
    | `"vert"` | **四条竖棱** | 墙身正面的石头 —— 玩家是**平视**看墙的，正面那四条竖边的倒角高光才是"石头感"的来源 |

    `"vert"` 的正面是**切了角的大面**（八边形），四条竖棱各一个窄倒角面；
    顶面是平的（反正大多被压顶或上一层石头盖住）。
    """
    cx = (x0 + x1) * 0.5
    cy = (y0 + y1) * 0.5
    cz = (z0 + z1) * 0.5
    rot = _make_rot(cx, cy, cz, yaw, tilt, roll)

    if mode == "vert":
        hx = (x1 - x0) * 0.5
        hy = (y1 - y0) * 0.5
        bxc = min(bevel, hx * 0.40)
        byc = min(bevel, hy * 0.40)

        def A(sx, sy, z):
            return (cx + sx * hx, cy + sy * (hy - byc), z)

        def B(sx, sy, z):
            return (cx + sx * (hx - bxc), cy + sy * hy, z)

        faces = [
            [A(-1, -1, z1), B(-1, -1, z1), B(1, -1, z1), A(1, -1, z1),
             A(1, 1, z1), B(1, 1, z1), B(-1, 1, z1), A(-1, 1, z1)],   # 顶面（切角八边形）
            [A(-1, -1, z0), B(-1, -1, z0), B(1, -1, z0), A(1, -1, z0),
             A(1, 1, z0), B(1, 1, z0), B(-1, 1, z0), A(-1, 1, z0)],   # 底面
            [A(1, -1, z0), A(1, 1, z0), A(1, 1, z1), A(1, -1, z1)],   # +X 面
            [A(-1, -1, z0), A(-1, 1, z0), A(-1, 1, z1), A(-1, -1, z1)],  # -X 面
            [B(-1, -1, z0), B(1, -1, z0), B(1, -1, z1), B(-1, -1, z1)],  # -Y 面
            [B(-1, 1, z0), B(1, 1, z0), B(1, 1, z1), B(-1, 1, z1)],     # +Y 面
        ]
        for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):          # 四条竖棱倒角
            faces.append([B(sx, sy, z0), A(sx, sy, z0),
                          A(sx, sy, z1), B(sx, sy, z1)])
    else:
        bx = min(bevel, (x1 - x0) * 0.30)
        by = min(bevel, (y1 - y0) * 0.30)
        bz = min(bevel, (z1 - z0) * 0.40)
        zb = z1 - bz
        Bv = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0)]
        Sv = [(p[0], p[1], zb) for p in Bv]
        Tv = [(x0 + bx, y0 + by, z1), (x1 - bx, y0 + by, z1),
              (x1 - bx, y1 - by, z1), (x0 + bx, y1 - by, z1)]
        faces = [Bv]
        for i in range(4):
            j = (i + 1) % 4
            faces.append([Bv[i], Bv[j], Sv[j], Sv[i]])
            faces.append([Sv[i], Sv[j], Tv[j], Tv[i]])
        faces.append(Tv)

    r = ref if ref is not None else (cx, cy, cz)
    for f in faces:
        add_poly(b, [rot(p) for p in f], slot, color, r)
    xs = [p[0] for f in faces for p in f]
    return min(xs), max(xs)


def hewn_block(b, x0, x1, y0, y1, z0, z1, slot, color, chamfer=None,
               yaw=0.0, tilt=0.0, roll=0.0, ref=None, chz_bottom=None):
    """切角石块：24 顶点 / 26 面（6 主面 + 12 棱面 + 8 角三角），全部精确平面。

    yaw  : 绕竖直轴（Z）偏转（度）—— 砌体不要码得整整齐齐。
    tilt : 绕 Y 轴偏转（度）—— 石头轻微歪头。
    roll : 绕 X 轴偏转（度）—— 石头**倒下来靠着墙**时用（YZ 面内翻倒）。
    三者都绕块心旋转，所以块仍然是凸的、面仍然是平面。
    返回旋转后的 X 范围（调用方据此保证不越出墙段）。
    """
    if chamfer is None:
        chamfer = (STONE_CHAMFER_M, STONE_CHAMFER_Y_M, STONE_CHAMFER_M)
    hx = (x1 - x0) * 0.5
    hy = (y1 - y0) * 0.5
    hz = (z1 - z0) * 0.5
    cx = (x0 + x1) * 0.5
    cy = (y0 + y1) * 0.5
    cz = (z0 + z1) * 0.5
    chx = min(chamfer[0], hx * 0.55)
    chy = min(chamfer[1], hy * 0.55)
    chz = min(chamfer[2], hz * 0.55)
    # 底面倒角可以不要：石头总是**压在下一层上**（下压 2.5 cm），
    # 底边根本看不见，但省掉的是 4 个棱面 + 4 个角三角（44 → 32 三角面）。
    chzb = chz if chz_bottom is None else min(chz_bottom, hz * 0.55)

    corner = {}
    for sx in (-1, 1):
        for sy in (-1, 1):
            for sz in (-1, 1):
                cz_i = (hz - chz) if sz > 0 else (hz - chzb)
                corner[(sx, sy, sz)] = (
                    (cx + sx * hx,         cy + sy * (hy - chy), cz + sz * cz_i),  # x 面
                    (cx + sx * (hx - chx), cy + sy * hy,        cz + sz * cz_i),  # y 面
                    (cx + sx * (hx - chx), cy + sy * (hy - chy), cz + sz * hz),    # z 面
                )

    rot = _make_rot(cx, cy, cz, yaw, tilt, roll)

    faces = []
    # ---- 4 个侧面（x 面 / y 面）：切了竖棱的四边形 ----
    for s in (-1, 1):
        faces.append([rot(corner[(s, sy, sz)][0]) for sy, sz in
                      ((-1, -1), (1, -1), (1, 1), (-1, 1))])
        faces.append([rot(corner[(sx, s, sz)][1]) for sx, sz in
                      ((-1, -1), (1, -1), (1, 1), (-1, 1))])
    # ---- 4 条竖棱的倒角（沿 Z，一直都在）----
    for sx in (-1, 1):
        for sy in (-1, 1):
            faces.append([rot(corner[(sx, sy, -1)][0]), rot(corner[(sx, sy, 1)][0]),
                          rot(corner[(sx, sy, 1)][1]), rot(corner[(sx, sy, -1)][1])])
    # ---- 顶面 ----
    if chz > 0.0:
        faces.append([rot(corner[(sx, sy, 1)][2]) for sx, sy in
                      ((-1, -1), (1, -1), (1, 1), (-1, 1))])
        # 顶面 4 条棱的倒角（只有顶面这一圈）
        for sy in (-1, 1):
            faces.append([rot(corner[(-1, sy, 1)][1]), rot(corner[(1, sy, 1)][1]),
                          rot(corner[(1, sy, 1)][2]), rot(corner[(-1, sy, 1)][2])])
        for sx in (-1, 1):
            faces.append([rot(corner[(sx, -1, 1)][0]), rot(corner[(sx, 1, 1)][0]),
                          rot(corner[(sx, 1, 1)][2]), rot(corner[(sx, -1, 1)][2])])
        # 顶部 4 个角三角
        for sx in (-1, 1):
            for sy in (-1, 1):
                a, bb, c = corner[(sx, sy, 1)]
                faces.append([rot(a), rot(bb), rot(c)])
    else:
        # 顶面不倒角 → 顶面直接是"切了竖棱的八边形"
        faces.append([rot(corner[(-1, -1, 1)][0]), rot(corner[(-1, -1, 1)][1]),
                      rot(corner[(1, -1, 1)][1]),  rot(corner[(1, -1, 1)][0]),
                      rot(corner[(1, 1, 1)][0]),   rot(corner[(1, 1, 1)][1]),
                      rot(corner[(-1, 1, 1)][1]),  rot(corner[(-1, 1, 1)][0])])
    # ---- 底面 ----
    if chzb > 0.0:
        faces.append([rot(corner[(sx, sy, -1)][2]) for sx, sy in
                      ((-1, -1), (1, -1), (1, 1), (-1, 1))])
        for sy in (-1, 1):
            faces.append([rot(corner[(-1, sy, -1)][1]), rot(corner[(1, sy, -1)][1]),
                          rot(corner[(1, sy, -1)][2]), rot(corner[(-1, sy, -1)][2])])
        for sx in (-1, 1):
            faces.append([rot(corner[(sx, -1, -1)][0]), rot(corner[(sx, 1, -1)][0]),
                          rot(corner[(sx, 1, -1)][2]), rot(corner[(sx, -1, -1)][2])])
        for sx in (-1, 1):
            for sy in (-1, 1):
                a, bb, c = corner[(sx, sy, -1)]
                faces.append([rot(a), rot(bb), rot(c)])
    else:
        # 底面倒角不要 → 底面直接是"切了竖棱的八边形"（石头压在下一层上，看不见）
        faces.append([rot(corner[(-1, -1, -1)][0]), rot(corner[(-1, -1, -1)][1]),
                      rot(corner[(1, -1, -1)][1]),  rot(corner[(1, -1, -1)][0]),
                      rot(corner[(1, 1, -1)][0]),   rot(corner[(1, 1, -1)][1]),
                      rot(corner[(-1, 1, -1)][1]),  rot(corner[(-1, 1, -1)][0])])

    r = ref if ref is not None else (cx, cy, cz)
    for f in faces:
        add_poly(b, f, slot, color, r)
    xs = [p[0] for f in faces for p in f]
    return min(xs), max(xs)


def seam_column(t_m=WALL_T_M, z0=PLINTH_M, z1=WALL_H_M - COPING_H_M,
                rows=WALL_ROWS, moss=0.20, seed=SEAM_PROFILE_SEED):
    """接缝端的"端石列"模板：逐行给出石头的深度 / 切角 / 颜色。

    所有墙段共用同一份（固定种子）→ 相邻两段的端面**逐点重合**，接缝零缝隙。

    端石列 = 和墙身一模一样的砌法（逐层错缝的石头），只是**接缝那一面被切平**。
    ⚠️ 早先这里是一根"整根挤出的光柱"，渲染出来像两根**混凝土柱**夹在墙里 ——
       又平又亮又没层次。现在换成切角石块逐层码，接缝处就是普通的墙。

    返回每行的 (front, back, chamfer, base_color, mossy)。
    """
    rng = random.Random(seed)
    row_h = (z1 - z0) / rows
    out = []
    for k in range(rows):
        t = k / max(1, rows - 1.0)
        base, mossy = _stone_base(rng, t, moss)
        out.append({
            "front": -t_m * 0.5 + rng.uniform(-0.010, 0.080),
            "back": t_m * 0.5 - rng.uniform(0.0, 0.080),
            "ch": (rng.uniform(0.030, 0.050), rng.uniform(0.035, 0.062),
                   rng.uniform(0.022, 0.040)),
            "base": base,
            "mossy": mossy,
            "z0": z0 + k * row_h,
            "z1": z0 + (k + 1) * row_h,
        })
    return out


def _stone_base(rng, t, moss, course_u=None):
    """取一块石头的底色（**整块石头一个调子**）+ 是不是长苔。

    t = 高度归一（0 = 墙脚，1 = 墙头）。越靠下越暗（潮气 + 阴影）。
    苔藓是**整块石头**染的，不是逐面撒点 —— 撒点就是彩色噪点。

    course_u = 这一层（course）的色调。同一层的石头围绕它小幅浮动，
    于是墙读起来是**一层一层砌上去的**（有横向的层次），
    而不是一堆亮度乱跳的积木 —— 这是"不杂"的关键。
    """
    if course_u is None:
        course_u = rng.random()
    u = min(1.0, max(0.0, course_u + rng.uniform(-0.15, 0.15)))
    base = PAL["stone_l"] if u < 0.30 else (PAL["stone_m"] if u < 0.78 else PAL["stone_d"])
    base = lerp3(PAL["stone_d"], base, 0.68 + 0.32 * t)
    if rng.random() < 0.07:
        base = lerp3(base, PAL["stone_warm"], 0.24)
    if rng.random() < 0.06:
        base = lerp3(base, PAL["stone_pale"], 0.18)
    mossy = rng.random() < moss * (0.10 + 0.85 * t)
    # 墙脚：潮气 + 泥垢 → 最下面一两层压得更暗更脏（"老墙"的关键细节）
    if t < 0.24:
        damp = lerp3(PAL["stone_x"], PAL["moss_d"], 0.40)
        base = lerp3(base, damp, (0.24 - t) * 1.9)
    return base, mossy


def _stone_color(base, mossy, kv=1.0):
    """石块的逐面着色函数：面与面之间只按法线做明暗（块面感来自明暗）。

    苔藓染在**朝上的整块棱面**上（不是零星撒点，也不是整块石头染绿）——
    这正是 low_poly_rock 的做法：一块朝上的大棱面整块长苔，
    于是"哪个面朝上"一眼就看得出来，墙也就有了体积感。
    """

    def col(n, c):
        out = facet_shade(base, n, kv)
        if mossy:
            if n.z > 0.32:
                out = lerp3(out, PAL["moss_m"], 0.55)     # 朝上的面整块长苔
            elif abs(n.y) > 0.45:
                out = lerp3(out, PAL["moss_m"], 0.18)     # 侧面带一点绿意
        return out

    return col


def build_base_rubble(b, rng, xa, xb, slot, t_m=WALL_T_M, plinth_m=PLINTH_M,
                       plinth_out_m=PLINTH_OUT_M, moss=0.20, tag=0.0,
                       piles=3, scatter=5, fallen=1, hot=None):
    """墙脚的碎石堆 —— 墙是**塌**出来的，脚下就该有掉下来的碎块。

    · 碎石是**一堆一堆**的（每堆 2~5 块，越往上越小），不是撒的一排小石子；
    · 碎块**坐在地上**（最低点正好 z=0，不许埋进地里，assets/AGENTS.md §1），
      堆起来的部分自然搭在下面那块上；
    · 塌口底下那堆最大（塌下来的石头就落在那儿）；
    · 两侧都有（墙是双面可见的）；
    · 另有整块**倒下来靠着墙**的大石头（用 roll 翻倒）；
    · 碎块会凸出墙体外廓 → 单段的"厚度"是**含碎石的包络**，
      基准表里量到的是包络，不是墙厚本身。
    """
    y_face = t_m * 0.5 + plinth_out_m + 0.025     # 基座外侧面
    hot_x, hot_w = hot if hot else (None, 0.0)

    def _chunk(cx, side, cz_floor, r, mossy_p=0.45, dark=0.45, out_r=0.05):
        """摆一块碎石；返回这一块的顶面高度（下一块搭上去用）。"""
        hx = min(r * rng.uniform(0.80, 1.50), 0.215)
        hy = r * rng.uniform(0.60, 0.95)
        hz = r * rng.uniform(0.40, 0.85)
        yaw = rng.uniform(0.0, 360.0)
        tilt = rng.uniform(-12.0, 12.0)
        roll = rng.uniform(-14.0, 14.0)
        ex, ey, ez = _block_extents(hx, hy, hz, yaw, tilt, roll)
        cx = min(max(cx, xa + ex + 0.03), xb - ex - 0.03)
        cy = side * min(y_face + out_r,
                        max(0.02, y_face + 0.30 - ey))
        cz = cz_floor + ez
        base = lerp3(PAL["stone_d"], PAL["stone_x"], rng.uniform(0.0, dark * 0.6))
        mossy = rng.random() < mossy_p * 0.62
        c = _stone_color(base, mossy, rng.uniform(0.92, 1.04))
        hewn_block_lite(b, cx - hx, cx + hx, cy - hy, cy + hy, cz - hz, cz + hz,
                        slot, c, bevel=0.020,
                        yaw=yaw, tilt=tilt, roll=roll)
        return cz + ez

    for side in (-1, 1):
        # ---- 碎石堆 ----
        for p in range(piles):
            if hot_x is not None and rng.random() < 0.6:
                px = hot_x + rng.uniform(-hot_w, hot_w)
            else:
                px = rng.uniform(xa + 0.2, xb - 0.2)
            top = 0.0
            n_ch = rng.randint(2, 4)
            for c in range(n_ch):
                r = rng.uniform(0.080, 0.190) * (1.0 - 0.12 * c)  # 越往上越小
                px += rng.uniform(-0.09, 0.09)
                top = _chunk(px, side, max(0.0, top - 0.05), r,
                             out_r=rng.uniform(0.0, 0.07))

        # ---- 零星散落的碎石 ----
        for c in range(scatter):
            px = rng.uniform(xa + 0.15, xb - 0.15)
            r = rng.uniform(0.050, 0.135)
            _chunk(px, side, 0.0, r, mossy_p=0.55, dark=0.55,
                   out_r=rng.uniform(0.09, 0.21))

        # ---- 整块倒下来靠着墙的大石头 ----
        for i in range(fallen):
            r = rng.uniform(0.13, 0.20)
            hx = r * rng.uniform(0.90, 1.30)
            hy = r * rng.uniform(0.55, 0.80)
            hz = r * rng.uniform(0.55, 0.85)
            yaw = rng.uniform(-25.0, 25.0)
            roll = side * rng.uniform(20.0, 38.0)   # 往墙那边倒
            ex, ey, ez = _block_extents(hx, hy, hz, yaw, 0.0, roll)
            px = min(max(rng.uniform(xa + 0.2, xb - 0.2), xa + ex + 0.03),
                     xb - ex - 0.03)
            cy = side * min(y_face + rng.uniform(0.02, 0.08),
                            max(0.02, y_face + 0.30 - ey))
            cz = ez
            base = lerp3(PAL["stone_m"], PAL["stone_d"], rng.uniform(0.2, 0.8))
            mossy = rng.random() < 0.35
            c = _stone_color(base, mossy, rng.uniform(0.94, 1.03))
            hewn_block_lite(b, px - hx, px + hx, cy - hy, cy + hy, cz - hz, cz + hz,
                            slot, c, bevel=0.030, yaw=yaw, roll=roll)


def stone_base(rng, t=0.5, moss=0.20, course_u=None):
    """对外版：取一块石头的底色 + 是不是长苔（大门拱身等也用这一套）。"""
    return _stone_base(rng, t, moss, course_u)


def stone_color(base, mossy, kv=1.0):
    """对外版：石块的逐面着色函数（一个平面 = 一块颜色）。"""
    return _stone_color(base, mossy, kv)


def build_coping_slabs(b, rng, x0, x1, top_at, slot, t_m=WALL_T_M,
                       coping_h_m=COPING_H_M, coping_out_m=COPING_OUT_M,
                       bay_m=WALL_BAY_M, joint_start=False, joint_end=False,
                       joint_z=None, tile_miss=0.20, tag=0.0, base_tone=None):
    """压顶：一块块石板（不是"巧克力条"）。

    · 每块石板独立：有缺、有厚薄、跟着墙头起伏，还带一点歪斜；
    · 接缝端的那块**必须存在、厚度固定、底面固定**（否则两段墙接起来墙顶掉一级）；
    · X 方向不外扩（拼接缝契约第 3 条）。

    top_at(x0, x1) 给石板底面所在高度（墙头剖面）。
    joint_z 给接缝端石板的底面高度（默认取墙头满高）。
    """
    n_tile, tile_w = tile_layout(x1 - x0, bay_m)
    for i in range(n_tile):
        is_joint = (i == 0 and joint_start) or (i == n_tile - 1 and joint_end)
        if not is_joint and rng.random() < tile_miss:
            continue
        tx0 = x0 + i * tile_w
        tx1 = tx0 + tile_w
        if not is_joint:
            tx0 += 0.014
            tx1 -= 0.014
        z_base = top_at(tx0, tx1)
        hh = coping_h_m if is_joint else coping_h_m * rng.uniform(0.60, 1.0)
        y_half = t_m * 0.5 + coping_out_m
        if is_joint:
            z_base = joint_z if joint_z is not None else z_base
        else:
            y_half -= rng.uniform(0.0, 0.03)      # 内侧收一点，石板就有厚薄
        base = PAL["stone_m"] if base_tone is None else base_tone
        base = lerp3(base, PAL["stone_d"], rng.uniform(0.0, 0.50))
        mossy = rng.random() < 0.30
        if mossy:
            base = lerp3(base, PAL["moss_m"], rng.uniform(0.12, 0.30))

        def col(n, c, base=base, mossy=mossy):
            out = facet_shade(base, n)
            if mossy and n.z > 0.30:
                out = lerp3(out, PAL["moss_d"], 0.30)
            return out

        if is_joint:
            # 接缝端那一片决定接缝剖面 → 留切角块（轻量块的剖面点数不一样）
            hewn_block(b, tx0, tx1, -y_half, y_half, z_base - 0.02, z_base + hh,
                       slot, col, chamfer=(FLAG_CHAMFER_M, FLAG_CHAMFER_M, FLAG_CHAMFER_M))
        else:
            hewn_block_lite(b, tx0, tx1, -y_half, y_half, z_base - 0.02, z_base + hh,
                            slot, col, bevel=FLAG_CHAMFER_M,
                            tilt=rng.uniform(-1.6, 1.6))
    return n_tile


# ==========================================================================
# 破败矮墙（大门两翼 / 独立破墙共用同一份实现）
# ==========================================================================
def build_wall_segment(b, rng, xa, xb, *, t_m=WALL_T_M, h_m=WALL_H_M,
                       plinth_m=PLINTH_M, plinth_out_m=PLINTH_OUT_M,
                       rows=WALL_ROWS, coping_h_m=COPING_H_M,
                       coping_out_m=COPING_OUT_M, bay_m=WALL_BAY_M,
                       slot_name="Stone", plant_slot="Plant", tag=0.0,
                       decay=0.16, decay_slope=0.45, moss=0.20,
                       joint_ends=("start", "end"), tile_miss=0.20,
                       decay_end="end", gap_chance=0.75, gap_rows=6.5,
                       keep_rows=3.0, ivy=2):
    """在 [xa, xb] 上砌一段破败矮墙（低多边形 · 切角石版）。

    joint_ends 里的 "start"/"end" 表示该端是**接缝端**：那里放一块"端石"，
    它的砌法 = seam_column() 模板（所有段共用同一份）→ 相邻两段的端面逐点重合，
    接缝既没有台阶也没有缝（见文件头「拼接缝契约」）。
    大门两翼用单个接缝端（朝外那一端），独立破墙两段都用。

    decay_end 指定**哪一端更残破**。墙头从这一端往另一端逐渐长高，
    所以两端接缝永远一样高，破败只发生在中段。

    gap_chance / gap_rows 控制"塌口"的几率与深浅；keep_rows 是普通残破
    最多能削掉几层。拼接用的模块要**小 keep_rows / 小 gap_rows**：
    一段墙如果中间塌得很深，复制几份拼起来就是一排柱子而不是一堵墙。
    """
    if xb < xa:
        xa, xb = xb, xa
    S = b.slot(slot_name)
    PL = b.slot(plant_slot)
    y0, y1 = -t_m * 0.5, t_m * 0.5
    length = xb - xa
    j_start = "start" in joint_ends
    j_end = "end" in joint_ends
    flip = (decay_end == "start")

    full_h = h_m - coping_h_m
    row_h = (full_h - plinth_m) / rows

    # ---- 墙头高度剖面：越靠近 decay_end 越残破，再挖一个明显的崩塌缺口 ----
    n_bay = max(2, int(round(length / bay_m)))
    bay_w = length / n_bay
    heights = []
    for i in range(n_bay):
        far = (n_bay - 1 - i) / (n_bay - 1.0) if flip else i / (n_bay - 1.0)
        h = full_h
        if rng.random() < decay + decay_slope * far:
            h -= row_h * rng.uniform(0.7, keep_rows)
        heights.append(max(plinth_m + row_h * 0.55, h))

    # 崩塌缺口：避开接缝端（否则接缝处会出现一个洞，拼接就断了），
    # 并且偏向 decay_end 那一侧 —— 残破要"越往外越厉害"。
    g_lo = 1 if j_start else 0
    g_hi = (n_bay - 2) if j_end else (n_bay - 1)
    if flip:
        g_lo, g_hi = (n_bay - 1 - g_hi), (n_bay - 1 - g_lo)
    if g_hi > g_lo and rng.random() < gap_chance:
        lo = max(g_lo, g_hi - max(1, int(n_bay * 0.45)))
        gap = rng.randrange(lo, g_hi + 1)
        gz = max(plinth_m + row_h * 0.55, full_h - row_h * gap_rows)
        heights[gap] = gz
        if gap - 1 >= 0:
            heights[gap - 1] = min(heights[gap - 1], gz + row_h * 1.1)
        if gap + 1 < n_bay:
            heights[gap + 1] = min(heights[gap + 1], gz + row_h * 0.7)

    # **接缝端强制满高** —— 这是"过渡自然"的关键：两段墙的端头一样高
    if j_start:
        heights[0] = full_h
    if j_end:
        heights[n_bay - 1] = full_h

    # **破口**：某一 bay 的上半段整块塌掉（墙被掏空 / 撞穿）。
    # 只塌上半段 —— 下半段是承重的，整段塌光的话墙就散架了，
    # 多段拼起来也只剩一排土堆。
    breach = -1
    if n_bay >= 4 and rng.random() < 0.45:
        lo = 1 if j_start else 0
        hi = (n_bay - 2) if j_end else (n_bay - 1)
        if hi > lo:
            breach = rng.randrange(lo, hi + 1)
            heights[breach] = min(heights[breach], full_h - row_h * 1.6)

    def top_at(x):
        i = min(n_bay - 1, max(0, int((x - xa) / bay_w)))
        return heights[i]

    def top_min(x0, x1):
        i0 = min(n_bay - 1, max(0, int((x0 - xa) / bay_w)))
        i1 = min(n_bay - 1, max(0, int((x1 - xa) / bay_w)))
        return min(heights[i0:i1 + 1])

    # ---- 基座：整条挤出，X 严格切在 [xa, xb]（契约第 3 条），侧面带收分 ----
    po = plinth_out_m
    plinth_prof = [
        (-(t_m * 0.5 + po + 0.025), 0.0),
        (-(t_m * 0.5 + po + 0.005), 0.07),
        (-(t_m * 0.5 + po * 0.60), plinth_m - 0.045),
        (-(t_m * 0.5 + po * 0.28), plinth_m),
        ((t_m * 0.5 + po * 0.28), plinth_m),
        ((t_m * 0.5 + po * 0.60), plinth_m - 0.045),
        ((t_m * 0.5 + po + 0.005), 0.07),
        ((t_m * 0.5 + po + 0.025), 0.0),
    ]
    plinth_col = lerp3(PAL["stone_d"], PAL["stone_m"], 0.30)

    def _plinth_col(n, c):
        col = facet_shade(plinth_col, n)
        if n.z < -0.30:
            col = col * 0.82
        return col

    extrude_x(b, xa, xb, plinth_prof, S, _plinth_col)

    # ---- 接缝端石列：逐层码起来的切角石块，接缝那一面切平 ----
    # 模板所有墙段共用同一份（固定种子）→ 相邻两段的端面逐点重合。
    col = seam_column(t_m, plinth_m, full_h, rows, moss)
    for k, row in enumerate(col):
        c = _stone_color(row["base"], row["mossy"], 0.98)
        hewn_block_lite(b, xa, xa + SEAM_W_M,
                        row["front"], row["back"], row["z0"] - 0.02, row["z1"], S, c,
                        bevel=0.030)
        hewn_block_lite(b, xb - SEAM_W_M, xb,
                        row["front"], row["back"], row["z0"] - 0.02, row["z1"], S, c,
                        bevel=0.030)

    # ---- 墙芯：逐 bay 的暗色内芯（塌口 / 缺石处露出来的就是它）----
    # 没有内芯的话，缺一块石头就是**看穿墙**，墙立刻变"纸片"。
    # 有了内芯，缺石处是一块发暗的凹面 → 墙有厚度、有阴影，才像废墟。
    core_in = 0.10
    core_col = lerp3(PAL["stone_d"], PAL["moss_d"], 0.30)
    for i in range(n_bay):
        cx0 = xa + i * bay_w
        cx1 = cx0 + bay_w
        if i == 0:
            cx0 = xa
        if i == n_bay - 1:
            cx1 = xb
        ztop = heights[i]
        if ztop <= plinth_m + 0.02:
            continue

        def _core_col(n, c, cc=core_col):
            out = facet_shade(cc, n)
            if n.z < -0.30:
                out = out * 0.85
            return out

        add_box(b, cx0, cx1, y0 + core_in, y1 - core_in, plinth_m - 0.02, ztop,
                S, _core_col)

    # ---- 墙身：逐层错缝砌石（外皮）----
    # 接缝端留出端石列：接缝平面上只允许有端石一个几何，
    # 端面剖面因此可解析（verify_seams() 逐点核对）。
    hard_lo = xa + SEAM_W_M
    hard_hi = xb - SEAM_W_M
    for k in range(rows):
        bz0 = plinth_m + k * row_h
        bz1 = bz0 + row_h
        course_u = rng.random()          # 这一层的色调（横向层次）
        x = hard_lo
        while True:
            w = rng.uniform(0.34, 0.62) if rng.random() < 0.4 else rng.uniform(0.44, 0.72)
            avail = hard_hi - x
            if avail < 0.12:
                break
            eroded = 0.0
            if k < rows - 1 and rng.random() < 0.34:
                eroded = rng.uniform(0.0, 0.30 * row_h)
            ztop = min(bz1 - eroded, top_min(x, x + w))
            # 缺石：越靠上层越容易缺（下面几层是承重的，塌了整段墙就散）
            miss = 0.05 + 0.16 * (k / max(1, rows - 1.0))
            in_breach = (breach >= 0 and
                         int((x + w * 0.5 - xa) / bay_w) == breach and
                         k >= rows * 0.35)
            if ztop > bz0 + 0.05 and not in_breach and rng.random() >= miss:
                # 前后深度逐块不同 → 墙面是起伏的，不是两张平板
                front = y0 + rng.uniform(-0.010, 0.130)
                if rng.random() < 0.12:
                    front = y0 + rng.uniform(0.130, 0.200)   # 滑出来的石头凸出墙面
                back = y1 - rng.uniform(0.0, 0.060)
                if back - front < 0.54:              # 墙芯不能太薄
                    mid = (front + back) * 0.5
                    front = mid - 0.27
                    back = mid + 0.27
                # 竖向也随手挪一点 → 层缝不再是一条直尺画的线
                zbot = bz0 - 0.025 + rng.uniform(-0.030, 0.018)
                yaw = rng.uniform(-4.2, 4.2)
                tilt = rng.uniform(-1.3, 1.3)
                if rng.random() < 0.12:
                    # 有几块是**滑出来歪在墙上**的：前凸 + 大偏转
                    tilt = rng.uniform(-16.0, 16.0)
                    yaw = rng.uniform(-9.0, 9.0)
                hx = min(w * 0.5, avail * 0.5)
                hy = (back - front) * 0.5
                hz = (ztop - zbot) * 0.5
                ext = _block_x_extent(hx, hy, hz, yaw, tilt)
                if 2.0 * ext > avail:
                    hx = max(0.05, hx - (2.0 * ext - avail) * 0.5)
                    ext = _block_x_extent(hx, hy, hz, yaw, tilt)
                if x + 2.0 * ext > hard_hi:
                    x = hard_hi - 2.0 * ext
                # 一块石头**一个调子**：底色按石头给，面与面之间只做明暗
                t = min(1.0, max(0.0, (bz0 - plinth_m) / max(1e-6, full_h - plinth_m)))
                base, mossy = _stone_base(rng, t, moss, course_u)
                c = _stone_color(base, mossy, rng.uniform(0.96, 1.04))

                # 崩口：有些石头的**前面被削掉一大块**、或**顶角崩了** ——
                # 完美完好的方石头再多也不是废墟。
                chy = rng.uniform(0.035, 0.070)
                if rng.random() < 0.14:
                    chy = rng.uniform(0.085, 0.135)      # 正面崩掉一大块
                chz = rng.uniform(0.022, 0.042)
                if rng.random() < 0.12:
                    chz = rng.uniform(0.055, 0.090)      # 顶角崩了
                chx = rng.uniform(0.030, 0.055)
                if rng.random() < 0.08:
                    chx = rng.uniform(0.060, 0.095)

                # 裂石：整块石头**裂成两半**，中间留一道缝，缝里露出暗色墙芯
                cracked = rng.random() < 0.16 and (x + ext - hx) > xa + 0.2
                if cracked:
                    xc = x + ext + rng.uniform(-0.06, 0.06)
                    gap = rng.uniform(0.016, 0.038)
                    hewn_block(b, x + ext - hx, xc - gap * 0.5,
                               front, back, zbot, ztop, S, c,
                               chamfer=(chx, chy, chz), chz_bottom=0.0,
                               yaw=yaw, tilt=tilt)
                    c2 = _stone_color(base, mossy, rng.uniform(0.94, 1.03))
                    hewn_block(b, xc + gap * 0.5, x + ext + hx,
                               front + rng.uniform(-0.025, 0.025), back, zbot, ztop,
                               S, c2, chamfer=(chx, chy, chz), chz_bottom=0.0,
                               yaw=yaw + rng.uniform(-3.0, 3.0),
                               tilt=tilt + rng.uniform(-1.5, 1.5))
                else:
                    hewn_block(b, x + ext - hx, x + ext + hx,
                               front, back, zbot, ztop, S, c,
                               chamfer=(chx, chy, chz), chz_bottom=0.0,
                               yaw=yaw, tilt=tilt)
                x = x + 2.0 * ext - 0.02          # 相邻石头压 2 cm，不留缝
            else:
                x = x + w
            if x >= hard_hi - 1e-6:
                break

    # ---- 压顶：一块块石板 ----
    build_coping_slabs(b, rng, xa, xb, top_min, S, t_m=t_m,
                       coping_h_m=coping_h_m, coping_out_m=coping_out_m,
                       bay_m=bay_m, joint_start=j_start, joint_end=j_end,
                       joint_z=full_h, tile_miss=tile_miss, tag=tag)

    # ---- 塌口：缺口里塞几块崩落的碎石头（别让缺口是一刀切的光板）----
    for i in range(n_bay):
        if heights[i] >= full_h - 0.06:
            continue
        bx = xa + (i + 0.5) * bay_w
        for k in range(rng.randint(2, 4)):
            r = rng.uniform(0.09, 0.19)
            sx = min(max(bx + rng.uniform(-0.45, 0.45) * bay_w, xa + r), xb - r)
            sz = heights[i] + rng.uniform(-0.05, 0.17)
            base = lerp3(PAL["stone_d"], PAL["stone_x"], rng.uniform(0.0, 0.30))
            mossy = rng.random() < 0.35

            def col(n, c, base=base, mossy=mossy):
                out = facet_shade(base, n)
                if mossy and n.z > 0.30:
                    out = lerp3(out, PAL["moss_d"], 0.30)
                return out

            hewn_block_lite(b, sx - r, sx + r,
                            y0 + rng.uniform(0.03, 0.13), y1 - rng.uniform(0.03, 0.13),
                            sz - r * 0.7, sz + r * 0.6, S, col, bevel=0.028,
                            yaw=rng.uniform(-25.0, 25.0), tilt=rng.uniform(-18.0, 18.0))

    # ---- 墙脚碎石：墙是塌出来的，脚下就该有掉下来的碎块 ----
    hot = None
    for i in range(n_bay):
        if heights[i] < full_h - 0.12:
            hot = (xa + (i + 0.5) * bay_w, bay_w * 0.9)
            break
    build_base_rubble(b, rng, xa, xb, S, t_m=t_m, plinth_m=plinth_m,
                      plinth_out_m=plinth_out_m, moss=moss, tag=tag,
                      piles=rng.randint(2, 3), scatter=rng.randint(3, 5),
                      fallen=rng.randint(1, 2), hot=hot)

    # ---- 墙脚护石：几块凸出来的底石，把基座那条光带打断 ----
    for k in range(rng.randint(3, 6)):
        r = rng.uniform(0.15, 0.25)
        sx = rng.uniform(hard_lo, max(hard_lo + 0.01, hard_hi - r))
        base, mossy = _stone_base(rng, 0.0, moss, 0.85)
        c = _stone_color(base, mossy, rng.uniform(0.95, 1.02))
        hewn_block_lite(b, sx - r, sx + r,
                        y0 - rng.uniform(0.03, 0.075), y0 + 0.18,
                        0.030, plinth_m + rng.uniform(0.02, 0.13), S, c,
                        bevel=0.030,
                        yaw=rng.uniform(-8.0, 8.0), tilt=rng.uniform(-4.0, 4.0))

    # ---- 垂下来的藤蔓：给墙一点生气 ----
    for k in range(ivy):
        if hard_hi - hard_lo < 0.6:
            break
        x = rng.uniform(hard_lo + 0.25, hard_hi - 0.25)
        ztop = top_at(x) + rng.uniform(0.0, 0.04)
        zbot = max(plinth_m * 0.5, ztop - rng.uniform(0.45, 1.15))
        # 藤蔓贴在墙面上（墙面本身前后起伏 ±0.1 m，贴太前会飘着）
        y = y0 + rng.uniform(0.02, 0.085)
        nseg = rng.randint(5, 8)
        for i in range(nseg):
            t = i / (nseg - 1.0)
            zz = ztop + (zbot - ztop) * t
            xx = x + math.sin(t * 4.2 + k * 1.7) * 0.10
            w = 0.10 * (1.0 - 0.55 * t)
            c = lerp3(PAL["leaf_d"], PAL["leaf_l"], 0.25 + 0.6 * rng.random())
            leaf = [(xx - w, y, zz), (xx + w, y, zz),
                    (xx + w * 0.55, y - 0.035, zz - 0.10),
                    (xx - w * 0.55, y - 0.035, zz - 0.10)]
            add_poly(b, leaf, PL, c, (xx, 0.0, zz))

    return heights


def tile_layout(length, bay_m):
    """压顶瓦片分格：返回 (片数, 单片宽度)。

    片数跟着砖的模数走，再**反算** tile_w = length / n，于是分格一定整除长度 ——
    两端都不会出现半片瓦，接缝处的压顶才能连成一条脊（见文件头「拼接缝契约」）。
    """
    n = int(round(length / max(0.25, bay_m * 1.08)))
    n = max(4, min(14, n))
    return n, length / n

# ==========================================================================
# 预览渲染（供各资产的 *_preview.png 使用）
# ==========================================================================
class PreviewRig:
    """一次性搭好 EEVEE + 灯光 + 地面 + 相机，然后按方位角批量出图。

    各脚本的预览风格保持一致：Standard 视图变换、浅蓝世界光、绿色地面。
    """

    def __init__(self, world_color=(0.60, 0.73, 0.86), ground_z=-0.01, ground_size=40.0):
        scene = bpy.context.scene
        for engine in ('BLENDER_EEVEE_NEXT', 'BLENDER_EEVEE', 'CYCLES'):
            try:
                scene.render.engine = engine
                break
            except TypeError:
                continue
        scene.render.image_settings.file_format = 'PNG'
        scene.render.resolution_percentage = 100
        scene.view_settings.view_transform = 'Standard'
        scene.view_settings.look = 'None'

        world = bpy.data.worlds.new("PreviewWorld")
        scene.world = world
        world.use_nodes = True
        bg = next(n for n in world.node_tree.nodes if n.type == 'BACKGROUND')
        bg.inputs[0].default_value = tuple(world_color) + (1.0,)
        bg.inputs[1].default_value = 0.85

        # 主光强 / 补光弱 → 棱面的明暗差才拉得开。
        # 补光太强的预览里，切角石块的倒角高光会被填平，墙就读成"瓷砖墙"。
        for nm, energy, rot, angle in [("Sun", 4.0, (52, 0, -118), 2.0),
                                       ("Fill", 0.55, (66, 0, 62), 22.0)]:
            ld = bpy.data.lights.new(nm, 'SUN')
            ld.energy = energy
            ld.angle = math.radians(angle)
            ob = bpy.data.objects.new(nm, ld)
            ob.rotation_euler = tuple(math.radians(v) for v in rot)
            scene.collection.objects.link(ob)

        me = bpy.data.meshes.new("GroundMesh")
        s = ground_size
        me.from_pydata([(-s, -s, ground_z), (s, -s, ground_z),
                        (s, s, ground_z), (-s, s, ground_z)], [], [(0, 1, 2, 3)])
        me.update()
        gm = bpy.data.materials.new("GroundPreviewMat")
        gm.use_nodes = True
        bsdf = next(n for n in gm.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
        bsdf.inputs['Base Color'].default_value = (0.15, 0.23, 0.10, 1.0)
        bsdf.inputs['Roughness'].default_value = 0.95
        me.materials.append(gm)
        ground = bpy.data.objects.new("GroundPreview", me)
        scene.collection.objects.link(ground)
        self.ground = ground

        cam_data = bpy.data.cameras.new("PreviewCam")
        cam_data.lens = 50.0
        self.cam = bpy.data.objects.new("PreviewCam", cam_data)
        scene.collection.objects.link(self.cam)
        scene.camera = self.cam

    def shoot(self, path, az_deg, el_deg, dist, target, res=(660, 580)):
        scene = bpy.context.scene
        scene.render.resolution_x, scene.render.resolution_y = res
        az, el = math.radians(az_deg), math.radians(el_deg)
        tgt = Vector(target)
        self.cam.location = tgt + Vector((math.cos(az) * math.cos(el),
                                          math.sin(az) * math.cos(el),
                                          math.sin(el))) * dist
        self.cam.rotation_euler = (tgt - self.cam.location).to_track_quat('-Z', 'Y').to_euler()
        scene.render.filepath = path
        bpy.ops.render.render(write_still=True)

    def contact_sheet(self, out_path, target, shots, res=(660, 580), cols=None):
        """shots = [(name, az, el, dist[, target]), ...] → 拼成一张接触表。

        第 5 项 target 可覆盖该格的取景中心（做局部特写用）。
        """
        tmp = []
        for k, shot in enumerate(shots):
            nm, az, el, dist = shot[0], shot[1], shot[2], shot[3]
            tgt = shot[4] if len(shot) > 4 else target
            p = os.path.join(os.path.dirname(out_path), "_shot_%02d_%s.png" % (k, nm))
            self.shoot(p, az, el, dist, tgt, res=res)
            tmp.append(p)
        cols = cols or len(tmp)
        stitch_images(tmp, out_path, cols)
        for p in tmp:
            try:
                os.remove(p)
            except OSError:
                pass


def stitch_images(paths, out_path, cols):
    """把若干同尺寸 PNG 横向 / 网格拼接（不依赖 PIL）。"""
    imgs = [bpy.data.images.load(p) for p in paths]
    w, h = imgs[0].size
    rows = (len(imgs) + cols - 1) // cols
    out = bpy.data.images.new("Preview", width=w * cols, height=h * rows)
    buf = [0.0] * (w * cols * h * rows * 4)
    for k, im in enumerate(imgs):
        px = list(im.pixels)
        cx, cy = k % cols, k // cols
        for y in range(h):
            src = y * w * 4
            dst = ((rows - 1 - cy) * h + y) * (w * cols) * 4 + cx * w * 4
            buf[dst:dst + w * 4] = px[src:src + w * 4]
    out.pixels = buf
    out.filepath_raw = out_path
    out.file_format = 'PNG'
    out.save()
    for im in imgs:
        bpy.data.images.remove(im)
    bpy.data.images.remove(out)
    print("PREVIEW", out_path)


def setup_preview_helpers():
    return PreviewRig()

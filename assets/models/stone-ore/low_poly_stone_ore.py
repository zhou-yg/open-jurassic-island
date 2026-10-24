# Blender 建模脚本：矿石堆（可开采的矿点，low-poly）
#
# 用法:
#   /Applications/Blender.app/Contents/MacOS/Blender --background --python low_poly_stone_ore.py
#   ... --python low_poly_stone_ore.py -- --nopreview
#   ... --python low_poly_stone_ore.py -- --seed 12      # 换一套随机堆法
#
# 产物（写入本目录）: low_poly_stone_ore.blend / .glb / _preview.png
#
# ---------------------------------------------------------------------------
# 造型（照参考图 stone-mine.jpeg）
# ---------------------------------------------------------------------------
# 参考图不是一整块石头，是几十块**棱角碎石**互相咬合堆出来的锥形矿堆，
# 石缝里嵌着酒红 / 深靛蓝两种矿晶。所以本脚本走"碎块堆体 + 嵌晶簇"的路子，
# 而不是 low_poly_rock 那种单块切割：
#
#   1) 堆体按**同心环**铺块（`RINGS`）：从外圈往里，每圈的块数按周长算，
#      块宽取 1.1~1.3 倍环间距 —— 相邻块必然互相咬合，堆体是"实心"的，
#      不会像纯随机撒点那样到处漏出地面（第一版就是栽在这里）。
#   2) 每块碎块 = icosphere 顶点**径向抖动** + 1~3 刀**大平面切削**。
#      抖动让相邻三角面互不共面（每面即一个棱面，逐面上色=逐棱面上色，
#      不会出现 §6.9 说的面内碎切脏斑）；平面切削造出参考图里那种
#      又长又直、反光成一大片的斜棱面。刀面必须离所有顶点 ≥0.03（模型单位），
#      否则贴着顶点切出来的 1~4 mm 碎边会是一条 0.2° 的发丝三角。
#   3) 高度场：整个堆体罩在一个椭圆穹顶上（`dome_h()`），碎块按穹顶高度往下沉，
#      于是顶部密、边缘摊开、轮廓是锥形而不是一个方块堆。落地不压平也不切，
#      只把整块**平移**到 min z = 0（压平 / 切割都会造出零面积三角）。
#   4) 矿晶：拆成两个物体（Rock / Crystal），Godot 里可以只给 Crystal 挂
#      自发光做"矿脉发亮"。晶体是**有尖端的棱柱**（5~6 棱 + 锥顶，部分断口平顶）
#      + 凸多面体"矿晶结核"两种；**按局部碎块顶面定位**（按穹顶定位会被前面的
#      碎块挡住，只剩一条棱），半埋、只露上半截 —— 参考图露出来的正是
#      一片片晶体棱面，不是完整的六棱柱插在石头顶上。
#   5) 上色：顶点色（线性空间），按**棱面**给色：
#      - 岩石：冷调炭灰蓝，明度主要由"棱面法线 · 固定太阳方向"决定，
#        再叠一层整块碎块的深浅（越埋在堆里越暗 = 廉价 AO）和贴地压暗
#      - 晶体：同一根晶体的棱面按受光方向分段（暗/中/亮/高光），
#        一块晶体上因此有明显明暗差 —— 低多边形宝石就靠这个读出来
#      `LIGHT_DIR` 必须和预览那盏太阳同向（见 `LIGHT_EULER`），
#      否则烘焙的受光面和渲染打光打架，晶体糊成一块糖。
#
# 尺度（§2 基准表）：包络 1.80 × 1.55 × 0.95 m，原点在堆底中心，min z = 0。
# 碎块造型直接按米搭，最后用一次三轴微缩放对齐基准（系数断言在 0.94~1.06），
# 也就是说那一步只是拧螺丝，不是拿缩放救尺寸。
import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "_shared"))
from ruin_kit import (  # noqa: E402
    MeshBuilder, clear_scene, hash01, lerp3, make_material,
    setup_preview_helpers, srgb2lin,
)

# ==========================================================================
# CONFIG —— 米
# ==========================================================================
OUT_DIR = os.path.dirname(os.path.abspath(__file__))
NAME = "low_poly_stone_ore"
SEED = 20260920

LONG_M = 1.80         # 长边（X）
WIDE_M = 1.55         # 短边（Y）
HIGH_M = 0.95         # 堆高（Z，底面 z = 0）

# 穹顶：碎块按这个高度场往下沉，决定了整体轮廓
RX_M, RY_M = 0.735, 0.635
PEAK_M = 0.75
PEAK_X, PEAK_Y = 0.04, 0.02

# 预览太阳（与 ruin_kit.PreviewRig 的 Sun 欧拉角一致）；顶点色的受光方向由它算
LIGHT_EULER = (52.0, 0.0, -118.0)
LIGHT_DIR = Euler(tuple(math.radians(v) for v in LIGHT_EULER), 'XYZ').to_matrix() @ Vector((0, 0, 1))
LIGHT_DIR.normalize()

# 同心环铺块：rn=归一化半径, gap=环间距(米，同时决定每圈块数), size=块尺寸区间,
#             sink=埋进穹顶的比例, cuts=每块切几刀平面
RINGS = [
    dict(rn=1.02, gap=0.32, size=(0.26, 0.46), sink=(0.30, 0.52), cuts=(2, 3)),
    dict(rn=0.80, gap=0.31, size=(0.24, 0.44), sink=(0.26, 0.48), cuts=(2, 3)),
    dict(rn=0.58, gap=0.30, size=(0.24, 0.42), sink=(0.22, 0.44), cuts=(2, 4)),
    dict(rn=0.36, gap=0.29, size=(0.22, 0.40), sink=(0.18, 0.40), cuts=(1, 3)),
    dict(rn=0.14, gap=0.27, size=(0.20, 0.36), sink=(0.14, 0.36), cuts=(1, 2)),
]
# 碎块形状：块 / 板 / 竖棱 / 大块（细分 1）
SHAPES = [
    dict(subdiv=0, squash=(1.00, 0.92, 0.78), jitter=0.22, cuts=2, weight=0.40),
    dict(subdiv=0, squash=(1.24, 0.96, 0.52), jitter=0.22, cuts=3, weight=0.28),
    dict(subdiv=0, squash=(0.84, 0.78, 1.06), jitter=0.26, cuts=3, weight=0.20),
    dict(subdiv=1, squash=(1.00, 0.96, 0.84), jitter=0.16, cuts=3, weight=0.12),
]

# 峰顶的横向石块：参考图的顶是一道脊，不是一个尖
CREST = [
    dict(az=24, size=0.36, surf=0.10, lift=0.03),
    dict(az=96, size=0.30, surf=0.14, lift=0.01),
    dict(az=146, size=0.32, surf=0.12, lift=0.02),
    dict(az=214, size=0.28, surf=0.15, lift=0.00),
    dict(az=268, size=0.30, surf=0.09, lift=0.01),
    dict(az=330, size=0.26, surf=0.16, lift=-0.01),
]

# 外围翘出来的块（打破圆形轮廓）+ 散落碎石
OUTLIERS = 6
OUTLIER_RN = (0.98, 1.04)
OUTLIER_SIZE = (0.16, 0.26)
PEBBLES = 8
PEBBLE_RN = (0.92, 1.05)
PEBBLE_SIZE = (0.05, 0.12)

# 整块"矿石结核"：嵌进堆体、只露一部分的晶体碎块（参考图里那些大片酒红棱面）
BOULDERS = [
    dict(rn=0.44, az=252, size=0.42, family="wine", sink=0.30),
    dict(rn=0.68, az=302, size=0.34, family="wine", sink=0.36),
    dict(rn=0.26, az=96, size=0.40, family="navy", sink=0.26),
    dict(rn=0.34, az=158, size=0.32, family="wine", sink=0.34),
    dict(rn=0.58, az=38, size=0.30, family="navy", sink=0.38),
    dict(rn=0.18, az=212, size=0.28, family="wine", sink=0.38),
    dict(rn=0.52, az=0, size=0.30, family="wine", sink=0.34),
    dict(rn=0.46, az=124, size=0.26, family="navy", sink=0.42),
    dict(rn=0.62, az=80, size=0.24, family="wine", sink=0.40),
    dict(rn=0.80, az=248, size=0.26, family="wine", sink=0.46),
    dict(rn=0.86, az=8, size=0.22, family="wine", sink=0.50),
]

# 晶簇：rn=半径, az=方位角(度), family=酒红/靛蓝, shards=同簇晶体根数,
#       r=截面半径, body=柱身长, tip=锥尖长, expose=埋进堆体的比例(越大露得越少),
#       spread=簇内方位散布(度)
CLUSTERS = [
    dict(rn=0.30, az=96, family="navy", shards=2, r=0.082, body=0.22, tip=0.062, expose=0.48, spread=16),
    dict(rn=0.47, az=252, family="wine", shards=1, r=0.072, body=0.18, tip=0.055, expose=0.52, spread=0),
    dict(rn=0.63, az=348, family="wine", shards=1, r=0.054, body=0.19, tip=0.060, expose=0.50, spread=0),
    dict(rn=0.72, az=150, family="navy", shards=1, r=0.046, body=0.13, tip=0.042, expose=0.58, spread=0),
]
CHIPS = 6             # 随机散布的小晶体碎片
CHIP_R = (0.024, 0.052)

# ==========================================================================
# 调色板（sRGB → 线性）
# ==========================================================================
PAL = {
    "rock_x": srgb2lin([0.030, 0.033, 0.042]),
    "rock_d": srgb2lin([0.082, 0.088, 0.104]),
    "rock_m": srgb2lin([0.168, 0.176, 0.196]),
    "rock_l": srgb2lin([0.330, 0.336, 0.356]),
    "rock_h": srgb2lin([0.500, 0.505, 0.528]),
}
# 每族晶体 4 档：暗 / 中 / 亮 / 高光
CRY = {
    "wine": (srgb2lin([0.100, 0.018, 0.038]),
             srgb2lin([0.222, 0.042, 0.088]),
             srgb2lin([0.344, 0.100, 0.160]),
             srgb2lin([0.478, 0.182, 0.240])),
    "navy": (srgb2lin([0.032, 0.037, 0.086]),
             srgb2lin([0.078, 0.096, 0.196]),
             srgb2lin([0.148, 0.180, 0.314]),
             srgb2lin([0.268, 0.315, 0.478])),
}


def clamp01(c):
    return [min(1.0, max(0.0, float(v))) for v in c]


# ==========================================================================
# 高度场：碎块都往这个穹顶上坐
# ==========================================================================
def dome_h(x, y):
    dx = (x - PEAK_X) / RX_M
    dy = (y - PEAK_Y) / RY_M
    # 足迹不是正圆：西南方向铺得更远，东北方向收一点（参考图左侧那条"尾巴"）
    az = math.atan2(dy, dx)
    r_scale = 1.0 + 0.09 * math.cos(az - 3.9) + 0.04 * math.cos(2.0 * az + 1.0)
    rn = math.hypot(dx, dy) / r_scale
    if rn >= 1.0:
        return 0.0
    h = PEAK_M * (1.0 - rn ** 1.55)
    # 一点不对称：右后侧略高，正前方压平一点（参考图的峰偏后、前面是缓坡）
    h *= 1.0 + 0.06 * math.cos(math.atan2(dy, dx) - 1.1)
    return max(0.0, h)


def surface_point(rn, az_deg):
    """按归一化半径 + 方位角取穹顶上的一点。"""
    a = math.radians(az_deg)
    x = PEAK_X + math.cos(a) * rn * RX_M
    y = PEAK_Y + math.sin(a) * rn * RY_M
    return Vector((x, y, dome_h(x, y)))


# ==========================================================================
# bmesh → MeshBuilder（一个 face = 一个棱面 = 一块颜色）
# ==========================================================================
def add_bm(b, bm, slot, color_fn):
    bm.normal_update()
    for f in bm.faces:
        area = f.calc_area()
        if area < 1e-8:                 # 退化面直接不要（导出后是一片黑斑）
            continue
        col = color_fn(f.normal.copy(), f.calc_center_median(), area)
        b.add([v.co.copy() for v in f.verts], slot, col)


def add_oriented(b, vs, slot, color_fn, ref):
    """加一个面，并按 ref（大致的外法线方向）修正绕序。

    MeshBuilder 直接 from_pydata，法线完全由绕序决定；绕反了在 Godot 里
    （背面剔除）会直接看不见。所以每个手发的面都过这一道。
    """
    n = Vector((0.0, 0.0, 0.0))                     # Newell 法线，多边形非平面也稳
    for i in range(len(vs)):
        a, c = vs[i], vs[(i + 1) % len(vs)]
        n.x += (a.y - c.y) * (a.z + c.z)
        n.y += (a.z - c.z) * (a.x + c.x)
        n.z += (a.x - c.x) * (a.y + c.y)
    if n.length < 1e-12:
        return
    n.normalize()
    if n.dot(ref) < 0.0:
        vs = list(reversed(vs))
        n = -n
    center = sum(vs, Vector()) / len(vs)
    area = 0.0
    for i in range(1, len(vs) - 1):
        area += (vs[i] - vs[0]).cross(vs[i + 1] - vs[0]).length * 0.5
    b.add(vs, slot, color_fn(n, center, area))


def fill_holes(bm):
    holes = [e for e in bm.edges if len(e.link_faces) == 1]
    if holes:
        bmesh.ops.holes_fill(bm, edges=holes, sides=0)
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()


def sink_to_ground(bm):
    """整块上移到 min z = 0（不切、不压）。

    试过两种"把碎块埋进地面"的做法，都会造出零面积三角形（Godot 里是黑斑）：
    把 z 压到 0 会压扁底部一圈三角形（实测 118 个），用 z=0 平面切则会在
    附近有顶点时切出 1~4 mm 的碎边。整体平移一个 dz 不改变任何三角形的形状，
    碎块看上去就是"坐"在地上，代价是轮廓底部略高几厘米，视觉上看不出来。
    """
    zmin = min(v.co.z for v in bm.verts)
    if zmin < 0.0:
        bmesh.ops.translate(bm, verts=bm.verts[:], vec=(0.0, 0.0, -zmin))


def try_cut(bm, rng):
    """在副本上试切一刀大平面棱面，验收通过才写回 bm。

    低多边形石头的"棱角"主要来自这种又长又直的大平面；只靠顶点抖动得到的是
    "多面体球"，不是碎块。验收门槛：切口面要够大（不然是一道划痕似的窄条）、
    总面积要占得住、且不能切出退化三角。
    """
    n = Vector((rng.uniform(-1.0, 1.0), rng.uniform(-1.0, 1.0),
                rng.uniform(-0.35, 1.0)))
    if n.length < 1e-3:
        return False
    n.normalize()
    trial = bm.copy()
    proj = [n.dot(v.co) for v in trial.verts]
    lo, hi = min(proj), max(proj)
    if hi - lo < 0.35:
        trial.free()
        return False
    co = n * (lo + (hi - lo) * rng.uniform(0.55, 0.82))
    # 刀面必须离所有顶点有点距离：贴着顶点切会切出 1~4 mm 的碎边，
    # 那种三角形的最小角接近 0°，在 Godot 里就是一片黑斑（实测 25 个）。
    if min(abs(co.dot(n) - p) for p in proj) < 0.03:
        trial.free()
        return False
    bmesh.ops.bisect_plane(trial, geom=trial.verts[:] + trial.edges[:] + trial.faces[:],
                           plane_co=co, plane_no=n, clear_outer=True)
    fill_holes(trial)
    bmesh.ops.dissolve_degenerate(trial, dist=1e-4, edges=trial.edges[:])
    trial.verts.ensure_lookup_table()
    trial.faces.ensure_lookup_table()
    trial.normal_update()
    total = sum(f.calc_area() for f in trial.faces)
    cap = [f for f in trial.faces if f.normal.dot(n) > 0.985]
    ok = (bool(cap) and sum(f.calc_area() for f in cap) >= total * 0.07
          and min(f.calc_area() for f in trial.faces) > 2e-5
          and min(e.calc_length() for e in trial.edges) > 0.02)
    trial.free()
    if not ok:
        return False

    bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:],
                           plane_co=co, plane_no=n, clear_outer=True)
    fill_holes(bm)
    bmesh.ops.dissolve_degenerate(bm, dist=1e-4, edges=bm.edges[:])
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    return True


def rock_chunk_bm(rng, shape):
    """一块多面体碎石：icosphere 顶点径向抖动 + 若干刀平面切削。"""
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=shape["subdiv"], radius=1.0)
    bm.verts.ensure_lookup_table()
    sq = shape["squash"]
    for v in bm.verts:
        d = 1.0 + rng.uniform(-shape["jitter"], shape["jitter"])
        v.co = Vector((v.co.x * d * sq[0], v.co.y * d * sq[1], v.co.z * d * sq[2]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    for _ in range(shape["cuts"]):
        try_cut(bm, rng)
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return bm


def pick_shape(rng):
    r = rng.random() * sum(s["weight"] for s in SHAPES)
    for s in SHAPES:
        r -= s["weight"]
        if r <= 0.0:
            return s
    return SHAPES[0]


def add_chunk(b, rng, center, size, slot, color_fn, cuts=None, tilt=0.45, shape=None):
    shp = dict(shape or pick_shape(rng))
    if cuts is not None:
        shp["cuts"] = rng.randint(*cuts)
    bm = rock_chunk_bm(rng, shp)
    rot = Euler((rng.uniform(-tilt, tilt), rng.uniform(-tilt, tilt),
                 rng.uniform(0.0, math.tau)), 'XYZ')
    s = size * 0.5
    M = Matrix.Translation(Vector(center)) @ rot.to_matrix().to_4x4() @ Matrix.Diagonal((s, s, s, 1.0))
    bmesh.ops.transform(bm, matrix=M, verts=bm.verts[:])
    sink_to_ground(bm)
    add_bm(b, bm, slot, color_fn)
    bm.free()


def crystal_bm(rng, r_m, body_m, tip_m, broken=False):
    """一根带尖端的晶体棱柱（石英式）：柱身 + 锥面，部分做断口平顶。

    柱身的上下两个角共用同一个方位角，所以每个侧面都是**平面四边形** ——
    低多边形晶体要的是"干净的大棱面"，不是抖动的碎面。
    """
    bm = bmesh.new()
    sides = rng.choice((5, 6))
    a0 = rng.uniform(0.0, math.tau)
    taper = rng.uniform(0.62, 0.84)
    ring0, ring1 = [], []
    for i in range(sides):
        a = a0 + math.tau * i / sides + rng.uniform(-0.05, 0.05)
        r0 = r_m * (1.0 + rng.uniform(-0.14, 0.14))
        r1 = r0 * taper
        ring0.append(bm.verts.new((math.cos(a) * r0, math.sin(a) * r0, 0.0)))
        ring1.append(bm.verts.new((math.cos(a) * r1, math.sin(a) * r1, body_m)))

    for i in range(sides):
        j = (i + 1) % sides
        bm.faces.new((ring0[i], ring0[j], ring1[j], ring1[i]))
    bm.faces.new(list(reversed(ring0)))          # 底面（埋在石头里，闭合用）

    if broken:
        # 断口：顶部再收一个小环，平顶 —— 断掉的晶体在参考图里也有
        ring2 = []
        h2 = body_m + tip_m * rng.uniform(0.45, 0.65)
        for i in range(sides):
            v = ring1[i]
            rr = math.hypot(v.co.x, v.co.y) * rng.uniform(0.40, 0.55)
            a = math.atan2(v.co.y, v.co.x)
            ring2.append(bm.verts.new((math.cos(a) * rr, math.sin(a) * rr, h2)))
        for i in range(sides):
            j = (i + 1) % sides
            bm.faces.new((ring1[i], ring1[j], ring2[j], ring2[i]))
        bm.faces.new(ring2)
    else:
        apex = bm.verts.new((rng.uniform(-0.18, 0.18) * r_m,
                             rng.uniform(-0.18, 0.18) * r_m,
                             body_m + tip_m))
        for i in range(sides):
            j = (i + 1) % sides
            bm.faces.new((ring1[i], ring1[j], apex))

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return bm


def place_crystal(b, rng, base, direction, r_m, body_m, tip_m, slot, color_fn, broken=False):
    bm = crystal_bm(rng, r_m, body_m, tip_m, broken=broken)
    q = Vector((0.0, 0.0, 1.0)).rotation_difference(direction.normalized())
    M = Matrix.Translation(Vector(base)) @ q.to_matrix().to_4x4()
    bmesh.ops.transform(bm, matrix=M, verts=bm.verts[:])
    sink_to_ground(bm)
    add_bm(b, bm, slot, color_fn)
    bm.free()


# ==========================================================================
# 上色
# ==========================================================================
def rock_color_fn(ao, warm=0.0):
    """岩石棱面颜色。

    ao   = 这块碎块在堆体里的深浅（越埋在缝里越暗）
    warm = 这块碎块的色温（-1 冷蓝灰 ~ +1 暖炭灰）；参考图里没有两块石头
           是同一个灰，逐块偏一点色温才不像塑料。
    """
    def fn(n, c, area):
        hsh = hash01(c.x * 3.7, c.y * 2.9, c.z * 2.3)
        # lit 用"最亮能拿到的值"归一：太阳斜射时朝上的面最多只拿到 LIGHT_DIR.z，
        # 不归一的话最亮那一档（rock_h）永远用不上
        lit = clamp01([max(0.0, n.dot(LIGHT_DIR)) / max(1e-6, LIGHT_DIR.z)])[0]
        # 明度主要吃受光：背光/朝下的棱面压到 rock_x，朝太阳的到 rock_h
        col = lerp3(PAL["rock_x"], PAL["rock_l"], 0.12 + 0.58 * lit)
        col = lerp3(col, PAL["rock_h"], 0.60 * max(0.0, lit - 0.55) / 0.45)
        col = col * (0.80 + 0.40 * hsh)               # 棱面之间的明暗差
        col = col * ao                                # 整块的深浅
        if n.z < -0.10:                               # 朝下的棱面吃不到天光
            col = lerp3(col, PAL["rock_x"], min(0.8, -n.z))
        if area > 0.04:                               # 大面 = 新断面，略亮
            col = lerp3(col, PAL["rock_l"], 0.12)
        if c.z < 0.14:                                # 接触阴影：贴地一圈压暗
            col = lerp3(col, PAL["rock_x"], 0.55 * (1.0 - c.z / 0.14))
        if warm > 0.0:                                # 色温：暖炭灰 / 冷蓝灰
            col = lerp3(col, col * [1.10, 1.05, 0.93], warm * 0.65)
        else:
            col = lerp3(col, col * [0.92, 0.98, 1.12], -warm * 0.65)
        if hsh < 0.05:                                # 一点点矿石沁色
            col = lerp3(col, CRY["wine"][0], 0.35)
        elif hsh < 0.085:
            col = lerp3(col, CRY["navy"][1], 0.30)
        return clamp01(col)

    return fn


def core_color(n, c, area):
    """内核棱面：整块压到最暗，好让碎块之间的缝读成"深石缝"而不是地面。"""
    hsh = hash01(c.x * 9.1, c.y * 7.3, c.z * 5.7)
    lit = max(0.0, n.dot(LIGHT_DIR))
    col = lerp3(PAL["rock_x"], PAL["rock_d"], 0.20 + 0.70 * lit)
    col = col * (0.72 + 0.34 * hsh)
    return clamp01(col)


def add_core(b, rng, slot):
    """堆体内核：抖动的锥顶穹顶 + 一圈落地的裙边。

    没有这一层，碎块之间就是空的（第一版看着像"散在地上的石头"）；有了它，
    缝里是暗的，反而变成参考图里那种深色石缝，堆体也就读成实心的。
    """
    sect = 18
    rings = (0.30, 0.54, 0.74, 0.90, 1.00)
    grid = []                                       # [环][扇区] -> Vector
    apex = Vector((PEAK_X, PEAK_Y, dome_h(PEAK_X, PEAK_Y) * rng.uniform(0.86, 0.94)))
    for k, rn in enumerate(rings):
        off = (0.5 if k % 2 else 0.0) * math.tau / sect   # 隔环错开半格，避免径向长条
        row = []
        for i in range(sect):
            a = off + math.tau * i / sect + rng.uniform(-0.25, 0.25) * math.tau / sect
            rr = rn * (1.0 + rng.uniform(-0.03, 0.03))
            x = PEAK_X + math.cos(a) * rr * RX_M
            y = PEAK_Y + math.sin(a) * rr * RY_M
            if rn >= 1.0:
                z = 0.0                                 # 最外圈落到地面
            else:
                z = dome_h(x, y) * rng.uniform(0.86, 0.98)
            row.append(Vector((x, y, z)))
        grid.append(row)

    def ref_for(p):
        d = Vector((p.x - PEAK_X, p.y - PEAK_Y, 0.0))
        if d.length < 1e-6:
            d = Vector((1.0, 0.0, 0.0))
        return (d.normalized() + Vector((0.0, 0.0, 0.55))).normalized()

    # 顶锥
    for i in range(sect):
        vs = [apex, grid[0][i], grid[0][(i + 1) % sect]]
        add_oriented(b, vs, slot, core_color, ref_for(grid[0][i]))
    # 环带（每格再切一刀，低多边形要的是碎面不是平滑环）
    for k in range(len(rings) - 1):
        lo, hi = grid[k], grid[k + 1]
        for i in range(sect):
            j = (i + 1) % sect
            quad = [lo[i], lo[j], hi[j], hi[i]]
            ref = ref_for((lo[i] + hi[j]) * 0.5)
            # 对角线按**几何**挑短的那条（隔格交替挑会不时挑出三点几乎共线的组合，
            # 切出来是一条发丝宽的长三角，就是"脏边"）
            if (quad[0] - quad[2]).length <= (quad[1] - quad[3]).length:
                add_oriented(b, [quad[0], quad[1], quad[2]], slot, core_color, ref)
                add_oriented(b, [quad[0], quad[2], quad[3]], slot, core_color, ref)
            else:
                add_oriented(b, [quad[0], quad[1], quad[3]], slot, core_color, ref)
                add_oriented(b, [quad[1], quad[2], quad[3]], slot, core_color, ref)
    # 底盖（贴地，看不见，闭合用）
    add_oriented(b, list(reversed(grid[-1])), slot, core_color, Vector((0.0, 0.0, -1.0)))


def crystal_color(family):
    d, m, l, h = CRY[family]

    def fn(n, c, area):
        hsh = hash01(c.x * 5.1, c.z * 4.3, n.y * 7.7)
        lit = n.dot(LIGHT_DIR) / max(1e-6, LIGHT_DIR.z)   # 归一：1 = 正对太阳
        if lit > 0.72:                                # 正对太阳：整块高光棱面
            col = lerp3(l, h, min(1.0, (lit - 0.72) / 0.28))
        elif lit > 0.10:
            col = lerp3(m, l, (lit - 0.10) / 0.62)
        else:                                         # 背光棱面压到最暗一档
            col = lerp3(d, m, max(0.0, lit + 0.5) / 0.60 * 0.90)
        # 逐棱面的**离散**明度：低多边形宝石靠"一面一个调子"才读得出来，
        # 只吃受光方向的话，同一侧的几个面会糊成一片
        mul = (0.80, 0.96, 1.10, 1.24)[min(3, int(hsh * 4.0))]
        return clamp01([col[i] * mul for i in range(3)])

    return fn


def local_top(verts, x, y, r=0.22, q=0.80):
    """(x, y) 附近碎石顶面的高度（取 80 分位，不是最高点）。

    矿晶如果按穹顶定位，就会被前面的碎块挡住（只剩一条棱）；按碎块的实际顶面
    定位，晶体才是"从石缝里长出来、露一大片"的样子。取分位而不是最大值，
    是为了不把晶体架在某根尖棱的尖上。
    """
    zs = [v[2] for v in verts if (v[0] - x) ** 2 + (v[1] - y) ** 2 < r * r]
    if not zs:
        return dome_h(x, y)
    zs.sort()
    return zs[min(len(zs) - 1, int(q * len(zs)))]


# ==========================================================================
# 组装
# ==========================================================================
def build(rng):
    rock = MeshBuilder()
    cry = MeshBuilder()
    R = rock.slot("Rock")
    C = cry.slot("Crystal")

    # ---- 内核：先把堆体填实，碎块之间才不会漏出地面 ----
    add_core(rock, rng, R)

    # ---- 堆体：同心环铺块，由外往里 ----
    for ring in RINGS:
        rn = ring["rn"]
        r_avg = (RX_M + RY_M) * 0.5
        count = max(1, int(round(math.tau * max(rn * r_avg, 0.10) / ring["gap"])))
        az0 = rng.uniform(0.0, 360.0)
        for i in range(count):
            az = az0 + 360.0 * i / count + rng.uniform(-0.30, 0.30) * 360.0 / count
            rr = max(0.0, rn + rng.uniform(-0.035, 0.035))
            p = surface_point(rr, az)
            size = rng.uniform(*ring["size"])
            sz = size * rng.uniform(0.58, 0.82)
            sink = rng.uniform(*ring["sink"])
            center = Vector((p.x, p.y, p.z - sink * sz + sz * 0.5))
            # 整块深浅：埋得越深越暗（廉价 AO），最上层提亮
            ao = 0.74 + 0.26 * (1.0 - sink) + 0.10 * rng.random()
            add_chunk(rock, rng, center, size, R,
                      rock_color_fn(min(ao, 1.06), rng.uniform(-1.0, 1.0)),
                      cuts=ring["cuts"], tilt=0.5)

    # ---- 峰顶脊：横躺的扁石 ----
    for spec in CREST:
        p = surface_point(spec["surf"], spec["az"])
        center = Vector((p.x, p.y, p.z + spec["lift"]))
        add_chunk(rock, rng, center, spec["size"], R,
                  rock_color_fn(1.02, rng.uniform(-0.6, 0.6)), cuts=(1, 2), tilt=0.26,
                  shape=dict(subdiv=0, squash=(1.36, 1.06, 0.52), jitter=0.18, cuts=1))

    # ---- 外围翘出来的块：打破圆形轮廓 ----
    for _ in range(OUTLIERS):
        rn = rng.uniform(*OUTLIER_RN)
        az = rng.uniform(0.0, 360.0)
        p = surface_point(rn, az)
        size = rng.uniform(*OUTLIER_SIZE)
        center = Vector((p.x, p.y, size * rng.uniform(0.05, 0.30)))
        add_chunk(rock, rng, center, size, R,
                  rock_color_fn(0.72, rng.uniform(-1.0, 1.0)), cuts=(1, 2), tilt=0.55)

    # 矿晶要贴着碎块的实际表面放（见 local_top）
    rock_verts = list(rock.verts)

    # ---- 矿晶结核：整块晶体色的多面体，半埋进碎块之间 ----
    for spec in BOULDERS:
        p = surface_point(spec["rn"], spec["az"])
        size = spec["size"]
        top = local_top(rock_verts, p.x, p.y, r=size * 0.55)
        center = Vector((p.x, p.y, top - size * spec["sink"]))
        bm = rock_chunk_bm(rng, dict(subdiv=0, squash=(1.0, 0.92, 0.80), jitter=0.16, cuts=1))
        rot = Euler((rng.uniform(-0.35, 0.35), rng.uniform(-0.35, 0.35),
                     rng.uniform(0.0, math.tau)), 'XYZ')
        M = (Matrix.Translation(center) @ rot.to_matrix().to_4x4()
             @ Matrix.Diagonal((size * 0.5, size * 0.5, size * 0.5, 1.0)))
        bmesh.ops.transform(bm, matrix=M, verts=bm.verts[:])
        sink_to_ground(bm)
        add_bm(cry, bm, C, crystal_color(spec["family"]))
        bm.free()

    # ---- 晶簇：长在堆体表面的斜插晶体 ----
    for spec in CLUSTERS:
        p = surface_point(spec["rn"], spec["az"])
        col = crystal_color(spec["family"])
        for _ in range(spec["shards"]):
            a = math.radians(spec["az"] + rng.uniform(-spec["spread"], spec["spread"]))
            o = Vector((math.cos(a), math.sin(a), 0.0))
            direction = (o * rng.uniform(0.30, 0.85)
                         + Vector((0.0, 0.0, rng.uniform(0.75, 1.35)))).normalized()
            scale = rng.uniform(0.72, 1.12) if spec["shards"] > 1 else 1.0
            body = spec["body"] * scale
            tip = spec["tip"] * scale
            # 晶体底埋进碎块 expose 比例的身长，只露上半截
            top = local_top(rock_verts, p.x, p.y, r=0.16)
            base = (Vector((p.x, p.y, top - 0.02)) - direction * (body * spec["expose"])
                    + o * rng.uniform(-0.04, 0.04))
            place_crystal(cry, rng, base, direction, spec["r"] * scale, body, tip,
                          C, col, broken=rng.random() < 0.2)

    # ---- 小晶体碎片：缝里 / 脚下零星露头 ----
    for _ in range(CHIPS):
        rn = rng.uniform(0.25, 0.95)
        az = rng.uniform(0.0, 360.0)
        p = surface_point(rn, az)
        family = "wine" if rng.random() < 0.7 else "navy"
        r = rng.uniform(*CHIP_R)
        a = math.radians(az + rng.uniform(-25, 25))
        o = Vector((math.cos(a), math.sin(a), 0.0))
        direction = (o * rng.uniform(0.2, 0.9)
                     + Vector((0.0, 0.0, rng.uniform(0.6, 1.4)))).normalized()
        body = r * rng.uniform(1.5, 2.8)
        top = local_top(rock_verts, p.x, p.y, r=0.13)
        base = (Vector((p.x, p.y, top - 0.015))
                - direction * (body * rng.uniform(0.30, 0.55)))
        place_crystal(cry, rng, base, direction, r, body, body * 0.45,
                      C, crystal_color(family), broken=rng.random() < 0.3)

    # ---- 散落碎石 ----
    for _ in range(PEBBLES):
        rn = rng.uniform(*PEBBLE_RN)
        az = rng.uniform(0.0, 360.0)
        p = surface_point(rn, az)
        size = rng.uniform(*PEBBLE_SIZE)
        center = Vector((p.x, p.y, size * rng.uniform(0.08, 0.26)))
        add_chunk(rock, rng, center, size, R,
                  rock_color_fn(0.70, rng.uniform(-1.0, 1.0)), cuts=(0, 1), tilt=0.5)

    # ---- 收尾：理论上每块都已坐在 z=0 上，这里只兜底 ----
    for b in (rock, cry):
        b.verts = [(v[0], v[1], max(0.0, v[2])) for v in b.verts]
    return rock, cry


def trim_to_spec(rock, cry):
    """把造型按基准表对齐：取两个网格合并后的包围盒，做一次三轴微缩放。

    造型本来就是按米搭的，这一步只是拧螺丝 —— 断言系数在 0.94~1.06 之间，
    超出说明穹顶/块尺寸设错了，应该回去改参数而不是放大缩放。
    """
    verts = rock.verts + cry.verts
    xs = [v[0] for v in verts]
    ys = [v[1] for v in verts]
    zs = [v[2] for v in verts]
    cx = (min(xs) + max(xs)) * 0.5
    cy = (min(ys) + max(ys)) * 0.5
    sx = LONG_M / (max(xs) - min(xs))
    sy = WIDE_M / (max(ys) - min(ys))
    sz = HIGH_M / (max(zs) - min(zs))
    print("RAW   X %.3f  Y %.3f  Z %.3f m" % (
        max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)))
    for s in (sx, sy, sz):
        assert 0.94 <= s <= 1.06, "造型偏离基准尺寸太多（系数 %.3f），回去调穹顶/块尺寸" % s
    for b in (rock, cry):
        b.verts = [((v[0] - cx) * sx, (v[1] - cy) * sy, v[2] * sz) for v in b.verts]
    return sx, sy, sz


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    do_preview = "--nopreview" not in argv
    seed = SEED
    if "--seed" in argv:
        seed = int(argv[argv.index("--seed") + 1])

    clear_scene()
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1.0
    random.seed(seed)
    rng = random.Random(seed)

    rock, cry = build(rng)
    sx, sy, sz = trim_to_spec(rock, cry)

    mats = {
        "Rock": make_material("StoneOreRock", 0.94),
        "Crystal": make_material("StoneOreCrystal", 0.46),
    }
    # 镜面强度压到 0.22：默认 0.5 会在粗糙度 0.46 的棱面上打出一片白高光，
    # 把酒红洗成粉灰（实测渲染平均色被抬到 #D8A0B4）。参考图的晶体是"润"不是"亮"。
    cry_bsdf = next(n for n in mats["Crystal"].node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    for key in ("Specular IOR Level", "Specular"):
        if key in cry_bsdf.inputs:
            cry_bsdf.inputs[key].default_value = 0.06
            break
    rock_ob = rock.build("Rock", mats)
    cry_ob = cry.build("Crystal", mats)

    # 物体变换保持单位阵：尺寸全在网格里（§1）
    for ob in (rock_ob, cry_ob):
        ob.select_set(True)
        assert all(abs(s - 1.0) < 1e-6 for s in ob.scale)

    glb = os.path.join(OUT_DIR, NAME + ".glb")
    blend = os.path.join(OUT_DIR, NAME + ".blend")
    bpy.ops.export_scene.gltf(
        filepath=glb, export_format='GLB', use_selection=False,
        export_apply=False, export_yup=True,
        export_normals=True, export_vertex_color='MATERIAL',
        export_animations=False,
    )

    if do_preview:
        rig = setup_preview_helpers()
        rig.contact_sheet(
            os.path.join(OUT_DIR, NAME + "_preview.png"),
            target=(0.0, 0.0, 0.40),
            shots=[("three_quarter", 232.0, 16.0, 2.50),
                   ("front", 300.0, 10.0, 2.50),
                   ("side", 88.0, 14.0, 2.50),
                   ("top", 232.0, 56.0, 2.25)],
        )

    bpy.ops.wm.save_as_mainfile(filepath=blend)

    # ---- 自检 ----
    xs = [v.co.x for ob in (rock_ob, cry_ob) for v in ob.data.vertices]
    ys = [v.co.y for ob in (rock_ob, cry_ob) for v in ob.data.vertices]
    zs = [v.co.z for ob in (rock_ob, cry_ob) for v in ob.data.vertices]
    faces = sum(len(ob.data.polygons) for ob in (rock_ob, cry_ob))
    print("=" * 62)
    print("%s  verts=%d  faces=%d" % (NAME, len(xs), faces))
    print("BBOX  X %.3f  Y %.3f  Z %.3f..%.3f m  (min z 应≈0)" % (
        max(xs) - min(xs), max(ys) - min(ys), min(zs), max(zs)))
    print("TRIM  sx %.3f  sy %.3f  sz %.3f" % (sx, sy, sz))
    print("LIGHT_DIR  (%.3f, %.3f, %.3f)" % tuple(LIGHT_DIR))
    assert abs(min(zs)) < 1e-6, "底面必须正好在 z=0"
    assert abs((max(xs) - min(xs)) - LONG_M) < 0.005, "长边漂了"
    assert abs((max(ys) - min(ys)) - WIDE_M) < 0.005, "短边漂了"
    assert abs((max(zs) - min(zs)) - HIGH_M) < 0.005, "高度漂了"
    assert abs((min(xs) + max(xs)) * 0.5) < 0.005, "原点应在堆底中心"

    # 三角面兜底：碎块都是多面体，只要没有退化三角形就不会有"脏边"
    min_ang, min_area, tiny = 180.0, 1e9, 0
    for ob in (rock_ob, cry_ob):
        me = ob.data
        for poly in me.polygons:
            a, b, c = [me.vertices[i].co for i in poly.vertices[:3]]
            for u, w in ((b - a, c - a), (c - b, a - b), (a - c, b - c)):
                if u.length > 1e-9 and w.length > 1e-9:
                    min_ang = min(min_ang, math.degrees(u.angle(w)))
            min_area = min(min_area, poly.area)
            if poly.area < 0.0004:
                tiny += 1
    print("TRI    min angle %.1f deg  min area %.5f m2  tiny %d" % (min_ang, min_area, tiny))
    # 门槛比 low_poly_rock 的 4° 松：那个资产是"一整块石头"，一条瘦棱面就毁容；
    # 这里是几十块 0.2~0.4 m 的小碎块堆成的，1.7° / 0.3 cm² 的发丝面
    # 在 1.8 m 的资产上就是 0.1 mm 宽的一道，不可见。真正要挡的是"塌成一条线"。
    assert min_ang >= 1.0, "有退化成一条线的三角形"
    assert min_area > 1e-6, "有零面积三角面"
    print("saved:", glb)
    print("saved:", blend)
    print("SELF-CHECK OK")


if __name__ == "__main__":
    main()

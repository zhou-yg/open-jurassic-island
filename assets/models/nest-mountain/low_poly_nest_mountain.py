"""Low-poly 鸟巢山 (nest mountain) generator.

用法:
    blender --background --python low_poly_nest_mountain.py
    blender --background --python low_poly_nest_mountain.py -- --nopreview
    blender --background --python low_poly_nest_mountain.py -- --nonest

产物（写入本目录）:
    low_poly_nest_mountain.blend
    low_poly_nest_mountain.glb          <- 只有山体（山顶留了鸟巢坑）
    low_poly_nest_mountain_preview.png  <- 2x2 拼图：3/4 视角（有/无占位鸟巢）/ 俯视 / 洞口特写
    low_poly_nest_mountain_cave.png     <- 山脚 + 山腰两个洞口
    low_poly_nest_mountain_top.png      <- 山顶鸟巢预留区俯视

造型（对照 assets/AGENTS.md §1 的米制约定）
--------------------------------------------
* 山脚占地 ≈ 100 m，主峰(山顶边缘岩唇) ≈ 51.5 m，海/地面 z = 0，原点在山体中心。
* 由下到上分四层，每层之间是陡岩壁（低多边形的平顶台地感）：
    1. 山脚 0–8 m    沙滩 + 草坡，岩壁上有 **山脚山洞**（洞口中心 ≈ z 6.8）
    2. 山腰 8–24 m   梯田式草台，台缘为裸岩；**山腰山洞**开在这里（洞口中心 ≈ z 16.5）
    3. 上层 24–46 m  裸岩陡壁 + 几条草脊
    4. 山顶 46–51.5 m 一整块平顶，中间是 **鸟巢预留坑**（口 Ø 11.5 m，深 7.5 m）
* 颜色全部烘进顶点色 "Col"（线性空间），一个材质一次 draw call。
  分色按 高度带 + 坡向 + 每面随机微差 三层叠出来，所以有参考图那种块面层次。

山洞（山脚 / 山腰各一个）
--------------------------
* 洞口位置不是写死的：在给定方位 / 高度 / 半径窗口里逐点打水平射线，
  按命中面法线挑一段"立得住的墙面"，所以不会有洞口朝天或者开在台地地面上。
* 洞体用一根**正圆柱**直接布尔切出来，切口是平整的一圈圆（口沿不加任何石块），
  切进去是直筒，洞底再扩一间石室。想要石头就单独摆 `low_poly_rock.glb`。
* 切之前在切口周围局部加密，避免粗三角形把圆沿切成锯齿。

山顶的鸟巢只做了 **预览占位**（对象名 `NestPlaceholder`）：
    - 它会存进 .blend 方便看比例，但 **不导出到 .glb**（GLB 只有山）。
    - 游戏里真正的鸟巢建议单独做成资产，摆在预留坑里。
    - 加 --nonest 可以不生成它。
"""

import math
import os
import random
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
NAME = "low_poly_nest_mountain"

# ==================== 尺寸（米，1 Blender unit = 1 m）====================
SIZE_M = 100.0            # 山脚占地跨度（含浅浅的水下裙边）
N = 151                   # 高度场分辨率（先密后减面，低多边形的块面靠 decimate 出来）
PEAK_H_M = 51.5           # 主峰高度 = 山顶岩唇顶面
NEST_R_M = 5.75           # 山顶鸟巢坑口半径（Ø 11.5 m）
NEST_FLOOR_M = 44.0       # 鸟巢坑底高度
PLATEAU_R_M = 11.5        # 山顶平台半径（平台外缘开始下落）
CAVE_R_M = 2.3            # 洞口半径
CAVE_DEPTH_M = 6.5        # 洞深
SEA_BOT_M = -9.0          # 水下裙边底部
TARGET_TRIS = 4000        # 山体目标三角面数（低多边形，但台阶要够多面才立得起来）
SEED = 20240731

# 高度剖面：rn = 归一化半径（0 = 山轴，1 = 岸线），值是高度（米）
# 折点故意留成硬拐角 —— 这些拐角就是"多层次"的台地/崖壁分界。
# 层次自上而下：山顶平台 → 上层岩壁 → 山腰大台地 → 山腰陡坡 → 山脚缓台地 → 沙滩
PROF_RN = np.array([0.000, 0.070, 0.115, 0.150, 0.235, 0.300, 0.330, 0.360,
                    0.470, 0.560, 0.590, 0.700, 0.790, 0.880, 0.945, 1.000, 1.060])
PROF_H = np.array([NEST_FLOOR_M, NEST_FLOOR_M + 2.2, PEAK_H_M - 1.2, PEAK_H_M,
                   PEAK_H_M - 1.6, PEAK_H_M - 4.0, PEAK_H_M - 8.5, PEAK_H_M - 9.5,
                   PEAK_H_M - 20.0, PEAK_H_M - 27.5, PEAK_H_M - 28.5, PEAK_H_M - 36.0,
                   PEAK_H_M - 42.5, PEAK_H_M - 46.5, PEAK_H_M - 50.0, -5.0, SEA_BOT_M])

# 冲沟（山体上的 V 形雨沟）：方位角°, 宽度 rad, 深度 m。避开两个洞口方位。
GULLIES = [(28.0, 0.30, 7.0), (196.0, 0.26, 6.0), (250.0, 0.22, 5.0),
           (86.0, 0.20, 4.5), (310.0, 0.19, 5.5)]


def angdiff(a, b):
    d = a - b
    return (d + math.pi) % (2 * math.pi) - math.pi

# 山洞：(方位角°, 目标高度 m, 洞半径 m, 洞深 m, 仰角°, 允许半径下限, 上限)
# 半径窗口把洞口钉在"该在的那层"：山脚洞在山脚外圈的岩壁上，
# 山腰洞必须在主锥体的山腰上，不许被外围小山包的陡面抢走。
CAVES = [
    (118.0, 7.0, 3.0, 7.5, 10.0, 24.0, 40.0),    # 山脚山洞
    (338.0, 16.5, 2.4, 6.0, 14.0, 16.0, 27.0),   # 山腰山洞
]


# ==================== 颜色工具 ====================
def srgb2lin(c):
    c = np.asarray(c, dtype=float)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


PAL = {
    "sea_deep": srgb2lin([0.14, 0.26, 0.33]),
    "sea_shal": srgb2lin([0.29, 0.45, 0.48]),
    "sand_l": srgb2lin([0.94, 0.88, 0.67]),
    "sand_d": srgb2lin([0.78, 0.70, 0.48]),
    "rock_l": srgb2lin([0.74, 0.68, 0.60]),
    "rock_m": srgb2lin([0.56, 0.48, 0.40]),
    "rock_d": srgb2lin([0.36, 0.30, 0.25]),
    "grass_l": srgb2lin([0.63, 0.80, 0.35]),
    "grass_m": srgb2lin([0.41, 0.66, 0.23]),
    "grass_d": srgb2lin([0.23, 0.45, 0.14]),
    "grass_x": srgb2lin([0.15, 0.33, 0.12]),
    "dirt": srgb2lin([0.42, 0.33, 0.22]),
    "cave_in": srgb2lin([0.06, 0.055, 0.05]),
    "twig_l": srgb2lin([0.72, 0.58, 0.36]),
    "twig_m": srgb2lin([0.55, 0.42, 0.25]),
    "twig_d": srgb2lin([0.36, 0.27, 0.16]),
}


# ==================== 噪声 ====================
def _hash2(ix, iy, seed):
    h = np.sin(ix * 127.1 + iy * 311.7 + seed * 74.7) * 43758.5453
    return h - np.floor(h)


def noise2(X, Y, freq, seed):
    x, y = X * freq, Y * freq
    ix, iy = np.floor(x), np.floor(y)
    fx, fy = x - ix, y - iy
    ux = fx * fx * (3 - 2 * fx)
    uy = fy * fy * (3 - 2 * fy)
    a, b = _hash2(ix, iy, seed), _hash2(ix + 1, iy, seed)
    c, d = _hash2(ix, iy + 1, seed), _hash2(ix + 1, iy + 1, seed)
    return (a * (1 - ux) + b * ux) * (1 - uy) + (c * (1 - ux) + d * ux) * uy


def fbm(X, Y, freq, seed, octaves=4, lac=2.07, gain=0.5):
    tot = np.zeros_like(X)
    amp, f, nrm = 1.0, freq, 0.0
    for i in range(octaves):
        tot += amp * noise2(X, Y, f, seed + i * 13.7)
        nrm += amp
        amp *= gain
        f *= lac
    return tot / nrm


# ==================== 高度场 ====================
BASE_R = SIZE_M * 0.5 * 0.96      # rn = 1 时的世界半径


def build_heightfield():
    xs = np.linspace(-SIZE_M / 2, SIZE_M / 2, N)
    X, Y = np.meshgrid(xs, xs)

    U, V = X / BASE_R, Y / (BASE_R * 0.92)
    TH = np.arctan2(V, U)
    r = np.sqrt(U * U + V * V)

    # 不平整的轮廓：山脚海岬般的起伏
    rsh = (1.0 + 0.085 * np.sin(3 * TH + 0.7) + 0.05 * np.sin(5 * TH + 2.1)
           + 0.03 * np.sin(8 * TH + 0.4) + 0.07 * (fbm(X, Y, 0.030, 3.0, 3) - 0.5) * 2.0)
    rn = r / np.maximum(rsh, 1e-6)

    H = np.interp(rn, PROF_RN, PROF_H)

    def bump(cx, cy, amp, sx, sy, rot=0.0):
        dx, dy = X - cx, Y - cy
        if rot:
            ca, sa = math.cos(rot), math.sin(rot)
            dx, dy = ca * dx - sa * dy, sa * dx + ca * dy
        return amp * np.exp(-(dx * dx / (2 * sx * sx) + dy * dy / (2 * sy * sy)))

    # 山脚一圈次峰 / 岩肩：把圆锥打散成"多峰山体"，低多边形剪影更好看
    for ang, dist, amp, s in [(18, 34, 9.0, 9.0), (74, 33, 7.5, 8.0),
                              (152, 35, 8.5, 9.5), (208, 33, 6.5, 8.0),
                              (262, 34, 8.0, 9.0), (312, 34, 7.0, 8.5)]:
        a = math.radians(ang)
        H += bump(math.cos(a) * dist, math.sin(a) * dist, amp, s, s * 0.85, a)
    # 山腰两条扶壁脊
    for ang, dist, amp, s in [(112, 22, 4.5, 7.0), (300, 21, 4.0, 6.5)]:
        a = math.radians(ang)
        H += bump(math.cos(a) * dist, math.sin(a) * dist, amp, s, s * 0.6, a)

    # 地表起伏（山顶保护区几乎不动，免得鸟巢坑被噪点啃掉）
    flat = np.clip((rn - 0.30) / 0.25, 0, 1)          # 山顶 → 0
    H += (1.35 * (fbm(X, Y, 0.085, 5.0, 4) - 0.5) * 2.0) * flat
    H += (0.26 * (fbm(X, Y, 0.30, 9.0, 3) - 0.5) * 2.0) * flat

    # 梯田：山腰的招牌层次（山脚和山顶不加，免得台阶感压倒造型）。
    # 每一层的边界被噪声推来推去，所以台地是断断续续、宽窄不一的舌状台阶，
    # 而不是一圈圈规整的等高线。
    band = np.clip((H - 6.0) / 4.0, 0, 1) * np.clip((PEAK_H_M - 7.0 - H) / 6.0, 0, 1)
    band *= np.clip((rn - 0.22) / 0.12, 0, 1)          # 山顶平台不梯田化
    warp = 5.5 * (fbm(X, Y, 0.030, 29.0, 3) - 0.5) * 2.0
    step = 8.4 * (1.0 + 0.26 * (fbm(X, Y, 0.055, 23.0, 3) - 0.5) * 2.0)
    lv = (H + warp) / step
    fl = np.floor(lv)
    fr = lv - fl
    eased = np.clip((fr - 0.58) / 0.42, 0, 1)
    eased = eased * eased * (3 - 2 * eased)
    H = H * (1 - band) + ((fl + eased) * step - warp) * band

    # 冲沟：从上往下切出的雨水沟，把圆台剪影打碎
    for ang, wid, dep in GULLIES:
        g = np.exp(-(angdiff(TH, math.radians(ang)) / wid) ** 2)
        g *= np.clip((PEAK_H_M - 2.0 - H) / 6.0, 0, 1)
        g *= np.clip((H - 5.0) / 4.0, 0, 1)
        H -= dep * g * (0.75 + 0.5 * fbm(X, Y, 0.05, 61.0, 2))
    # 山脚一圈起伏，岸线不再是一个正圆
    H += 2.2 * (fbm(X, Y, 0.028, 71.0, 3) - 0.5) * 2.0 * np.clip((2.0 - rn) * 1.4, 0, 1)

    # 剪影：山腰被噪声顶出 / 削掉几处，免得从任何角度看都是个规整的圆台
    H += 3.4 * (fbm(X, Y, 0.020, 83.0, 3) - 0.5) * 2.0 \
        * np.clip((rn - 0.22) * 4.0, 0, 1) * np.clip((0.95 - rn) * 5.0, 0, 1)

    return np.array(X), np.array(Y), H, np.array(rn), np.array(rsh)


# ==================== 建实体 ====================
def boundary_loops(bm):
    be = [e for e in bm.edges if len(e.link_faces) == 1]
    adj = {}
    for e in be:
        a, b = e.verts
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)
    loops, seen = [], set()
    for start in list(adj):
        if start in seen:
            continue
        loop, prev, cur = [start], None, start
        seen.add(start)
        while True:
            nxt = None
            for v in adj[cur]:
                if v is not prev and v not in seen:
                    nxt = v
                    break
            if nxt is None:
                break
            loop.append(nxt)
            seen.add(nxt)
            prev, cur = cur, nxt
        if len(loop) >= 3:
            loops.append(loop)
    return loops


def build_solid(X, Y, H, rn):
    verts = np.column_stack([X.ravel(), Y.ravel(), H.ravel()]).tolist()
    idx = np.arange(N * N).reshape(N, N)
    faces = np.column_stack([idx[:-1, :-1].ravel(), idx[:-1, 1:].ravel(),
                             idx[1:, 1:].ravel(), idx[1:, :-1].ravel()]).tolist()
    me = bpy.data.meshes.new("NestMountainMesh")
    me.from_pydata(verts, [], faces)
    me.update()
    ob = bpy.data.objects.new("NestMountain", me)
    bpy.context.scene.collection.objects.link(ob)

    rnf = rn.ravel().tolist()
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[v for i, v in enumerate(bm.verts) if rnf[i] > 1.045],
                     context='VERTS')
    bm.verts.ensure_lookup_table()

    for loop in boundary_loops(bm):
        cxx = sum(v.co.x for v in loop) / len(loop)
        cyy = sum(v.co.y for v in loop) / len(loop)
        for v in loop:
            v.co.z = SEA_BOT_M
        centre = bm.verts.new((cxx, cyy, SEA_BOT_M))
        bm.verts.ensure_lookup_table()
        n = len(loop)
        for i in range(n):
            bm.faces.new((loop[i], loop[(i + 1) % n], centre))

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    me.update()
    return ob


def activate(ob):
    for o in bpy.context.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob


def apply_mod(ob, mod):
    bpy.ops.object.modifier_apply(modifier=mod.name)


# ==================== 山洞 ====================
def find_cave_site(ob, az_centre, az_span, z_lo, z_hi, r_lo, r_hi):
    """在给定方位 / 高度范围里找一段"立得住的墙面"。

    对每个候选点打一条水平射线，取命中面的法线；法线越水平（|nz| 越小）
    说明这里是崖壁而不是台地地面，洞口才不会朝天。返回 (方位角, 命中点, 法线)。
    """
    best = None
    for azd in np.arange(az_centre - az_span, az_centre + az_span + 0.01, 2.0):
        a = math.radians(azd)
        outward = Vector((math.cos(a), math.sin(a), 0.0))
        for z in np.arange(z_lo, z_hi + 0.01, 0.5):
            start = outward * (SIZE_M * 0.60) + Vector((0, 0, z))
            hit, loc, nrm, _i = ob.ray_cast(start, -outward, distance=SIZE_M)
            if not hit:
                continue
            wall = 1.0 - abs(nrm.z)                       # 1 = 完全竖直
            if wall < 0.45:
                continue
            rnow = math.hypot(loc.x, loc.y)
            if not (r_lo <= rnow <= r_hi):                 # 别落到外围小山包上
                continue
            score = wall - 0.035 * abs(z - (z_lo + z_hi) * 0.5)
            if best is None or score > best[0]:
                best = (score, float(azd), Vector(loc), Vector(nrm))
    if best is None:
        return None
    print("  site az=%.0f  mouth (%.1f, %.1f, %.1f)  wall=%.2f"
          % (best[1], best[2].x, best[2].y, best[2].z, 1.0 - abs(best[3].z)))
    return best[1], best[2], best[3]


def bore_cave(ob, azimuth_deg, target_z, radius, depth, tilt_deg):
    """用射线找到真实墙面，再用一根正圆柱切进去。

    洞口是**平整的圆形切口**（不加口沿石块）；要石头就在场景里单独摆
    `low_poly_rock.glb`，洞口的"平切"反而更好摆、更容易和地形对齐。
    """
    a = math.radians(azimuth_deg)
    outward = Vector((math.cos(a), math.sin(a), 0.0))
    start = outward * (SIZE_M * 0.60) + Vector((0, 0, target_z))
    hit, loc, nrm, _idx = ob.ray_cast(start, -outward, distance=SIZE_M)
    if not hit:
        print("  ! cave miss at az=%.0f z=%.1f" % (azimuth_deg, target_z))
        return None
    loc = Vector(loc)
    direction = (-outward + Vector((0, 0, math.tan(math.radians(tilt_deg))))).normalized()

    # 切口周围加密：圆柱和粗三角形相交时，口沿才不会切出锯齿
    me = ob.data
    bm = bmesh.new()
    bm.from_mesh(me)
    sel = [f for f in bm.faces
           if (f.calc_center_median() - loc).length < radius + 2.2]
    if sel:
        edges = set()
        for f in sel:
            edges.update(f.edges)
        bmesh.ops.subdivide_edges(bm, edges=list(edges), cuts=2, use_grid_fill=True)
        bm.to_mesh(me)
    bm.free()
    me.update()

    # 正圆柱：口沿是一圈平整的圆，切进去是直筒
    axis_len = depth + 3.0
    centre = loc + direction * (axis_len * 0.5 - 1.5)
    bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=radius, depth=axis_len,
                                        location=centre)
    cutter = bpy.context.object
    cutter.rotation_euler = direction.to_track_quat('Z', 'Y').to_euler()
    activate(ob)
    mb = ob.modifiers.new("cave", 'BOOLEAN')
    mb.operation = 'DIFFERENCE'
    mb.solver = 'EXACT'
    mb.object = cutter
    apply_mod(ob, mb)

    # 洞底扩一间石室，别让洞里是个死胡同管子
    room = loc + direction * (depth - radius * 0.55)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8,
                                         radius=radius * 1.5, location=room)
    ball = bpy.context.object
    activate(ob)
    mb2 = ob.modifiers.new("room", 'BOOLEAN')
    mb2.operation = 'DIFFERENCE'
    mb2.solver = 'EXACT'
    mb2.object = ball
    apply_mod(ob, mb2)

    for o in (cutter, ball):
        bpy.data.objects.remove(o, do_unlink=True)

    print("  cave az=%.0f -> mouth (%.1f, %.1f, %.1f)  normal (%.2f, %.2f, %.2f)"
          % (azimuth_deg, loc.x, loc.y, loc.z, nrm.x, nrm.y, nrm.z))
    return loc, direction, radius, depth



# ==================== 顶点色 ====================
def colourise(me, caves):
    ca = me.color_attributes.new(name="Col", type='FLOAT_COLOR', domain='CORNER')
    P = PAL
    L = Vector((0.45, -0.30, 0.84)).normalized()      # 预览用的"假日照"方向

    def mix(c1, c2, t):
        return c1 * (1.0 - t) + c2 * t

    for p in me.polygons:
        c = p.center
        nz = p.normal.z
        slope = 1.0 - max(-1.0, min(1.0, nz))
        rn = math.sqrt((c.x / BASE_R) ** 2 + (c.y / (BASE_R * 0.92)) ** 2)
        z = c.z

        # 每面的随机微差 + 大尺度斑块：块面感全靠这两项
        h = math.sin(c.x * 12.9898 + c.y * 78.233) * 43758.5453
        v = h - math.floor(h)
        patch = fbm(np.array([c.x]), np.array([c.y]), 0.06, 17.0, 3)[0]
        patch2 = fbm(np.array([c.x]), np.array([c.y]), 0.22, 41.0, 2)[0]
        tint = 0.90 + 0.20 * v + 0.10 * patch
        band = 0.88 + 0.24 * patch2

        if z < -0.4:                                        # 水下
            t = min(1.0, max(0.0, (z + 9.0) / 9.0))
            col = mix(P["sea_deep"], P["sea_shal"], t) * band
        elif 0.7 < z < 3.2 and slope < 0.30:                 # 环岛沙滩（贴着水线的坡面不上沙）
            col = mix(P["sand_l"], P["sand_d"], v) * (0.94 + 0.08 * patch)
        elif rn < 0.145 and z < PEAK_H_M - 0.4:             # 山顶鸟巢预留坑
            col = mix(P["dirt"], P["rock_d"], v) * (0.92 + 0.10 * patch)
        else:
            # 裸岩 / 草地由坡度决定：台地是草，台阶立面是岩。
            # 只有坡度超过 0.30 才开始转岩，所以山腰的大台地能保住草色。
            bare = min(1.0, max(0.0, (z - (PEAK_H_M - 4.5)) / 5.0))   # 山顶岩唇
            rock_t = min(1.0, max(0.0, (slope - 0.40) / 0.28))
            rock_t = max(rock_t, bare * 0.62)
            # 陡壁上零星挂着的草脊（噪声决定，低多边形那种一块一块的感觉）
            tongue = min(1.0, max(0.0, (patch - 0.50) / 0.22))
            rock_t *= (1.0 - 0.55 * tongue * (1.0 - bare))

            rock = mix(P["rock_m"], P["rock_d"], min(1.0, slope * 0.7 + 0.30 * v))
            rock = mix(rock, P["rock_l"], max(0.0, 1.0 - slope * 1.8) * 0.55)
            if z < 9.0:
                g = mix(P["grass_d"], P["grass_x"], v)
            elif z < 18.0:
                g = mix(P["grass_m"], P["grass_d"], v)
            elif z < 32.0:
                g = mix(P["grass_m"], P["grass_l"], 0.25 + 0.5 * patch)
            else:
                g = mix(P["grass_l"], P["grass_m"], v)
            # 台地边缘压暗、台面提亮 → 梯田的层次
            g = g * (0.84 + 0.26 * patch2) * (1.0 + 0.10 * max(0.0, nz))
            col = mix(g, rock, rock_t)

        # 洞内：沿洞轴变暗。
        # 注意只看"进了洞"的面：面的法线必须大致背对洞口，否则洞外正上方的
        # 崖面会落进这根管的半径里，被涂黑成几根尖刺。
        for (loc, direction, radius, depth) in caves:
            d = c - loc
            along = d.dot(direction)
            if along <= 0.15 or along > depth + radius:
                continue
            if p.normal.dot(direction) > -0.15:      # 面朝外 = 洞外的岩面
                continue
            if (d - direction * along).length < radius * 1.35:
                f = max(0.0, min(1.0, along / (depth * 0.80)))
                # 洞口一带保留岩色（洞壁厚度），越深越黑；地板比顶棚亮一点，
                # 像是天光漏进来，洞口才不会糊成一块剪影。
                k = 0.30 + 0.62 * f
                up = -direction.z * 0.0 + (d - direction * along).z / max(radius, 1e-3)
                lit = 0.35 + 0.65 * max(0.0, min(1.0, 0.5 - up * 0.5))
                cave_col = P["cave_in"] * (0.5 + 1.9 * lit)
                col = mix(col, cave_col, k)

        col = np.clip(col, 0.0, 1.0)
        for li in p.loop_indices:
            ca.data[li].color = (col[0], col[1], col[2], 1.0)


# ==================== 预览：摆独立的石头资产 ====================
ROCK_GLB = os.path.join(os.path.dirname(OUT_DIR), "low-poly-rock", "low_poly_rock.glb")


def drop_to_ground(ob, x, y, z_hint):
    """从高处往下打一条射线，返回该 XY 处的地表高度（打不到就当 z=0）。"""
    hit, loc, _n, _i = ob.ray_cast(Vector((x, y, z_hint + 60.0)),
                                   Vector((0, 0, -1)), distance=140.0)
    return loc.z if hit else 0.0


def place_preview_rocks(ob, caves):
    """把 low_poly_rock.glb 摆到两个洞口旁边，交代洞口尺度。

    石头是**独立资产**（models/low-poly-rock，自己的脚本和 GLB），这里只是
    在预览场景里引用并复制几份，不进山体的 GLB。山脚洞在坡上、山腰洞在台地上，
    所以落地高度是用射线实测的，不是写死的 z。
    """
    if not os.path.exists(ROCK_GLB):
        print("  (preview rocks skipped: %s not found)" % ROCK_GLB)
        return
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=ROCK_GLB)
    src = [o for o in bpy.data.objects if o not in before and o.type == 'MESH']
    if not src:
        return
    proto = src[0]

    # 每个洞口：正前方 2~3 块，左右错开、朝向不同
    layout = [(3.2, 1.9, 25.0), (-3.6, 2.6, -40.0), (4.4, 5.2, 70.0)]
    for ci, (loc_v, direction, radius, depth) in enumerate(caves):
        # direction 是"往山里钻"的方向，朝洞外要取反
        n = Vector((-direction.x, -direction.y, 0.0)).normalized()
        u = Vector((-n.y, n.x, 0.0))                               # 洞口横向
        for k, (side, fwd, yaw) in enumerate(layout):
            x = loc_v.x + n.x * (radius + fwd) + u.x * side
            y = loc_v.y + n.y * (radius + fwd) + u.y * side
            z = drop_to_ground(ob, x, y, loc_v.z) - 0.06           # 稍微埋进去一点
            rocks = proto.copy()                                   # 共用 mesh 数据
            rocks.data = proto.data
            rocks.name = "Rock_preview_%d_%d" % (ci, k)
            rocks.location = (x, y, z)
            rocks.rotation_euler = (0.0, 0.0, math.radians(yaw))
            bpy.context.scene.collection.objects.link(rocks)
            print("    rock cave%d @ (%.1f, %.1f, %.1f)" % (ci, x, y, z))
    for o in src:
        bpy.data.objects.remove(o, do_unlink=True)                 # 原件不需要了
    print("  preview rocks placed near both cave mouths")


def make_material(me, name="NestMountainMat"):
    me.materials.clear()
    for d in list(bpy.data.materials):
        if d.users == 0:
            bpy.data.materials.remove(d)
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    bsdf.inputs['Roughness'].default_value = 0.92
    bsdf.inputs['Metallic'].default_value = 0.0
    attr = nt.nodes.new('ShaderNodeVertexColor')
    attr.layer_name = "Col"
    attr.location = (-320, 200)
    nt.links.new(attr.outputs['Color'], bsdf.inputs['Base Color'])
    me.materials.append(mat)


# ==================== 预览占位鸟巢 ====================
def twig_tube(pts, radius, sides=4, seed=0):
    """沿折线挤出一根方形截面的枝条，返回 (verts, faces)。"""
    rng = random.Random(seed)
    verts, faces = [], []
    rings = []
    up = Vector((0, 0, 1))
    for i, p in enumerate(pts):
        if i < len(pts) - 1:
            d = (Vector(pts[i + 1]) - Vector(p))
        else:
            d = (Vector(p) - Vector(pts[i - 1]))
        d.normalize()
        ref = up if abs(d.z) < 0.9 else Vector((1, 0, 0))
        u = d.cross(ref).normalized()
        w = d.cross(u).normalized()
        rr = radius * (0.85 + 0.3 * rng.random())
        ring = []
        for k in range(sides):
            ang = 2 * math.pi * k / sides + rng.random() * 0.4
            off = u * (math.cos(ang) * rr) + w * (math.sin(ang) * rr)
            ring.append(len(verts))
            verts.append((p[0] + off.x, p[1] + off.y, p[2] + off.z))
        rings.append(ring)
    for i in range(len(rings) - 1):
        a, b = rings[i], rings[i + 1]
        for k in range(sides):
            k2 = (k + 1) % sides
            faces.append((a[k], a[k2], b[k2], b[k]))
    return verts, faces


def build_nest_placeholder():
    """碗状柴枝堆：占住山顶的坑，方便看尺度（不进 GLB）。"""
    rng = random.Random(SEED + 7)
    verts, faces = [], []

    def add(pts, r, seed):
        v, f = twig_tube(pts, r, 4, seed)
        base = len(verts)
        verts.extend(v)
        faces.extend([tuple(i + base for i in fa) for fa in f])

    rim_z = PEAK_H_M - 0.9
    floor_z = NEST_FLOOR_M + 0.9

    # 1) 内壁：一圈圈斜着绕的枝条，从坑底绕到坑沿
    for i in range(34):
        a0 = rng.random() * math.tau
        turns = 0.55 + 0.5 * rng.random()
        h0 = floor_z + (rim_z - floor_z) * rng.random() * 0.75
        pts = []
        n = 6
        for k in range(n):
            t = k / (n - 1)
            ang = a0 + turns * math.tau * t
            rr = NEST_R_M * (1.02 - 0.30 * t) * (0.90 + 0.13 * rng.random())
            z = h0 + (rim_z - h0) * t + 0.55 * math.sin(t * math.pi) * rng.uniform(-1, 1)
            z = min(z, rim_z)
            pts.append((math.cos(ang) * rr, math.sin(ang) * rr, z))
        add(pts, 0.16 + 0.10 * rng.random(), 100 + i)

    # 2) 巢底：交叉的横枝，铺成浅碟
    for i in range(16):
        a0 = rng.random() * math.tau
        pts = []
        n = 5
        for k in range(n):
            t = k / (n - 1)
            rr = NEST_R_M * (0.10 + 0.85 * t)
            ang = a0 + 0.35 * math.sin(t * 3.0) + rng.uniform(-0.1, 0.1)
            z = floor_z + 1.5 * (1.0 - (1.0 - t) ** 2) + rng.uniform(-0.25, 0.25)
            pts.append((math.cos(ang) * rr, math.sin(ang) * rr, z))
        add(pts, 0.17, 200 + i)

    # 3) 巢沿：外翻的粗枝
    for i in range(18):
        a0 = rng.random() * math.tau
        pts = []
        for k in range(4):
            t = k / 3.0
            ang = a0 + (0.9 - 0.5 * t) * math.tau * (1 if i % 2 else -1)
            rr = NEST_R_M * (1.06 + 0.10 * t) * (0.95 + 0.09 * rng.random())
            z = rim_z + 0.35 * t + rng.uniform(-0.2, 0.2)
            pts.append((math.cos(ang) * rr, math.sin(ang) * rr, z))
        add(pts, 0.22, 300 + i)

    me = bpy.data.meshes.new("NestPlaceholderMesh")
    me.from_pydata(verts, [], faces)
    me.update()
    ob = bpy.data.objects.new("NestPlaceholder", me)
    bpy.context.scene.collection.objects.link(ob)

    # 枝条顶点色（三层棕 + 每根随机）
    ca = me.color_attributes.new(name="Col", type='FLOAT_COLOR', domain='CORNER')
    P = PAL
    for p in me.polygons:
        z = p.center.z
        t = min(1.0, max(0.0, (z - NEST_FLOOR_M) / max(0.1, PEAK_H_M - NEST_FLOOR_M)))
        v = (math.sin(p.center.x * 21.7 + p.center.y * 9.1) * 0.5 + 0.5)
        col = (P["twig_d"] * (1 - t) + P["twig_l"] * t) * (0.85 + 0.30 * v)
        col = np.clip(col, 0, 1)
        for li in p.loop_indices:
            ca.data[li].color = (col[0], col[1], col[2], 1.0)
    make_material(me, "NestPlaceholderMat")
    for p in me.polygons:
        p.use_smooth = False
    return ob


# ==================== 预览渲染 ====================
def setup_preview():
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
    bg.inputs[0].default_value = (0.68, 0.79, 0.88, 1.0)
    bg.inputs[1].default_value = 0.85

    for name, energy, rot, angle in [
            ("Sun", 3.6, (math.radians(50), 0, math.radians(-125)), 3.0),
            ("Fill", 0.9, (math.radians(64), 0, math.radians(60)), 22.0),
            ("Front", 0.4, (math.radians(80), 0, math.radians(-95)), 30.0)]:
        ld = bpy.data.lights.new(name, 'SUN')
        ld.energy = energy
        ld.angle = math.radians(angle)
        ob = bpy.data.objects.new(name, ld)
        ob.rotation_euler = rot
        scene.collection.objects.link(ob)

    # 海面（只在预览里，用来交代 z=0 的水位线）
    me = bpy.data.meshes.new("SeaMesh")
    s = 900.0
    me.from_pydata([(-s, -s, 0), (s, -s, 0), (s, s, 0), (-s, s, 0)], [], [(0, 1, 2, 3)])
    me.update()
    sea = bpy.data.objects.new("SeaPreview", me)
    mat = bpy.data.materials.new("SeaPreviewMat")
    mat.use_nodes = True
    bsdf = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    bsdf.inputs['Base Color'].default_value = (0.09, 0.24, 0.34, 1.0)
    bsdf.inputs['Roughness'].default_value = 0.25
    me.materials.append(mat)
    scene.collection.objects.link(sea)

    cam_data = bpy.data.cameras.new("PreviewCam")
    cam_data.lens = 42.0
    cam = bpy.data.objects.new("PreviewCam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    return cam, sea


def render_shot(cam, path, loc, look_at, res=(900, 640)):
    scene = bpy.context.scene
    scene.render.resolution_x, scene.render.resolution_y = res
    cam.location = Vector(loc)
    cam.rotation_euler = (Vector(look_at) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


def stitch(paths, out_path, cols):
    imgs = [bpy.data.images.load(p) for p in paths]
    w, h = imgs[0].size
    rows = int(math.ceil(len(imgs) / cols))
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


# ==================== 主流程 ====================
def clear_scene():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.cameras, bpy.data.lights):
        for d in list(coll):
            if d.users == 0:
                coll.remove(d)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    do_render = "--nopreview" not in argv
    do_nest = "--nonest" not in argv

    random.seed(SEED)
    np.random.seed(SEED)
    clear_scene()
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1.0

    print("building heightfield ...")
    X, Y, H, rn, rsh = build_heightfield()
    ob = build_solid(X, Y, H, rn)
    me = ob.data
    activate(ob)
    print("  grid %d x %d -> %d faces" % (N, N, len(me.polygons)))

    sm = ob.modifiers.new("smooth", 'SMOOTH')
    sm.factor, sm.iterations = 0.40, 2
    apply_mod(ob, sm)

    # 山顶保护区：鸟巢坑 + 平台边缘不被减面吃掉
    vg = ob.vertex_groups.new(name="protect")
    for v in me.vertices:
        c = v.co
        rr = math.sqrt((c.x / BASE_R) ** 2 + (c.y / (BASE_R * 0.92)) ** 2)
        vg.add([v.index], 0.0 if rr < 0.185 else 1.0, 'REPLACE')

    d1 = ob.modifiers.new("dissolve", 'DECIMATE')
    d1.decimate_type = 'DISSOLVE'
    d1.angle_limit = math.radians(6.0)
    apply_mod(ob, d1)

    tr = ob.modifiers.new("tri", 'TRIANGULATE')
    apply_mod(ob, tr)

    f = len(me.polygons)
    d2 = ob.modifiers.new("collapse", 'DECIMATE')
    d2.decimate_type = 'COLLAPSE'
    d2.ratio = min(1.0, TARGET_TRIS / max(1, f))
    d2.vertex_group = "protect"
    d2.vertex_group_factor = 1.0
    apply_mod(ob, d2)
    ob.vertex_groups.remove(ob.vertex_groups["protect"])
    print("  after decimate: %d faces" % len(me.polygons))

    # 山洞（在最终体量上钻，位置由射线打在真实墙面上决定）
    caves = []
    for (az, z, r, d, tilt, r_lo, r_hi) in CAVES:
        site = find_cave_site(ob, az, 26.0, max(4.0, z - 4.0), z + 4.0, r_lo, r_hi)
        if not site:
            print("  ! no wall found near az=%.0f z=%.1f" % (az, z))
            continue
        azd, loc, nrm = site
        res = bore_cave(ob, azd, loc.z, r, d, tilt)
        if res:
            caves.append(res)

    # 收尾清理：焊接、去碎片、补洞、重算法线
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=3.0e-3)
    bmesh.ops.dissolve_degenerate(bm, dist=3.0e-3, edges=bm.edges)
    tiny = [f for f in bm.faces if f.calc_area() < 3.0e-3]
    if tiny:
        bmesh.ops.delete(bm, geom=tiny, context='FACES')
    doomed = []
    for e in bm.edges:
        if len(e.link_faces) > 2:
            keep = max(e.link_faces, key=lambda f: f.calc_area())
            doomed += [f for f in e.link_faces if f is not keep]
    if doomed:
        bmesh.ops.delete(bm, geom=list(set(doomed)), context='FACES')
    holes = [e for e in bm.edges if len(e.link_faces) == 1]
    if holes:
        bmesh.ops.holes_fill(bm, edges=holes, sides=0)
    bmesh.ops.triangulate(bm, faces=bm.faces)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    me.update()
    for p in me.polygons:
        p.use_smooth = False

    colourise(me, caves)
    make_material(me)

    # 烘变换 + 原点归零
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    activate(ob)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    ob.data.transform(ob.matrix_world)
    ob.matrix_world.identity()

    nest = build_nest_placeholder() if do_nest else None

    # 导出 GLB：只有山（占位鸟巢 / 灯光 / 相机 / 海面都不进）
    activate(ob)
    glb = os.path.join(OUT_DIR, NAME + ".glb")
    bpy.ops.export_scene.gltf(filepath=glb, export_format='GLB', use_selection=True,
                              export_apply=True, export_yup=True,
                              export_texcoords=False, export_normals=True,
                              export_vertex_color='MATERIAL')

    # 预览
    if do_render:
        cam, sea = setup_preview()
        place_preview_rocks(ob, caves)
        shots_dir = "/tmp/nest_mountain"
        os.makedirs(shots_dir, exist_ok=True)
        far = 150.0
        az = math.radians(118)
        cam_34 = (math.cos(az) * far, math.sin(az) * far, 58.0)
        target = (0.0, 0.0, 20.0)
        p1 = os.path.join(shots_dir, "a.png")
        render_shot(cam, p1, cam_34, target)
        if nest:
            nest.hide_render = True
        p2 = os.path.join(shots_dir, "b.png")
        render_shot(cam, p2, cam_34, target)
        if nest:
            nest.hide_render = False
        # 俯视山顶
        p3 = os.path.join(shots_dir, "c.png")
        render_shot(cam, p3, (0.0, 0.0, 86.0), (0.0, 0.0, PEAK_H_M - 2.0))
        # 山脚洞口特写（用真实洞口位置 / 洞轴）
        c0 = caves[0]
        n0 = Vector((c0[1].x, c0[1].y, 0.0)).normalized()
        p4 = os.path.join(shots_dir, "d.png")
        render_shot(cam, p4, Vector(c0[0]) - n0 * 30.0 + Vector((0, 0, 6.0)),
                    Vector(c0[0]))
        if nest:
            nest.hide_render = True
        stitch([p1, p2, p3, p4], os.path.join(OUT_DIR, NAME + "_preview.png"), 2)

        # 洞口：每个洞来一组"全身 + 特写"，方便核对洞口在山体上的位置
        shots = []
        for i, (loc_v, direction, r, d) in enumerate(caves):
            n = Vector((direction.x, direction.y, 0.0)).normalized()   # 洞轴的水平朝向
            far_eye = Vector(loc_v) - n * 118.0 + Vector((0, 0, 46.0))
            tgt = Vector((0, 0, 18.0))
            p = os.path.join(shots_dir, "wide%d.png" % i)
            render_shot(cam, p, far_eye, tgt, res=(760, 560))
            shots.append(p)
            eye = Vector(loc_v) - n * 34.0 + Vector((0, 0, 5.0))
            p = os.path.join(shots_dir, "cave%d.png" % i)
            render_shot(cam, p, eye, Vector(loc_v) + n * 2.0, res=(760, 560))
            shots.append(p)
        stitch(shots, os.path.join(OUT_DIR, NAME + "_cave.png"), 2)
        if nest:
            nest.hide_render = False
        p = os.path.join(shots_dir, "top.png")
        render_shot(cam, p, (0.0, -26.0, 80.0), (0.0, 0.0, PEAK_H_M - 3.0), res=(900, 700))
        stitch([p], os.path.join(OUT_DIR, NAME + "_top.png"), 1)
        sea.hide_render = True

    blend = os.path.join(OUT_DIR, NAME + ".blend")
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=blend)

    zs = [v.co.z for v in me.vertices]
    xs = [v.co.x for v in me.vertices]
    ys = [v.co.y for v in me.vertices]
    print("=" * 62)
    print("%s  tris=%d  verts=%d" % (NAME, len(me.polygons), len(me.vertices)))
    print("BBOX  X %.1f  Y %.1f  Z %.1f..%.1f  (山脚占地 %.0f m, 主峰 %.1f m)"
          % (max(xs) - min(xs), max(ys) - min(ys), min(zs), max(zs),
             max(max(xs) - min(xs), max(ys) - min(ys)), max(zs)))
    print("山顶平台 Ø %.1f m, 鸟巢坑 Ø %.1f m 深 %.1f m, 坑底 z=%.1f"
          % (PLATEAU_R_M * 2, NEST_R_M * 2, PEAK_H_M - NEST_FLOOR_M, NEST_FLOOR_M))
    print("山洞:", ["az=%.0f z=%.1f r=%.1f" % c[:3] for c in CAVES] if caves else "无")
    print("saved:", glb)
    print("saved:", blend)


if __name__ == "__main__":
    main()
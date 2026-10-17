# Blender 建模脚本：Low-Poly 石头（洞口 / 路边点缀用的独立资产）
#
# 用法:
#   blender --background --python low_poly_rock.py
#   blender --background --python low_poly_rock.py -- --nopreview
#   blender --background --python low_poly_rock.py -- --seed 12     # 试别的随机造型
#
# 产物（写入本目录）:
#   low_poly_rock.blend / low_poly_rock.glb / low_poly_rock_preview.png
#
# ---------------------------------------------------------------------------
# 造型
# ---------------------------------------------------------------------------
# 一颗 2.9 m 量级的巨石。低多边形石头的干净来自两件事，本脚本对两件都做了硬约束：
#
#   1) 所有面都是**精确平面**：形体由 icosphere 起手，用一串切割平面削出棱面，
#      每个棱面都由单一平面切出来（切割平面上的多边形必然共面）。先两刀削掉
#      icosphere 的极点尖顶（不然五个面汇聚成一个尖，那是宝石不是石头）。
#      不做任何逐顶点随机推拉——那会把面揉成非平面碎面，正是"边缘不干净"的根源。
#
#   2) 每一刀都**先在副本上验收**：切割若和已有棱面近乎平行，会切出一条又长又窄
#      的棱面（sliver），单独一块颜色时看着就是一道划痕。所以每次切割都在 bmesh
#      副本上试切、压成最终形态、再量棱面质量，只有全部过门槛才采纳，否则丢弃重试。
#      干净因此是**构造保证**的，不靠种子运气：
#
#        facet_quality()  棱面紧凑度 4πA/P² >= MIN_FACET_ISO、面积、最短棱边
#        tri_quality()    三角面兜底（防退化）
#        cut_is_clean()   以上合起来的验收闸门
#
#      量的是"棱面"而不是三角面：同一棱面内的三角形共面同色，面内细长三角在画面
#      和 Godot 里都看不出来；真正可见的是棱面本身。
#
# 底部是"最低点往上 42% 高度"处的一刀平切面，原点在底部中心，Godot 里 position
# 就是落地点。尺寸最后逐轴归一到 §2 基准表（2.92 × 2.55 × 1.34 m），不靠 Godot 缩放。
#
# ---------------------------------------------------------------------------
# 颜色（顶点色 COLOR_0，线性空间，单材质）
# ---------------------------------------------------------------------------
# 按**棱面**（共面片）而非三角形上色：一个平面 = 一块颜色，棱线因此是干净的分色边界。
# （旧版按三角面上色，同平面内的碎切会渲染成一片脏斑，这是"边缘不干净"的另一半原因。）
# 灰褐岩石按高度 + 棱面朝向 + 随机值分三档，顶面朝上的大棱面整块长苔藓。
import math
import os
import random
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Vector

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
NAME = "low_poly_rock"

# ==================== 尺寸（米）====================
LONG_M = 2.92             # 长边（X）
WIDE_M = 2.55             # 短边（Y）
HIGH_M = 1.34             # 高（Z，底面 z=0）
SEED = 20240812

# ==================== 造型参数 ====================
TOP_CUTS = 2              # 先削顶的刀数（去极点尖顶）
CUTS = 13                 # 之后采纳的随机切割刀数（不含落地面）
CUT_H_LO, CUT_H_HI = 0.52, 0.95   # 切割平面到原点的距离（icosphere 半径=1）
CUT_Z_MIN = -0.45         # 切割方向 z 的下限（不从头底往上切，底面交给 z=0）
CUT_H_DELAY = 0.05        # 刀面与任何顶点的最小间距，避免把顶点劈成碎角
TRY_PER_CUT = 260         # 每刀最多试多少个候选方向

# ==================== 质量门槛（验收用，单位=米）====================
# 决定"边缘干净"的是棱面：既长又窄的棱面会像一道划痕，必须挡掉
MIN_FACET_ISO = 0.46      # 棱面紧凑度 4πA/P² 下限（正圆=1；0.46 ≈ 不许超过 5:1 的长条）
MIN_FACET_AREA_M2 = 0.050 # 棱面面积下限（约 22cm × 22cm）
MIN_FACET_EDGE_M = 0.090  # 棱面最短边长下限
# 三角面只兜"退化"，不追求面内三角都胖（面内共面同色，看不出来）
MIN_TRI_ANGLE = 4.0       # 三角面最小内角（度）
MIN_TRI_AREA_M2 = 0.0008  # 三角面最小面积
BOTTOM_MIN_M2 = 0.90      # 平底接触面积下限（太小说明石头是尖底立着）
SQUASH = (1.45, 1.25, 1.00)   # 压成躺在地上的石头
BASE_FRAC = 0.42          # 底面切在"最低点 + 42% 高度"处：落地面积够大，又少一片下棱面


def srgb2lin(c):
    c = np.asarray(c, dtype=float)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


PAL = {
    "rock_l": srgb2lin([0.74, 0.68, 0.60]),
    "rock_m": srgb2lin([0.56, 0.48, 0.40]),
    "rock_d": srgb2lin([0.36, 0.30, 0.25]),
    "moss": srgb2lin([0.34, 0.50, 0.20]),
}


def clear_scene():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.cameras, bpy.data.lights):
        for d in list(coll):
            if d.users == 0:
                coll.remove(d)


def activate(ob):
    for o in bpy.context.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob


# ==================== 网格工具 ====================
def dissolve_coplanar(bm, angle_deg=0.05):
    """把同一平面上的碎面合并回一个大棱面（切割会不断把棱面劈成两半）。"""
    bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(angle_deg),
                             verts=bm.verts[:], edges=bm.edges[:])
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()


def fill_boundary(bm):
    """切割后补上切口面（必然是平面多边形）。"""
    holes = [e for e in bm.edges if len(e.link_faces) == 1]
    if holes:
        bmesh.ops.holes_fill(bm, edges=holes, sides=0)
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()


def bisect(bm, normal, dist, clear_outer=False, clear_inner=False):
    bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:],
                           plane_co=normal * dist, plane_no=normal,
                           clear_outer=clear_outer, clear_inner=clear_inner)
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    fill_boundary(bm)
    dissolve_coplanar(bm)


def visible_faces(bm):
    """可见棱面：排除埋在土里的平底面（z=0 那一整块）。"""
    return [f for f in bm.faces if not all(v.co.z < 1e-6 for v in f.verts)]


def facet_quality(bm):
    """棱面质量（决定"边缘干不干净"）：(最小紧凑度, 最小面积, 最短棱边)。

    紧凑度 = 4πA/P²：正圆为 1，长条会趋近 0。低多边形石头的"脏"通常就是
    某几块又长又窄的棱面（刀面与已有棱面近乎平行时切出来的一条），
    它单独一个颜色时看着就像一道划痕。所以这里把它直接挡在门外。

    注意：量的是**棱面**而不是三角面。同一棱面内的三角形共面同色，
    面内的细长三角形在画面和 Godot 里都看不出来；真正可见的是棱面本身。
    """
    isos, areas, edges = [], [], []
    for f in visible_faces(bm):
        a = f.calc_area()
        p = f.calc_perimeter()
        if a <= 0.0 or p <= 0.0:
            return 0.0, 0.0, 0.0
        isos.append(4.0 * math.pi * a / (p * p))
        areas.append(a)
        edges.append(min(e.calc_length() for e in f.edges))
    if not isos:
        return 0.0, 0.0, 0.0
    return min(isos), min(areas), min(edges)


def tri_quality(bm):
    """三角面兜底质量（防退化）：(最小内角°, 最小面积)。量在三角化副本上。"""
    tmp = bm.copy()
    bmesh.ops.triangulate(tmp, faces=tmp.faces[:], quad_method='BEAUTY', ngon_method='BEAUTY')
    tmp.faces.ensure_lookup_table()
    min_ang = 180.0
    min_area = 1e9
    for f in tmp.faces:
        if len(f.verts) != 3 or all(v.co.z < 1e-6 for v in f.verts):
            continue
        a, b, c = [v.co for v in f.verts]
        for p, q, r in ((a, b, c), (b, c, a), (c, a, b)):
            u, w = q - p, r - p
            if u.length < 1e-9 or w.length < 1e-9:
                tmp.free()
                return 0.0, 0.0
            min_ang = min(min_ang, math.degrees(u.angle(w)))
        min_area = min(min_area, f.calc_area())
    tmp.free()
    return min_ang, min_area


def bottom_area(bm):
    """落在 z=0 上的平底面积（接触地面的那一块）。"""
    return sum(f.calc_area() for f in bm.faces
               if all(abs(v.co.z) < 1e-6 for v in f.verts))


def finalize_shape(bm, frac=None):
    """把造型收成最终形态：压成躺石 -> 切平底面 -> 归一到尺寸基准。

    验收必须量在**最终形态**上：压扁和逐轴归一都是非等比缩放，会改变棱面形状，
    在中间形态量着合格、缩放后照样可能变窄。最终量纲都是米。
    """
    frac = BASE_FRAC if frac is None else frac
    out = bm.copy()
    for v in out.verts:
        v.co.x *= SQUASH[0]
        v.co.y *= SQUASH[1]
        v.co.z *= SQUASH[2]

    zs = [v.co.z for v in out.verts]
    z_c = min(zs) + (max(zs) - min(zs)) * frac
    # 落地面别贴着顶点，否则接触边缘会碎
    for _ in range(60):
        if min(abs(z_c - z) for z in zs) > 0.03:
            break
        z_c += 0.01
    bisect(out, Vector((0, 0, 1)), z_c, clear_inner=True)
    for v in out.verts:
        v.co.z -= z_c

    xs = [v.co.x for v in out.verts]
    ys = [v.co.y for v in out.verts]
    zs = [v.co.z for v in out.verts]
    cx = (max(xs) + min(xs)) * 0.5
    cy = (max(ys) + min(ys)) * 0.5
    sx = LONG_M / (max(xs) - min(xs))
    sy = WIDE_M / (max(ys) - min(ys))
    sz = HIGH_M / max(1e-9, max(zs))
    for v in out.verts:
        v.co.x = (v.co.x - cx) * sx
        v.co.y = (v.co.y - cy) * sy
        v.co.z = max(0.0, v.co.z * sz)
    bmesh.ops.recalc_face_normals(out, faces=out.faces[:])
    out.verts.ensure_lookup_table()
    out.faces.ensure_lookup_table()
    return out


def cut_is_clean(bm):
    """一刀是否干净：量最终形态的棱面质量 + 三角面兜底 + 落地面积。"""
    fin = finalize_shape(bm)
    iso, farea, fedge = facet_quality(fin)
    ang, tarea = tri_quality(fin)
    ok = (iso >= MIN_FACET_ISO
          and farea >= MIN_FACET_AREA_M2
          and fedge >= MIN_FACET_EDGE_M
          and ang >= MIN_TRI_ANGLE
          and tarea >= MIN_TRI_AREA_M2
          and bottom_area(fin) >= BOTTOM_MIN_M2)
    fin.free()
    return ok


def attempt_cut(bm, n, h0):
    """用给定方向和大致刀深试切一刀；验收通过就写回 bm，返回是否成功。"""
    n = n.normalized()
    proj = [n.dot(v.co) for v in bm.verts]
    lo, hi = min(proj), max(proj)
    if hi - lo < 0.25:
        return False
    # 刀面离每个顶点都至少有 CUT_H_DELAY 的距离：绝不把顶点劈出零碎小角
    cands = [h0 + k * 0.015 for k in (0, -1, 1, -2, 2, -3, 3, -4, 4, -5, 5)]
    cands = [c for c in cands
             if lo + 0.02 < c < hi - 0.02 and min(abs(c - p) for p in proj) > CUT_H_DELAY]
    if not cands:
        return False
    h = min(cands, key=lambda c: abs(c - h0))
    outside = sum(1 for p in proj if p > h + 1e-9)
    inside = sum(1 for p in proj if p < h - 1e-9)
    if outside < 1 or inside < 4:
        return False

    trial = bm.copy()
    bisect(trial, n, h, clear_outer=True)
    ok = len(trial.faces) > 3 and cut_is_clean(trial)
    trial.free()
    if not ok:
        return False
    bisect(bm, n, h, clear_outer=True)
    return True


def try_cut(bm, rng, h_lo=None, h_hi=None, z_min=None, tries=None):
    """随便找个方向试切，直到切出一刀干净的。"""
    h_lo = CUT_H_LO if h_lo is None else h_lo
    h_hi = CUT_H_HI if h_hi is None else h_hi
    z_min = CUT_Z_MIN if z_min is None else z_min
    tries = TRY_PER_CUT if tries is None else tries
    for _ in range(tries):
        n = Vector((rng.uniform(-1.0, 1.0), rng.uniform(-1.0, 1.0),
                    rng.uniform(z_min, 1.0)))
        if n.length < 1e-3:
            continue
        if attempt_cut(bm, n, rng.uniform(h_lo, h_hi)):
            return True
    return False


def try_top_cut(bm, rng, tries=60):
    """削顶：把 icosphere 的极点削成一块缓坡顶面。

    不做这刀，五个面会汇聚在极点变成一个尖顶——那是"宝石"而不是"石头"的样子。
    """
    for _ in range(tries):
        theta = math.radians(rng.uniform(10.0, 33.0))     # 顶面倾角
        phi = rng.uniform(0.0, 2.0 * math.pi)
        n = Vector((math.sin(theta) * math.cos(phi),
                    math.sin(theta) * math.sin(phi),
                    math.cos(theta)))
        if attempt_cut(bm, n, rng.uniform(0.76, 0.93)):
            return True
    return False


def build_rock():
    rng = random.Random(SEED)
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=1, radius=1.0)
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    dissolve_coplanar(bm)

    # 1) 先削顶（TOP_CUTS 刀），去掉"五面汇聚的极点尖顶"
    top = 0
    for _ in range(TOP_CUTS * 6):
        if top >= TOP_CUTS:
            break
        if try_top_cut(bm, rng):
            top += 1
    assert top == TOP_CUTS, "削顶刀没切成功（%d/%d）" % (top, TOP_CUTS)

    # 2) 主造型：一刀一刀削出棱面，每刀都按最终形态验收
    accepted = 0
    for _ in range(CUTS * 4):
        if accepted >= CUTS:
            break
        if try_cut(bm, rng):
            accepted += 1
    assert accepted == CUTS, "只切出 %d 刀（目标 %d），请调 CUTS / 阈值" % (accepted, CUTS)

    # 3) 压成躺石 + 切平底面 + 归一到尺寸基准（尺寸在这里就已经精确命中了）
    fin = finalize_shape(bm)
    bm.free()
    bm = fin

    # 3) 清尾：合并重合点 / 去退化面，再三角化（导出用三角面）
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-4)
    bmesh.ops.dissolve_degenerate(bm, edges=bm.edges[:], dist=1e-4)
    dissolve_coplanar(bm)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    facet_count = len(bm.faces)
    bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method='BEAUTY', ngon_method='BEAUTY')
    bm.faces.ensure_lookup_table()
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.normal_update()

    me = bpy.data.meshes.new(NAME + "Mesh")
    bm.to_mesh(me)
    bm.free()
    me.update()
    ob = bpy.data.objects.new(NAME, me)
    bpy.context.scene.collection.objects.link(ob)
    for p in me.polygons:
        p.use_smooth = False
    return ob, facet_count


# ==================== 棱面分组 + 上色 ====================
def plane_groups(me):
    """把三角面按"共面"聚成棱面。三角化后同一棱面的三角形法线/载距完全一致。"""
    groups = []      # [{"n": Vector, "d": float, "faces": [idx]}]
    cos_tol = math.cos(math.radians(0.25))
    for p in me.polygons:
        n = p.normal.copy()
        d = n.dot(p.center)
        for g in groups:
            if n.dot(g["n"]) > cos_tol and abs(d - g["d"]) < 1.5e-3:
                g["faces"].append(p.index)
                break
        else:
            groups.append({"n": n, "d": d, "faces": [p.index]})
    return groups


def hash01(*vals):
    h = math.sin(sum(v * k for v, k in zip(vals, (12.9898, 78.233, 37.719))) * 43758.5453)
    return h - math.floor(h)


def colourise(me):
    ca = me.color_attributes.new(name="Col", type='FLOAT_COLOR', domain='CORNER')
    P = PAL
    for g in plane_groups(me):
        faces = [me.polygons[i] for i in g["faces"]]
        area = sum(f.area for f in faces)
        centre = Vector((0, 0, 0))
        for f in faces:
            centre += f.center
        centre /= len(faces)
        nz = g["n"].z
        h = hash01(centre.x * 3.1, centre.y * 2.7, centre.z * 2.3)

        # 底暗上亮（接触阴影感）。一整块棱面一个颜色，棱线就是干净的分色边界
        t = min(1.0, max(0.0, (centre.z - 0.04) / (HIGH_M * 0.85)))
        rock = P["rock_d"] * (1.0 - t) + P["rock_m"] * t
        rock = rock * (0.92 + 0.16 * h)                   # 棱面之间轻微明暗差
        if nz > 0.35:                                     # 朝上的棱面吃一点天光
            rock = rock * 0.82 + P["rock_l"] * (0.18 + 0.10 * h)
        if area < 0.16:                                   # 小碎面 = 新断面，略亮
            rock = rock * 0.86 + P["rock_l"] * 0.14
        if nz > 0.50 and centre.z > HIGH_M * 0.52 and h > 0.30:
            # 顶面朝上的大棱面整块长苔藓（低多边形靠"整块分色"表现，不靠斑纹）
            k = 0.34 + 0.26 * h
            rock = rock * (1.0 - k) + P["moss"] * k
        # 朝下的棱面渐暗（接触阴影）。用渐变而不是一刀切，
        # 否则石头底下会出现一条生硬的黑带，比不干净还扎眼
        rock = rock * (1.0 - 0.30 * max(0.0, -nz))
        if centre.z < 0.10:
            rock = rock * (0.78 + 0.22 * centre.z / 0.10)
        col = np.clip(rock, 0.0, 1.0)
        for f in faces:
            for li in f.loop_indices:
                ca.data[li].color = (col[0], col[1], col[2], 1.0)


def make_material(me):
    for d in list(bpy.data.materials):
        if d.users == 0:
            bpy.data.materials.remove(d)
    mat = bpy.data.materials.new(NAME + "Mat")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    bsdf.inputs['Roughness'].default_value = 0.94
    bsdf.inputs['Metallic'].default_value = 0.0
    attr = nt.nodes.new('ShaderNodeVertexColor')
    attr.layer_name = "Col"
    attr.location = (-320, 200)
    nt.links.new(attr.outputs['Color'], bsdf.inputs['Base Color'])
    me.materials.append(mat)


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
            ("Sun", 3.4, (50, 0, -125), 3.0),
            ("Fill", 0.9, (64, 0, 60), 22.0)]:
        ld = bpy.data.lights.new(name, 'SUN')
        ld.energy = energy
        ld.angle = math.radians(angle)
        ob = bpy.data.objects.new(name, ld)
        ob.rotation_euler = tuple(math.radians(v) for v in rot)
        scene.collection.objects.link(ob)

    # 草地地面，交代落地点
    me = bpy.data.meshes.new("GroundMesh")
    s = 12.0
    me.from_pydata([(-s, -s, 0), (s, -s, 0), (s, s, 0), (-s, s, 0)], [], [(0, 1, 2, 3)])
    me.update()
    ground = bpy.data.objects.new("GroundPreview", me)
    gm = bpy.data.materials.new("GroundPreviewMat")
    gm.use_nodes = True
    bsdf = next(n for n in gm.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    bsdf.inputs['Base Color'].default_value = (0.17, 0.26, 0.10, 1.0)
    bsdf.inputs['Roughness'].default_value = 0.95
    me.materials.append(gm)
    scene.collection.objects.link(ground)

    cam_data = bpy.data.cameras.new("PreviewCam")
    cam_data.lens = 55.0
    cam = bpy.data.objects.new("PreviewCam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    return cam


def render_shot(cam, path, az_deg, el_deg, dist, target, res=(620, 560)):
    scene = bpy.context.scene
    scene.render.resolution_x, scene.render.resolution_y = res
    az, el = math.radians(az_deg), math.radians(el_deg)
    tgt = Vector(target)
    cam.location = tgt + Vector((math.cos(az) * math.cos(el),
                                 math.sin(az) * math.cos(el),
                                 math.sin(el))) * dist
    cam.rotation_euler = (tgt - cam.location).to_track_quat('-Z', 'Y').to_euler()
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


def stitch(paths, out_path, cols):
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


def main():
    global SEED
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    do_render = "--nopreview" not in argv
    if "--seed" in argv:
        SEED = int(argv[argv.index("--seed") + 1])

    random.seed(SEED)
    clear_scene()
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1.0

    ob, facet_count = build_rock()
    me = ob.data
    activate(ob)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)

    colourise(me)
    make_material(me)

    glb = os.path.join(OUT_DIR, NAME + ".glb")
    bpy.ops.export_scene.gltf(filepath=glb, export_format='GLB', use_selection=True,
                              export_apply=True, export_yup=True,
                              export_texcoords=False, export_normals=True,
                              export_vertex_color='MATERIAL')

    if do_render:
        cam = setup_preview()
        shots = []
        for i, (az, el, d) in enumerate([(225, 16, 5.0), (315, 12, 5.0),
                                         (45, 20, 5.0), (135, 9, 5.0)]):
            p = "/tmp/rock_shot_%d.png" % i
            render_shot(cam, p, az, el, d, (0.0, 0.0, 0.62))
            shots.append(p)
        stitch(shots, os.path.join(OUT_DIR, NAME + "_preview.png"), 4)

    blend = os.path.join(OUT_DIR, NAME + ".blend")
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=blend)

    # 自检：尺寸 / 落地 / 棱面与三角面质量
    zs = [v.co.z for v in me.vertices]
    xs = [v.co.x for v in me.vertices]
    ys = [v.co.y for v in me.vertices]
    bm = bmesh.new()
    bm.from_mesh(me)
    groups = plane_groups(me)
    fin = bm.copy()
    bmesh.ops.dissolve_limit(fin, angle_limit=math.radians(0.05),
                             verts=fin.verts[:], edges=fin.edges[:])
    iso, farea, fedge = facet_quality(fin)
    ang, tarea = tri_quality(fin)
    barea = bottom_area(fin)
    fin.free()
    bm.free()
    print("=" * 62)
    print("%s  facets=%d  tris=%d  verts=%d" % (NAME, len(groups), len(me.polygons), len(me.vertices)))
    print("BBOX  X %.2f  Y %.2f  Z %.2f..%.2f m   (min z 应≈0)"
          % (max(xs) - min(xs), max(ys) - min(ys), min(zs), max(zs)))
    print("FACET  min iso %.2f  min area %.3f m²  min edge %.3f m  bottom %.2f m²"
          % (iso, farea, fedge, barea))
    print("TRI    min angle %.1f°  min area %.4f m²" % (ang, tarea))
    assert abs(min(zs)) < 0.02, "石头底面必须落在 z=0"
    assert abs((max(xs) - min(xs)) - LONG_M) < 0.02, "长边漂了"
    assert abs((max(ys) - min(ys)) - WIDE_M) < 0.02, "短边漂了"
    assert abs((max(zs) - min(zs)) - HIGH_M) < 0.02, "高度漂了"
    assert iso >= MIN_FACET_ISO - 1e-6, "有又长又窄的棱面"
    assert farea >= MIN_FACET_AREA_M2 - 1e-6, "有碎小棱面"
    assert fedge >= MIN_FACET_EDGE_M - 1e-6, "有窄棱边"
    assert ang >= MIN_TRI_ANGLE - 1e-6, "有退化三角面"
    assert tarea >= MIN_TRI_AREA_M2 - 1e-6, "有零面积三角面"
    assert barea >= BOTTOM_MIN_M2 - 1e-6, "落地面积太小"
    print("saved:", glb)
    print("saved:", blend)


if __name__ == "__main__":
    main()

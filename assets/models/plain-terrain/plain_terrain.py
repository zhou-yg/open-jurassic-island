"""Low-poly plain / grassland terrain block — one of the basic island terrain patches.

程序化生成一块约 10 × 10 m 的平原地形块：
  * **有机轮廓，没有矩形平边**：只保留起伏主体，周围那圈平地整块切掉，
    边界是一条按谐波生成的闭合曲线（不是方框），轮廓处高度渐入到 z = 0；
  * 内部带轻微起伏（不是平面），格点 0.5 m，flat shading，保持 low-poly 面感；
  * 草丛绿 -> 浅黄绿 -> 草绿 -> 深绿 的多层绿色分层材质槽（按高度 + 噪声过渡）。

Usage:
    /Applications/Blender.app/Contents/MacOS/Blender --background \
        --python assets/models/plain-terrain/plain_terrain.py

Outputs (脚本是唯一事实来源, .blend/.glb/png 都是产物):
    plain_terrain.blend
    plain_terrain.glb
    plain_terrain_preview.png      3/4 视图
    plain_terrain_top.png          顶视图（看有机轮廓与分层绿色）
    plain_terrain_scatter.png      散落摆放验证（3 份不同旋转/位置）

尺寸约定见 assets/AGENTS.md：公制、1 unit = 1 m、+Z 向上、原点在铺装中心 (0,0,0)、
scale 必须为 1、导出 export_yup=True。
"""

import math
import os

import bmesh
import bpy
import numpy as np
from mathutils import Vector

# ==========================================================================
# CONFIG —— 所有尺寸单位都是米
# ==========================================================================
OUT_DIR = os.path.dirname(os.path.abspath(__file__))
NAME = "plain_terrain"

SIZE_M = 10.0        # 地块包络尺寸（X / Y）；实际轮廓是有机的，见 OUTLINE_*
CELL_M = 0.5         # 格点间距，10 × 10 m -> 21 × 21 顶点
BASE_T = 0.14        # 地块基准面高度，轮廓处渐入到 0（小一点才不像坐垫）

# --- 轮廓：有机外形，没有矩形平边 -----------------------------------------
# 半径按几阶谐波起伏，得到一条自然的不规则闭合曲线；再整体缩放到 SIZE_M 包络。
OUTLINE_AMP = 0.16   # 半径起伏幅度（相对半径）
OUTLINE_SEGS = 160   # 轮廓采样数
OUTLINE_SEED = 20260419
TAPER_M = 1.1        # 从轮廓向内多少米内高度渐入到 0（越大边缘越薄）
SNAP_BAND = 0.35     # 覆盖度低于此值的顶点吸附到轮廓曲线上（消掉格点锯齿）

# --- 起伏（米）-------------------------------------------------------------
# 「略带起伏」：整块落差 1 m 上下，是平原不是山丘
NOISE_AMP = 0.58     # 主起伏：低频噪声（铺满整块，不能只有一处小坡）
NOISE_CELL_M = 5.0
SWELL_AMP = 0.34     # 更慢的第二层起伏
HILLS_AMP = 0.34     # 几个宽缓的小土坡
HILLS_R_M = 5.0      # 半径大 -> 坡缓
HILLS_N = 2
HILLS_JITTER = 0.25
DIP_AMP = 0.32       # 一处浅洼
MICRO_AMP = 0.06     # 顶点级微起伏，让同高区域也有细小三角面变化
MICRO_CELL_M = 0.8
SEED = 20260418

# --- 多层绿色：sRGB hex（与 island/jurassic_island.py 的调色板同系）--------
PALETTE_HEX = {
    "grass_dark":  "#3D7534",   # 最深：洼地
    "grass_deep":  "#4F8539",   # 深绿：背光低处
    "grass_mid":   "#679A3E",   # 草绿主体
    "grass_light": "#86B04F",   # 向阳浅黄绿
}
# 分层：从最低到最高逐层叠盖（后面的覆盖前面的）。
# 阈值取高度的分位数——注意是「比较高度数值」，不是「按面排名」：
# 高度相近的面排名是任意的，会切出随机三角斑块与锯齿边。
# 第一层 q=None 表示「兜底」（最低的一档），其余按阈值由低到高递增。
# (名称, 槽位, 分位阈值, 抖动幅度, 抖动尺度 m)
LAYERS = [
    ("grass_dark",  0, None, 0.0,   2.6),   # 兜底：最低洼
    ("grass_deep",  1, 0.15, 0.030, 2.4),   # 15% 以上 -> 深绿（低处背光）
    ("grass_mid",   2, 0.40, 0.030, 2.2),   # 40% 以上 -> 草绿主体（占大头）
    ("grass_light", 3, 0.84, 0.025, 2.0),   # 84% 以上 -> 坡顶浅绿
]

# --- 预览渲染 --------------------------------------------------------------
PREVIEW_RES = (960, 720)
TOP_RES = (768, 768)


# ==========================================================================
# 工具函数
# ==========================================================================
def srgb_to_linear(c):
    """sRGB 通道 -> Blender 线性空间（AGENTS.md §6.6）。"""
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hex_to_linear_rgba(h):
    h = h.lstrip("#")
    rgb = tuple(srgb_to_linear(int(h[i:i + 2], 16) / 255.0) for i in (0, 2, 4))
    return (rgb[0], rgb[1], rgb[2], 1.0)


def value_noise_2d(xs, ys, cell, seed):
    """固定种子的 value noise：格点随机值 + smoothstep 双线性插值。

    完全确定性（random.seed + np.random.default_rng），保证可复现。
    返回 0..1，和输入同形状。
    """
    rng = np.random.default_rng(seed)
    g = rng.random((64, 64))
    fx, fy = xs / cell, ys / cell
    ix, iy = np.floor(fx).astype(int), np.floor(fy).astype(int)
    tx, ty = fx - ix, fy - iy
    sx = tx * tx * (3.0 - 2.0 * tx)
    sy = ty * ty * (3.0 - 2.0 * ty)
    ix %= 64
    iy %= 64
    x1 = (ix + 1) % 64
    y1 = (iy + 1) % 64
    v00 = g[iy, ix]
    v10 = g[iy, x1]
    v01 = g[y1, ix]
    v11 = g[y1, x1]
    top = v00 + (v10 - v00) * sx
    bot = v01 + (v11 - v01) * sx
    return top + (bot - top) * sy


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


# ==========================================================================
# 1) 高度场
# ==========================================================================
# ==========================================================================
# 1) 轮廓：有机闭合曲线（没有矩形平边）
# ==========================================================================
def outline_table():
    """返回 (theta, radius)：plan 空间里那条有机轮廓的极坐标采样表。

    半径由几阶谐波叠加而成（固定种子 -> 可复现），得到一条自然的不规则
    闭合曲线；再整体缩放到 SIZE_M 包络，保证包络不超过 10 m。
    轮廓是星形（每个 θ 只对应一个半径），所以后面可以直接用它算覆盖度。
    """
    th = np.linspace(0.0, 2.0 * math.pi, OUTLINE_SEGS, endpoint=False)
    rng = np.random.default_rng(OUTLINE_SEED)
    r = np.ones_like(th)
    # 只取低阶谐波：轮廓大起大落但保持圆润，不会有碎刺
    for k, weight in ((2, 0.62), (3, 0.46), (5, 0.30), (7, 0.16)):
        amp = OUTLINE_AMP * weight * (1.0 - 0.45 * rng.random())
        phase = rng.random() * 2.0 * math.pi
        r += amp * np.cos(k * th + phase)

    px, py = r * np.cos(th), r * np.sin(th)
    # 缩放到包络：|x| / |y| 的最大值恰好等于半边长
    sx = (SIZE_M * 0.5) / np.abs(px).max()
    sy = (SIZE_M * 0.5) / np.abs(py).max()
    qx, qy = px * sx, py * sy

    th_q = np.arctan2(qy, qx)
    rad_q = np.hypot(qx, qy)

    # 缩放在各轴为正，角序不变；仍按角排序一次，防止浮点造成的乱序
    order = np.argsort(th_q)
    th_q, rad_q = th_q[order], rad_q[order]

    # 首尾各补一个周期，方便 np.interp 做环绕插值
    th_ext = np.concatenate(([th_q[-1] - 2.0 * math.pi], th_q,
                             [th_q[0] + 2.0 * math.pi]))
    rad_ext = np.concatenate(([rad_q[-1]], rad_q, [rad_q[0]]))
    return th_ext, rad_ext


def coverage_field(xs, ys, th_ext, rad_ext):
    """覆盖度 c：0 = 轮廓线上（及更外），1 = 轮廓内 TAPER_M 米以上。

    这就是「切掉外面平地」的依据：轮廓外 c <= 0，面片会被删掉；
    轮廓内先有一段 TAPER_M 的渐入带，高度在这段里平滑降到 0。
    """
    r = np.hypot(xs, ys)
    th = np.arctan2(ys, xs)
    # 环绕到插值表的主区间
    th = np.where(th < th_ext[0], th + 2.0 * math.pi, th)
    r_edge = np.interp(th, th_ext, rad_ext)
    return np.clip((r_edge - r) / TAPER_M, 0.0, 1.0)


# ==========================================================================
# 2) 高度场
# ==========================================================================
def build_height_field(n):
    """返回 (h, c, xs, ys)：n × n 个顶点的高度 + 覆盖度 + 居中平面坐标。

    形态是「一块抬起的平缓草场」：基准面 BASE_T，上面铺满 1 m 量级的
    慢波起伏 + 两处宽缓土坡 + 一处浅洼。四边不再压平成矩形，而是沿着
    有机轮廓在 TAPER_M 距离内渐入到 0 —— 即用户要的「只保留起伏的部分」。
    """
    idx = np.arange(n, dtype=float)
    # 注意：必须乘 CELL_M 换成「米」，并且居中到原点（原点 = 铺装中心）。
    # 直接用格点索引（0..n-1）在 CELL_M=1 时碰巧是对的，换分辨率就整体错位。
    g = idx * CELL_M - SIZE_M * 0.5
    xs, ys = np.meshgrid(g, g)

    th_ext, rad_ext = outline_table()
    c = coverage_field(xs, ys, th_ext, rad_ext)

    relief = np.zeros_like(xs)

    # --- 主起伏：低频噪声铺满整块 ---------------------------------------
    relief += NOISE_AMP * (value_noise_2d(xs, ys, NOISE_CELL_M, SEED + 11) - 0.5) * 2.0
    relief += SWELL_AMP * (value_noise_2d(xs, ys, NOISE_CELL_M * 2.2, SEED + 23) - 0.5) * 2.0

    # --- 宽缓的小土坡（坐标居中，所以按 -5..5 取点）----------------------
    rng = np.random.default_rng(SEED)
    span = SIZE_M * 0.5
    for _ in range(HILLS_N):
        cx = span * (0.22 + 0.56 * rng.random()) - span * 0.5
        cy = span * (0.22 + 0.56 * rng.random()) - span * 0.5
        r = HILLS_R_M * (0.8 + 0.4 * rng.random())
        a = HILLS_AMP * (1.0 - HILLS_JITTER * rng.random())
        d = np.sqrt((xs - cx) ** 2 + (ys - cy) ** 2)
        relief += a * np.exp(-(d / r) ** 2)

    # --- 一处浅洼（负高度），让起伏有上有下 ------------------------------
    bx, by = span * 0.70 - span * 0.5, span * 0.28 - span * 0.5
    relief -= DIP_AMP * np.exp(-(((xs - bx) ** 2 + (ys - by) ** 2) / (3.0 ** 2)))

    # --- 顶点级微起伏 -----------------------------------------------------
    relief += MICRO_AMP * (value_noise_2d(xs, ys, MICRO_CELL_M, SEED + 71) - 0.5)

    # 负起伏不能把基准面吃穿（否则渐入带会掉到 z < 0）
    relief = np.maximum(relief, -BASE_T * 0.55)

    # 轮廓渐入：c = 0 处高度正好 0，c >= 1 处保留完整起伏
    h = (BASE_T + relief) * smoothstep(0.0, 1.0, c)
    h = np.maximum(h, 0.0)
    return h, c, xs, ys


# ==========================================================================
# 2) 材质：多层绿色，按高度 + 噪声分层
# ==========================================================================
def make_materials():
    mats = {}
    for key in [L[0] for L in LAYERS]:
        mat = bpy.data.materials.new("plain_%s" % key)
        mat.use_nodes = True
        bsdf = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
        bsdf.inputs['Base Color'].default_value = hex_to_linear_rgba(PALETTE_HEX[key])
        bsdf.inputs['Roughness'].default_value = 0.93
        bsdf.inputs['Metallic'].default_value = 0.0
        mat.diffuse_color = hex_to_linear_rgba(PALETTE_HEX[key])   # 视口色
        mats[key] = mat
    return mats


def assign_layer_slots(me):
    """按高度给每个面分配材质槽：从低到高逐层叠盖。

    关键点（踩过的坑都记在这）：
    * 阈值用高度的分位数比较高度数值，**不能按面排名**：
      高度相近的面排名是任意的，会切出随机三角斑块和锯齿边；
    * 边界加一点固定种子的噪声抖动，色带边缘才不是刀切的等高线；
    * 轮廓已经是有机曲线且高度渐入到 0，不再需要「边缘压回中位面」那套
      补偿（那是矩形拼接块才要的）。
    """
    for key in [L[0] for L in LAYERS]:
        me.materials.append(bpy.data.materials["plain_%s" % key])

    cent = np.array([[sum(me.vertices[v].co[k] for v in p.vertices) / len(p.vertices)
                      for k in range(3)] for p in me.polygons])
    xs_c, ys_c, zs_c = cent[:, 0], cent[:, 1], cent[:, 2]

    qs = [q for _n, _s, q, _a, _c in LAYERS if q is not None]
    thresholds = np.quantile(zs_c, qs) if qs else np.array([])
    t_span = float(max(thresholds.max() - thresholds.min(), 1e-6)) if len(thresholds) else 1.0

    for i, p in enumerate(me.polygons):
        cx, cy = xs_c[i], ys_c[i]
        slot = LAYERS[0][1]                     # 兜底层
        for j, (name, s, q, amp, cell) in enumerate(LAYERS):
            if q is None:
                continue
            n = value_noise_2d(np.array([cx]), np.array([cy]), cell, SEED + 101)[0] - 0.5
            jitter = n * amp * 2.0 * t_span
            if zs_c[i] >= thresholds[j - 1] + jitter:
                slot = s
        p.material_index = slot


# ==========================================================================
# 3) 建网格
# ==========================================================================
def build_mesh(h, c, xs, ys):
    """按轮廓切掉外面的平地，返回 (mesh, 保留下来的面数)。

    做法：
      1. 轮廓外的顶点、以及贴着轮廓的一圈顶点，全部**径向吸附到轮廓曲线**上，
         高度归零。这样边界就是那条曲线本身，而不是 0.5 m 格点的锯齿台阶。
      2. 四个角都在轮廓外的四边形整个不生成 —— 外面的平地就此切掉。
    剩下的就是「只有起伏主体、没有矩形边框」的一块地形。
    """
    n = h.shape[0]
    th_ext, rad_ext = outline_table()

    r = np.hypot(xs, ys)
    th = np.arctan2(ys, xs)
    th = np.where(th < th_ext[0], th + 2.0 * math.pi, th)
    r_edge = np.interp(th, th_ext, rad_ext)

    outside = c <= 0.0
    near_rim = (c > 0.0) & (c < SNAP_BAND)
    snap = outside | near_rim

    px = np.where(snap, r_edge * np.cos(th), xs)
    py = np.where(snap, r_edge * np.sin(th), ys)
    pz = np.where(snap, 0.0, h)

    verts = [(float(px[j, i]), float(py[j, i]), float(pz[j, i]))
             for j in range(n) for i in range(n)]

    faces = []
    for j in range(n - 1):
        for i in range(n - 1):
            corners = ((j, i), (j, i + 1), (j + 1, i + 1), (j + 1, i))
            if all(outside[jj, ii] for jj, ii in corners):
                continue
            faces.append((j * n + i, j * n + i + 1,
                          (j + 1) * n + i + 1, (j + 1) * n + i))

    me = bpy.data.meshes.new(NAME)
    me.from_pydata(verts, [], faces)
    me.update()
    return me, len(faces)


def cleanup_mesh(ob):
    """删掉裁切/吸附后留下的退化面与孤立顶点。"""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces],
                     context='VERTS')
    degenerate = [f for f in bm.faces if f.calc_area() < 1e-6]
    if degenerate:
        bmesh.ops.delete(bm, geom=degenerate, context='FACES')
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces],
                     context='VERTS')
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()


def triangulate_and_shade(ob):
    """三角化（low-poly 面感）+ flat shading。"""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()
    for p in ob.data.polygons:
        p.use_smooth = False


# ==========================================================================
# 4) 预览渲染
# ==========================================================================
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
    bg.inputs[0].default_value = (0.62, 0.75, 0.86, 1.0)
    bg.inputs[1].default_value = 0.80

    for name, energy, rot, angle in [
            ("Sun", 3.2, (math.radians(48), 0, math.radians(-120)), 2.6),
            ("Fill", 0.85, (math.radians(62), 0, math.radians(65)), 22.0),
            ("Front", 0.35, (math.radians(80), 0, math.radians(-95)), 30.0)]:
        ld = bpy.data.lights.new(name, 'SUN')
        ld.energy = energy
        ld.angle = math.radians(angle)
        lo = bpy.data.objects.new(name, ld)
        lo.rotation_euler = rot
        scene.collection.objects.link(lo)

    # 海平面参照面（只在预览里，不进 GLB）
    # 注意：必须放到 z = 0 以下一点。压平的边缘也在 z = 0，共面会 z-fighting，
    # 渲染出来只剩中间抬起的那一半。
    me = bpy.data.meshes.new("SeaMesh")
    s = 120.0
    z_sea = -0.05
    me.from_pydata([(-s, -s, z_sea), (s, -s, z_sea), (s, s, z_sea), (-s, s, z_sea)],
                   [], [(0, 1, 2, 3)])
    me.update()
    sea = bpy.data.objects.new("SeaPreview", me)
    mat = bpy.data.materials.new("SeaPreviewMat")
    mat.use_nodes = True
    bsdf = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    bsdf.inputs['Base Color'].default_value = (0.07, 0.22, 0.32, 1.0)
    bsdf.inputs['Roughness'].default_value = 0.30
    me.materials.append(mat)
    scene.collection.objects.link(sea)

    cam_data = bpy.data.cameras.new("PreviewCam")
    cam_data.lens = 45.0
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


# ==========================================================================
# 主流程
# ==========================================================================
def reset_scene():
    # MCP 沙箱里 read_factory_settings 会被拦截，用 homefile（AGENTS.md §5）
    try:
        bpy.ops.wm.read_homefile(use_empty=True, use_factory_startup=True)
    except Exception:
        bpy.ops.wm.read_homefile(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1.0


def main():
    reset_scene()
    n = int(round(SIZE_M / CELL_M)) + 1
    h, c, xs, ys = build_height_field(n)

    me, kept = build_mesh(h, c, xs, ys)
    ob = bpy.data.objects.new(NAME, me)
    bpy.context.scene.collection.objects.link(ob)
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)

    # 网格已经建在居中的平面坐标上（原点 = 铺装中心）。裁切/吸附之后会有
    # 退化面与孤立顶点，先清掉。
    cleanup_mesh(ob)
    triangulate_and_shade(ob)

    make_materials()
    assign_layer_slots(me)

    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    ob.data.transform(ob.matrix_world)
    ob.matrix_world.identity()

    # ---- 自检 ----
    zs = [v.co.z for v in me.vertices]
    xr = (min(v.co.x for v in me.vertices), max(v.co.x for v in me.vertices))
    yr = (min(v.co.y for v in me.vertices), max(v.co.y for v in me.vertices))
    counts = {}
    for p in me.polygons:
        counts[me.materials[p.material_index].name] = \
            counts.get(me.materials[p.material_index].name, 0) + 1
    print("[plain_terrain] verts=%d tris=%d (kept quads=%d)" %
          (len(me.vertices), len(me.polygons), kept))
    print("[plain_terrain] span X=%.3f Y=%.3f  relief=%.3f m (z %.3f .. %.3f)"
          % (xr[1] - xr[0], yr[1] - yr[0], max(zs) - min(zs), min(zs), max(zs)))
    print("[plain_terrain] material slots: %s" % counts)
    print("[plain_terrain] scale=%s rot=%s loc=%s"
          % (tuple(round(v, 6) for v in ob.scale),
             tuple(round(v, 6) for v in ob.rotation_euler),
             tuple(round(v, 6) for v in ob.location)))

    # 轮廓处高度渐入到 0，所以最低点应该贴着地面
    assert -0.01 <= min(zs) <= 0.05, "轮廓处应该渐入到 z≈0，实测 %.4f" % min(zs)
    assert 8.0 <= (xr[1] - xr[0]) <= SIZE_M + 0.02, "X 包络漂了"
    assert 8.0 <= (yr[1] - yr[0]) <= SIZE_M + 0.02, "Y 包络漂了"
    # 矩形平边已被切掉：包络内不该再被填满（否则就是没裁干净）。
    # 参考：内切圆的方形填充率是 0.785，所以 0.8~0.88 是正常范围。
    fill = kept * (CELL_M ** 2) / (SIZE_M * SIZE_M)
    print("[plain_terrain] plan fill ratio = %.2f (矩形应是 1.00)" % fill)
    assert fill < 0.92, "轮廓外的平地没切干净，填充率 %.2f" % fill
    assert abs(max(zs)) < 4.0, "起伏过大，平原不该有 4 m 以上的落差"
    for k in [L[0] for L in LAYERS]:
        assert "plain_%s" % k in counts, "分层 %s 没有用到" % k

    # ---- 导出 ----
    blend = os.path.join(OUT_DIR, NAME + ".blend")
    glb = os.path.join(OUT_DIR, NAME + ".glb")
    cam, sea = setup_preview()
    bpy.ops.wm.save_as_mainfile(filepath=blend)

    sea.hide_render = False
    d = 11.5
    render_shot(cam, os.path.join(OUT_DIR, NAME + "_preview.png"),
                (d * 0.95, -d, d * 0.58), (0.0, 0.0, 0.35), PREVIEW_RES)
    render_shot(cam, os.path.join(OUT_DIR, NAME + "_top.png"),
                (0.0, -0.001, 15.5), (0.0, 0.0, 0.0), TOP_RES)

    # 散落摆放验证：复制 3 份、各自旋转和错位，检查轮廓拼在一起是否自然。
    # （已经是有机轮廓，不再做 2 × 2 无缝拼接验证。）
    copies = []
    for k, (dx, dy, rot) in enumerate(((-7.2, -2.4, 0.7),
                                       (6.8, -3.6, 2.1),
                                       (-1.0, 7.0, 4.0))):
        cp = ob.copy()
        cp.data = ob.data.copy()
        cp.location = (dx, dy, 0.0)
        cp.rotation_euler = (0.0, 0.0, rot)
        bpy.context.scene.collection.objects.link(cp)
        copies.append(cp)
    render_shot(cam, os.path.join(OUT_DIR, NAME + "_scatter.png"),
                (22.0, -30.0, 17.0), (0.0, 0.0, 0.0), (960, 720))
    for cp in copies:
        bpy.data.objects.remove(cp, do_unlink=True)

    sea.hide_render = True
    # 导出前把预览用的相机 / 灯光 / 海面从场景里删掉：
    # hide_render 不影响 glTF 导出，只有真正不在场景里才不会被写进 .glb。
    for o in list(bpy.context.scene.collection.objects):
        if o.type != 'MESH' or o.name.startswith("Sea"):
            bpy.data.objects.remove(o, do_unlink=True)
    bpy.ops.export_scene.gltf(
        filepath=glb, export_format='GLB',
        export_apply=True, export_yup=True,
        use_selection=False, use_visible=False,
    )
    print("[plain_terrain] wrote %s / %s" % (blend, glb))


if __name__ == "__main__":
    main()
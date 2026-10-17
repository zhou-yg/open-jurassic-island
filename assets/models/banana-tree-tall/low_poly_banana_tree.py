# Blender 建模脚本：Low-Poly 香蕉树（高 / 矮两种款式）
#
# 用法:
#   blender --background --python low_poly_banana_tree.py                 # 两款都生成
#   blender --background --python low_poly_banana_tree.py -- tall         # 只生成高款
#   blender --background --python low_poly_banana_tree.py -- short        # 只生成矮款
#   blender --background --python low_poly_banana_tree.py -- tall --nopreview
#
# 产物（写入 <款式目录>）: low_poly_banana_tree.blend / .glb / _preview.png
#
# ---------------------------------------------------------------------------
# 造型说明
# ---------------------------------------------------------------------------
# 香蕉树不是"树干 + 树冠"，而是"假茎 + 一丛巨大的叶"。这版把三处重做：
#
# 1) 叶片（frond）—— 参考椰子树那种"大片、带褶皱、多层次绿"：
#    * 叶柄(petiole)从假茎顶端一个点放射长出，前 30% 只有叶柄没有叶肉，
#      这一段叶片卷成 U 形槽（叶鞘）—— 这正是"大片 + 褶皱"的来源。
#    * 叶身沿长度采样 21 段，每段再切 13 个横向站点，主脉隆起、叶缘下垂，
#      叶面上四道折痕交替起伏 → 折扇一样的褶皱，是真正的立体曲面。
#    * 叶片沿长轴逐渐扭转（roll），出鞘时近乎竖立、到叶尖摊平朝上，
#      所以从任何角度看都能看到大片叶面，而不是一条线。
#    * 末端 ~9% 用"中脉 + 两侧撕开的缺口"做出香蕉叶标志性的破叶裂口。
#    * 叶色不是单一绿：叶背暗绿、叶面中绿、内侧受光更亮、叶缘偏黄、主脉黄绿、
#      叶柄偏黄、老叶尖发黄 —— 全部烘进顶点色，一次 draw call 拿到多层次绿。
#
# 2) 假茎（pseudostem）—— 多层次 + 递进颜色 + 纹理：
#    * 8 条叶鞘沿高度 + 周向螺旋卷绕（1.15 圈），每条自身有 4×4 的截面环，
#      相邻叶鞘互相搭接 → 表面有台阶、竖向沟槽和叶鞘边缘的翻边。
#    * 顶点色按高度递进：根部闷黄绿 → 中部黄绿 → 顶端偏青；每片叶鞘自身
#      也从基部暗到上缘亮，翻边再提亮一档。
#    * 竖向沟槽、叶鞘边界、顶端截断截面各叠一层明暗，纹理不花面数。
#
# 3) 根部基座（base）—— 不再简陋：
#    * 12 道放射状气生根肋（根隆），绕茎基一圈、向外伸再插进地面。
#    * 3 片干枯下垂的旧叶鞘包住茎基，遮掉"光杆插在地上"的感觉。
#    * 每棵 3 株根出小苗(sucker)，各有小假茎 + 3 片小叶（含卷筒嫩叶）。
#
# ---------------------------------------------------------------------------
# Godot 侧约定（改动会破坏 components/vegetation/banana_tree/banana_tree.gd）
# ---------------------------------------------------------------------------
# * 两个网格节点必须叫 "Stalk" 与 "Leaves"（组件按名字含 "stalk" 找假茎半径）。
# * 原点在根部 y=0，模型沿 +Y 生长；高款约 4.77 m，矮款约 2.66 m
#   （组件的 tree_height / 自检 [7] 依赖这两个数值）。
# * 假茎半径剖面保持原值：高款底部 0.35 顶部 0.24，矮款底部 0.365 顶部 0.26；
#   因为 banana_tree.gd 的 bunch_outset=0.62 与自检 [11]"香蕉不插进假茎"依赖它。
# * 颜色走顶点色 COLOR_0（材质里挂 Color Attribute 节点），导出后 Godot 的
#   StandardMaterial3D 会直接用顶点色，不需要额外配置。
import bpy
import math
import os
import random
import sys
from mathutils import Vector, Matrix

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def srgb_to_linear(c):
    """sRGB -> 线性。顶点色 / glTF COLOR_0 都是线性空间，
    直接把按肉眼(sRGB)挑的颜色写进去会整体发白、发灰。"""
    out = []
    for v in c:
        out.append(v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4)
    return tuple(out)


# ==================== 调色板 ====================
# 全部烘成顶点色；下面的命名只表达"用在哪儿"，实际颜色由 grad() 插值出来。
PAL = {
    # 假茎：从根部闷黄绿到顶端偏青，逐级提亮
    "stalk_root":  (0.215, 0.270, 0.088),
    "stalk_low":   (0.300, 0.360, 0.112),
    "stalk_mid":   (0.430, 0.480, 0.140),
    "stalk_high":  (0.520, 0.560, 0.176),
    "stalk_tip":   (0.450, 0.545, 0.156),
    "stalk_cut":   (0.230, 0.270, 0.082),   # 假茎顶端截断截面
    "sheath_dead": (0.470, 0.395, 0.170),   # 根部干枯旧叶鞘
    # 叶：多层次绿
    "leaf_deep":   (0.075, 0.240, 0.090),   # 叶背 / 阴影面
    "leaf_dark":   (0.135, 0.350, 0.125),
    "leaf_mid":    (0.205, 0.450, 0.142),
    "leaf_light":  (0.300, 0.555, 0.158),
    "leaf_bright": (0.420, 0.675, 0.195),   # 内侧受光面
    "leaf_edge":   (0.510, 0.710, 0.210),   # 叶缘
    "leaf_amber":  (0.620, 0.665, 0.225),   # 老叶尖端的黄
    "midrib":      (0.560, 0.620, 0.190),   # 主脉
    "petiole":     (0.495, 0.535, 0.170),   # 叶柄
    "sucker":      (0.330, 0.420, 0.130),
}

# 上面这些颜色是按"眼睛看到的"（sRGB）挑的，这里统一转成线性再参与计算，
# 否则写进顶点色后整体会偏白偏灰 —— 之前那种"奶茶色"就是这么来的。
PAL = {k: srgb_to_linear(v) for k, v in PAL.items()}

# ==================== 款式参数 ====================
# 两种款式共用同一套生成函数，只改参数，造型语言保持一致。
STYLES = {
    # 高款：细高，叶片大而多，像野生蕉
    "tall": {
        "seed": 7,
        "target_height": 4.77,       # 最终整树高度（Godot banana_tree.gd 用）
        "stalk_height": 3.63,
        "stalk_r_bottom": 0.350,
        "stalk_r_top": 0.240,
        "sheaths": 7,                # 假茎叶鞘条数（重叠搭接）
        "sheath_overlap": 0.55,      # 相邻叶鞘的周向重叠比例（0.5 = 刚好搭一半）
        "leaf_scars": 11,            # 假茎表面的老叶痕圈数
        "root_flare": 12,            # 根部环形根隆数量
        "suckers": [(72.0, 0.60, 1.00), (206.0, 0.74, 0.82), (322.0, 0.54, 0.66)],
        "leaf_count": 11,
        "leaf_len": 2.02,
        "leaf_width": 0.70,
        "leaf_tiers": 4,
        "leaf_pitch": (54.0, -4.0),  # 内层 / 外层的叶柄仰角
        "leaf_arch": (10.0, 58.0),   # 内层 / 外层的整叶下垂角
        "petiole_frac": 0.30,
        "leaf_roll0": 52.0,          # 叶根扭转角（0 = 叶面朝上）
        "leaf_roll1": 4.0,           # 叶尖扭转角
        "lean_x": 0.34,              # 假茎顶端相对根部在 X 方向的偏移（米）
        "lean_y": -0.16,             # 假茎顶端相对根部在 Y 方向的偏移（米）
        "twist_deg": 115.0,          # 叶鞘沿高度一共扭转多少度
        "crown_drop": 0.30,          # 树冠沿假茎往下延伸的比例（越大树冠越"包"住茎顶）
        "fringe": 56,                # 茎顶毛茸茸的须状纤维片数
        "crown_blades": 9,           # 茎顶直立的短叶数（肉穗/新叶苞）
    },
    # 矮款：粗矮，叶片短而宽，像庭院矮蕉
    "short": {
        "seed": 23,
        "target_height": 2.66,
        "stalk_height": 2.16,
        "stalk_r_bottom": 0.365,
        "stalk_r_top": 0.260,
        "sheaths": 6,
        "sheath_overlap": 0.55,
        "leaf_scars": 9,
        "root_flare": 12,
        "suckers": [(60.0, 0.56, 0.95), (198.0, 0.70, 0.78), (300.0, 0.52, 0.62)],
        "leaf_count": 10,
        "leaf_len": 1.52,
        "leaf_width": 0.66,
        "leaf_tiers": 4,
        "leaf_pitch": (50.0, -6.0),
        "leaf_arch": (12.0, 60.0),
        "petiole_frac": 0.31,
        "leaf_roll0": 50.0,
        "leaf_roll1": 3.0,
        "lean_x": 0.22,
        "lean_y": -0.11,
        "twist_deg": 100.0,
        "crown_drop": 0.34,
        "fringe": 48,
        "crown_blades": 8,
    },
}

# 叶片横向站点 [0..1]：0 = 一侧叶缘，0.5 = 主脉，1 = 另一侧叶缘。
# 折痕落在 0.22/0.38/0.62/0.78，左右交替起伏 → 折扇一样的褶皱。
LEAF_SITES = (0.0, 0.09, 0.22, 0.30, 0.38, 0.44, 0.50,
              0.56, 0.62, 0.70, 0.78, 0.91, 1.0)
LEAF_CENTER = 6                      # LEAF_SITES 里 0.5 的下标
LEAF_RIDGES = (2, 4, 8, 10)          # 上下起伏的折痕下标
# 每段的"叶缘下垂量"乘子：叶柄段是 U 形槽，叶身展开，叶尖略收
SECTION_SCOOP = (1.65, 1.35, 1.05, 0.86, 0.74, 0.68, 0.64, 0.63, 0.63, 0.65,
                 0.68, 0.72, 0.77, 0.83, 0.90, 0.97, 1.04, 1.11, 1.18, 1.25, 1.32)
FROND_SEG = 20                       # 叶片沿长度分几段（站点数 = FROND_SEG + 1）


# ==================== 通用工具 ====================
def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.unit_settings.system = 'METRIC'


def lerp(a, b, t):
    t = max(0.0, min(1.0, t))
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


def mul(c, k):
    return (max(0.0, c[0] * k), max(0.0, c[1] * k), max(0.0, c[2] * k))


def grad(stops, t):
    """多段渐变色带。stops = [(位置, 颜色), ...]，位置递增。"""
    t = max(0.0, min(1.0, t))
    if t <= stops[0][0]:
        return stops[0][1]
    for i in range(len(stops) - 1):
        t0, c0 = stops[i]
        t1, c1 = stops[i + 1]
        if t <= t1:
            u = 0.0 if t1 - t0 < 1e-9 else (t - t0) / (t1 - t0)
            u = u * u * (3.0 - 2.0 * u)      # 平滑，避免生硬色阶
            return lerp(c0, c1, u)
    return stops[-1][1]


def make_vc_material(name, fallback, roughness=0.92):
    """材质：Base Color 接 Color Attribute 节点，颜色完全由顶点色驱动。
    同时给 BSDF 一个近似底色，这样即使节点没连上也不至于渲成黑块。"""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    bsdf.inputs["Base Color"].default_value = (*fallback, 1.0)
    bsdf.inputs["Roughness"].default_value = roughness
    vc = nt.nodes.new('ShaderNodeVertexColor')
    vc.layer_name = "Col"
    vc.location = (-320, 220)
    nt.links.new(vc.outputs['Color'], bsdf.inputs['Base Color'])
    mat.diffuse_color = (*fallback, 1.0)
    return mat


def build_object(name, verts, faces, cols, mat, per_face=False):
    """从顶点/面/颜色建网格对象，并写入 CORNER 颜色属性 "Col"。

    [param cols] 默认是逐顶点颜色（长度 = 顶点数）；[param per_face] 为真时
    它是逐面颜色（长度 = 面数），面的四个角用同一个颜色 → 干脆的 low-poly 面块。
    """
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.validate(verbose=False)
    mesh.update()
    n_verts = len(mesh.vertices)
    ob = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(ob)
    ob.data.materials.append(mat)
    ca = mesh.color_attributes.new(name="Col", type='BYTE_COLOR', domain='CORNER')
    if per_face:
        for poly in mesh.polygons:
            c = cols[min(poly.index, len(cols) - 1)]
            for li in poly.loop_indices:
                ca.data[li].color = (c[0], c[1], c[2], 1.0)
    else:
        assert len(cols) >= n_verts, "%s: 顶点色数量 %d < 顶点数 %d" % (name, len(cols), n_verts)
        for poly in mesh.polygons:
            for li in poly.loop_indices:
                c = cols[mesh.loops[li].vertex_index]
                ca.data[li].color = (c[0], c[1], c[2], 1.0)
    return ob


def centroid(vs, face):
    n = float(len(face))
    return (sum(vs[i][0] for i in face) / n,
            sum(vs[i][1] for i in face) / n,
            sum(vs[i][2] for i in face) / n)


def face_centers(verts, faces):
    return [centroid(verts, f) for f in faces]


def axis_gain(centers, axis, lo, hi):
    """把某个轴上的位置映射成 0..1，用于沿该轴做渐变。"""
    span = max(1e-6, hi - lo)
    return [max(0.0, min(1.0, (c[axis] - lo) / span)) for c in centers]


def vertex_colors_of(ob):
    """取出一个网格对象逐顶点的颜色（从 loop 颜色折叠到顶点上）。"""
    src = ob.data.color_attributes["Col"]
    out = [None] * len(ob.data.vertices)
    for poly in ob.data.polygons:
        for li in poly.loop_indices:
            vi = ob.data.loops[li].vertex_index
            if out[vi] is None:
                out[vi] = tuple(src.data[li].color)[:3]
    return [(c if c is not None else PAL["leaf_mid"]) for c in out]


def append_geom(v_all, f_all, c_all, verts, faces, cols):
    base = len(v_all)
    v_all.extend(verts)
    f_all.extend([tuple(i + base for i in f) for f in faces])
    c_all.extend(cols)


def place(ob, matrix, offset):
    """把 ob 的几何按矩阵旋转 + 平移，返回 (verts, faces, cols)，随后可删除 ob。"""
    verts = [tuple(matrix @ Vector(v.co)) for v in ob.data.vertices]
    verts = [(v[0] + offset[0], v[1] + offset[1], v[2] + offset[2]) for v in verts]
    return verts, [tuple(p.vertices) for p in ob.data.polygons], vertex_colors_of(ob)


def basis_from_z(z_dir, reference=(0.0, 0.0, 1.0)):
    z = Vector(z_dir).normalized()
    ref = Vector(reference)
    x = ref.cross(z)
    if x.length < 1e-5:
        ref = Vector((1.0, 0.0, 0.0))
        if abs(ref.dot(z)) > 0.99:
            ref = Vector((0.0, 1.0, 0.0))
        x = ref.cross(z)
    x.normalize()
    return x, z.cross(x), z


def join_meshes(objs, name):
    objs = [o for o in objs if o is not None]
    objs = [o for o in objs if len(o.data.vertices) > 0]
    if not objs:
        return None
    bpy.ops.object.select_all(action='DESELECT')
    for ob in objs:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    if len(objs) > 1:
        bpy.ops.object.join()
    merged = bpy.context.view_layer.objects.active
    merged.name = name
    merged.data.name = name
    return merged


# ==================== 假茎：重叠叶鞘 + 老叶痕 ====================
def sheath_radius(cfg, t):
    """t = 0 根部 .. 1 顶端。假茎半径（延续原模型：高款 0.35→0.24，矮款 0.365→0.26）。"""
    r0 = cfg["stalk_r_bottom"]
    r1 = cfg["stalk_r_top"]
    return r0 + (r1 - r0) * (t ** 0.78)


def stalk_axis(cfg, t):
    """假茎中轴：从根部竖直起步、越往上越倾斜向外，形成自然的弯。

    返回 (x, y)。t 可以是任意实数（用来取切线 / 延伸到树冠）。
    """
    s = t ** 1.7
    return (cfg["lean_x"] * s, cfg["lean_y"] * s)


def stalk_frame(cfg, t):
    """在高度比例 t 处的中轴局部坐标系：(原点, 沿轴单位向量, 侧向单位向量)。

    截面始终垂直于中轴，所以树干是"弯"而不是"斜"。
    """
    e = 1e-3
    x0, y0 = stalk_axis(cfg, t)
    x1, y1 = stalk_axis(cfg, t + e)
    tangent = Vector((x1 - x0, y1 - y0, e * cfg["stalk_height"])).normalized()
    # 侧向取水平面内与切线垂直的方向
    side = Vector((tangent.y, -tangent.x, 0.0))
    if side.length < 1e-6:
        side = Vector((1.0, 0.0, 0.0))
    side.normalize()
    return Vector((x0, y0, t * cfg["stalk_height"])), tangent, side


def stalk_twist(cfg, t):
    """叶鞘沿高度的扭转角（弧度）。树干不仅弯，还带一点拧。"""
    return math.radians(cfg["twist_deg"]) * (t ** 1.25)


def stalk_point(cfg, t, ang, r):
    """在高度比例 t、圆周角 ang、半径 r 处的中轴坐标 (x, y, z)。"""
    origin, _, side = stalk_frame(cfg, t)
    a = ang + stalk_twist(cfg, t)
    return origin + side * (math.cos(a) * r) + Vector((0.0, 0.0, 1.0)).cross(side) * (math.sin(a) * r)


def stalk_radius_along(cfg, z):
    """给定世界 Z，反解出对应的 t 与半径（用于 Godot 侧挂果串/采样）。"""
    h = cfg["stalk_height"]
    t = max(0.0, min(1.2, z / max(1e-6, h)))
    return t, sheath_radius(cfg, t)


STALK_STOPS = (
    (0.00, PAL["stalk_root"]),
    (0.09, PAL["stalk_low"]),
    (0.36, PAL["stalk_mid"]),
    (0.72, PAL["stalk_high"]),
    (1.00, PAL["stalk_tip"]),
)


def stalk_color_at(cfg, p, t):
    """假茎表面某点的颜色：沿高度递进 + 竖向沟槽 + 叶痕，全部烘进顶点色。"""
    col = grad(STALK_STOPS, max(0.0, min(1.0, t)))
    # 老叶痕：一圈圈横向的暗带 + 下缘暗线 + 上缘高光，模拟叶鞘脱落后留下的环
    n = cfg["leaf_scars"]
    ph = (t * n) % 1.0
    band = abs(ph - 0.5) * 2.0                    # 每圈中间 0 → 1
    col = mul(col, 0.74 + 0.30 * band)
    if ph < 0.12:                                 # 叶痕下缘的暗线
        col = mul(col, 0.60 + 3.0 * ph)
    elif ph > 0.94:                               # 叶痕上缘的小高光
        col = mul(col, 1.10)
    return col


def build_stalk(cfg, mat):
    """假茎：沿一条"向上逐渐倾斜 + 扭转"的中轴扫出的一圈圈叶鞘。

    用横截面扫掠（而不是竖直圆柱）来建，所以树干是真的带弧度的弯，
    同时叶鞘随高度扭转，表面有搭接台阶、竖向沟槽和老叶痕。
    """
    h = cfg["stalk_height"]
    n_sheath = cfg["sheaths"]
    seg = 14                                    # 沿高度分几段（弯 + 扭要够密才顺）
    n_circle = 18                               # 每段圆周站点数
    verts, faces = [], []

    # ---- 基础外轮廓：截面垂直于中轴，半径带轻微起伏 ----
    ring_base = len(verts)
    for k in range(seg + 1):
        t = k / float(seg)
        r = sheath_radius(cfg, t) * (1.0 + 0.035 * math.sin(math.pi * t))
        for s in range(n_circle):
            a = s / float(n_circle) * math.tau
            groove = 0.022 * (0.5 - 0.5 * math.cos(a * n_sheath))
            p = stalk_point(cfg, t, a, r - groove)
            verts.append((p.x, p.y, p.z))
    for k in range(seg):
        for s in range(n_circle):
            s2 = (s + 1) % n_circle
            faces.append((ring_base + k * n_circle + s, ring_base + k * n_circle + s2,
                          ring_base + (k + 1) * n_circle + s2, ring_base + (k + 1) * n_circle + s))
    faces.append(tuple(range(ring_base, ring_base + n_circle)))
    top = ring_base + seg * n_circle
    faces.append(tuple(range(top + n_circle - 1, top - 1, -1)))

    # ---- 每条叶鞘：一片竖向长条，随高度跟着中轴弯、跟着扭转转 ----
    across = 4
    t_lo, t_hi = 0.045, 1.0
    half = math.pi / n_sheath * (1.0 + cfg["sheath_overlap"])
    n_sheath_seg = 10
    for i in range(n_sheath):
        a_mid = i / float(n_sheath) * math.tau
        t0 = t_lo + 0.055 * (i % 3)              # 各片起点错开一点
        base = len(verts)
        for k in range(n_sheath_seg):
            f = k / float(n_sheath_seg - 1.0)
            t = t0 + (t_hi - t0) * f
            bulge = 1.0 + 0.055 * math.sin(math.pi * min(1.0, f * 1.25))
            flare = 1.06 if k == n_sheath_seg - 1 else 1.0
            r = sheath_radius(cfg, t) * bulge * flare
            for s in range(across + 1):
                a = a_mid - half + 2.0 * half * (s / float(across))
                edge = abs(s / float(across) - 0.5) * 2.0
                p = stalk_point(cfg, t, a, r * (1.0 - 0.075 * edge))
                verts.append((p.x, p.y, p.z))
        for k in range(n_sheath_seg - 1):
            for s in range(across):
                b = base + k * (across + 1) + s
                faces.append((b, b + 1, b + (across + 1) + 1, b + (across + 1)))
        tb = base + (n_sheath_seg - 1) * (across + 1)
        faces.append(tuple(range(tb, tb + across + 1)))
        faces.append(tuple(range(base + across, base - 1, -1)))

    centers = face_centers(verts, faces)
    cols = []
    for c in centers:
        t = max(0.0, min(1.0, c[2] / max(1e-6, h)))
        col = stalk_color_at(cfg, c, t)
        # 半径相对理论值：偏大 = 叶鞘隆起(亮)，偏小 = 沟槽(暗)
        r = math.hypot(c[0] - stalk_axis(cfg, t)[0], c[1] - stalk_axis(cfg, t)[1])
        ratio = r / max(1e-6, sheath_radius(cfg, t))
        col = mul(col, max(0.62, min(1.34, 1.0 + 2.4 * (ratio - 1.0))))
        cols.append(col)
    return build_object("Stalk", verts, faces, cols, mat, per_face=True)


def build_stalk_cap(cfg, mat):
    """假茎顶端的截断截面：深色圆盘 + 一圈稍亮的断口（跟着弯的中轴走）。"""
    h = cfg["stalk_height"]
    r = cfg["stalk_r_top"] * 0.99
    sides = 10
    origin, _, _ = stalk_frame(cfg, 0.995)
    verts = [tuple(origin)]
    for s in range(sides):
        a = s / float(sides) * math.tau
        p = stalk_point(cfg, 0.995, a, r)
        verts.append((p.x, p.y, p.z))
    faces = [(0, 1 + s, 1 + ((s + 1) % sides)) for s in range(sides)]
    cols = [PAL["stalk_cut"]] + [lerp(PAL["stalk_cut"], PAL["stalk_low"], 0.35)] * sides
    return build_object("StalkCap", verts, faces, cols, mat)


# ==================== 根部基座：外扩根盘 + 根隆 + 干枯叶鞘 ====================
def build_root_flare(cfg, mat, n_ring=18, n_prof=5):
    """根盘：贴着地面的外扩喇叭口，周向有 nr 道根隆（ridge），对正假茎的沟槽。

    这是"根部不再简陋"的主体 —— 一个连续的、缓缓落到地面的裙状基座，
    而不是插在地上的光杆。
    """
    h = cfg["stalk_height"]
    rb = cfg["stalk_r_bottom"]
    nr = cfg["root_flare"]
    verts, faces = [], []
    for k in range(n_prof):
        f = k / float(n_prof - 1.0)
        # f=0 顶端（接假茎）.. f=1 地面
        z = h * 0.095 * (1.0 - f) ** 1.55 - 0.030 * f
        flare = rb * (1.0 + 0.40 * (f ** 1.05))
        for s in range(n_ring):
            a = s / float(n_ring) * math.tau
            ridge = 1.0 + 0.105 * (math.cos(a * nr) * 0.5 + 0.5) * f
            # 几道低频谐波让根盘轮廓不是正圆，更像有机的根颈
            wob = 1.0 + 0.055 * math.sin(a * 3.0 + 0.7) + 0.035 * math.sin(a * 5.0 - 1.3)
            r = flare * ridge * (1.0 + (wob - 1.0) * f)
            verts.append((math.cos(a) * r, math.sin(a) * r, z))
    for k in range(n_prof - 1):
        for s in range(n_ring):
            s2 = (s + 1) % n_ring
            faces.append((k * n_ring + s, k * n_ring + s2,
                          (k + 1) * n_ring + s2, (k + 1) * n_ring + s))
    top = (n_prof - 1) * n_ring
    faces.append(tuple(range(top + n_ring - 1, top - 1, -1)))
    faces.append(tuple(range(n_ring)))

    centers = face_centers(verts, faces)
    cols = []
    for c in centers:
        # 从假茎的暗黄绿平滑过渡到贴地处的枯黄（用连续渐变，避免出现硬色带）
        t = max(0.0, min(1.0, (h * 0.095 - c[2]) / max(1e-6, h * 0.13)))
        t = t * t * (3.0 - 2.0 * t)
        col = grad(((0.0, stalk_color_at(cfg, c, 0.07)),
                    (0.55, lerp(PAL["stalk_low"], PAL["sheath_dead"], 0.35)),
                    (1.0, lerp(PAL["sheath_dead"], PAL["stalk_root"], 0.45))), t)
        r = math.hypot(c[0], c[1])
        # 半径越大越暗 → 根隆之间的沟自然出现阴影
        col = mul(col, 1.12 - 0.26 * min(1.0, max(0.0, (r / max(1e-6, rb) - 1.0) / 0.7)))
        cols.append(col)
    return build_object("RootFlare", verts, faces, cols, mat, per_face=True)


def build_root_sheaths(cfg, mat):
    """根部 3 片干枯下垂的旧叶鞘：像真正的老叶一样贴着茎向下披垂。

    每片是一条"上宽下尖"的带子，沿高度逐渐向外、向下弯，末端收成尖并有点卷边，
    而不是一块直挺挺的板子。颜色由贴茎处的暗绿过渡到枯黄。
    """
    h = cfg["stalk_height"]
    rb = cfg["stalk_r_bottom"]
    verts, faces = [], []
    seg = 6                      # 沿垂落方向的段数
    across = 3                   # 横向站点数
    for i in range(3):
        a0 = i * math.tau / 3.0 + 0.8
        span = math.radians(76.0)           # 这片叶鞘包住多少圆周
        z_top = h * (0.150 + 0.030 * i)
        drop = h * (0.170 + 0.015 * i)      # 垂下来更长，像挂在茎上的枯叶
        grid = []
        for k in range(seg + 1):
            f = k / float(seg)              # 0 贴茎 .. 1 叶尖
            # 上宽下窄，末端收成尖；先向外鼓再收回来 → 像披垂下来的样子
            half = span * 0.5 * (1.0 - 0.70 * f ** 1.25)
            out = rb * (1.03 + 0.26 * math.sin(math.pi * (f ** 0.62)) ** 0.95)
            z = z_top - drop * (f ** 1.35)
            row = []
            for j in range(across):
                q = j / float(across - 1.0) * 2.0 - 1.0     # -1..1
                ang = a0 + half * q
                # 横向做一点卷边：两侧比中间略高、略收
                curl = 0.014 * (q * q)
                r = out - curl * 1.6
                row.append((math.cos(ang) * r, math.sin(ang) * r, z + curl))
            grid.append(row)
        base = len(verts)
        for row in grid:
            verts.extend(row)
        for k in range(seg):
            for j in range(across - 1):
                b = base + k * across + j
                faces.append((b, b + 1, b + across + 1, b + across))
        # 这片叶鞘的背面（贴着茎的一侧），让它有厚度而不是纸片
        back0 = len(verts)
        for row in grid:
            for (x, y, z) in row:
                r = math.hypot(x, y)
                rr = r - 0.022
                ang = math.atan2(y, x)
                verts.append((math.cos(ang) * rr, math.sin(ang) * rr, z - 0.012))
        for k in range(seg):
            for j in range(across - 1):
                b = back0 + k * across + j
                faces.append((b, b + across, b + across + 1, b + 1))
        # 两侧与末端的封边
        for k in range(seg):
            o = base + k * across
            faces.append((o, o + across, back0 + k * across + across, back0 + k * across))

    centers = face_centers(verts, faces)
    cols = []
    for c in centers:
        t = max(0.0, min(1.0, (h * 0.150 - c[2]) / max(1e-6, h * 0.26)))
        r = math.hypot(c[0], c[1])
        col = grad(((0.0, PAL["stalk_low"]),
                    (0.35, PAL["sheath_dead"]),
                    (0.72, mul(PAL["sheath_dead"], 0.80)),
                    (1.0, mul(PAL["sheath_dead"], 0.55))), t)
        # 越靠外越暗，做出垂坠的阴影
        col = mul(col, 1.10 - 0.30 * min(1.0, max(0.0, (r / max(1e-6, rb) - 1.0) / 0.7)))
        cols.append(col)
    return build_object("RootSheaths", verts, faces, cols, mat, per_face=True)


# ==================== 叶片 ====================
def build_frond(name, cfg, mat, length, width, arch_deg, gain=1.0):
    """一片香蕉叶的原始几何（局部坐标：叶根在原点，沿 +X 伸出，-Z 下垂）。

    * 中轴线按 [param arch_deg] 做"先微抬、再持续下垂"的拱形 —— 蕉叶典型的
      外翻弧线。
    * 叶柄段卷成 U 形槽；叶身展开成中间凹、两边下垂的 V 形大叶；
      叶面上四道折痕左右交替起伏，形成折扇一样的褶皱。
    * 叶尖沿中脉撕开成齿，做出香蕉叶标志性的破叶。
    * 沿叶长的扭转(roll)烘进顶点坐标：叶根较竖、叶尖摊平朝上。

    [param arch_deg] 是"叶轴累计下垂的总角度"，不是叶根处某个确定仰角，
    所以外层叶(大 arch)自然更外翻、更长。
    """
    seg = FROND_SEG
    n = len(LEAF_SITES)
    pet = cfg["petiole_frac"]
    arch = math.radians(arch_deg)
    r0, r1 = math.radians(cfg["leaf_roll0"]), math.radians(cfg["leaf_roll1"])
    tear_from = 0.93

    # 先沿叶长积分出中轴线：前 1/4 微微抬起，之后持续下垂
    axis = []
    x = z = 0.0
    step = length / seg
    for s_i in range(seg + 1):
        axis.append((x, z))
        if s_i == seg:
            break
        a = arch * (0.13 - 1.17 * (((s_i + 0.5) / seg) ** 1.5))
        x += math.cos(a) * step
        z += math.sin(a) * step
    # 把拱形整体抬起来，让叶根从假茎顶端往上走
    zmin = min(p[1] for p in axis)
    axis = [(p[0], p[1] - zmin) for p in axis]

    verts = []
    for s_i in range(seg + 1):
        t = s_i / seg
        ax, az = axis[s_i]
        u = max(0.0, (t - pet) / (1.0 - pet))
        if t < pet:
            w = width * 0.22
            ridge = width * 0.070
        else:
            w = width * (math.sin(math.pi * (0.055 + 0.915 * min(1.0, u ** 0.92))) ** 0.30)
            ridge = width * 0.095 * math.sin(math.pi * (min(1.0, u * 0.92) ** 0.8))
        scoop = SECTION_SCOOP[min(s_i, len(SECTION_SCOOP) - 1)]
        flut = width * 0.062 * (0.40 + 0.90 * u)
        roll = r0 + (r1 - r0) * (u ** 0.60)
        cr, sr = math.cos(roll), math.sin(roll)
        fold = 1.0 if (s_i % 2) == 0 else -1.0
        for j, q in enumerate(LEAF_SITES):
            off = abs(q - 0.5) * 2.0
            v = (q - 0.5) * w
            section = w * 0.26 * (off ** 2.05) * scoop         # 叶缘下垂成 V 形
            if j in LEAF_RIDGES:
                section += fold * flut                         # 褶皱起伏
            if j == LEAF_CENTER:
                section = -ridge                               # 主脉隆起
            py = v * cr - section * sr
            pz = v * sr + section * cr
            verts.append((ax, py, az + pz))

    faces = []
    for s_i in range(seg):
        for j in range(n - 1):
            a = s_i * n + j
            faces.append((a, a + 1, a + 1 + n, a + n))

    # ---- 叶裂：最后一段中脉两侧被撕开 ----
    verts_col = [None] * len(verts)
    extra_cols = []
    for s_i in range(seg):
        if (s_i + 1) / float(seg) < tear_from:
            continue
        for side, j in ((-1, 1), (1, 11)):
            a = s_i * n + j
            b = s_i * n + LEAF_CENTER
            p0 = Vector(verts[a]).lerp(Vector(verts[b]), 0.24)
            p1 = Vector(verts[a]).lerp(Vector(verts[b]), 0.62)
            i0 = len(verts)
            verts.append((p0.x, p0.y, p0.z))
            verts.append((p1.x, p1.y, p1.z))
            if side < 0:
                faces.append((a, i0, i0 + 1))
                extra_cols.append(lerp(PAL["leaf_edge"], PAL["midrib"], 0.35))
                extra_cols.append(lerp(PAL["midrib"], PAL["leaf_amber"], 0.4))
            else:
                faces.append((a, i0 + 1, i0))
                extra_cols.append(lerp(PAL["leaf_amber"], PAL["midrib"], 0.35))
                extra_cols.append(lerp(PAL["midrib"], PAL["leaf_amber"], 0.55))

    # ---- 顶点色 ----
    cols = [None] * len(verts)
    for s_i in range(seg + 1):
        t = s_i / seg
        for j, q in enumerate(LEAF_SITES):
            off = abs(q - 0.5) * 2.0
            if j == LEAF_CENTER:
                base = PAL["midrib"] if t > pet else PAL["petiole"]
            elif t < pet:
                base = lerp(PAL["petiole"], PAL["leaf_mid"], 0.2 + 0.6 * (t / max(1e-6, pet)))
            else:
                # 内侧(靠主脉)更亮 = 受光面，外侧偏暗 = 叶背投影
                base = grad(((0.0, PAL["leaf_dark"]),
                             (0.42, PAL["leaf_mid"]),
                             (0.78, PAL["leaf_light"]),
                             (1.0, PAL["leaf_bright"])), 1.0 - off)
                base = lerp(base, PAL["leaf_deep"], 0.30 * off)
            if t > 0.72:                                     # 老叶尖端发黄
                base = lerp(base, PAL["leaf_amber"],
                            (t - 0.72) / 0.28 * (0.30 if j != LEAF_CENTER else 0.15))
            if t > tear_from:                                # 裂口附近偏干
                base = lerp(base, PAL["leaf_amber"],
                            (t - tear_from) / (1.0 - tear_from) * 0.30)
            if j in LEAF_RIDGES:                             # 折痕两面明暗
                base = mul(base, 0.88 if j in (2, 8) else 1.10)
            cols[s_i * n + j] = mul(base, gain)
    for k, c in enumerate(extra_cols):
        cols[(seg + 1) * n + k] = c
    for i in range(len(cols)):
        if cols[i] is None:
            cols[i] = mul(PAL["leaf_mid"], gain)
    return build_object(name, verts, faces, cols, mat)


# ==================== 茎顶的"毛"：须状纤维 + 直立短叶 ====================
def build_crown_fringe(cfg, mat):
    """茎顶一圈毛茸茸的须状纤维（老叶鞘分解出来的纤维），把光秃秃的茎顶盖住。

    每根须是一条细长的小管子，从茎顶密布的一圈往外、往上翘，末端微微下垂。
    """
    h = cfg["stalk_height"]
    r_top = cfg["stalk_r_top"]
    n = cfg["fringe"]
    rng = random.Random(cfg["seed"] + 991)
    verts, faces, cols = [], [], []
    top_t = 1.0

    for i in range(n):
        # 须根均匀铺一圈，再抖动一点，避免看起来像齿轮
        a = (i / float(n)) * math.tau + rng.uniform(-0.10, 0.10)
        # 起点沿中轴往下一点散布，让"毛"有厚度
        t0 = top_t - rng.uniform(0.010, 0.115)
        origin, tangent, side = stalk_frame(cfg, t0)
        length = r_top * rng.uniform(1.5, 3.4)
        # 朝外 + 朝上，末端往下勾
        out_dir = (side * math.cos(a) + Vector((0.0, 0.0, 1.0)).cross(side) * math.sin(a)).normalized()
        up = 0.55 + 0.65 * rng.random()
        seg = 3
        w = r_top * 0.030 * rng.uniform(0.75, 1.3)
        ring_prev = None
        for k in range(seg + 1):
            f = k / float(seg)
            dist = length * f
            # 越往外越往上翘，最后一段回勾一点
            lift = up * f - 0.55 * f * f
            p = origin + out_dir * dist + Vector((0.0, 0.0, h * 0.030)) * (lift * 3.0)
            taper = w * (1.0 - 0.80 * f)
            ring = []
            for s in range(3):
                aa = s / 3.0 * math.tau + a
                off = (side * math.cos(aa) + Vector((0.0, 0.0, 1.0)).cross(side) * math.sin(aa)) * taper
                ring.append(p + off)
            ring_prev = ring
            verts.extend(tuple(v) for v in ring)
        base = len(verts) - (seg + 1) * 3
        for k in range(seg):
            for s in range(3):
                s2 = (s + 1) % 3
                faces.append((base + k * 3 + s, base + k * 3 + s2,
                              base + (k + 1) * 3 + s2, base + (k + 1) * 3 + s))
        faces.append((base, base + 1, base + 2))
        tb = base + seg * 3
        faces.append((tb + 2, tb + 1, tb))

    centers = face_centers(verts, faces)
    for c in centers:
        t = max(0.0, min(1.0, c[2] / max(1e-6, h)))
        # 顶端纤维偏枯黄，越往下越接近茎色
        col = grad(((0.0, lerp(PAL["stalk_high"], PAL["sheath_dead"], 0.45)),
                    (0.25, lerp(PAL["stalk_tip"], PAL["sheath_dead"], 0.65)),
                    (1.0, mul(PAL["sheath_dead"], 0.62))), t)
        cols.append(col)
    return build_object("CrownFringe", verts, faces, cols, mat, per_face=True)


def build_crown_blades(cfg, mat):
    """茎顶直立的短叶 / 未展开的新叶苞：让顶端有"向上的生命感"，而不是一个平截面。"""
    h = cfg["stalk_height"]
    r_top = cfg["stalk_r_top"]
    n = cfg["crown_blades"]
    rng = random.Random(cfg["seed"] + 313)
    objs = []
    for i in range(n):
        az = 360.0 * i / float(n) + rng.uniform(-18.0, 18.0)
        # 越短的越靠外、越斜，形成一丛
        short = 0.32 + 0.42 * rng.random()
        ln = cfg["leaf_len"] * short
        sub = dict(cfg)
        sub["petiole_frac"] = 0.12
        sub["leaf_roll0"] = 80.0 - 25.0 * short      # 越长越摊开
        sub["leaf_roll1"] = 60.0 - 30.0 * short
        arch = 6.0 + 22.0 * short
        ob = build_frond("Blade_%d" % i, sub, mat, ln, ln * 0.20, arch, 1.16)
        t0 = 0.995
        origin, _, _ = stalk_frame(cfg, t0)
        a = math.radians(az) + stalk_twist(cfg, t0)
        off = origin + Vector((math.cos(a) * r_top * 0.45, math.sin(a) * r_top * 0.45, 0.0))
        pitch = math.radians(84.0 - 34.0 * short)
        rot = Matrix.Rotation(az, 4, 'Z') @ Matrix.Rotation(-pitch, 4, 'Y')
        v, f, c = place(ob, rot, tuple(off))
        bpy.data.objects.remove(ob, do_unlink=True)
        objs.append(build_object("Blade_%d" % i, v, f, c, mat))
    return objs


# ==================== 树冠布叶 ====================
def tier_value(pair, tf):
    """把 (内层值, 外层值) 按层级比例 tf 插值。"""
    return pair[0] + (pair[1] - pair[0]) * tf


def build_crown(cfg, mat):
    """叶柄从假茎顶端一段里放射长出，分 4 层：内层挺立、外层下垂，形成喷泉状树冠。

    叶柄起点沿假茎往下铺开（crown_drop），所以树冠是"包"住茎顶的一丛，
    而不是全挤在一个平面上 —— 顶端因此不再光秃秃。
    """
    h = cfg["stalk_height"]
    n = cfg["leaf_count"]
    tiers = cfg["leaf_tiers"]
    r_top = cfg["stalk_r_top"]
    golden = 137.5
    drop = cfg["crown_drop"]
    objs = []
    for i in range(n):
        tier = i % tiers
        tf = tier / max(1.0, tiers - 1.0)
        az = i * golden + tier * 41.0
        sub = dict(cfg)
        sub["leaf_pitch"] = tier_value(cfg["leaf_pitch"], tf)
        sub["leaf_roll0"] = cfg["leaf_roll0"] * (1.0 + 0.35 * tf)
        arch = tier_value(cfg["leaf_arch"], tf)
        # 外层叶更长，但叶柄抬角更低 → 大而外翻的树冠
        length = cfg["leaf_len"] * (1.0 + 0.16 * tf)
        width = cfg["leaf_width"] * (1.0 + 0.02 * tf)
        ob = build_frond("Frond_%02d" % i, sub, mat, length, width, arch, 1.0 + 0.12 * tf)
        # 叶柄起点：沿弯曲中轴往下铺开，越外层越低
        t0 = 1.0 - drop * tf - (i % 3) * 0.012
        origin, _, _ = stalk_frame(cfg, t0)
        a = math.radians(az) + stalk_twist(cfg, t0)
        offset = origin + Vector((math.cos(a) * r_top * (0.55 + 0.20 * tf),
                                  math.sin(a) * r_top * (0.55 + 0.20 * tf), 0.0))
        pitch = math.radians(sub["leaf_pitch"])
        rot = Matrix.Rotation(az, 4, 'Z') @ Matrix.Rotation(-pitch, 4, 'Y')
        v, f, c = place(ob, rot, tuple(offset))
        bpy.data.objects.remove(ob, do_unlink=True)
        objs.append(build_object("Crown_%02d" % i, v, f, c, mat))
    return objs


# ==================== 根出小苗 ====================
def build_sucker(name, cfg, mat, ang_deg, dist, scale, seed):
    """根出小苗：一段细假茎 + 3 片小叶（含一株卷筒嫩叶）。"""
    rng = random.Random(seed)
    ang = math.radians(ang_deg)
    lean = math.radians(11.0 + 7.0 * scale)
    base = Vector((math.cos(ang) * dist, math.sin(ang) * dist, 0.0))
    z_dir = (Vector((0.0, 0.0, 1.0)) * math.cos(lean)
             + Vector((math.cos(ang), math.sin(ang), 0.0)) * math.sin(lean)).normalized()
    sh = min(cfg["stalk_height"] * 0.42, 0.70) * scale
    parts = []

    # 小假茎：4 段收细
    sides = 6
    rings = []
    for f, k in ((0.0, 1.0), (0.36, 0.85), (0.70, 0.60), (1.0, 0.28)):
        r = cfg["stalk_r_bottom"] * 0.30 * scale * k
        ex, ey, ez = basis_from_z(z_dir)
        ring = []
        for s in range(sides):
            a = s / float(sides) * math.tau
            p = base + ez * (sh * f) + (ex * math.cos(a) + ey * math.sin(a)) * r
            ring.append(tuple(p))
        rings.append(ring)
    verts, faces = [], []
    for ring in rings:
        verts.extend(ring)
    for k in range(len(rings) - 1):
        for s in range(sides):
            s2 = (s + 1) % sides
            faces.append((k * sides + s, k * sides + s2,
                          (k + 1) * sides + s2, (k + 1) * sides + s))
    faces.append((0, 1, 2, 3))
    top = (len(rings) - 1) * sides
    faces.append((top + 3, top + 2, top + 1, top))
    centers = face_centers(verts, faces)
    cols = []
    for c in centers:
        t = max(0.0, min(1.0, (c[2] - base.z) / max(1e-6, sh)))
        cols.append(mul(grad(((0.0, PAL["stalk_root"]), (0.5, PAL["sucker"]),
                               (1.0, PAL["stalk_mid"])), t), 0.92))
    parts.append(build_object(name + "_Stem", verts, faces, cols, mat, per_face=True))

    # 小叶：前两片展开、第三片是挺立的卷筒嫩叶
    for j in range(4):
        leaf_az = ang_deg + 20.0 + j * 92.0 + rng.uniform(-14.0, 14.0)
        ln = (0.46 + 0.20 * rng.random()) * scale
        sub = dict(cfg)
        sub["petiole_frac"] = 0.26 if j < 3 else 0.44
        sub["leaf_roll0"] = 62.0 if j < 3 else 86.0
        sub["leaf_roll1"] = 6.0
        arch = 46.0 if j < 3 else 10.0
        leaf = build_frond(name + "_LeafSrc%d" % j, sub, mat, ln, ln * 0.40, arch, 0.96)
        pitch = math.radians(30.0 + j * 4.0) if j < 3 else math.radians(84.0)
        rot = Matrix.Rotation(math.radians(leaf_az), 4, 'Z') @ Matrix.Rotation(-pitch, 4, 'Y')
        tip = base + z_dir * (sh * (0.50 + 0.14 * j))
        v, f, c = place(leaf, rot, tuple(tip))
        bpy.data.objects.remove(leaf, do_unlink=True)
        parts.append(build_object(name + "_Leaf%d" % j, v, f, c, mat))
    return parts


# ==================== 组装一棵树 ====================
def build_tree(cfg, render=True):
    random.seed(cfg["seed"])
    reset_scene()
    mat = make_vc_material("BananaTree", PAL["leaf_mid"])

    # 注意：茎顶的须状纤维算"叶"，不能放进 Stalk。
    # Godot 侧按节点名里是否含 "stalk" 来量假茎半径，纤维向外伸出很长，
    # 混进 Stalk 会把半径撑大，导致果串被判定为"插进树干"（自检 [11]）。
    stalk = join_meshes([build_stalk(cfg, mat),
                         build_stalk_cap(cfg, mat),
                         build_root_flare(cfg, mat),
                         build_root_sheaths(cfg, mat)], "Stalk")

    leaves = list(build_crown(cfg, mat))
    leaves.extend(build_crown_blades(cfg, mat))
    leaves.append(build_crown_fringe(cfg, mat))
    for i, (ang, dist, sc) in enumerate(cfg["suckers"]):
        leaves.extend(build_sucker("Sucker_%d" % i, cfg, mat, ang, dist, sc, cfg["seed"] + i))
    leaves = join_meshes(leaves, "Leaves")

    for ob in (stalk, leaves):
        for poly in ob.data.polygons:
            poly.use_smooth = False

    # 整体缩放到目标高度：原点在根部 (0,0,0)，缩放后依然贴地，
    # 模型比例不变，只是把"叶片下垂造成的变矮"补回来。
    raw_h = max(v.co.z for o in (stalk, leaves) for v in o.data.vertices)
    fit = cfg["target_height"] / max(1e-6, raw_h)
    if abs(fit - 1.0) > 1e-4:
        for ob in (stalk, leaves):
            ob.data.transform(Matrix.Scale(fit, 4))
        print("fit scale %.4f (raw height %.3f -> %.3f)" % (fit, raw_h, cfg["target_height"]))

    zs = [v.co.z for o in (stalk, leaves) for v in o.data.vertices]
    xs = [v.co.x for o in (stalk, leaves) for v in o.data.vertices]
    ys = [v.co.y for o in (stalk, leaves) for v in o.data.vertices]
    tris = sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in (stalk, leaves))
    print("STYLE height %.3f  span %.2f x %.2f  tris %d  verts %d" % (
        max(zs), max(xs) - min(xs), max(ys) - min(ys), tris,
        sum(len(o.data.vertices) for o in (stalk, leaves))))

    blend_path = os.path.join(BASE_DIR, "low_poly_banana_tree.blend")
    bpy.ops.wm.save_as_mainfile(filepath=blend_path)
    glb_path = os.path.join(BASE_DIR, "low_poly_banana_tree.glb")
    bpy.ops.export_scene.gltf(
        filepath=glb_path, export_format='GLB',
        export_vertex_color='MATERIAL', use_selection=False,
        export_apply=True, export_yup=True,
    )
    print("SAVED", glb_path)

    if render:
        render_preview(os.path.join(BASE_DIR, "low_poly_banana_tree_preview.png"), cfg)
    return stalk, leaves


# ==================== 预览渲染 ====================
def render_preview(out_path, cfg, shot_count=4):
    """按几个角度渲染当前场景并横排拼成一张图，供快速人工检查造型。"""
    scene = bpy.context.scene
    try:
        scene.render.engine = 'BLENDER_EEVEE'
    except TypeError:
        scene.render.engine = 'CYCLES'
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = 'PNG'
    scene.render.resolution_x = 640
    scene.render.resolution_y = 860
    scene.render.resolution_percentage = 100

    world = bpy.data.worlds.new("PreviewWorld")
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.80, 0.86, 0.92, 1.0)
    bg.inputs[1].default_value = 1.0

    sun = bpy.data.objects.new("Sun", bpy.data.lights.new("SunL", 'SUN'))
    sun.data.energy = 3.2
    sun.data.angle = math.radians(12)
    sun.rotation_euler = (math.radians(56), 0.0, math.radians(38))
    scene.collection.objects.link(sun)
    fill = bpy.data.objects.new("Fill", bpy.data.lights.new("FillL", 'SUN'))
    fill.data.energy = 1.1
    fill.rotation_euler = (math.radians(70), 0.0, math.radians(215))
    scene.collection.objects.link(fill)

    cam_data = bpy.data.cameras.new("PrevCam")
    cam = bpy.data.objects.new("PrevCam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    cam_data.lens = 58.0

    # 按实际包围盒取景，保证整棵树（含外翻的叶片）都在画面里
    pts = [v.co for ob in scene.objects if ob.type == 'MESH' for v in ob.data.vertices]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    target = (lo + hi) * 0.5
    span = max((hi - lo).x, (hi - lo).y, (hi - lo).z)
    # 竖直画幅里高度占主导，再加上叶片横向展开，取一个稳的机位距离
    dist = span * 1.75
    aspect = scene.render.resolution_x / float(scene.render.resolution_y)
    if aspect < 1.0:
        dist /= aspect * 0.92
    shots = []
    for i in range(shot_count):
        ang = math.radians(28.0 + i * (360.0 / shot_count))
        elev = math.radians(12.0 if i % 2 == 0 else 26.0)
        pos = target + Vector((math.cos(ang) * math.cos(elev),
                               math.sin(ang) * math.cos(elev),
                               math.sin(elev))) * dist
        cam.location = pos
        cam.rotation_euler = (target - pos).to_track_quat('-Z', 'Y').to_euler()
        path = "/tmp/banana_shot_%d.png" % i
        scene.render.filepath = path
        bpy.ops.render.render(write_still=True)
        shots.append(path)

    imgs = [bpy.data.images.load(p) for p in shots]
    w, h = imgs[0].size
    out = bpy.data.images.new("Preview", width=w * len(imgs), height=h)
    buf = [0.0] * (w * len(imgs) * h * 4)
    for k, im in enumerate(imgs):
        px = list(im.pixels)
        for y in range(h):
            src = y * w * 4
            dst = (y * w * len(imgs) + k * w) * 4
            buf[dst:dst + w * 4] = px[src:src + w * 4]
    out.pixels = buf
    out.filepath_raw = out_path
    out.file_format = 'PNG'
    out.save()
    for im in imgs:
        bpy.data.images.remove(im)
    bpy.data.images.remove(out)
    print("PREVIEW", out_path)


# ==================== 入口 ====================
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
wanted = [a for a in argv if a in STYLES] or list(STYLES.keys())
do_render = "--nopreview" not in argv
for key in wanted:
    build_tree(STYLES[key], render=do_render)
print("ALL_DONE", wanted)
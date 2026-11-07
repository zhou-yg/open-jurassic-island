# Blender 建模脚本：Low-Poly 香蕉树（高 / 矮两种款式）
#
# 用法:
#   blender --background --python low_poly_banana_tree.py            # 生成"本目录"对应的那一款
#   blender --background --python low_poly_banana_tree.py -- tall    # 强制生成高款
#   blender --background --python low_poly_banana_tree.py -- short   # 强制生成矮款
#   blender --background --python low_poly_banana_tree.py -- tall --nopreview
#
# 产物（写入 <款式目录>）: low_poly_banana_tree.blend / .glb / _preview.png
#
# ---------------------------------------------------------------------------
# 造型说明
# ---------------------------------------------------------------------------
# 香蕉树不是"树干 + 树冠"，而是"假茎 + 一丛巨大的叶"。这一版做了四件事：
#
# 1) 叶片（frond）—— 更像真的蕉叶，同时面数砍到原来的 1/3：
#    * 轮廓：叶身从叶柄末端就展开、约 45% 处最宽、最后 25% 收成一个**钝尖**
#      （旧版叶尖是 50% 满宽的平头，像被剪过），叶缘有起伏的波浪（沿叶长做正弦扰动）。
#    * 横截面改成**固定的 9 个站点**：叶缘下垂最狠 → 靠叶缘略抬 → 一道横向褶皱
#      隆起 → 微凹 → **主脉抬起最高** → 镜像。褶皱是"沿叶长平行"的纵向折痕
#      （真蕉叶就是这样），旧版是逐段交替的锯齿褶，读起来像揉皱的纸。
#    * 叶尖 20% 做**边缘碎裂**（隔段挖掉最外一列面 → 锯齿状的叶缘），
#      叶尖 12% 再沿主脉**纵向开裂**（香蕉叶标志性的"破叶"）。
#    * 颜色：靠主脉亮、靠叶缘暗；褶皱脊略亮、谷略暗（几何起伏 + 顶点色呼应）；
#      外层老叶偏黄，内层新叶偏翠绿。
#
# 2) 假茎（pseudostem）—— 竖向纹理 + 横向老叶痕：
#    * 7 条叶鞘沿高度 + 周向螺旋卷绕（1.15 圈），相邻叶鞘互相搭接 → 表面有
#      台阶、竖向沟槽和叶鞘边缘的翻边。
#    * 顶点色改成"按角度"算：叶鞘接缝处压暗（竖向条纹），再叠一层高度渐变
#      + 一圈圈的老叶痕横环。旧版是按"半径比"逐面取色，结果是一块块方格状
#      杂色（patchy），不像假茎。
#
# 3) 根部基座（base）—— 根盘不再是"多边形底座"：
#    * 根盘改成平滑的有机喇叭口（更多环、更圆），周向根隆顺着沟槽走。
#    * 3 片干枯下垂的旧叶鞘包住茎基，遮掉"光杆插在地上"的感觉，且**不穿到
#      地面以下**（整棵树的最低点严格是 z = 0）。
#
# 4) 树冠 —— 更满、更像"喷泉"：
#    * 4 层叶（内层挺立 / 两个中层半展 / 外层长而下垂），外层更长更大。
#    * 茎顶 10 片直立的新叶苞（中模）+ 28 根**粗壮的**干枯纤维（旧版是 56 根
#      头发丝粗的须，在渲染里只是一片白色划痕）。
#
# 5) 配色 —— 每类材质最多 2 种颜色，且树干不能和叶子同色相（重做）：
#    * 全树只有 **4 个颜色**：叶绿 ×2 + 树干暖褐 ×2（干枯的旧叶鞘/纤维用树干暗色）。
#      叶绿 hue≈130°、树干暖褐 hue≈35° —— 相差近 95°，「叶」和「干」一眼分开。
#      之前树干用的是橄榄绿（和叶子几乎同色相）→ 整棵树粘成一团绿，又像竹子。
#    * 层次和交错不再靠多加颜色，而是靠"同一对颜色怎么排"做出来：
#      - 叶片：叶缘 = 深色的干净暗边，主脉 = 浅色的干净亮脉，
#        中间 = 棋盘式交错（相邻面换色）→ 编织感；
#        暗边多宽（margin）= 整片叶越暗 → 层次感（外层老叶 2，内层新叶 1）。
#      - 假茎：假茎本体就是一个颜色，只在叶鞘接缝处留一条细暗线。
#        之前是"整条扇区都压暗" → 渲染出来是竹子；假茎本来就是一圈圈卷起来的叶鞘。
#      - 横向的明暗交给太阳自己；自己再叠横环，竖线一交叉又变方格杂色。
#
# 6) 面块要大 —— 低多角的"干净"是面块大，不是面数少：
#    叶片分面从 9 站 × 11 段（88 面）改成 7 站 × 6 段（36 面），假茎 12×16 → 9×18。
#    面块大了一倍，颜色块从"碎屑子"变成大块的几何形状——
#    之前那种颜色"杂"很大程度上就是面太小。
#
# ---------------------------------------------------------------------------
# Godot 侧约定（改动会破坏 components/vegetation/banana_tree/banana_tree.gd）
# ---------------------------------------------------------------------------
# * 两个网格节点必须叫 "Stalk" 与 "Leaves"（组件按名字含 "stalk" 找假茎半径）。
# * 原点在根部 y=0，模型沿 +Y 生长；高款约 4.77 m，矮款约 2.66 m
#   （组件的 tree_height / 自检 [7] 依赖这两个数值）。
# * 假茎半径剖面保持原值：高款底部 0.35 顶部 0.24，矮款底部 0.365 顶部 0.26；
#   因为 banana_tree.gd 的 bunch_outset=0.62 与自检 [11]"香蕉不插进假茎"依赖它。
#   注意脚本末尾会把整棵树等比缩放到目标高度，所以**导出后**的实际半径是
#   剖面值 × fit（高款约 0.314 / 0.216 m）—— fit 必须保持不变，否则果串会插进
#   假茎（自检 [11] 会报错）。脚本里的 "fit_target" 就是这个值，偏离超过 0.010
#   会打印 "!! WARNING"（见脚本末尾的自检输出）。
# * **假茎上不能有往外突出的东西**（干枯叶鞘、叶子都归 "Leaves"）：Godot 侧
#   用假茎网格的最大半径判定香蕉是否插进树干，凸出来就会撑大这个半径。
# * 颜色走顶点色 COLOR_0（材质里挂 Color Attribute 节点），导出后 Godot 的
#   StandardMaterial3D 会直接用顶点色，不需要额外配置。
#   注意：COLOR_0 是**逐面**的（一个面内部所有 loop 共用一个颜色）。
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
# low-poly 的配色纪律：**每一类材质最多 2 种颜色**。
#
# ⚠️ 关键：**树干不能和叶子同一个色相**，否则整棵树糊成一团绿。
#   叶子 = 冷调深绿（hue≈130°），树干/枯叶 = 暖调黄褐（hue≈45°），
#   两者在色轮上差着将近 90°，一眼就能分开"叶"和"干"。
#
# 全树只有 4 个颜色：叶绿 ×2 + 树干黄褐 ×2（干枯的旧叶鞘/纤维用树干的暗色）。
PAL = {
    # 叶片绿：2 档（深 / 浅）—— 偏冷、偏深，别做成发黄的橄榄绿
    "leaf_dark":  (0.176, 0.376, 0.169),
    "leaf_light": (0.255, 0.510, 0.220),
    # 树干暖褐：2 档（暗 / 亮）—— 干浮的旧叶鞘，和叶子拉开色相
    "bark_dark":  (0.373, 0.302, 0.188),
    "bark_light": (0.545, 0.447, 0.286),
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
        "fit_target": 0.894,        # 旧版的 fit：导出后的假茎剖面要和老版一模一样
        "stalk_height": 3.63,
        "stalk_r_bottom": 0.350,
        "stalk_r_top": 0.240,
        "stalk_bands": 10,           # 假茎的叶鞘环带数（每带一道台阶）
        "stalk_sides": 9,            # 假茎圆周分几个面（面块大 → low-poly）
        "leaf_scars": 11,            # 假茎表面的老叶痕圈数
        "root_flare": 12,            # 根部环形根隆数量
        "root_wraps": 3,             # 根部干枯下垂的旧叶鞘片数
        "suckers": [(72.0, 0.60, 1.00), (206.0, 0.74, 0.82), (322.0, 0.54, 0.66)],
        "leaf_len": 2.02,
        "leaf_width": 0.78,
        "petiole_frac": 0.30,        # 叶柄占整片叶长的比例
        "leaf_roll1": 4.0,           # 叶尖扭转角（0 = 叶面朝上）
        # 树冠四层：内层挺立 / 中层半展 / 外层长而下垂（喷泉状）
        "crown_tiers": [
            {"count": 4, "pitch": 54.0, "arch": 12.0, "len": 0.80, "wid": 0.80,
             "drop": 0.00, "roll0": 70.0, "margin": 1, "parity": 0},
            {"count": 4, "pitch": 34.0, "arch": 32.0, "len": 0.94, "wid": 0.94,
             "drop": 0.07, "roll0": 60.0, "margin": 1, "parity": 1},
            {"count": 4, "pitch": 12.0, "arch": 52.0, "len": 1.04, "wid": 1.02,
             "drop": 0.14, "roll0": 52.0, "margin": 2, "parity": 0},
            {"count": 3, "pitch": 2.0, "arch": 76.0, "len": 0.98, "wid": 1.04,
             "drop": 0.13, "roll0": 46.0, "margin": 2, "parity": 1},
        ],
        "lean_x": 0.34,              # 假茎顶端相对根部在 X 方向的偏移（米）
        "lean_y": -0.16,             # 假茎顶端相对根部在 Y 方向的偏移（米）
        "twist_deg": 0.0,            # 假茎不扭转（扭了会变成"扭的条"，不 low-poly）
        "blade_short": (0.56, 1.20),  # 茎顶新叶苞（最短/最长 × 叶长）
        "fringe": 28,                # 茎顶干枯纤维的根数
        "crown_blades": 10,          # 茎顶直立的短叶数（肉穗/新叶苞）
    },
    # 矮款：粗矮，叶片短而宽，像庭院矮蕉
    "short": {
        "seed": 23,
        "target_height": 2.66,
        "fit_target": 0.783,
        "stalk_height": 2.16,
        "stalk_r_bottom": 0.365,
        "stalk_r_top": 0.260,
        "stalk_bands": 7,            # 假茎的叶鞘环带数
        "stalk_sides": 9,            # 假茎圆周分几个面
        "leaf_scars": 9,
        "root_flare": 12,
        "root_wraps": 3,
        "suckers": [(60.0, 0.56, 0.95), (198.0, 0.70, 0.78), (300.0, 0.52, 0.62)],
        "leaf_len": 1.52,
        "leaf_width": 0.72,
        "petiole_frac": 0.31,
        "leaf_roll1": 3.0,
        "crown_tiers": [
            {"count": 3, "pitch": 52.0, "arch": 14.0, "len": 0.80, "wid": 0.82,
             "drop": 0.00, "roll0": 68.0, "margin": 1, "parity": 0},
            {"count": 3, "pitch": 32.0, "arch": 34.0, "len": 0.94, "wid": 0.94,
             "drop": 0.07, "roll0": 59.0, "margin": 1, "parity": 1},
            {"count": 3, "pitch": 10.0, "arch": 54.0, "len": 1.04, "wid": 1.02,
             "drop": 0.14, "roll0": 51.0, "margin": 2, "parity": 0},
            {"count": 3, "pitch": 0.0, "arch": 78.0, "len": 0.98, "wid": 1.04,
             "drop": 0.13, "roll0": 45.0, "margin": 2, "parity": 1},
        ],
        "lean_x": 0.22,
        "lean_y": -0.11,
        "twist_deg": 0.0,            # 同上：假茎不扭转
        "blade_short": (0.50, 1.12),
        "fringe": 24,
        "crown_blades": 9,
    },
}

# ==================== 叶片的横截面剖面 ====================
# 每个档位 = 站点表 + 每个站点的"下垂量" + 沿叶长的段数。
# 下垂量约定与旧版一致：**正 = 往下（叶缘垂），负 = 往上（主脉抬起、褶皱隆起）**。
#   hi : 树冠大叶，9 站点 × 11 段（144 顶点 / 88 面）
#   mid: 茎顶新叶苞，7 站点 × 8 段
#   lo : 根出小苗的小叶，5 站点 × 6 段
LEAF_PROFILE = {
    "hi": {
        # 7 站 = 6 条横带：暗边 / 交错带 / 亮主脉 / 交错带 / 暗边 …
        "sites": (0.00, 0.17, 0.33, 0.50, 0.67, 0.83, 1.00),
        "droop": (0.55, 0.10, -0.30, -0.48, -0.30, 0.10, 0.55),
        "center": 3,
        "seg": 6,
    },
    "mid": {
        "sites": (0.00, 0.25, 0.50, 0.75, 1.00),
        "droop": (0.50, -0.24, -0.48, -0.24, 0.50),
        "center": 2,
        "seg": 4,
    },
    "lo": {
        "sites": (0.00, 0.25, 0.50, 0.75, 1.00),
        "droop": (0.50, -0.24, -0.48, -0.24, 0.50),
        "center": 2,
        "seg": 4,
    },
}

# 横截面整体起伏的幅度系数（米 / 半宽）。
# ⚠️ 这个数决定叶片"平"还是"爪"：叶片横截面的总起伏（主脉到叶缘）约
#    0.22 × 0.48 + 0.22 × 0.55 ≈ 0.23 × 全宽。旧版是 0.19 × 全宽，
#    调到 0.3 以上叶片就会变成"香蕉形的爪子"，一点也不像叶子了。
FOLD_SCALE = 0.22
# 叶缘下垂的幅度系数。
EDGE_DROOP = 0.55


# ==================== 通用工具 ====================
def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.unit_settings.system = 'METRIC'


def lerp(a, b, t):
    t = max(0.0, min(1.0, t))
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


def mul(c, k):
    return (max(0.0, c[0] * k), max(0.0, c[1] * k), max(0.0, c[2] * k))


def smoothstep(a, b, x):
    """a→b 之间的平滑过渡（0..1）。"""
    if abs(b - a) < 1e-9:
        return 0.0 if x < a else 1.0
    u = max(0.0, min(1.0, (x - a) / (b - a)))
    return u * u * (3.0 - 2.0 * u)


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
    它是逐面颜色（长度 = 面数），面的几个角用同一个颜色 → 干脆的 low-poly 面块。
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


def vertex_colors_of(ob):
    """取出一个网格对象逐顶点的颜色（从 loop 颜色折叠到顶点上）。"""
    src = ob.data.color_attributes["Col"]
    out = [None] * len(ob.data.vertices)
    for poly in ob.data.polygons:
        for li in poly.loop_indices:
            vi = ob.data.loops[li].vertex_index
            if out[vi] is None:
                out[vi] = tuple(src.data[li].color)[:3]
    return [(c if c is not None else PAL["leaf_light"]) for c in out]


def face_colors_of(ob):
    """取出一个网格对象逐面的颜色。

    ⚠️ low-poly 的"块面感"就靠这个：颜色必须**逐面纯色**，不能逐顶点插值 ——
    逐顶点插值会在一个面里混出中间色，块面就没了。
    """
    src = ob.data.color_attributes["Col"]
    out = []
    for poly in ob.data.polygons:
        out.append(tuple(src.data[poly.loop_start].color)[:3])
    return out


def place(ob, matrix, offset, per_face=False):
    """把 ob 的几何按矩阵旋转 + 平移，返回 (verts, faces, cols)，随后可删除 ob。"""
    verts = [tuple(matrix @ Vector(v.co)) for v in ob.data.vertices]
    verts = [(v[0] + offset[0], v[1] + offset[1], v[2] + offset[2]) for v in verts]
    faces = [tuple(p.vertices) for p in ob.data.polygons]
    cols = face_colors_of(ob) if per_face else vertex_colors_of(ob)
    return verts, faces, cols


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
    """假茎沿高度的扭转角（弧度）。

    ⚠️ **必须是 0**：一旦扭转，每个环带的圆周分点都会转一个角度 → 竖向棱边变成螺旋带。
    这个"扭的条"效果一点都不 low-poly（真实的香薯假茎是一圈圈直上卷的，不会螺旋）。
    """
    return math.radians(cfg["twist_deg"]) * (t ** 1.25)


def stalk_point(cfg, t, ang, r):
    """在高度比例 t、圆周角 ang、半径 r 处的中轴坐标 (x, y, z)。"""
    origin, _, side = stalk_frame(cfg, t)
    a = ang + stalk_twist(cfg, t)
    return origin + side * (math.cos(a) * r) + Vector((0.0, 0.0, 1.0)).cross(side) * (math.sin(a) * r)


def build_stalk(cfg, mat):
    """假茎：**一叠卷起来的叶鞘**（不是一个扫掠圆柱）。

    每一带 = 一个略带锥度的环带：
      * 底边往外翻出一圈**唇口**（叶柄切断留下的边），上一带的底唇压住下一带的
        顶边 → 侧影上就是**一层层台阶**，这才是香蕉假茎的标志；
      * 环带本身随高度收细，整条茎是微微鼓肚再收的。
    每一带沿中轴再拧一点 → 竖向的接缝是**螺旋**的。

    ⚠️ 旧版是"扫掠圆柱 + 几片贴在圆柱**里面**的叶鞘" → 渲染出来是一根光筒子，
    什么结构都读不出来。现在每一片叶鞘都是**真的浮在外面**的一圈。

    圆周只分 9 个点、每带只 3 圈 → 面块大，平面着色下每块棱面都清清楚楚。
    """
    h = cfg["stalk_height"]
    n_bands = cfg["stalk_bands"]
    n_circle = cfg["stalk_sides"]
    verts, faces, kinds = [], [], []

    def ring(z, scale):
        """在高度 z 处扫一圈点（半径按假茎剖面 × scale）。"""
        t = max(0.0, min(1.0, z / h))
        r = sheath_radius(cfg, t) * scale
        row = []
        for s in range(n_circle):
            a = s / float(n_circle) * math.tau
            p = stalk_point(cfg, t, a, r)
            row.append(len(verts))
            verts.append((p.x, p.y, p.z))
        return row

    def bridge(a, b, kind):
        for s in range(n_circle):
            s2 = (s + 1) % n_circle
            faces.append((a[s], a[s2], b[s2], b[s]))
            kinds.append(kind)

    prev_top = None
    for k in range(n_bands):
        t0 = k / float(n_bands)
        t1 = (k + 1) / float(n_bands)
        z0, z1 = t0 * h, t1 * h
        z_lip = z0 + (z1 - z0) * 0.22
        r_lip = ring(z0, 1.055)        # 唇口：最外一圈（切断的叶柄边）
        r_body = ring(z_lip, 0.99)     # 唇口上方
        r_top = ring(z1, 0.99)         # 本带顶部（下一带的唇口压住它）
        bridge(r_lip, r_body, "lip")   # 唇口的斜面（在阴影里）
        bridge(r_body, r_top, "body")  # 环带本体
        if prev_top is not None:
            bridge(prev_top, r_lip, "ledge")   # 台阶面：上一带顶 → 本带唇口
        prev_top = r_top
    # 底面（贴着地面，看不见，补上免得开口）
    bridge(list(reversed(prev_top)), list(reversed(prev_top)), "cap")

    cols = []
    for kind in kinds:
        # 唇口 / 台阶都是朝下的面，本来就在阴影里 → 用暗色；
        # 环带本体是竖面 → 用亮色。这样"横向的暗环"正好落在台阶上，
        # 和几何结构对得上，不是凭空画的条纹。
        cols.append(PAL["bark_dark"] if kind in ("lip", "ledge", "cap")
                    else PAL["bark_light"])
    return build_object("Stalk", verts, faces, cols, mat, per_face=True)


def build_stalk_cap(cfg, mat):
    """假茎顶端的截断截面：深色圆盘 + 一圈稍亮的断口（跟着弯的中轴走）。"""
    r = cfg["stalk_r_top"] * 0.99
    sides = 10
    origin, _, _ = stalk_frame(cfg, 0.995)
    verts = [tuple(origin)]
    for s in range(sides):
        a = s / float(sides) * math.tau
        p = stalk_point(cfg, 0.995, a, r)
        verts.append((p.x, p.y, p.z))
    faces = [(0, 1 + s, 1 + ((s + 1) % sides)) for s in range(sides)]
    cols = [PAL["bark_dark"]] * (sides + 1)
    return build_object("StalkCap", verts, faces, cols, mat)


# ==================== 根部基座：外扩根盘 + 干枯叶鞘 ====================
def build_root_flare(cfg, mat, n_ring=20, n_prof=6):
    """根盘：贴着地面的外扩喇叭口，周向有 nr 道根隆，对正假茎的沟槽。

    这是"根部不再简陋"的主体 —— 一个连续的、缓缓落到地面的裙状基座，
    而不是插在地上的光杆。底圈正好落在 z = 0（整棵树的最低点）。
    """
    h = cfg["stalk_height"]
    rb = cfg["stalk_r_bottom"]
    nr = cfg["root_flare"]
    verts, faces = [], []
    for k in range(n_prof):
        f = k / float(n_prof - 1.0)
        # f=0 顶端（接假茎）.. f=1 地面
        z = h * 0.125 * (1.0 - f) ** 1.7
        flare = rb * (1.0 + 0.24 * (f ** 1.25))
        for s in range(n_ring):
            a = s / float(n_ring) * math.tau
            ridge = 1.0 + 0.075 * (math.cos(a * nr) * 0.5 + 0.5) * f
            # 几道低频谐波让根盘轮廓不是正圆，更像有机的根颈
            wob = 1.0 + 0.050 * math.sin(a * 3.0 + 0.7) + 0.028 * math.sin(a * 5.0 - 1.3)
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
        # 根盘是一圈平滑外扩的喇叭口（不是"一叠叶鞘"），所以**不能**像假茎那样
        # 叠横向明暗环 —— 那会让它看着像个"纵条纹台座"。统一用亮色，
        # 和假茎本体连成一体；暗色留给根部的干枯叶鞘。
        col = PAL["bark_light"]
        cols.append(col)
    return build_object("RootFlare", verts, faces, cols, mat, per_face=True)


def build_root_sheaths(cfg, mat):
    """根部几片干枯下垂的旧叶鞘：像真正的老叶一样贴着茎向下披垂。

    每片是一条"上宽下尖"的带子，沿高度逐渐向外、向下弯，末端收成尖并有点卷边，
    而不是一块直挺挺的板子。颜色由贴茎处的暗绿过渡到枯黄。
    叶尖停在地表之上（不穿到 z < 0），整棵树的最低点因此严格是 0。
    """
    h = cfg["stalk_height"]
    rb = cfg["stalk_r_bottom"]
    n = cfg["root_wraps"]
    verts, faces = [], []
    seg = 5                      # 沿垂落方向的段数
    across = 3                   # 横向站点数
    for i in range(n):
        a0 = i * math.tau / n + 0.8
        span = math.radians(78.0)           # 这片叶鞘包住多少圆周
        z_top = h * (0.150 + 0.028 * i)
        drop = h * (0.135 + 0.014 * i)      # 垂下来更长，像挂在茎上的枯叶
        grid = []
        for k in range(seg + 1):
            f = k / float(seg)              # 0 贴茎 .. 1 叶尖
            # 上宽下窄，末端收成尖；先向外鼓再收回来 → 像披垂下来的样子
            half = span * 0.5 * (1.0 - 0.70 * f ** 1.25)
            out = rb * (1.03 + 0.24 * math.sin(math.pi * (f ** 0.62)) ** 0.95)
            z = max(0.0, z_top - drop * (f ** 1.35))
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
        # 一跟叶鞘的上下提亮两档：贴茎处比较亮，尖处已枯
        col = PAL["bark_light"] if t < 0.30 else PAL["bark_dark"]
        cols.append(col)
        cols.append(col)
    return build_object("RootSheaths", verts, faces, cols, mat, per_face=True)


# ==================== 叶片 ====================
def blade_shape(u):
    """叶身宽度轮廓：u=0 叶柄末端 .. u=1 叶尖。

    真蕉叶是"宽桨形 + 钝尖"：从叶柄就展开，中段一直是满宽，最后 25% 才收成
    一个钝尖。旧版叶尖是 50% 满宽（平头，像被剪过），这一版收到 30% —— 再尖
    就会变成"香蕉形的爪子"，不像叶子了。
    u=0 时宽度 = 叶柄宽度（16%），所以叶柄和叶身之间没有台阶。
    """
    u = max(0.0, min(1.0, u))
    if u <= 0.45:
        return 0.16 + 0.84 * (u / 0.45) ** 0.55
    t = (u - 0.45) / 0.55
    if t <= 0.55:
        return 1.0
    k = (t - 0.55) / 0.45
    return 1.0 - 0.70 * (k ** 1.35)


def build_frond(name, cfg, mat, length, width, arch_deg, margin=1,
                detail="hi", phase=0.0, parity=0):
    """一片香蕉叶的原始几何（局部坐标：叶根在原点，沿 +X 伸出，-Z 下垂）。

    * 中轴线按 [param arch_deg] 做"先微抬、再持续下垂"的拱形 —— 蕉叶典型的
      外翻弧线；**叶根固定在原点**，所以摆到假茎上时是真正"从茎顶长出来"。
    * 横截面按 LEAF_PROFILE 的 9 个站点排布：叶缘下垂 → 褶皱隆起 → 主脉最高，
      形成真蕉叶那种"纵向平行折痕 + 边缘下垂"的立体曲面。
    * 叶尖 20% 边缘碎裂、叶尖 12% 沿主脉纵向开裂 → 香蕉叶标志性的破叶。
    * 沿叶长的扭转(roll)烘进顶点坐标：叶根较竖、叶尖摊平朝上。
    * 边缘沿叶长做正弦扰动 → 叶缘是起伏的波浪线，不是直边。
    * **颜色逐面纯色**，而且整片叶子**只有 2 个绿色**：叶缘一条干净的暗边、
      主脉一条干净的亮脉、中间棋盘式交错（相邻面换色）—— 这就是 low-poly 叶子的
      "编织感"。层次靠"暗边多宽"和"交错相位"做，不再靠多加颜色。

    [param arch_deg] 是"叶轴累计下垂的总角度"，不是叶根处某个确定仰角，
    所以外层叶(大 arch)自然更外翻、更长。
    [param margin] 是暗边的宽度（几条横向带）。越宽 → 整片叶越暗（老叶）。
    [param parity] 是交错的相位偏移（让不同层的叶子花纹不一样）。
    """
    prof = LEAF_PROFILE[detail]
    sites = prof["sites"]
    droop = prof["droop"]
    n = len(sites)
    center = prof["center"]
    seg = prof["seg"]
    pet = cfg["petiole_frac"]
    arch = math.radians(arch_deg)
    r0, r1 = math.radians(cfg["leaf_roll0"]), math.radians(cfg["leaf_roll1"])
    tear_from = 0.80          # 边缘开始碎裂的位置
    split_from = 0.88         # 主脉开始纵向开裂的位置

    # ---- 中轴线：叶根在原点，先微抬再持续下垂 ----
    axis = []
    x = z = 0.0
    step = length / seg
    for i in range(seg + 1):
        axis.append((x, z))
        if i == seg:
            break
        a = arch * (0.16 - 1.25 * (((i + 0.5) / seg) ** 1.4))
        x += math.cos(a) * step
        z += math.sin(a) * step

    verts = []
    for i in range(seg + 1):
        t = i / seg
        ax, az = axis[i]
        if t < pet:
            # 叶柄段：窄、卷成 U 形槽（叶鞘）
            u = 0.0
            w = width * 0.16
            scoop = 1.55
            corr = 0.0
        else:
            u = (t - pet) / (1.0 - pet)
            w = width * blade_shape(u)
            # 叶缘沿叶长起伏 → 波浪状叶缘
            w *= 1.0 + 0.055 * math.sin(3.0 * math.pi * u + phase)
            scoop = 0.62 + 0.26 * (1.0 - u)      # 靠叶柄凹槽深、叶身浅
            corr = 0.55 + 0.75 * u                # 褶皱幅度向叶尖变大
        roll = r0 + (r1 - r0) * (max(0.0, u) ** 0.60)
        cr, sr = math.cos(roll), math.sin(roll)
        for j, q in enumerate(sites):
            off = abs(q - 0.5) * 2.0
            v = (q - 0.5) * w
            section = w * FOLD_SCALE * (EDGE_DROOP * (off ** 2.1) * scoop
                                       + droop[j] * corr)
            py = v * cr - section * sr
            pz = v * sr + section * cr
            verts.append((ax, py, az + pz))

    # ---- 面：整张叶身；叶尖部分按规则挖掉若干面 → 碎裂叶缘 / 纵向开裂 ----
    #      fmeta 记下每个面属于"哪一段 × 哪一横带"，后面按它取色。
    faces = []
    fmeta = []
    for i in range(seg):
        t_mid = (i + 0.5) / seg
        u_mid = max(0.0, (t_mid - pet) / (1.0 - pet))
        for j in range(n - 1):
            a = i * n + j
            quad = (a, a + 1, a + 1 + n, a + n)
            if u_mid > tear_from:
                # 边缘碎裂：隔段挖掉最外一列 → 锯齿状叶缘
                if j == 0 and (i % 2) == 0:
                    faces.append((quad[1], quad[2], quad[3]))
                    fmeta.append((i, j, u_mid))
                    continue
                if j == n - 2 and (i % 2) == 1:
                    faces.append((quad[0], quad[1], quad[2]))
                    fmeta.append((i, j, u_mid))
                    continue
            if u_mid > split_from:
                # 纵向开裂：主脉两侧交替挖掉最内一列 → 破叶
                if j == center - 1 and (i % 2) == 0:
                    faces.append((quad[1], quad[2], quad[3]))
                    fmeta.append((i, j, u_mid))
                    continue
                if j == center and (i % 2) == 1:
                    faces.append((quad[0], quad[1], quad[2]))
                    fmeta.append((i, j, u_mid))
                    continue
            faces.append(quad)
            fmeta.append((i, j, u_mid))

    # ---- 逐面纯色：横向色阶档位 × 沿叶长的棋盘交错 × 整片叶的档位偏移 ----
    # ---- 逐面纯色：整片叶子只有 2 个绿色，靠"怎么排"做出交错和层次 ----
    #   * 叶缘 = 深色（留一条干净的暗边）
    #   * 主脉 = 浅色（一条干净的亮脉）
    #   * 中间 = 棋盘式交错（相邻面换色）→ low-poly 叶子的"编织感"
    #   * margin 越大 → 暗边越宽 → 整片叶越暗（外层老叶用 2，内层新叶用 1）
    n_bands = n - 1
    cols = []
    for (i, j, u_mid) in fmeta:
        if j < margin or j >= n_bands - margin:
            col = PAL["leaf_dark"]                 # 叶缘：干净的暗边
        elif j == center - 1 or j == center:
            col = PAL["leaf_light"]                # 主脉：干净的亮脉
        else:
            col = (PAL["leaf_light"] if ((i + j + parity) % 2 == 0)
                   else PAL["leaf_dark"])           # 内部：交错
        cols.append(col)
    return build_object(name, verts, faces, cols, mat, per_face=True)


# ==================== 茎顶的"毛"：干枯纤维 + 直立短叶 ====================
def build_crown_fringe(cfg, mat):
    """茎顶一圈干枯的叶鞘纤维（老叶鞘分解出来的纤维），把光秃秃的茎顶盖住。

    每根是一条**粗壮**的三棱锥管（不是旧版那种头发丝粗的须），
    从茎顶往外、往上翘一点再往下垂，末端收成尖。
    """
    h = cfg["stalk_height"]
    r_top = cfg["stalk_r_top"]
    n = cfg["fringe"]
    rng = random.Random(cfg["seed"] + 991)
    verts, faces, cols = [], [], []
    top_t = 1.0

    for i in range(n):
        # 须根均匀铺一圈，再抖动一点，避免看起来像齿轮
        a = (i / float(n)) * math.tau + rng.uniform(-0.13, 0.13)
        # 起点全部贴着芦顶的圈（分布在芢侧会像碎木棒）
        t0 = top_t - rng.uniform(0.000, 0.030)
        origin, tangent, side = stalk_frame(cfg, t0)
        length = r_top * rng.uniform(0.85, 1.45)
        # 朝外 + 朝上，末端往下勾
        out_dir = (side * math.cos(a) + Vector((0.0, 0.0, 1.0)).cross(side) * math.sin(a)).normalized()
        up = 0.75 + 0.65 * rng.random()
        seg = 2
        w = r_top * rng.uniform(0.135, 0.185)
        for k in range(seg + 1):
            f = k / float(seg)
            dist = length * f
            # 越往外越往上翘，最后一段回勾一点
            lift = up * f - 0.55 * f * f
            p = origin + out_dir * dist + Vector((0.0, 0.0, h * 0.030)) * (lift * 4.5)
            taper = w * (1.0 - 0.82 * f)
            ring = []
            for s in range(3):
                aa = s / 3.0 * math.tau + a
                off = (side * math.cos(aa) + Vector((0.0, 0.0, 1.0)).cross(side) * math.sin(aa)) * taper
                ring.append(p + off)
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
        col = PAL["bark_light"] if (i % 2 == 0) else PAL["bark_dark"]
        cols.append(col)
        cols.append(col)
    return build_object("CrownFringe", verts, faces, cols, mat, per_face=True)


def build_crown_blades(cfg, mat):
    """茎顶直立的短叶 / 未展开的新叶苞：让顶端有"向上的生命感"，而不是一个平截面。"""
    n = cfg["crown_blades"]
    rng = random.Random(cfg["seed"] + 313)
    objs = []
    for i in range(n):
        az = 360.0 * i / float(n) + rng.uniform(-20.0, 20.0)
        # 越短的越靠外、越斜，形成一丛
        lo, hi = cfg.get("blade_short", (0.48, 1.08))
        short = lo + (hi - lo) * rng.random()
        ln = cfg["leaf_len"] * short
        sub = dict(cfg)
        sub["petiole_frac"] = 0.12
        sub["leaf_roll0"] = 80.0 - 25.0 * short      # 越长越摊开
        sub["leaf_roll1"] = 60.0 - 30.0 * short
        arch = 6.0 + 22.0 * short
        ob = build_frond("Blade_%d" % i, sub, mat, ln, ln * 0.22, arch, 1,
                         detail="mid", phase=rng.uniform(0.0, 6.0),
                         parity=i % 2)
        t0 = 0.985
        origin, _, _ = stalk_frame(cfg, t0)
        a = math.radians(az) + stalk_twist(cfg, t0)
        off = origin + Vector((math.cos(a) * cfg["stalk_r_top"] * 0.30,
                               math.sin(a) * cfg["stalk_r_top"] * 0.30, 0.0))
        pitch = math.radians(84.0 - 20.0 * short)
        rot = Matrix.Rotation(az, 4, 'Z') @ Matrix.Rotation(-pitch, 4, 'Y')
        v, f, c = place(ob, rot, tuple(off), per_face=True)
        bpy.data.objects.remove(ob, do_unlink=True)
        objs.append(build_object("Blade_%d" % i, v, f, c, mat, per_face=True))
    return objs


# ==================== 树冠布叶 ====================
def build_crown(cfg, mat):
    """叶柄从假茎顶端一段里放射长出，分 3 层：内层挺立、外层下垂，形成喷泉状树冠。

    叶柄起点沿假茎往下铺开（各层的 drop），所以树冠是"包"住茎顶的一丛，
    而不是全挤在一个平面上 —— 顶端因此不再光秃秃。
    """
    rng = random.Random(cfg["seed"] + 77)
    tiers = cfg["crown_tiers"]
    n_tiers = len(tiers)
    r_top = cfg["stalk_r_top"]
    objs = []
    for ti, tier in enumerate(tiers):
        count = tier["count"]
        for k in range(count):
            # 每层绕一圈，层与层之间错开半格 → 立体而不是一圈平铺
            az = (ti * 37.0 + k * (360.0 / count) + rng.uniform(-9.0, 9.0)) % 360.0
            sub = dict(cfg)
            sub["leaf_roll0"] = tier["roll0"]
            length = cfg["leaf_len"] * tier["len"] * rng.uniform(0.94, 1.08)
            width = cfg["leaf_width"] * tier["wid"] * rng.uniform(0.95, 1.05)
            # 外层叶更长，但叶柄抬角更低 → 大而外翻的树冠
            ob = build_frond("Frond_%02d" % len(objs), sub, mat, length, width,
                             tier["arch"], tier["margin"], detail="hi",
                             phase=rng.uniform(0.0, 6.28),
                             parity=tier["parity"])
            # 叶柄起点：沿弯曲中轴往下铺开，越外层越低
            t0 = 1.0 - tier["drop"] - (k % 3) * 0.012
            origin, _, _ = stalk_frame(cfg, t0)
            a = math.radians(az) + stalk_twist(cfg, t0)
            offset = origin + Vector((math.cos(a) * r_top * (0.55 + 0.20 * ti),
                                      math.sin(a) * r_top * (0.55 + 0.20 * ti), 0.0))
            pitch = math.radians(tier["pitch"])
            rot = Matrix.Rotation(az, 4, 'Z') @ Matrix.Rotation(-pitch, 4, 'Y')
            v, f, c = place(ob, rot, tuple(offset), per_face=True)
            bpy.data.objects.remove(ob, do_unlink=True)
            objs.append(build_object("Crown_%02d" % len(objs), v, f, c, mat, per_face=True))
    return objs


# ==================== 根出小苗 ====================
def build_sucker(name, cfg, mat, ang_deg, dist, scale, seed):
    """根出小苗：一段细假茎 + 3 片小叶（两片展开、一片是挺立的卷筒嫩叶）。"""
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
            # 底圈压到地面：整棵树的最低点严格是 z = 0
            p.z = max(0.0, p.z)
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
        # 小苗的假茎是绿的（就是一只小香蕉），不是干枝 → 用叶绿两档
        cols.append(PAL["leaf_light"] if (int(t * 4.0) % 2 == 0) else PAL["leaf_dark"])
    parts.append(build_object(name + "_Stem", verts, faces, cols, mat, per_face=True))

    # 小叶：前两片展开、第三片是挺立的卷筒嫩叶
    for j in range(3):
        leaf_az = ang_deg + 24.0 + j * 118.0 + rng.uniform(-14.0, 14.0)
        ln = (0.46 + 0.20 * rng.random()) * scale
        sub = dict(cfg)
        sub["petiole_frac"] = 0.26 if j < 2 else 0.44
        sub["leaf_roll0"] = 62.0 if j < 2 else 86.0
        sub["leaf_roll1"] = 6.0
        arch = 46.0 if j < 2 else 10.0
        leaf = build_frond(name + "_LeafSrc%d" % j, sub, mat, ln, ln * 0.40, arch, 1,
                           detail="lo", phase=rng.uniform(0.0, 6.0),
                           parity=j % 2)
        pitch = math.radians(30.0 + j * 4.0) if j < 2 else math.radians(84.0)
        rot = Matrix.Rotation(math.radians(leaf_az), 4, 'Z') @ Matrix.Rotation(-pitch, 4, 'Y')
        tip = base + z_dir * (sh * (0.50 + 0.14 * j))
        v, f, c = place(leaf, rot, tuple(tip), per_face=True)
        bpy.data.objects.remove(leaf, do_unlink=True)
        parts.append(build_object(name + "_Leaf%d" % j, v, f, c, mat, per_face=True))
    return parts


# ==================== 组装一棵树 ====================
def build_tree(cfg, render=True):
    random.seed(cfg["seed"])
    reset_scene()
    mat = make_vc_material("BananaTree", PAL["leaf_light"])

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
    # ⚠️ fit 必须贴着 fit_target：假茎是"先按米建、再整体缩放"的，
    #    所以 fit 变了 = 导出后的假茎半径和高度都变了 —— 而 banana_tree.gd 的
    #    bunch_outset=0.62 和自检 [11]"香蕉不插进假茎"都按这个剖面算的。
    target_fit = cfg.get("fit_target")
    if target_fit and abs(fit - target_fit) > 0.010:
        print("!! WARNING fit %.4f != fit_target %.4f —— 导出后的假茎半径/高度会变，"
              "自检 [11] 可能失败（调叶长/叶柄仰角把原始高度顶到 %.3f m）"
              % (fit, target_fit, cfg["target_height"] / target_fit))

    # ---------------- 自检 ----------------
    zs = [v.co.z for o in (stalk, leaves) for v in o.data.vertices]
    xs = [v.co.x for o in (stalk, leaves) for v in o.data.vertices]
    ys = [v.co.y for o in (stalk, leaves) for v in o.data.vertices]
    tris = sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in (stalk, leaves))
    verts = sum(len(o.data.vertices) for o in (stalk, leaves))
    stalk_zs = [v.co.z for v in stalk.data.vertices]
    # 假茎在每个高度上的最大半径（Godot 侧就是这么量的）
    prof = {}
    for v in stalk.data.vertices:
        key = round(v.co.z, 2)
        prof.setdefault(key, []).append(v)
    r_base = r_top = 0.0
    for key, pts in prof.items():
        cx = sum(p.co.x for p in pts) / len(pts)
        cy = sum(p.co.y for p in pts) / len(pts)
        r = max(math.hypot(p.co.x - cx, p.co.y - cy) for p in pts)
        if key < 0.10:
            r_base = max(r_base, r)
        if key > 0.95 * max(stalk_zs):
            r_top = max(r_top, r)
    scales = [max(abs(s) for s in ob.scale) for ob in (stalk, leaves)]
    print("SIZE CHECK style=%s" % cfg.get("_name", "?"))
    print("  height     %.3f m (target %.3f)" % (max(zs), cfg["target_height"]))
    print("  span       X %.2f  Y %.2f m" % (max(xs) - min(xs), max(ys) - min(ys)))
    print("  min z      %.4f m (must be 0)" % min(zs))
    print("  stalk top  %.3f m" % max(stalk_zs))
    print("  stalk r    base %.3f m  top %.3f m" % (r_base, r_top))
    print("  tris %d   verts %d   fit %.4f" % (tris, verts, fit))
    print("  nodes      %s / %s   scale=%s" % (
        stalk.name, leaves.name, ["%.3f" % s for s in scales]))

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
    # ⚠️ 视图变换必须用 Standard：Blender 默认的 AgX 会把高饱和的绿压成
    #    一片"发灰的橄榄绿"，low-poly 的块面感全看不出来（看猴子那套也是这么做的）。
    try:
        scene.view_settings.view_transform = 'Standard'
    except TypeError:
        pass

    world = bpy.data.worlds.new("PreviewWorld")
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.80, 0.86, 0.92, 1.0)
    bg.inputs[1].default_value = 1.0

    sun = bpy.data.objects.new("Sun", bpy.data.lights.new("SunL", 'SUN'))
    sun.data.energy = 2.3
    sun.data.angle = math.radians(12)
    sun.rotation_euler = (math.radians(56), 0.0, math.radians(38))
    scene.collection.objects.link(sun)
    fill = bpy.data.objects.new("Fill", bpy.data.lights.new("FillL", 'SUN'))
    fill.data.energy = 0.65
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
def _style_from_dir():
    """按所在目录名决定款式（banana-tree-tall / banana-tree-short）。

    这样每个目录里的脚本只生成"自己"那款 —— 旧版不传参数时会把两款都写进
    同一个目录，后一款直接把前一款的 .glb 覆盖掉。
    """
    name = os.path.basename(BASE_DIR).lower()
    if "tall" in name:
        return "tall"
    if "short" in name:
        return "short"
    return None


argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
wanted = [a for a in argv if a in STYLES]
if not wanted:
    dir_style = _style_from_dir()
    wanted = [dir_style] if dir_style else list(STYLES.keys())
do_render = "--nopreview" not in argv
for key in wanted:
    cfg = dict(STYLES[key])
    cfg["_name"] = key
    build_tree(cfg, render=do_render)
print("ALL_DONE", wanted)

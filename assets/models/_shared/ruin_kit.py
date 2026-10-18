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
# 一段墙的两个端面要能和另一段墙的端面**严丝合缝**地对上，靠三条硬约定：
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
#
# 错缝为什么能跨缝对上：
#   偶数层 off=0 → 首块从 xa 起、末块到 xb 止，砖缝正好落在接缝上（正确砌法）；
#   奇数层 off=bay_w/2 → 两端各是半块砖，相邻段拼起来就是"一整块砖 + 一道竖缝"。
#   两种情况都跟"镜像"无关：镜像只翻转 X 的方向，层奇偶性不变，
#   所以把相邻段镜像放置既增加了外观变化，又不会破坏接缝。
#
# 因此**换墙的尺寸（bay_m / 高度 / 压顶）时两个脚本要一起动**：
# 常量都从本文件导出，不要在各自的脚本里另写一份。

import math
import os

import bpy
import numpy as np
from mathutils import Vector

__all__ = [
    "srgb2lin", "PAL", "hash01", "lerp3", "shade",
    "MeshBuilder", "BOX_FACES", "box", "extrude_y",
    "clear_scene", "make_material", "make_materials",
    "build_wall_segment", "tile_layout",
    "PreviewRig", "setup_preview_helpers", "stitch_images",
    "WALL_BAY_M", "WALL_T_M", "WALL_H_M",
    "PLINTH_M", "PLINTH_OUT_M", "WALL_ROWS", "COPING_H_M", "COPING_OUT_M",
    "TILE_N",
]


# ==========================================================================
# 调色板（sRGB → 线性）
# ==========================================================================
def srgb2lin(c):
    c = np.asarray(c, dtype=float)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


PAL = {
    "stone_l": srgb2lin([0.66, 0.63, 0.55]),
    "stone_m": srgb2lin([0.55, 0.51, 0.44]),
    "stone_d": srgb2lin([0.40, 0.37, 0.32]),
    "stone_x": srgb2lin([0.29, 0.27, 0.24]),
    "wood_l": srgb2lin([0.51, 0.40, 0.28]),
    "wood_m": srgb2lin([0.39, 0.30, 0.21]),
    "wood_d": srgb2lin([0.27, 0.21, 0.15]),
    "iron_l": srgb2lin([0.40, 0.39, 0.38]),
    "iron_m": srgb2lin([0.30, 0.29, 0.29]),
    "rust": srgb2lin([0.47, 0.27, 0.14]),
    "rust_l": srgb2lin([0.60, 0.36, 0.18]),
    "rust_d": srgb2lin([0.30, 0.17, 0.10]),
    "moss_l": srgb2lin([0.44, 0.56, 0.25]),
    "moss_m": srgb2lin([0.31, 0.45, 0.19]),
    "moss_d": srgb2lin([0.20, 0.32, 0.13]),
    "leaf_m": srgb2lin([0.26, 0.42, 0.19]),
    "leaf_d": srgb2lin([0.18, 0.31, 0.14]),
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
# 破败矮墙（大门两翼 / 独立破墙共用同一份实现）
# ==========================================================================
def build_wall_segment(b, rng, xa, xb, *, t_m=WALL_T_M, h_m=WALL_H_M,
                       plinth_m=PLINTH_M, plinth_out_m=PLINTH_OUT_M,
                       rows=WALL_ROWS, coping_h_m=COPING_H_M,
                       coping_out_m=COPING_OUT_M, bay_m=WALL_BAY_M,
                       slot_name="Stone", tag=0.0,
                       decay=0.16, decay_slope=0.45, moss=0.20,
                       joint_ends=("start", "end"), tile_miss=0.20,
                       decay_end="end", gap_chance=0.75, gap_rows=6.5,
                       keep_rows=3.0):
    """在 [xa, xb] 上砌一段破败矮墙：基座 + 错缝砖墙 + 崩塌缺口 + 残缺压顶。

    joint_ends 里的 "start"/"end" 表示该端是**接缝端**：强制满高、压顶必留一片、
    基座与压顶在 X 方向不外扩 —— 这样另一段墙可以严丝合缝地接上（见文件头契约）。
    大门两翼用单个接缝端（朝拱门那端），独立破墙两段都用。

    decay_end 指定**哪一端更残破**（"end" / "start"）。墙头从这一端往另一端
    逐渐长高，所以两端接缝永远一样高，破败只发生在中段。

    gap_chance / gap_rows 控制"塌口"的几率与深浅：gap_rows 是塌口**削掉几层砖**
    （6.5 ≈ 削到只剩墙脚，2 = 只塌掉两层，墙还连成一片）。
    keep_rows 是普通残破最多能削掉几层（越大越破）。

    拼接用的模块要**小 keep_rows / 小 gap_rows**：一段墙如果中间塌得很深，
    复制几份拼起来就是一排柱子而不是一堵墙 —— 分段残破要靠"缺砖 / 缺瓦 / 苔藓"
    来表达，整体高度不要太起伏。

    返回墙头高度剖面 heights（便于自检 / 调试）。
    """
    if xb < xa:
        xa, xb = xb, xa
    S = b.slot(slot_name)
    y0, y1 = -t_m * 0.5, t_m * 0.5
    length = xb - xa
    j_start = "start" in joint_ends
    j_end = "end" in joint_ends
    flip = (decay_end == "start")

    # ---- 基座：X 两端严格切在 [xa, xb]，只朝 Y 外扩 ----
    box(b, xa, xb, y0 - plinth_out_m, y1 + plinth_out_m,
        0.0, plinth_m, S, {"top": shade(PAL["stone_m"], 0.4),
                           "side": shade(PAL["stone_d"], 0.5),
                           "bottom": PAL["stone_x"]})

    # ---- 墙头高度剖面：越靠近 decay_end 越残破，再挖一个明显的崩塌缺口 ----
    n_bay = max(2, int(round(length / bay_m)))
    bay_w = length / n_bay
    z0 = plinth_m
    row_h = (h_m - coping_h_m - plinth_m) / rows
    full_h = h_m - coping_h_m
    heights = []
    for i in range(n_bay):
        far = (n_bay - 1 - i) / (n_bay - 1.0) if flip else i / (n_bay - 1.0)
        h = full_h
        if rng.random() < decay + decay_slope * far:
            h -= row_h * rng.uniform(0.7, keep_rows)
        heights.append(max(z0 + row_h * 0.55, h))

    # 崩塌缺口：避开接缝端（否则接缝处会出现一个洞，拼接就断了），
    # 并且偏向 decay_end 那一侧 —— 残破要"越往外越厉害"。
    g_lo = 1 if j_start else 0
    g_hi = (n_bay - 2) if j_end else (n_bay - 1)
    if flip:
        g_lo, g_hi = (n_bay - 1 - g_hi), (n_bay - 1 - g_lo)
    if g_hi > g_lo and rng.random() < gap_chance:
        lo = max(g_lo, g_hi - max(1, int(n_bay * 0.45)))
        gap = rng.randrange(lo, g_hi + 1)
        gz = max(z0 + row_h * 0.55, full_h - row_h * gap_rows)
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

    def top_at(x):
        i = min(n_bay - 1, max(0, int((x - xa) / bay_w)))
        return heights[i]

    # ---- 墙身砖块（错缝：奇数层整体挪半块，块数 +1 兜住两端）----
    for k in range(rows):
        bz0 = z0 + k * row_h
        bz1 = bz0 + row_h
        off = 0.0 if k % 2 == 0 else bay_w * 0.5
        n = n_bay + (1 if k % 2 else 0)
        for i in range(n):
            cx0 = xa + i * bay_w - off
            cx1 = cx0 + bay_w
            if cx1 <= xa + 0.01 or cx0 >= xb - 0.01:
                continue
            # 截到墙的范围内（错缝时首尾两块被切短，接缝才是"砌"出来的）
            cx0, cx1 = max(cx0, xa), min(cx1, xb)
            zz1 = min(bz1, top_at(0.5 * (cx0 + cx1)))
            if zz1 <= bz0 + 0.04:
                continue
            c = lerp3(PAL["stone_d"], PAL["stone_m"], 0.2 + 0.55 * rng.random())
            if rng.random() < 0.26:
                c = lerp3(c, PAL["stone_x"], 0.42)
            if rng.random() < moss:
                c = lerp3(c, PAL["moss_m"], 0.5)
            if rng.random() < 0.10:
                c = lerp3(c, PAL["stone_l"], 0.35)
            box(b, cx0, cx1, y0, y1, bz0, zz1, S, shade(c, hash01(i, k, tag)))

    # ---- 塌口露出的内芯断面（深色 + 苔），做出"断面"的层次 ----
    for i in range(n_bay):
        if heights[i] < full_h - 0.02:
            box(b, xa + i * bay_w + 0.02, xa + (i + 1) * bay_w - 0.02,
                y0 + 0.03, y1 - 0.03, heights[i] - 0.04, heights[i], S,
                lerp3(PAL["stone_x"], PAL["moss_d"], 0.4))

    # ---- 压顶瓦片：逐片，部分缺失 / 残缺（接缝端必留一片，压顶脊才连得上）----
    n_tile, tile_w = tile_layout(length, bay_m)
    for i in range(n_tile):
        is_joint_tile = (i == 0 and j_start) or (i == n_tile - 1 and j_end)
        if not is_joint_tile and rng.random() < tile_miss:
            continue
        tx0 = xa + i * tile_w
        tx1 = tx0 + tile_w
        tz = full_h
        cx = 0.5 * (tx0 + tx1)
        if top_at(cx) < tz - 0.06:
            continue
        # 接缝那片压顶取**固定满厚度**：压顶高度本来就是随机的，
        # 但端头如果也随机，两段墙接起来就会在墙顶掉一个台阶。
        hh = coping_h_m if is_joint_tile else coping_h_m * (0.70 + 0.30 * rng.random())
        c = lerp3(PAL["wood_m"], PAL["wood_l"], 0.35 * rng.random())
        c = lerp3(c, PAL["moss_m"], 0.55) if rng.random() < 0.38 else lerp3(c, PAL["wood_d"], 0.28)
        box(b, tx0, tx1, y0 - coping_out_m, y1 + coping_out_m, tz, tz + hh, S,
            {"top": shade(c, hash01(i, tag, 9)),
             "side": shade(lerp3(c, PAL["wood_d"], 0.4), hash01(i, tag, 2)),
             "bottom": PAL["stone_x"]})
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
        bg.inputs[1].default_value = 0.95

        for nm, energy, rot, angle in [("Sun", 3.6, (52, 0, -118), 3.0),
                                       ("Fill", 0.9, (66, 0, 62), 22.0)]:
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

# Blender 建模脚本：Low-Poly 草丛（两款：尖叶草墩 + 圆润灌木草）
#
# 用法:
#   blender --background --python low_poly_grass.py                 # 两款都生成
#   blender --background --python low_poly_grass.py -- tuft         # 只生成尖叶草墩
#   blender --background --python low_poly_grass.py -- clump        # 只生成圆润灌木草
#   blender --background --python low_poly_grass.py -- --nopreview  # 不渲染预览图
#
# 产物（写入 assets/models/grass/）:
#   grass_tuft.blend  / grass_tuft.glb  / grass_tuft_preview.png
#   grass_clump.blend / grass_clump.glb / grass_clump_preview.png
#
# ---------------------------------------------------------------------------
# 造型说明（对着参考图做的，两款都刻意做得非常简单）
# ---------------------------------------------------------------------------
# 每片叶子 = 一条"折起来的带子"：左缘 / 中脊 / 右缘三个点一排，
# 中脊往外顶出一点形成 V 形折痕（grass 叶子的自然断面），
# 沿长度方向切 3~4 段，末端收敛成一个尖点。
# 所以一片叶子只有 10~14 个三角形，一整丛 200 个三角形上下。
#
# 两款的区别只在"叶子形状 + 排布 + 配色"：
#   * grass_tuft （左图）—— 细长、尖锐、向上抽，中心高外围倒伏，
#                          冷色深绿打底、叶尖泛黄绿。
#   * grass_clump（右图）—— 短宽、圆钝、团成一坨，
#                          亮暗对比更强，顶部大片叶子被照得很亮。
#
# ---------------------------------------------------------------------------
# 颜色分层（重点：不是单一绿色，而是把层次全烘进顶点色）
# ---------------------------------------------------------------------------
# 每个顶点的颜色由 5 层叠出来，所以一次 draw call 就有参考图那种层次：
#   1. 长度渐变：根部深绿 → 中段中绿 → 叶尖黄绿（每款各 5 个色标）
#   2. 断面明暗：中脊提亮、两侧叶缘压暗（V 形折痕的受光差异）
#   3. 根部环境光遮蔽：基部整体压到 ~0.4，往上渐亮，做出"丛底发黑"
#   4. 单叶随机深浅：每片叶子 ±15% 明暗，避免每片一样
#   5. 面朝向打光：按面法线与光照方向点乘再乘 0.72~1.08，
#      朝上的大面自然变亮、背光面变暗 —— 这就是参考图里那种
#      一块亮一块暗的低多边形块面感
#
# ---------------------------------------------------------------------------
# Godot 侧约定
# ---------------------------------------------------------------------------
# * 原点在根部 (0,0,0)，模型沿 +Z 生长，导出 yup 后在 Godot 里沿 +Y。
# * 颜色走顶点色 COLOR_0（材质里挂 Color Attribute 节点），
#   导出后 Godot 的 StandardMaterial3D 自动 vertex_color_use_as_albedo。
# * 全部面片 flat shading（硬边），保留低多边形的块面感。
import bpy
import bmesh
import math
import os
import random
import sys
from mathutils import Vector, Matrix

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = BASE_DIR


# ==================== 颜色工具 ====================
def srgb_to_linear(c):
    """sRGB -> 线性。顶点色 / glTF COLOR_0 都是线性空间。"""
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hex_lin(h):
    """'#RRGGBB' -> 线性空间的 (r, g, b)。"""
    h = h.lstrip("#")
    return tuple(srgb_to_linear(int(h[i:i + 2], 16) / 255.0) for i in (0, 2, 4))


def lerp(a, b, t):
    return a + (b - a) * t


def smoothstep(a, b, x):
    if b <= a:
        return 1.0 if x >= b else 0.0
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3.0 - 2.0 * t)


def sample_stops(stops, t):
    """stops = [(位置 0~1, (r,g,b)), ...] 线性插值取色。"""
    if t <= stops[0][0]:
        return stops[0][1]
    for i in range(len(stops) - 1):
        t0, c0 = stops[i]
        t1, c1 = stops[i + 1]
        if t <= t1:
            k = (t - t0) / max(1e-9, t1 - t0)
            return tuple(lerp(c0[j], c1[j], k) for j in range(3))
    return stops[-1][1]


# ==================== 场景 / 材质 ====================
def clear_scene():
    """清空当前场景（不碰用户偏好，避免把 MCP 插件一起重置掉）。"""
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.lights,
                 bpy.data.cameras, bpy.data.images):
        for item in list(coll):
            if item.users == 0:
                coll.remove(item)


def make_material(name):
    """顶点色材质：Color Attribute -> Principled Base Color。"""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Roughness"].default_value = 0.85
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = 0.15
    vcol = nt.nodes.new("ShaderNodeVertexColor")
    vcol.layer_name = "Col"
    vcol.location = (-320, 120)
    nt.links.new(vcol.outputs["Color"], bsdf.inputs["Base Color"])
    return mat


# ==================== 单片叶子 ====================
def add_blade(bm, vcol, base, azimuth, lean_deg, length, width, fold,
              twist_deg, segs, stops, rng, shade, ao_span):
    """往 bmesh 里加一片"折起来的带子"叶子，并记录每顶点的颜色。

    base      : 叶根世界坐标
    azimuth   : 倒伏方向（弧度）
    lean_deg  : 叶尖相对竖直方向的倾角（0=笔直向上，90=完全趴下）
    length    : 叶长
    width     : 叶根半宽
    fold      : 中脊顶出量（相对半宽的比例）
    twist_deg : 沿叶长累计扭转角（让叶片翻面，避免看起来像一条线）
    """
    az = Vector((math.cos(azimuth), math.sin(azimuth), 0.0))
    azx, azy = az.x, az.y
    side0 = Vector((-azy, azx, 0.0))          # 横向（叶片宽度方向）
    lean0 = math.radians(lean_deg * 0.22)     # 根部接近直立
    lean1 = math.radians(lean_deg)
    step = length / segs

    # 沿弧线积分出骨架点（叶片自然弯曲，不是一根直线）
    pts, dirs = [], []
    pos = Vector(base)
    for i in range(segs + 1):
        t = i / segs
        pts.append(pos.copy())
        ang = lean0 + (lean1 - lean0) * (t ** 1.30)
        d = Vector((math.sin(ang) * azx, math.sin(ang) * azy, math.cos(ang)))
        dirs.append(d)
        if i < segs:
            tm = (i + 0.5) / segs
            angm = lean0 + (lean1 - lean0) * (tm ** 1.30)
            pos += Vector((math.sin(angm) * azx, math.sin(angm) * azy,
                           math.cos(angm))) * step

    rings = []
    for i in range(segs):
        t = i / segs
        p = pts[i]
        d = dirs[i]
        # 扭转：横向向量绕生长轴旋转
        side = Matrix.Rotation(math.radians(twist_deg) * t, 4, d) @ side0
        nvec = d.cross(side).normalized()
        # 让折痕朝外（远离草丛中轴），受光更自然
        if nvec.dot(Vector((p.x, p.y, 0.0))) < 0.0:
            nvec = -nvec
        w = width * (1.0 - t ** 1.55)
        fold_amt = fold * w
        left = bm.verts.new(p - side * w)
        right = bm.verts.new(p + side * w)
        center = bm.verts.new(p + nvec * fold_amt)
        rings.append((left, center, right))
        for u, v in ((-1.0, left), (0.0, center), (1.0, right)):
            col = sample_stops(stops, t)
            edge = 1.06 if u == 0.0 else 0.88        # 第 2 层：中脊亮 / 叶缘暗
            ao = 0.40 + 0.60 * smoothstep(0.0, ao_span, t)   # 第 3 层：根部压暗
            k = edge * ao * shade                     # 第 4 层：单叶随机深浅
            vcol[v] = (col[0] * k, col[1] * k, col[2] * k)

    tip = bm.verts.new(pts[segs])
    tc = sample_stops(stops, 1.0)
    vcol[tip] = (tc[0] * 1.02 * shade, tc[1] * 1.02 * shade, tc[2] * 1.02 * shade)

    for i in range(segs - 1):
        a, b, c = rings[i]
        d, e, f = rings[i + 1]
        bm.faces.new((a, b, e, d))
        bm.faces.new((b, c, f, e))
    a, b, c = rings[-1]
    bm.faces.new((a, b, tip))
    bm.faces.new((b, c, tip))
    return len(rings) * 3 + 1


def finish_mesh(bm, vcol, name, mat, light_dir):
    """烘焙第 5 层：按面朝向打光，写进 loop 颜色，然后建对象。"""
    cl = bm.loops.layers.float_color.new("Col")
    for face in bm.faces:
        face.normal_update()
        n = face.normal
        lam = max(0.0, n.dot(light_dir))
        k = 0.72 + 0.36 * lam          # 朝光面 1.08，背光面 0.72
        for loop in face.loops:
            c = vcol[loop.vert]
            loop[cl] = (c[0] * k, c[1] * k, c[2] * k, 1.0)

    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    mesh.materials.append(mat)
    for poly in mesh.polygons:          # 硬边，保留低多边形块面
        poly.use_smooth = False
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


# ==================== 两款草的造型参数 ====================
# 颜色色标全部取自参考图采样（见文件顶部说明）
TUFT_STOPS = [
    (0.00, hex_lin("#2A3F2A")),   # 根部最暗
    (0.30, hex_lin("#3F6A3F")),
    (0.58, hex_lin("#557F3F")),
    (0.80, hex_lin("#7FAA3F")),
    (1.00, hex_lin("#AABF55")),   # 叶尖黄绿
]
CLUMP_STOPS = [
    (0.00, hex_lin("#3F553F")),
    (0.28, hex_lin("#3F6A3F")),
    (0.58, hex_lin("#557F3F")),
    (0.82, hex_lin("#7FAA3F")),
    (1.00, hex_lin("#AABF55")),
]

STYLES = {
    # 左图：尖叶草墩 —— 细长、尖锐、向上抽
    "tuft": dict(
        object_name="GrassTuft",
        stops=TUFT_STOPS,
        segs=4, fold=0.50, width_scale=1.0, ao_span=0.45,
        # (数量, 根半径min, 根半径max, 倾角min, 倾角max, 叶长min, 叶长max, 半宽)
        layers=[
            (7, 0.018, 0.050, 4.0, 18.0, 0.72, 0.82, 0.034),
            (7, 0.045, 0.090, 26.0, 44.0, 0.52, 0.68, 0.030),
            (5, 0.075, 0.120, 54.0, 76.0, 0.30, 0.48, 0.026),
        ],
        twist=44.0, seed=11,
    ),
    # 右图：圆润灌木草 —— 短宽、圆钝、团成一坨
    "clump": dict(
        object_name="GrassClump",
        stops=CLUMP_STOPS,
        segs=3, fold=0.52, width_scale=1.0, ao_span=0.50,
        layers=[
            # 中心补心：几片短叶堵住圆形轮廓正中的空洞
            (4, 0.004, 0.022, 2.0, 14.0, 0.24, 0.32, 0.060),
            (8, 0.030, 0.068, 10.0, 30.0, 0.30, 0.42, 0.072),
            (8, 0.062, 0.100, 38.0, 58.0, 0.26, 0.36, 0.080),
            (6, 0.082, 0.118, 60.0, 78.0, 0.24, 0.34, 0.070),   # 外圈下垂裙摆
        ],
        twist=70.0, seed=23,
    ),
}


def build_style(cfg):
    rng = random.Random(cfg["seed"])
    mat = make_material("grass_%s" % cfg["object_name"].lower())
    bm = bmesh.new()
    vcol = {}
    light_dir = Vector((-0.35, -0.45, 0.82)).normalized()

    for (count, r0, r1, lean0, lean1, len0, len1, half_w) in cfg["layers"]:
        for i in range(count):
            # 一圈铺开，再加一点抖动，避免看得出规律
            ang = (i / float(count)) * math.tau + rng.uniform(-0.22, 0.22)
            radius = rng.uniform(r0, r1)
            base = (math.cos(ang) * radius, math.sin(ang) * radius, 0.0)
            add_blade(
                bm, vcol,
                base=base,
                azimuth=ang,
                lean_deg=rng.uniform(lean0, lean1),
                length=rng.uniform(len0, len1),
                width=half_w * cfg["width_scale"] * rng.uniform(0.88, 1.12),
                fold=cfg["fold"] * rng.uniform(0.85, 1.15),
                twist_deg=cfg["twist"] * rng.uniform(-0.6, 1.0),
                segs=cfg["segs"],
                stops=cfg["stops"],
                rng=rng,
                shade=rng.uniform(0.86, 1.12),
                ao_span=cfg["ao_span"],
            )

    obj = finish_mesh(bm, vcol, cfg["object_name"], mat, light_dir)
    mesh = obj.data
    # 折痕会让最底下几个顶点掉到 z<0，夹回地面，保证根盘正好落在 y=0
    below = 0
    for v in mesh.vertices:
        if v.co.z < 0.0:
            v.co.z = 0.0
            below += 1
    if below:
        print("clamped %d verts to ground" % below)
    xs = [v.co.x for v in mesh.vertices]
    ys = [v.co.y for v in mesh.vertices]
    zs = [v.co.z for v in mesh.vertices]
    tris = sum(len(p.vertices) - 2 for p in mesh.polygons)
    print("STYLE %-12s height %.3f  span %.2f x %.2f  faces %d  tris %d  verts %d"
          % (obj.name, max(zs), max(xs) - min(xs), max(ys) - min(ys),
             len(mesh.polygons), tris, len(mesh.vertices)))
    return obj


# ==================== 导出 ====================
def export_style(cfg, render=True):
    obj = build_style(cfg)
    name = cfg["object_name"]
    stem = "grass_%s" % ("tuft" if name == "GrassTuft" else "clump")

    blend_path = os.path.join(OUT_DIR, stem + ".blend")
    bpy.ops.wm.save_as_mainfile(filepath=blend_path)

    glb_path = os.path.join(OUT_DIR, stem + ".glb")
    bpy.ops.export_scene.gltf(
        filepath=glb_path, export_format='GLB',
        export_vertex_color='MATERIAL', use_selection=False,
        export_apply=True, export_yup=True,
    )
    print("SAVED", glb_path)

    if render:
        render_preview(os.path.join(OUT_DIR, stem + "_preview.png"), 0.85)
    return obj


# ==================== 预览渲染 ====================
def render_preview(out_path, span_ratio=0.85, shot_count=4):
    """几个角度各渲一张横排拼起来，方便快速人工检查造型和配色。"""
    scene = bpy.context.scene
    for engine in ('BLENDER_EEVEE_NEXT', 'BLENDER_EEVEE', 'CYCLES'):
        try:
            scene.render.engine = engine
            break
        except TypeError:
            continue
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = 'PNG'
    scene.render.resolution_x = 620
    scene.render.resolution_y = 560
    scene.render.resolution_percentage = 100

    world = bpy.data.worlds.new("PreviewWorld")
    scene.world = world
    world.use_nodes = True
    bg = next(n for n in world.node_tree.nodes if n.type == 'BACKGROUND')
    bg.inputs[0].default_value = (0.82, 0.87, 0.90, 1.0)
    bg.inputs[1].default_value = 0.85

    sun = bpy.data.objects.new("Sun", bpy.data.lights.new("SunL", 'SUN'))
    sun.data.energy = 3.0
    sun.data.angle = math.radians(14)
    sun.rotation_euler = (math.radians(52), 0.0, math.radians(-42))
    scene.collection.objects.link(sun)
    fill = bpy.data.objects.new("Fill", bpy.data.lights.new("FillL", 'SUN'))
    fill.data.energy = 0.9
    fill.rotation_euler = (math.radians(72), 0.0, math.radians(150))
    scene.collection.objects.link(fill)

    cam_data = bpy.data.cameras.new("PrevCam")
    cam = bpy.data.objects.new("PrevCam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    cam_data.lens = 60.0

    meshes = [o for o in scene.objects if o.type == 'MESH']
    pts = [o.matrix_world @ v.co for o in meshes for v in o.data.vertices]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    target = (lo + hi) * 0.5
    span = max((hi - lo).x, (hi - lo).y, (hi - lo).z)

    shots = []
    for i in range(shot_count):
        ang = math.radians(30.0 + i * (360.0 / shot_count))
        elev = math.radians(16.0 if i % 2 == 0 else 34.0)
        dist = span * 2.05 * span_ratio
        pos = target + Vector((math.cos(ang) * math.cos(elev),
                               math.sin(ang) * math.cos(elev),
                               math.sin(elev))) * dist
        cam.location = pos
        cam.rotation_euler = (target - pos).to_track_quat('-Z', 'Y').to_euler()
        path = "/tmp/grass_shot_%d.png" % i
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
def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    do_render = "--nopreview" not in argv
    keys = [a for a in argv if a in STYLES]
    for key in (keys or list(STYLES.keys())):
        clear_scene()
        export_style(STYLES[key], render=do_render)


if __name__ == "__main__":
    main()
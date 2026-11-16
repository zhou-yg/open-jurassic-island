# Blender 建模脚本：岛屿植被地面（grass base）
#
# 用法:
#   blender --background --python island_grass_base.py
#   blender --background --python island_grass_base.py -- --nopreview
#
# 产物（写入 assets/models/grass/）:
#   island_grass_base.blend
#   island_grass_base.glb
#   island_grass_base_preview.png
#
# ---------------------------------------------------------------------------
# 它是什么
# ---------------------------------------------------------------------------
# 一块**和岛屿台面完全同形**的草地底板：上表面就是
# `assets/models/island/sky-island-basic.glb` 里那块平顶岩盘（节点 `Cubo_44-col`，
# 也就是 Godot 里带 `-col` 后缀、导入即 StaticBody3D 的那块）的轮廓，
# 底下压一层厚度塞进岩石里 —— 玩家 / 恐龙 / 草 / 树都站在这一层上面。
#
# 为什么不做成矩形：
#   岛面是**不规则的圆盘**（半径 29.5~34.7 m，56 个轮廓点，中间还有小缺口）。
#   做成矩形就会有一圈悬在岛外的草地（2026-11 删掉旧草毯就是因为这个）。
#   所以底板直接抄岛面的轮廓，一根草都不会长到岛外。
#
# 尺寸约定
# ---------------------------------------------------------------------------
# 源 GLB 的岛面轮廓（Godot 坐标，未缩放）：
#   X ∈ [-2.4173, 2.3837]   Z ∈ [-2.5304, 2.4456]   （长宽比 1.03645）
# `terrain.tscn` 里的 `IslandBase` 把整个岛放大 **13 倍**（62 m 的组件岛），
# 所以本脚本把轮廓乘 13 导出 —— 导出的 GLB **和组件岛同一尺度**，可以直接
# 摆在 `IslandBase` 旁边（顶面 y = 0，就是岛面高度）。
#
#   成品尺寸：X 62.41 m × Z 64.69 m（= 62.41 × 1.03645）
#
# Godot 侧 `components/island-grass-base.tscn` 会按"矩形宽"缩放它：
# 宽 = width，长 = width × 1.03645（固定比例，抄自岛面本身）。
import bpy
import bmesh
import math
import os
import random
import sys
from mathutils import Vector

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = BASE_DIR
SRC_GLB = os.path.normpath(os.path.join(BASE_DIR, "..", "island", "sky-island-basic.glb"))

# 组件岛里 IslandBase 的缩放（terrain.tscn）—— 导出件跟它同一尺度
ISLAND_SCALE = 13.0
# 底板厚度（米）：往下扎进岩石里，岛缘看不到"薄片"
THICKNESS = 0.60
# 底环内缩（米）：底面比顶面小一圈，藏进岩石体，不会在岛缘支出一圈绿边
RIM_INSET = 0.30
# 岛面轮廓的焊接容差（源 GLB 里同一个点被拆成好几个顶点）
WELD_DIST = 1e-4

# 草地底板配色：4 档绿（压过一点饱和度，跟岛上其它低多边形资产一个调子）
# 底板要**比草暗一档** —— 底板是从上往下看的满光照，草是侧着看的，
# 同一个绿色底板渲染出来会比草亮一大截，缝里看着像雪。
GREEN_STOPS = ["#22361F", "#284223", "#2E4D27", "#35592D"]


# ==================== 颜色工具 ====================
def srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hex_lin(h):
    h = h.lstrip("#")
    return tuple(srgb_to_linear(int(h[i:i + 2], 16) / 255.0) for i in (0, 2, 4))


PAL = [hex_lin(h) for h in GREEN_STOPS]


def value_noise(x, y, freq, seed):
    """便宜的二维值噪声（哈希 + 双线性），返回 0~1。"""
    def h(ix, iy):
        n = (ix * 374761393 + iy * 668265263 + seed * 1442695040888963407) & 0xFFFFFFFF
        n = (n ^ (n >> 13)) * 1274126177 & 0xFFFFFFFF
        return ((n ^ (n >> 16)) & 0xFFFF) / 65535.0

    fx, fy = x * freq, y * freq
    ix, iy = math.floor(fx), math.floor(fy)
    tx, ty = fx - ix, fy - iy
    tx = tx * tx * (3 - 2 * tx)
    ty = ty * ty * (3 - 2 * ty)
    a = h(ix, iy) * (1 - tx) + h(ix + 1, iy) * tx
    b = h(ix, iy + 1) * (1 - tx) + h(ix + 1, iy + 1) * tx
    return a * (1 - ty) + b * ty


# ==================== 场景 ====================
def clear_scene():
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.lights,
                 bpy.data.cameras, bpy.data.images):
        for item in list(coll):
            if item.users == 0:
                coll.remove(item)


def make_material(name):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Roughness"].default_value = 0.92
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = 0.10
    vcol = nt.nodes.new("ShaderNodeVertexColor")
    vcol.layer_name = "Col"
    vcol.location = (-320, 120)
    nt.links.new(vcol.outputs["Color"], bsdf.inputs["Base Color"])
    return mat


# ==================== 取岛面轮廓 ====================
def import_island():
    """导入源 GLB，返回台面（`-col`）网格对象。"""
    bpy.ops.import_scene.gltf(filepath=SRC_GLB)
    hits = [ob for ob in bpy.data.objects
            if ob.type == "MESH" and "-col" in ob.name]
    if not hits:
        raise RuntimeError("源 GLB 里没找到 `-col` 台面网格")
    return hits[0]


def boundary_loops(mesh):
    """返回网格的边界环（顶点索引列表的列表）。

    源 GLB 里同一个位置被拆成了好几个顶点（焊接前是 54 个三角、56 个点），
    所以先按 (x, y) 位置焊接，再数每条边被几个面用过 —— 只用一次的边就是边界。
    """
    verts = [v.co.copy() for v in mesh.vertices]
    # 位置 -> 新索引
    weld = {}
    remap = []
    for v in verts:
        key = (round(v.x, 4), round(v.y, 4))
        if key not in weld:
            weld[key] = len(weld)
        remap.append(weld[key])

    edge_count = {}
    for poly in mesh.polygons:
        ids = [remap[i] for i in poly.vertices]
        for k in range(len(ids)):
            a, b = ids[k], ids[(k + 1) % len(ids)]
            key = (a, b) if a < b else (b, a)
            edge_count[key] = edge_count.get(key, 0) + 1

    adj = {}
    for (a, b), cnt in edge_count.items():
        if cnt == 1:
            adj.setdefault(a, []).append(b)
            adj.setdefault(b, []).append(a)

    loops = []
    seen = set()
    for start in sorted(adj.keys()):
        if start in seen:
            continue
        loop = [start]
        seen.add(start)
        prev, cur = None, start
        while True:
            nxt = None
            for cand in adj.get(cur, []):
                if cand != prev and cand not in seen:
                    nxt = cand
                    break
            if nxt is None:
                break
            loop.append(nxt)
            seen.add(nxt)
            prev, cur = cur, nxt
        loops.append(loop)
    loops.sort(key=len, reverse=True)

    # 焊接后的顶点表（按首次出现顺序）
    welded = [None] * len(weld)
    for v in verts:
        key = (round(v.x, 4), round(v.y, 4))
        if welded[weld[key]] is None:
            welded[weld[key]] = v
    return loops, welded


# ==================== 建底板 ====================
def build_base(outline_xy, thickness, rim_inset):
    """outline_xy: 一圈 (x, y)（Blender 平面坐标，岛面平面）。"""
    n = len(outline_xy)
    cx = sum(p[0] for p in outline_xy) / n
    cy = sum(p[1] for p in outline_xy) / n

    bm = bmesh.new()
    top, bot = [], []
    for (x, y) in outline_xy:
        top.append(bm.verts.new((x, y, 0.0)))
        dx, dy = cx - x, cy - y
        d = math.hypot(dx, dy) or 1.0
        # 底环朝中心内缩 —— 侧壁是斜的，藏进岩石里
        bot.append(bm.verts.new((x + dx / d * rim_inset,
                                 y + dy / d * rim_inset, -thickness)))
    bm.verts.ensure_lookup_table()

    bm.faces.new(top)                              # 顶面（草地）
    bm.faces.new(list(reversed(bot)))              # 底面
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((top[i], bot[i], bot[j], top[j]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])

    # n 边形（岛面轮廓带小缺口）交给 Blender 自己三角化，比扇形更稳
    bmesh.ops.triangulate(bm, faces=bm.faces[:],
                          quad_method="BEAUTY", ngon_method="BEAUTY")
    bm.normal_update()
    return bm


def paint_ground(bm, mat, rng):
    """按噪声给每个三角面分一档绿，再叠一点逐面明暗差。"""
    bm.faces.ensure_lookup_table()
    cl = bm.loops.layers.float_color.new("Col")
    # 岛缘距离（用来给边缘加一点 AO 暗边）
    for face in bm.faces:
        c = face.calc_center_median()
        n = value_noise(c.x, c.y, 0.055, 1337)
        n2 = value_noise(c.x, c.y, 0.31, 99)
        tone = min(len(PAL) - 1, int(n * len(PAL)))
        col = PAL[tone]
        k = 0.96 + 0.08 * n2                      # 逐面 ±4% 明暗差
        r, g, b = col[0] * k, col[1] * k, col[2] * k
        for loop in face.loops:
            loop[cl] = (r, g, b, 1.0)
    mesh = bpy.data.meshes.new("IslandGrassBase")
    bm.to_mesh(mesh)
    bm.free()
    mesh.materials.append(mat)
    for poly in mesh.polygons:
        poly.use_smooth = False
    obj = bpy.data.objects.new("IslandGrassBase", mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


# ==================== 导出 ====================
def export(obj, render=True):
    blend_path = os.path.join(OUT_DIR, "island_grass_base.blend")
    bpy.ops.wm.save_as_mainfile(filepath=blend_path)

    glb_path = os.path.join(OUT_DIR, "island_grass_base.glb")
    bpy.ops.export_scene.gltf(
        filepath=glb_path, export_format='GLB',
        export_vertex_color='MATERIAL', use_selection=False,
        export_apply=True, export_yup=True,
    )
    print("SAVED", glb_path)
    if render:
        render_preview(os.path.join(OUT_DIR, "island_grass_base_preview.png"))
    return obj


# ==================== 预览渲染 ====================
def render_preview(out_path, shot_count=3):
    scene = bpy.context.scene
    for engine in ('BLENDER_EEVEE_NEXT', 'BLENDER_EEVEE', 'CYCLES'):
        try:
            scene.render.engine = engine
            break
        except TypeError:
            continue
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = 'PNG'
    scene.render.resolution_x = 760
    scene.render.resolution_y = 620
    scene.render.resolution_percentage = 100

    world = bpy.data.worlds.new("PreviewWorld")
    scene.world = world
    world.use_nodes = True
    bg = next(n for n in world.node_tree.nodes if n.type == 'BACKGROUND')
    bg.inputs[0].default_value = (0.82, 0.87, 0.90, 1.0)
    bg.inputs[1].default_value = 0.9

    sun = bpy.data.objects.new("Sun", bpy.data.lights.new("SunL", 'SUN'))
    sun.data.energy = 3.2
    sun.data.angle = math.radians(12)
    sun.rotation_euler = (math.radians(46), 0.0, math.radians(-38))
    scene.collection.objects.link(sun)

    cam_data = bpy.data.cameras.new("PrevCam")
    cam = bpy.data.objects.new("PrevCam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    cam_data.lens = 50.0

    meshes = [o for o in scene.objects if o.type == 'MESH']
    pts = [o.matrix_world @ v.co for o in meshes for v in o.data.vertices]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    target = (lo + hi) * 0.5
    span = max((hi - lo).x, (hi - lo).y, (hi - lo).z)

    shots = []
    # 第一个是俯视图（看形状对不对），后面是斜视图（看厚度）
    cams = [(0.0, 88.0), (38.0, 26.0), (215.0, 22.0)]
    for i, (ang, elev) in enumerate(cams[:shot_count]):
        a, e = math.radians(ang), math.radians(elev)
        dist = span * 2.8
        pos = target + Vector((math.cos(a) * math.cos(e),
                               math.sin(a) * math.cos(e),
                               math.sin(e))) * dist
        cam.location = pos
        cam.rotation_euler = (target - pos).to_track_quat('-Z', 'Y').to_euler()
        path = "/tmp/grass_base_shot_%d.png" % i
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

    clear_scene()
    island = import_island()
    loops, welded = boundary_loops(island.data)
    if not loops:
        raise RuntimeError("台面网格没有边界环")
    loop = loops[0]
    mw = island.matrix_world
    outline = [(mw @ welded[i]) for i in loop]
    top_z = sum(p.z for p in outline) / len(outline)

    # 搬到 Blender 平面坐标（XY），顶面落在 z=0
    outline_xy = [(p.x * ISLAND_SCALE, p.y * ISLAND_SCALE) for p in outline]
    print("OUTLINE pts=%d  source z=%.4f" % (len(outline_xy), top_z))

    # 清掉导入的岛，只留我们自己建的底板
    for ob in list(bpy.data.objects):
        if ob is not None:
            bpy.data.objects.remove(ob, do_unlink=True)

    bm = build_base(outline_xy, THICKNESS, RIM_INSET)
    mat = make_material("grass_island_ground")
    rng = random.Random(7)
    obj = paint_ground(bm, mat, rng)

    mesh = obj.data
    xs = [v.co.x for v in mesh.vertices]
    ys = [v.co.y for v in mesh.vertices]
    zs = [v.co.z for v in mesh.vertices]
    tris = sum(len(p.vertices) - 2 for p in mesh.polygons)
    print("BASE size X=%.2f Y=%.2f Z=%.2f  tris=%d verts=%d"
          % (max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs),
             tris, len(mesh.vertices)))
    print("BASE ratio Z/X = %.5f" % ((max(ys) - min(ys)) / (max(xs) - min(xs))))
    print("BASE top z = %.4f  bottom z = %.4f" % (max(zs), min(zs)))

    export(obj, render=do_render)


if __name__ == "__main__":
    main()

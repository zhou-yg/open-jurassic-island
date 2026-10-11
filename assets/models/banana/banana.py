# Blender 建模脚本：Low-Poly 单根香蕉（Bunch 的最小单元）
# 用法:
#   blender --background --python banana.py
#   blender --background --python banana.py -- --preview      # 额外渲染预览图
# 生成: banana.blend + banana.glb
#
# 为什么单独建一根香蕉：
#   香蕉树 / 香蕉串 / 香蕉道具都要用到香蕉，把它做成独立资产后，
#   在 Godot 里就能用「香蕉串组件」按参数拼出任意根数的一把，
#   再用「香蕉树组件」按参数挂若干把，不用为每种组合重新建模。
#
# 朝向约定（便于 Godot 摆放）：
#   原点 = 香蕉的蒂（与果轴相连的一端），挂在原点、向 -Z 生长并朝 +X 弯曲。
#   导出 GLB（Z-up → Y-up）后在 Godot 里即：原点在蒂、向 -Y 垂下、朝 +X 弯。
import bpy
import math
import os
import sys
from mathutils import Vector

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ==================== 参数区（想改香蕉造型改这里） ====================
BANANA_LENGTH = 0.55      # 香蕉长度（米），与树上果串里的单根一致
BANANA_RADIUS = 0.072     # 最粗处半径（细长才像香蕉，太粗会变成玉米）
BANANA_SEGMENTS = 6       # 沿长度的分段数（low-poly 关键：段数少才有硬折面）
BANANA_SIDES = 4          # 截面边数
BANANA_CURVE = 0.22       # 弯曲强度：越大越弯（每段方向偏转量）
BANANA_TIP_TAPER = 0.35   # 末端收尖程度

COLORS = {
    "banana":     (0.92, 0.78, 0.12),  # 香蕉黄
    "banana_tip": (0.30, 0.24, 0.08),  # 蒂 / 尖端的深色
}


def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.unit_settings.system = 'METRIC'


def make_material(name, color, roughness=0.85):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = roughness
    mat.diffuse_color = (*color, 1.0)
    return mat


def build_banana(mats):
    """
    一根带弯度的香蕉：沿弧线摆一串四边形截面，两端收尖。
    为了 low-poly 观感，只分 BANANA_SEGMENTS 段、BANANA_SIDES 边。
    另外把「蒂」和「尖端」两圈面单独赋深色材质，视觉上有头有尾。
    """
    segments = BANANA_SEGMENTS
    sides = BANANA_SIDES

    # 生长方向：从原点向 -Z，朝 +X 逐渐弯曲
    d = Vector((0.0, 0.0, -1.0))
    side = Vector((1.0, 0.0, 0.0))   # 弯曲所绕的侧向量
    step = BANANA_LENGTH / segments

    verts = []
    faces = []
    face_mats = []   # 每个面用哪个材质槽
    p = Vector((0.0, 0.0, 0.0))
    dir_now = d.copy()
    ring_centers = []

    for s in range(segments + 1):
        t = s / segments
        # 半径：中段最粗，两端收细
        # 半径包络：两端收细，末端收得更尖
        env = math.sin(math.pi * (0.10 + 0.90 * t)) ** 0.55
        tip = 1.0 - max(0.0, (t - 0.72) / 0.28) ** 1.6 * (1.0 - BANANA_TIP_TAPER)
        r = BANANA_RADIUS * env * tip + 0.004
        ring_centers.append(p.copy())
        for k in range(sides):
            a = math.pi * 2.0 * k / sides + math.pi / 4.0
            # 截面平面由 d 与 side 张成
            up = dir_now.cross(side).normalized()
            verts.append(tuple(p + up * (math.cos(a) * r) + side * (math.sin(a) * r)))
        p = p + dir_now * step
        dir_now = (dir_now + side * BANANA_CURVE).normalized()

    # 侧面
    for s in range(segments):
        for k in range(sides):
            a = s * sides + k
            b = s * sides + (k + 1) % sides
            c = (s + 1) * sides + (k + 1) % sides
            d2 = (s + 1) * sides + k
            faces.append((a, b, c, d2))
            # 首尾两段用深色，做出蒂与尖
            face_mats.append(1 if (s == 0 or s >= segments - 2) else 0)

    # 两端封口
    faces.append(tuple(reversed(range(sides))))
    face_mats.append(1)
    last = segments * sides
    faces.append(tuple(range(last, last + sides)))
    face_mats.append(1)

    mesh = bpy.data.meshes.new("Banana")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    ob = bpy.data.objects.new("Banana", mesh)
    bpy.context.scene.collection.objects.link(ob)
    ob.data.materials.append(mats["banana"])
    ob.data.materials.append(mats["banana_tip"])
    for poly, mi in zip(ob.data.polygons, face_mats):
        poly.material_index = mi
    return ob


def setup_preview():
    """搭一个等距视角的预览场景，返回临时物体列表（渲染完删掉）"""
    scene = bpy.context.scene
    try:
        scene.render.engine = 'BLENDER_EEVEE_NEXT'
    except Exception:
        scene.render.engine = 'BLENDER_EEVEE'
    scene.render.resolution_x = 700
    scene.render.resolution_y = 700
    scene.render.image_settings.file_format = 'PNG'

    world = bpy.data.worlds.new("PreviewWorld")
    scene.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.86, 0.90, 0.95, 1.0)

    helpers = []
    key = bpy.data.lights.new("Key", type='SUN')
    key.energy = 4.0
    key_ob = bpy.data.objects.new("Key", key)
    scene.collection.objects.link(key_ob)
    key_ob.rotation_euler = (math.radians(52), 0.0, math.radians(35))
    helpers.append(key_ob)

    fill = bpy.data.lights.new("Fill", type='SUN')
    fill.energy = 1.8
    fill_ob = bpy.data.objects.new("Fill", fill)
    scene.collection.objects.link(fill_ob)
    fill_ob.rotation_euler = (math.radians(66), 0.0, math.radians(215))
    helpers.append(fill_ob)

    cam_data = bpy.data.cameras.new("Cam")
    cam_data.lens = 60
    cam = bpy.data.objects.new("Cam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    helpers.append(cam)

    center = Vector((0.10, 0.0, -BANANA_LENGTH * 0.5))
    cam.location = center + Vector((0.85, -0.95, 0.35))
    direction = center - Vector(cam.location)
    cam.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
    return helpers


def render_preview(path):
    scene = bpy.context.scene
    scene.render.filepath = path
    try:
        scene.eevee.taa_render_samples = 64
    except Exception:
        pass
    bpy.ops.render.render(write_still=True)


# ==================== 主流程 ====================
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
WANT_PREVIEW = "--preview" in argv

reset_scene()
mats = {k: make_material(k, v) for k, v in COLORS.items()}

banana = build_banana(mats)

# 硬边着色 + 变换应用，保持和其他模型一致
for poly in banana.data.polygons:
    poly.use_smooth = False
bpy.ops.object.select_all(action='DESELECT')
banana.select_set(True)
bpy.context.view_layer.objects.active = banana
bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)

if WANT_PREVIEW:
    helpers = setup_preview()
    render_preview(f"{BASE_DIR}/banana_preview.png")
    for ob in helpers:
        bpy.data.objects.remove(ob, do_unlink=True)

bpy.ops.wm.save_as_mainfile(filepath=f"{BASE_DIR}/banana.blend")
bpy.ops.export_scene.gltf(
    filepath=f"{BASE_DIR}/banana.glb",
    export_format='GLB',
    export_apply=True,
    export_yup=True,
)

# ==================== 自检输出 ====================
xs = [v.co.x for v in banana.data.vertices]
ys = [v.co.y for v in banana.data.vertices]
zs = [v.co.z for v in banana.data.vertices]
print("DONE: banana built")
print("顶点 %d / 面 %d" % (len(banana.data.vertices), len(banana.data.polygons)))
print("包围盒: X %.3f  Y %.3f  Z %.3f" % (
    max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)))
print("蒂在原点，向 -Z 垂长 %.3f m，朝 +X 弯曲" % (max(zs) - min(zs)))
print("材质槽:", [m.name for m in banana.data.materials])
# Blender 建模脚本：Low-Poly 苹果树（树干 + 蓬松树冠 + 表面可见的红苹果）
# 用法: /Applications/Blender.app/Contents/MacOS/Blender --background --python low_poly_tree.py
# 生成: low_poly_tree.blend + low_poly_tree.glb（可直接用于 Godot）
#
# 关键点：苹果不是随便摆的坐标，而是用射线求出“树冠球体外表面”，
#        再把苹果贴在表面上，保证从任何角度看都不会被树叶球吞掉。
import bpy
import bmesh
import math
import random
from mathutils import Vector

random.seed(42)  # 固定随机种子：每次生成完全相同的树

OUT_DIR = "/Users/zhouyunge/Documents/godot/open-jurassic-island/assets/models"

# ==================== 参数区（想改造型改这里即可） ====================
TRUNK_HEIGHT = 2.70      # 树干高度（圆锥，底部更粗）
TRUNK_R_BOTTOM = 0.42    # 树干底部半径
TRUNK_R_TOP = 0.20       # 树干顶部半径

CROWN_CENTER = Vector((0.0, 0.0, 3.60))  # 树冠中心

# 树冠 = 一堆低面数二十面体球（center, radius, 材质名）
CROWN = [
    (Vector((0.00, 0.00, 3.60)), 1.45, "leaf_a"),  # 主体大团
    (Vector((0.95, 0.25, 3.05)), 0.85, "leaf_b"),
    (Vector((-0.90, 0.40, 3.20)), 0.80, "leaf_b"),
    (Vector((0.30, -0.95, 3.25)), 0.80, "leaf_b"),
    (Vector((-0.35, -0.70, 3.85)), 0.72, "leaf_c"),
    (Vector((0.65, 0.60, 4.20)), 0.70, "leaf_c"),
    (Vector((-0.50, -0.45, 4.25)), 0.66, "leaf_b"),
]

APPLE_R = 0.20           # 苹果半径
APPLE_INSET = 0.40       # 苹果中心相对叶面往内嵌的比例（0=刚好贴面，1=全嵌入）

# 苹果在树冠上的方向：(方位角°, 仰角°)，俯视一圈均匀分布
APPLE_DIRECTIONS = [
    (10, -8), (55, 18), (100, -22), (145, 6), (190, -14),
    (235, 22), (280, -26), (325, 8), (250, 45),
]

COLORS = {
    "trunk":   (0.32, 0.19, 0.10),  # 棕色树干
    "leaf_a":  (0.10, 0.38, 0.14),  # 深绿
    "leaf_b":  (0.16, 0.50, 0.18),  # 中绿
    "leaf_c":  (0.26, 0.60, 0.20),  # 亮绿
    "apple":   (0.72, 0.05, 0.04),  # 红苹果
    "stem":    (0.22, 0.13, 0.06),  # 苹果柄
    "apple_leaf": (0.30, 0.58, 0.20),  # 苹果小叶
}

# ==================== 1. 清空场景 ====================
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.unit_settings.system = 'METRIC'

# ==================== 2. 材质 ====================
def make_material(name, color):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.9
    mat.diffuse_color = (*color, 1.0)  # 视口/Workbench 颜色
    return mat

MATS = {k: make_material(k, v) for k, v in COLORS.items()}

# ==================== 3. 树干 + 树枝 ====================
def add_cone_between(name, base, direction, length, r1, r2, mat, vertices=7):
    """在 base 点沿 direction 生成一段锥体（树枝）"""
    d = Vector(direction).normalized()
    bpy.ops.mesh.primitive_cone_add(
        vertices=vertices, radius1=r1, radius2=r2, depth=length,
        location=base + d * (length / 2.0),
    )
    ob = bpy.context.active_object
    ob.name = name
    ob.rotation_euler = d.to_track_quat('Z', 'Y').to_euler()
    ob.data.materials.append(mat)
    return ob

# 主干：底部粗、顶部细的七边形圆锥，底面正好落在 z=0
bpy.ops.mesh.primitive_cone_add(
    vertices=7, radius1=TRUNK_R_BOTTOM, radius2=TRUNK_R_TOP,
    depth=TRUNK_HEIGHT, location=(0, 0, TRUNK_HEIGHT / 2.0),
)
trunk = bpy.context.active_object
trunk.name = "Trunk"
trunk.data.materials.append(MATS["trunk"])

# 两根树枝，从主干上部斜插进树冠，让造型不是“棒棒糖”
branch_a = add_cone_between(
    "Branch_A", Vector((0.0, 0.0, 2.35)), (0.75, 0.25, 0.65), 1.05,
    0.15, 0.06, MATS["trunk"],
)
branch_b = add_cone_between(
    "Branch_B", Vector((0.0, 0.0, 2.15)), (-0.65, -0.45, 0.62), 0.95,
    0.14, 0.06, MATS["trunk"],
)

# ==================== 4. 树冠：低面数二十面体球团 ====================
leaf_objects = []
for i, (center, radius, mat_key) in enumerate(CROWN, start=1):
    bpy.ops.mesh.primitive_ico_sphere_add(
        subdivisions=1, radius=radius, location=center,
    )
    ob = bpy.context.active_object
    ob.name = f"Leaves_{i:02d}_{mat_key}"
    # 轻微随机旋转 -> 每个球的面朝向不同，整体更像手工 low-poly
    ob.rotation_euler = (random.uniform(-0.35, 0.35),
                         random.uniform(-0.35, 0.35),
                         random.uniform(0, math.pi))
    ob.data.materials.append(MATS[mat_key])
    leaf_objects.append(ob)

# ==================== 5. 求树冠外表面（射线 × 球） ====================
def crown_surface_distance(direction):
    """从树冠中心沿 direction 射出，返回最外层球面交点距离；没有交点返回 None"""
    d = Vector(direction).normalized()
    best = None
    for center, radius, _ in CROWN:
        oc = CROWN_CENTER - center
        b = oc.dot(d)
        c = oc.dot(oc) - radius * radius
        disc = b * b - c
        if disc < 0.0:
            continue
        t = -b + math.sqrt(disc)  # 从树冠中心量起的出射距离
        if best is None or t > best:
            best = t
    return best

def apple_direction(azimuth_deg, elevation_deg):
    az = math.radians(azimuth_deg)
    el = math.radians(elevation_deg)
    return Vector((math.cos(el) * math.cos(az),
                   math.cos(el) * math.sin(az),
                   math.sin(el)))

# ==================== 6. 红苹果 + 苹果柄 + 小叶 ====================
def add_apple(name, location, normal):
    bpy.ops.mesh.primitive_ico_sphere_add(
        subdivisions=1, radius=APPLE_R, location=location,
    )
    ob = bpy.context.active_object
    ob.name = name
    ob.rotation_euler = normal.to_track_quat('Z', 'Y').to_euler()
    ob.data.materials.append(MATS["apple"])
    return ob

def add_apple_stem(name, location, normal, length=0.17):
    d = Vector(normal).normalized()
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=5, radius=0.028, depth=length,
        location=location + d * (length / 2.0),
    )
    ob = bpy.context.active_object
    ob.name = name
    ob.rotation_euler = d.to_track_quat('Z', 'Y').to_euler()
    ob.data.materials.append(MATS["stem"])
    return ob

def add_apple_leaf(name, location, normal, spin_deg):
    """一片朝外翘起的小尖叶（4 顶点手工网格，足够 low-poly）"""
    mesh = bpy.data.meshes.new(name)
    leaf_len, leaf_wid = 0.20, 0.065
    verts = [(0.0, 0.0, 0.0),
             (leaf_len * 0.45, leaf_wid, 0.0),
             (leaf_len, 0.0, 0.0),
             (leaf_len * 0.45, -leaf_wid, 0.0)]
    mesh.from_pydata(verts, [], [(0, 1, 2, 3)])
    mesh.update()
    ob = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(ob)
    ob.data.materials.append(MATS["apple_leaf"])
    # 先把叶片从柄的轴向往外翘起(X 轴 -60°)，再整体对齐苹果朝向，最后绕柄自转
    base = normal.to_track_quat('Z', 'Y').to_euler()
    ob.rotation_euler = (base.x + math.radians(-60),
                         base.y + math.radians(random.uniform(-12, 12)),
                         base.z + math.radians(spin_deg))
    ob.location = location
    return ob

apples, stems, apple_leaves = [], [], []
UP = Vector((0.0, 0.0, 1.0))
for i, (az, el) in enumerate(APPLE_DIRECTIONS, start=1):
    direction = apple_direction(az, el)
    t = crown_surface_distance(direction)
    if t is None:
        continue
    surface = CROWN_CENTER + direction * t
    # 往叶面里嵌一点，看起来是“长在树上”而不是漂浮的球
    center = surface - direction * (APPLE_R * APPLE_INSET)
    # 苹果柄不要沿着法线直挺挺朝外（会像把手），而是偏向上方 —— 像从上面的树枝垂下来
    stem_dir = (direction * 0.40 + UP * 0.80).normalized()
    apples.append(add_apple(f"Apple_{i:02d}", center, direction))
    stem_base = center + stem_dir * (APPLE_R * 0.80)
    stems.append(add_apple_stem(f"AppleStem_{i:02d}", stem_base, stem_dir))
    apple_leaves.append(
        add_apple_leaf(f"AppleLeaf_{i:02d}", stem_base + stem_dir * 0.155, stem_dir, i * 43)
    )

# ==================== 7. 按材质分组合并，层级干净 ====================
def join_objects(objs, name):
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
    merged.data.name = name  # 网格数据同名，Godot 里资源列表更干净
    return merged

trunk_group = join_objects([trunk, branch_a, branch_b], "Trunk")
leaves_group = join_objects(leaf_objects, "Leaves")
apples_group = join_objects(apples, "Apples")
stems_group = join_objects(stems, "AppleStems")
leaves_small_group = join_objects(apple_leaves, "AppleLeaves")

# ==================== 8. 收尾：应用变换 + flat shading + 原点归零 ====================
mesh_objects = [o for o in bpy.data.objects if o.type == 'MESH']
bpy.ops.object.select_all(action='DESELECT')
for ob in mesh_objects:
    ob.select_set(True)
bpy.context.view_layer.objects.active = mesh_objects[0]
bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)

for ob in mesh_objects:
    for poly in ob.data.polygons:
        poly.use_smooth = False  # 硬边，Low-Poly 的关键

# 把所有对象原点统一放到树根 (0,0,0)，方便在 Godot 里直接摆位
for ob in mesh_objects:
    ob.data.transform(ob.matrix_world)   # 把世界变换烘进网格
    ob.matrix_world.identity()

# ==================== 9. 保存 .blend 与 .glb ====================
blend_path = f"{OUT_DIR}/low_poly_tree.blend"
bpy.ops.wm.save_as_mainfile(filepath=blend_path)

glb_path = f"{OUT_DIR}/low_poly_tree.glb"
bpy.ops.export_scene.gltf(filepath=glb_path, export_format='GLB')

# ==================== 10. 自检输出 ====================
print("DONE: tree built")
print("Groups:", [(o.name, len(o.data.polygons)) for o in bpy.data.objects if o.type == 'MESH'])
print("Apples:", len(apples), "Stems:", len(stems), "AppleLeaves:", len(apple_leaves))
zs = [v.co.z for o in bpy.data.objects if o.type == 'MESH' for v in o.data.vertices]
print("Bounds Z: %.3f -> %.3f" % (min(zs), max(zs)))
print("Triangles:", sum(len(o.data.polygons) for o in bpy.data.objects if o.type == 'MESH'))
# Blender 建模脚本：Low-Poly 香蕉树（两种高矮款式）
# 用法:
#   blender --background --python low_poly_banana_tree.py                 # 两款都生成
#   blender --background --python low_poly_banana_tree.py -- tall         # 只生成高款
#   blender --background --python low_poly_banana_tree.py -- short        # 只生成矮款
# 生成: <款式目录>/low_poly_banana_tree.blend + .glb
#
# 结构：香蕉树不是"树干+树冠"，而是
#   - 假茎(pseudostem)：由叶鞘包裹而成的圆柱，分两段做出叶鞘层次，越往上越细
#   - 蕉叶：叶柄从假茎顶端一点放射状长出，叶片细长、沿主脉隆起、带下垂弧线，
#           叶面沿长轴扭转(roll)——不扭转的话从侧面看叶子就是一条线
#   - 根出小苗(sucker)：香蕉树标志性的丛生感
# 两种款式共用同一套生成函数，只改参数，造型语言保持一致。
import bpy
import math
import os
import random
import sys
from mathutils import Vector, Euler

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

COLORS = {
    "stalk":      (0.36, 0.40, 0.14),  # 假茎：偏黄绿的叶鞘
    "stalk_dark": (0.28, 0.33, 0.11),  # 假茎下半段阴影色
    "leaf_a":     (0.13, 0.42, 0.14),  # 叶背深绿
    "leaf_b":     (0.20, 0.55, 0.16),  # 叶面中绿
    "leaf_c":     (0.30, 0.65, 0.18),  # 亮绿
    "midrib":     (0.42, 0.52, 0.16),  # 主脉
}

# ==================== 款式参数 ====================
# 高款：细高，叶片大而多，像野生蕉
# 矮款：粗矮，叶片短而宽，像庭院矮蕉
STYLES = {
    "tall": {
        "dir": ".",   # 脚本与产物同目录
        "seed": 7,
        "stalk_height": 3.60,
        "stalk_r_bottom": 0.32,
        "stalk_r_top": 0.24,
        "suckers": 2,              # 根部小苗
        "leaf_count": 9,
        "leaf_len": 2.15,
        "leaf_width": 0.62,
        "leaf_droop": 72.0,        # 叶片末端下垂角度（度）
        "leaf_pitch": 42.0,        # 叶柄抬升角（度），越大越挺立
        "leaf_roll": 62.0,         # 叶面扭转角（度），决定侧面能看到多少叶面
        "leaf_tiers": 3,           # 叶片分几层螺旋排列
    },
    "short": {
        "dir": ".",   # 脚本与产物同目录
        "seed": 23,
        "stalk_height": 2.05,
        "stalk_r_bottom": 0.34,
        "stalk_r_top": 0.26,
        "suckers": 2,
        "leaf_count": 7,
        "leaf_len": 1.48,
        "leaf_width": 0.50,
        "leaf_droop": 74.0,        # 叶片末端下垂角度（度）
        "leaf_pitch": 36.0,        # 叶柄抬升角（度），越大越挺立
        "leaf_roll": 58.0,         # 叶面扭转角（度）
        "leaf_tiers": 2,
    },
}


# ==================== 通用工具 ====================
def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.unit_settings.system = 'METRIC'


def make_material(name, color, roughness=0.9):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = roughness
    mat.diffuse_color = (*color, 1.0)
    return mat


def new_mesh_object(name, verts, faces, mat):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    ob = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(ob)
    ob.data.materials.append(mat)
    return ob


def add_cone_between(name, base, direction, length, r1, r2, mat, vertices=6):
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


def join_objects(objs, name):
    objs = [o for o in objs if o is not None]
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


# ==================== 假茎 + 根出小苗 ====================
def build_stalk(cfg, mats):
    """假茎：两段锥体做出叶鞘的层次感，下粗上细"""
    h = cfg["stalk_height"]
    lower_h = h * 0.55
    upper_h = h - lower_h
    r_bot = cfg["stalk_r_bottom"]
    r_mid = (cfg["stalk_r_bottom"] + cfg["stalk_r_top"]) / 2.0
    r_top = cfg["stalk_r_top"]

    lower = add_cone_between("Stalk_Lower", Vector((0, 0, 0)), (0, 0, 1),
                             lower_h, r_bot * 1.12, r_mid, mats["stalk_dark"], vertices=8)
    upper = add_cone_between("Stalk_Upper", Vector((0, 0, lower_h)), (0, 0, 1),
                             upper_h, r_mid, r_top, mats["stalk"], vertices=8)

    parts = [lower, upper]

    # 叶鞘接缝：几道环绕的细环，让假茎不那么像一根光溜溜的管子
    for i in range(3):
        t = 0.18 + i * 0.22
        z = h * t
        r = r_bot + (r_top - r_bot) * t
        bpy.ops.mesh.primitive_cone_add(
            vertices=8, radius1=r * 1.06, radius2=r * 1.06, depth=0.055,
            location=(0, 0, z),
        )
        ring = bpy.context.active_object
        ring.name = f"Stalk_Ring_{i}"
        ring.data.materials.append(mats["stalk"])
        parts.append(ring)

    # 根出小苗（香蕉树标志性的"丛生"感）
    for i in range(cfg["suckers"]):
        ang = math.radians(70 + i * 137)
        lean = math.radians(12 + i * 4)
        base = Vector((math.cos(ang) * 0.30, math.sin(ang) * 0.30, 0.0))
        d = Vector((math.cos(ang) * math.sin(lean), math.sin(ang) * math.sin(lean), math.cos(lean)))
        sh = 0.62 + 0.12 * i
        parts.append(add_cone_between(f"Sucker_{i}", base, d, sh,
                                      r_bot * 0.46, r_top * 0.38, mats["stalk"], vertices=6))
        # 小苗上两片没展开的筒状幼叶
        for j, (t, lr) in enumerate(((0.62, 0.13), (0.85, 0.10))):
            tip = base + d * (sh * t)
            ld = (d + Vector((math.cos(ang + 0.6), math.sin(ang + 0.6), 0.35))).normalized()
            parts.append(add_cone_between(f"SuckerLeaf_{i}_{j}", tip, ld, lr * 3.2,
                                          lr, lr * 0.25, mats["leaf_b"], vertices=4))
    return parts


# ==================== 蕉叶 ====================
def build_leaf(name, base, azimuth_deg, cfg, mats, tier_index):
    """
    一片香蕉叶：沿长度方向采样若干截面，每段按 droop 角度逐渐下垂，
    中间做出一条主脉隆起，得到细长、带弧度的典型蕉叶。
    """
    segments = 6
    length = cfg["leaf_len"] * (1.0 if tier_index != 0 else 0.88)
    width = cfg["leaf_width"] * (1.0 if tier_index != 0 else 0.92)
    droop = math.radians(cfg["leaf_droop"])
    petiole = length * 0.30   # 叶柄：叶片前面一段没有叶肉的梗

    # 局部坐标系：叶根在原点，向 +X 伸出，-Z 方向下垂
    verts = []
    faces = []
    step = length / segments
    for s_i in range(segments + 1):
        t = s_i / segments
        # 沿叶长积分出弧线位置
        x = 0.0
        z = 0.0
        for q in range(s_i):
            a = -droop * (((q + 0.5) / segments) ** 1.9)
            x += math.cos(a) * step
            z += math.sin(a) * step
        # 叶柄段保持细窄，过了叶柄才开始展宽，末端收成尖
        if t < petiole / length:
            w = width * 0.16
            ridge = 0.0
        else:
            u = (t - petiole / length) / (1.0 - petiole / length)
            w = width * math.sin(math.pi * (0.18 + 0.82 * u)) ** 0.5
            ridge = 0.055 * width * math.sin(math.pi * u)
        # 叶片沿自身长轴做一点扭转（roll）：蕉叶出鞘后叶面会转向朝外，
        # 不扭转的话从侧面看就是一条线，几乎看不见叶子
        roll = math.radians(cfg["leaf_roll"]) * (0.35 + 0.65 * t)
        cr, sr = math.cos(roll), math.sin(roll)
        for wy, wz in ((-1.0, 0.0), (-0.45, ridge * 0.55), (0.0, ridge),
                       (0.45, ridge * 0.55), (1.0, 0.0)):
            py = wy * w * 0.5
            pz = wz
            verts.append((x, py * cr - pz * sr, z + py * sr + pz * cr))

    # 铺面：每个截面 5 个点，相邻截面对应点连成四边形
    for s_i in range(segments):
        for k in range(4):
            a = s_i * 5 + k
            b = s_i * 5 + k + 1
            c = (s_i + 1) * 5 + k + 1
            d = (s_i + 1) * 5 + k
            faces.append((a, b, c, d))

    ob = new_mesh_object(name, verts, faces, mats["leaf_b"])

    # 摆放：绕 Z 转方位角，再整体抬起一点（叶根朝上、叶尖下垂）
    # 绕 Y 轴负向旋转 = 叶尖抬起，绕 Z 轴分布方位角
    ob.rotation_euler = Euler((0.0, math.radians(-(cfg['leaf_pitch'] + tier_index * 5)),
                               math.radians(azimuth_deg)), 'XYZ')
    ob.location = base
    return ob


def build_leaf_set(cfg, mats):
    """
    香蕉叶的排布关键：所有叶子的叶柄都从假茎顶端（一个点）放射状长出，
    再通过不同的仰角/下垂度形成"喷泉"状树冠。
    """
    h = cfg["stalk_height"]
    n = cfg["leaf_count"]
    tiers = cfg["leaf_tiers"]
    golden = 137.5
    r_top = cfg["stalk_r_top"]
    crown = Vector((0.0, 0.0, h * 0.995))
    leaves = []
    for i in range(n):
        tier = i % tiers
        az = i * golden + tier * 31.0
        sub_cfg = dict(cfg)
        # 外圈叶子更下垂、更短，内圈更挺立
        sub_cfg["leaf_droop"] = cfg["leaf_droop"] * (1.0 + tier * 0.10)
        sub_cfg["leaf_pitch"] = cfg["leaf_pitch"] + tier * 7.0
        base = Vector((math.cos(math.radians(az)) * r_top * 0.85,
                       math.sin(math.radians(az)) * r_top * 0.85,
                       crown.z - tier * 0.05))
        leaves.append(build_leaf(f"Leaf_{i:02d}", base, az, sub_cfg, mats, tier))
    return leaves


# ==================== 单棵树的组装 ====================
def build_tree(cfg):
    random.seed(cfg["seed"])
    reset_scene()
    mats = {k: make_material(k, v) for k, v in COLORS.items()}

    stalk_parts = build_stalk(cfg, mats)
    leaf_parts = build_leaf_set(cfg, mats)

    stalk = join_objects(stalk_parts, "Stalk")
    leaves = join_objects(leaf_parts, "Leaves")

    mesh_objects = [o for o in bpy.data.objects if o.type == 'MESH']
    bpy.ops.object.select_all(action='DESELECT')
    for ob in mesh_objects:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = mesh_objects[0]
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)

    for ob in mesh_objects:
        for poly in ob.data.polygons:
            poly.use_smooth = False

    # 原点统一挪到根部 (0,0,0)，方便在 Godot 里直接摆位
    for ob in mesh_objects:
        ob.data.transform(ob.matrix_world)
        ob.matrix_world.identity()

    zs = [v.co.z for o in mesh_objects for v in o.data.vertices]
    xs = [v.co.x for o in mesh_objects for v in o.data.vertices]
    ys = [v.co.y for o in mesh_objects for v in o.data.vertices]
    out_dir = os.path.join(BASE_DIR, cfg["dir"])
    os.makedirs(out_dir, exist_ok=True)
    print("STYLE %s: height %.3f  footprint %.2f x %.2f  tris %d" % (
        cfg["dir"], max(zs),
        max(xs) - min(xs), max(ys) - min(ys),
        sum(len(o.data.polygons) for o in mesh_objects)))

    blend_path = os.path.join(out_dir, "low_poly_banana_tree.blend")
    bpy.ops.wm.save_as_mainfile(filepath=blend_path)
    glb_path = os.path.join(out_dir, "low_poly_banana_tree.glb")
    bpy.ops.export_scene.gltf(filepath=glb_path, export_format='GLB')
    print("SAVED", glb_path)


# 命令行参数: 无参数 = 两款都做；tall / short = 只做指定款式
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
wanted = [a for a in argv if a in STYLES] or list(STYLES.keys())
for key in wanted:
    build_tree(STYLES[key])

print("ALL_DONE", wanted)
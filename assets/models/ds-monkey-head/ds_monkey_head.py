# -*- coding: utf-8 -*-
"""
ds_monkey_head.py —— 猴子的「头」（只做头，不含身体）

参考图：assets/models/ds-monkey-head/reference.jpg（2x2 四视图：正 / 侧 / 3-4 / 背）
本脚本自成一体：参数、形体、分色规则全部从这张参考图上量出来，不引用仓库里另外几只猴
（low_poly_monkey / smart_lowpoly_monkey / ds_lowpoly_monkey / m3_monkey_head）
的任何代码或参数。

坐标与尺度
----------
* 单位：米（1 Blender unit = 1 m）。
* 面朝 **+Y**，+Z 向上（导出 glTF 后 Godot 里 −Z 向前）。
* 原点在**颅骨中心**（不是脚底）：头是挂在脖子上的零件，见 assets/AGENTS.md §2.5。
* 所有物体 scale = 1、rotation = 0，网格本身在世界坐标里。

为什么不用「均匀经纬球 + 逐面判色」
------------------------------------
实测：12x11 的经纬球上按面心方向判色，发际线那道「中间带尖」的 V 形会被量化成一整条
水平线（一个面环的高度 ≈ 12°，而 V 形本身只有 9° 的起伏），脸盘变成一块方板。
所以这里把**分色边界做成拓扑本身**：

* 环向分 10 列：脸盘 4 列居中 + 两侧各 3 列毛区；
* 脸盘那 4 列的左右边界就是「脸的侧边界」`SIDE_LIMIT(el)` —— 边界线随仰角收窄，
  所以下巴附近的脸盘比眼睛高度窄（参考图就是这样，不是一堵竖墙）；
* 第 4 条环线是**发际线**，它的仰角随方位角变化（正中压下 9°，两侧升回去），
  于是 V 形是真实的一条折线边，而不是染出来的锯齿。

其余形体要点
------------
* 颅骨不是椭球：上半颗头接近球，下半颗头（颧骨 / 下颌）鼓出去；前后深度不对称，
  脸下部整个「吻部」往前顶出 ≈ 0.05 m（量自侧视图）。
* 眼睛是**正面投影的贴片**：眼白 / 瞳孔 / 高光三层同心圆片，各抬 0.8 mm。
  贴片按正面射线贴回颅骨的**真实棱面**上（不是贴理想球面），正面看轮廓是正圆。
* 耳朵是「挖了坑的盘」：外圈厚棕毛边、里面凹进去的盘底是橘色。
* 头顶呆毛是一片带缺口的薄鳍，前上翘、尖端收薄。
"""

import bpy
import bmesh
import math
import os
import shutil

from mathutils import Vector
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
NAME = "ds_monkey_head"
GLB_PATH = os.path.join(HERE, NAME + ".glb")
BLEND_PATH = os.path.join(HERE, NAME + ".blend")
PREVIEW_PATH = os.path.join(HERE, NAME + "_preview.png")
RENDER_DIR = os.path.join(HERE, "_render_tmp")


# =====================================================================
# 0. 干净起点 + 公制
# =====================================================================
bpy.ops.wm.read_homefile(use_empty=True, use_factory_startup=True)
scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'
scene.unit_settings.scale_length = 1.0
scene.render.fps = 30

for act in list(bpy.data.actions):
    bpy.data.actions.remove(act)


# =====================================================================
# 1. 头部几何（共用模块）
# =====================================================================
# 头部（颅骨 / 脸盘 / 呆毛 / 耳朵 / 可动五官 / 两段表情）被两个资产复用，
# 所以放在 models/_shared/monkey_head.py，这里只负责"清场景 → 摆预览 → 导出"。
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "_shared"))
sys.modules.pop("monkey_head", None)      # 同一个 Blender 会话里重跑时要丢掉缓存
import monkey_head as MH
from monkey_head import *          # 头部常量 / 工具函数 / 已建好的零件

CLIPS = {"DSMonkey_Laugh": MH.CLIPS["Laugh"],
         "DSMonkey_Fear": MH.CLIPS["Fear"]}
MH.build_clips(CLIPS)

# =====================================================================
# 8. 自检
# =====================================================================
def report():
    xs, ys, zs, tris = [], [], [], 0
    for ob in MESHES:
        for v in ob.data.vertices:
            p = ob.matrix_world @ v.co
            xs.append(p.x); ys.append(p.y); zs.append(p.z)
        tris += sum(len(p.vertices) - 2 for p in ob.data.polygons)
        assert all(abs(s - 1.0) < 1e-6 for s in ob.scale), ob.name
        assert all(abs(r) < 1e-6 for r in ob.rotation_euler), ob.name
    print("=" * 68)
    print("DS MONKEY HEAD")
    for ob in MESHES:
        print("  %-16s verts %4d  faces %4d  %s" %
              (ob.name, len(ob.data.vertices), len(ob.data.polygons),
               [m.name for m in ob.data.materials]))
    print("  bbox  X %.3f  Y %.3f  Z %.3f m" %
          (max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)))
    print("  z %.4f .. %.4f   tris %d" % (min(zs), max(zs), tris))
    print("=" * 68)
    return max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)


SX, SY, SZ = report()


# =====================================================================
# 9. 预览（2x2 四视图，Standard 视图变换）
# =====================================================================
def setup_preview():
    world = bpy.data.worlds.new("DSWorld")
    world.use_nodes = True
    bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs[0].default_value = (0.78, 0.78, 0.78, 1.0)
    bg.inputs[1].default_value = 0.32
    scene.world = world

    def add_area(name, loc, energy, size):
        ld = bpy.data.lights.new(name, 'AREA')
        ld.energy = energy
        ld.color = (1.0, 0.97, 0.93)
        ld.size = size
        ob = bpy.data.objects.new(name, ld)
        bpy.context.collection.objects.link(ob)
        ob.location = loc
        ob.rotation_euler = (Vector((0.0, 0.0, 0.02)) - Vector(loc)) \
            .to_track_quat('-Z', 'Y').to_euler()
        return ob

    add_area("DSKey", (1.7, 1.9, 2.1), 120.0, 1.6)
    add_area("DSFill", (-2.0, 1.2, 0.2), 40.0, 2.4)
    add_area("DSRim", (0.3, -2.2, 1.2), 40.0, 1.4)

    cam_data = bpy.data.cameras.new("DSPreviewCam")
    cam_data.type = 'ORTHO'
    cam_data.ortho_scale = 0.455
    cam = bpy.data.objects.new("DSPreviewCam", cam_data)
    bpy.context.collection.objects.link(cam)
    scene.camera = cam

    try:
        scene.render.engine = 'BLENDER_EEVEE'
    except TypeError:
        try:
            scene.render.engine = 'BLENDER_EEVEE_NEXT'
        except TypeError:
            pass
    scene.render.film_transparent = False
    scene.view_settings.view_transform = 'Standard'
    scene.view_settings.look = 'None'
    scene.render.resolution_x = 640
    scene.render.resolution_y = 560
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    if hasattr(scene, "eevee") and hasattr(scene.eevee, "taa_render_samples"):
        scene.eevee.taa_render_samples = 48
    return cam


def render_views(cam):
    import numpy as np
    scene.render.resolution_x = 640
    scene.render.resolution_y = 560
    if not os.path.isdir(RENDER_DIR):
        os.makedirs(RENDER_DIR)
    views = [("front", 0.0), ("side", -90.0), ("back", 180.0), ("q34", -38.0)]
    dist = 3.0
    target = Vector((0.0, 0.0, 0.008))
    paths = []
    for name, az_deg in views:
        az = math.radians(az_deg)
        cam.location = Vector((math.sin(az) * dist, math.cos(az) * dist, 0.02))
        cam.rotation_euler = (target - cam.location).to_track_quat('-Z', 'Y').to_euler()
        path = os.path.join(RENDER_DIR, "view_%s.png" % name)
        scene.render.filepath = path
        bpy.ops.render.render(write_still=True)
        paths.append(path)

    W, H = scene.render.resolution_x, scene.render.resolution_y
    buf = np.ones((H * 2, W * 2, 4), dtype=np.float32)
    for i, path in enumerate(paths):
        img = bpy.data.images.load(path, check_existing=False)
        a = np.array(img.pixels[:], dtype=np.float32).reshape(H, W, 4)
        bpy.data.images.remove(img)
        r, c = divmod(i, 2)
        buf[(1 - r) * H:(1 - r) * H + H, c * W:(c + 1) * W] = a
    out = bpy.data.images.new("ds_monkey_head_preview", W * 2, H * 2, alpha=False)
    out.pixels = buf.ravel().tolist()
    out.filepath_raw = PREVIEW_PATH
    out.file_format = 'PNG'
    out.save()
    shutil.rmtree(RENDER_DIR, ignore_errors=True)   # 单视图是中间产物
    print("preview ->", PREVIEW_PATH)


EXPR_PREVIEW_PATH = os.path.join(HERE, NAME + "_expressions.png")


def render_expressions(cam):
    """表情接触表：静止 / 笑（第 19 帧）/ 惊恐（第 3 帧）"""
    import numpy as np
    if not os.path.isdir(RENDER_DIR):
        os.makedirs(RENDER_DIR)
    scene.render.resolution_x = 520
    scene.render.resolution_y = 600
    az = math.radians(-22.0)
    cam.location = Vector((math.sin(az) * 3.0, math.cos(az) * 3.0, 0.03))
    cam.rotation_euler = (Vector((0.0, 0.0, 0.004)) - cam.location) \
        .to_track_quat('-Z', 'Y').to_euler()

    keys = dict(CLIPS["DSMonkey_Laugh"][1])
    fkeys = dict(CLIPS["DSMonkey_Fear"][1])
    shots = [("rest", {}), ("laugh", keys[3]), ("fear", fkeys[3])]
    paths = []
    for tag, pose in shots:
        apply_pose(pose)
        path = os.path.join(RENDER_DIR, "expr_%s.png" % tag)
        scene.render.filepath = path
        bpy.ops.render.render(write_still=True)
        paths.append(path)
    apply_pose({})

    W, H = scene.render.resolution_x, scene.render.resolution_y
    buf = np.ones((H, W * len(paths), 4), dtype=np.float32)
    for i, path in enumerate(paths):
        img = bpy.data.images.load(path, check_existing=False)
        a = np.array(img.pixels[:], dtype=np.float32).reshape(H, W, 4)
        bpy.data.images.remove(img)
        buf[:, i * W:(i + 1) * W] = a
    shutil.rmtree(RENDER_DIR, ignore_errors=True)
    out = bpy.data.images.new("ds_monkey_head_expressions", W * len(paths), H, alpha=False)
    out.pixels = buf.ravel().tolist()
    out.filepath_raw = EXPR_PREVIEW_PATH
    out.file_format = 'PNG'
    out.save()
    print("expressions ->", EXPR_PREVIEW_PATH)


cam = setup_preview()
render_views(cam)
render_expressions(cam)

# =====================================================================
# 10. 保存 .blend / 导出 .glb
# =====================================================================
bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH)

bpy.ops.object.select_all(action='DESELECT')
for ob in MESHES:
    ob.select_set(True)
bpy.context.view_layer.objects.active = head
try:
    bpy.ops.export_scene.gltf(
        filepath=GLB_PATH,
        export_format='GLB',
        use_selection=True,
        export_apply=True,
        export_yup=True,
        export_animations=True,
        export_animation_mode='ACTIONS',
        export_merge_animation='NLA_TRACK',
        export_cameras=False,
        export_lights=False,
    )
    print("glb ->", GLB_PATH)
except Exception as exc:            # MCP 沙箱里 bpy.context 没有 active_object，会走到这里
    print("!! GLB 导出失败（在 Blender 界面里跑脚本不会有这个问题）:", exc)
print("SIZE CHECK: X %.3f  Y %.3f  Z %.3f" % (SX, SY, SZ))

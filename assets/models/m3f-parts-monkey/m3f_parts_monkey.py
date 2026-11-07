# -*- coding: utf-8 -*-
"""m3f-parts-monkey —— 用**零件**拼出来的整只猴（最终版）

参考图：assets/models/ds-monkey-body/reference.png（2×2 四视图，基准 `simple-lowpoly-monkey_bg.png`）

三块零件拼起来：
  ① 头   —— `models/_shared/monkey_head.py`（共用头，圆脸 + 面罩隆起 + 2 段表情）
  ② 身   —— 本脚本现建的车削躯干（比 ds-monkey-body 再宽一档，橘色肚皮一大片）
  ③ 四肢 —— `models/ds-monkey-trunk/ds_monkey_trunk.py`（左右严格对称的手 / 脚 / 尾巴）

产物：
  m3f_parts_monkey.glb        一个网格层级 + 4 段动画（头的 Laugh/Fear + 身体的 Idle/Sit）
  m3f_parts_monkey.blend
  m3f_parts_monkey_preview.png  四视图
  m3f_parts_monkey_anim.png     接触表

规矩见 assets/AGENTS.md §1（米制、scale 恒 1、原点在摆放锚点）。
"""
import bpy, bmesh, math, os, sys
import numpy as np
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS = os.path.dirname(HERE)
SHARED = os.path.join(MODELS, "_shared")
TRUNK = os.path.join(MODELS, "ds-monkey-trunk")

PREFIX = "M3FPartsMonkey"
HEAD_SCALE = 1.05              # 头：参考图颅宽 0.300 m，整体按 1.05 挂到脖子上
HEAD_C_Z = 0.420               # 颅心离地高度
NECK_Z = 0.300                 # 头节点（脖子的转轴）离地高度

BLEND_PATH = os.path.join(HERE, "m3f_parts_monkey.blend")
GLB_PATH = os.path.join(HERE, "m3f_parts_monkey.glb")
PREVIEW_PNG = os.path.join(HERE, "m3f_parts_monkey_preview.png")
ANIM_PNG = os.path.join(HERE, "m3f_parts_monkey_anim.png")

# 关节锚点（世界坐标，+Z 向上）
SHOULDER_R = Vector((0.132, 0.000, 0.238))
HIP_R = Vector((0.072, 0.000, 0.142))
TAIL_BASE = Vector((0.000, -0.078, 0.134))

PAL = {
    "fur":      (0.478, 0.271, 0.153),   # #7A4527 身体的棕
    "fur_light": (0.541, 0.322, 0.200),  # #8A5233 头盖（浅一档）
    "fur_dark": (0.306, 0.173, 0.114),   # #4E2C1D
    "tan":      (0.859, 0.659, 0.431),   # #DBA86E 脸 / 肚皮
    "tan_deep": (0.788, 0.561, 0.341),   # #C98F57 手掌 / 脚掌
}
ROUGH = {"fur": 0.72, "fur_light": 0.72, "fur_dark": 0.74, "tan": 0.70, "tan_deep": 0.70}
MATS = {}
MAT_ORDER = ["fur", "fur_light", "fur_dark", "tan", "tan_deep"]
MAT_INDEX = {n: i for i, n in enumerate(MAT_ORDER)}

# 躯干剖面（z, 半宽 rx, 半深 ry）—— 比 ds-monkey-body 宽一档，贴合参考图的"胖身子"
TORSO_PROFILE = [
    (0.095, 0.098, 0.082),
    (0.125, 0.126, 0.100),
    (0.165, 0.135, 0.108),
    (0.205, 0.132, 0.106),
    (0.245, 0.118, 0.098),
    (0.275, 0.090, 0.080),
    (0.295, 0.052, 0.050),
]
TORSO_C = Vector((0.0, 0.0, 0.195))
BELLY_AZ = 1.05                # 肚皮：正面 ±60° 以内
BELLY_Z = (0.118, 0.268)       # 肚皮的高度区间


# =====================================================================
# 0. 零件：① 四肢（它的 import 会清空场景，先导它）② 共用头
# =====================================================================
sys.path.insert(0, TRUNK)
import ds_monkey_trunk as TR          # STANDALONE=False → 只建几何，不导出

sys.path.insert(0, SHARED)
sys.modules.pop("monkey_head", None)
import monkey_head as MH              # 共用头（不���场景，只往上加物体）

# 头的小零件立刻改名（后面拼片段表要用新名字）
for ob in MH.MESHES:
    ob.name = PREFIX + "_" + ob.name.replace("DSMonkey", "")

scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'


# =====================================================================
# 1. 材质
# =====================================================================
def lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

def make_materials():
    for key in MAT_ORDER:
        rgb = PAL[key]
        m = bpy.data.materials.new(PREFIX + "_" + key)
        m.use_nodes = True
        bsdf = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
        bsdf.inputs["Base Color"].default_value = tuple(lin(c) for c in rgb) + (1.0,)
        bsdf.inputs["Roughness"].default_value = ROUGH[key]
        MATS[key] = m
make_materials()


# =====================================================================
# 2. 躯干（车削）+ 橘色肚皮（逐面换材质）
# =====================================================================
def build_torso():
    verts, faces, slots = [], [], []
    cols = 12
    rings = []
    for (z, rx, ry) in TORSO_PROFILE:
        idx = []
        for k in range(cols):
            a = 2.0 * math.pi * k / cols
            idx.append(len(verts))
            verts.append(Vector((rx * math.sin(a), ry * math.cos(a), z)))
        rings.append(idx)
    for j in range(len(rings) - 1):
        for k in range(cols):
            k2 = (k + 1) % cols
            faces.append((rings[j][k], rings[j][k2],
                          rings[j + 1][k2], rings[j + 1][k]))
    # 顶盖
    top = len(verts)
    verts.append(Vector((0.0, 0.0, TORSO_PROFILE[-1][0] + 0.010)))
    for k in range(cols):
        faces.append((rings[-1][k], rings[-1][(k + 1) % cols], top))
    # 底盖
    bot = len(verts)
    verts.append(Vector((0.0, 0.0, TORSO_PROFILE[0][0] - 0.030)))
    for k in range(cols):
        faces.append((bot, rings[0][(k + 1) % cols], rings[0][k]))

    # 逐面定材质：正面 + 高度区间内 = 橘色肚皮，其余是棕毛
    for i, f in enumerate(faces):
        c = Vector((0.0, 0.0, 0.0))
        for vi in f:
            c += verts[vi]
        c /= len(f)
        d = c - TORSO_C
        az = math.atan2(d.x, d.y)
        if (d.y > 0.0 and abs(az) < BELLY_AZ
                and BELLY_Z[0] <= c.z <= BELLY_Z[1]):
            slots.append(MAT_INDEX["tan"])
        else:
            slots.append(MAT_INDEX["fur"])
    me = bpy.data.meshes.new(PREFIX + "_Torso")
    me.from_pydata([tuple(v) for v in verts], [], [f for f in faces])
    me.validate()
    for key in MAT_ORDER:
        me.materials.append(MATS[key])
    for i, poly in enumerate(me.polygons):
        poly.material_index = slots[i]
        poly.use_smooth = False
    ob = bpy.data.objects.new(PREFIX + "_Torso", me)
    scene.collection.objects.link(ob)
    return ob


def build_neck():
    """脖子：短管 + 球，正好顶到下巴下面。"""
    verts, faces = [], []
    r0, r1, z0, z1 = 0.052, 0.046, 0.285, 0.345
    cols = 10
    rings = []
    for (r, z) in ((r0, z0), (r1, z1)):
        idx = []
        for k in range(cols):
            a = 2.0 * math.pi * k / cols
            idx.append(len(verts))
            verts.append(Vector((r * math.sin(a), r * math.cos(a), z)))
        rings.append(idx)
    for k in range(cols):
        k2 = (k + 1) % cols
        faces.append((rings[0][k], rings[0][k2], rings[1][k2], rings[1][k]))
    top = len(verts)
    verts.append(Vector((0.0, 0.0, z1 + 0.018)))
    for k in range(cols):
        faces.append((rings[1][k], rings[1][(k + 1) % cols], top))
    me = bpy.data.meshes.new(PREFIX + "_Neck")
    me.from_pydata([tuple(v) for v in verts], [], faces)
    me.validate()
    me.materials.append(MATS["fur"])
    ob = bpy.data.objects.new(PREFIX + "_Neck", me)
    scene.collection.objects.link(ob)
    return ob


torso = build_torso()
neck = build_neck()


# =====================================================================
# 3. 头：共用头缩放 + 摆到脖子上
# =====================================================================
head_root = MH.head                     # 共用头的颅骨网格（五官都是它的子物体）
head_parts = [ob for ob in MH.MESHES]
# ⚠️ 偏置是相对**头节点**的：颅心在世界 HEAD_C_Z，头节点在 NECK_Z，
#    两者之差才是要加到零件位置 / 颅骨顶点上的量（加两次会把头飞到半空）
off = Vector((0.0, 0.0, HEAD_C_Z - NECK_Z))
for ob in head_parts:
    ob.location = off + Vector(ob.location) * HEAD_SCALE
    for v in ob.data.vertices:
        v.co = v.co * HEAD_SCALE
for v in head_root.data.vertices:
    v.co += off
head_root.location = Vector((0.0, 0.0, 0.0))

head_node = bpy.data.objects.new(PREFIX + "_Head", None)
head_node.empty_display_size = 0.05
scene.collection.objects.link(head_node)
head_root.parent = head_node
head_root.matrix_parent_inverse.identity()


# =====================================================================
# 4. 四肢零件：摆到锚点上
# =====================================================================
limb_of = {}
for ob in TR.PARTS:
    tag = ob.name.replace("DSMonkeyTrunk_", "")
    ob.name = PREFIX + "_" + tag          # 先改名，后面拼关键帧表才找得到
    limb_of[tag] = ob

def place(ob, loc):
    ob.location = Vector(loc)
    ob.rotation_euler = (0.0, 0.0, 0.0)
    return ob

place(limb_of["Arm_R"], (SHOULDER_R.x, SHOULDER_R.y, SHOULDER_R.z))
place(limb_of["Arm_L"], (-SHOULDER_R.x, SHOULDER_R.y, SHOULDER_R.z))
place(limb_of["Leg_R"], (HIP_R.x, HIP_R.y, HIP_R.z))
place(limb_of["Leg_L"], (-HIP_R.x, HIP_R.y, HIP_R.z))
place(limb_of["Tail"], TAIL_BASE)


# =====================================================================
# 5. 骨架层级
# =====================================================================
def empty(name, parent=None, loc=(0, 0, 0)):
    ob = bpy.data.objects.new(PREFIX + "_" + name, None)
    ob.empty_display_size = 0.04
    scene.collection.objects.link(ob)
    if parent is not None:
        ob.parent = parent
        ob.matrix_parent_inverse.identity()
    ob.location = Vector(loc)
    return ob

root = empty("Root")
hips = empty("Hips", root, (0.0, 0.0, 0.0))    # 躯干网格按世界 z 建的，hips 不再叠加高度
torso.parent = hips
torso.matrix_parent_inverse.identity()
torso.location = Vector((0.0, 0.0, 0.0))
neck.parent = torso
neck.matrix_parent_inverse.identity()
neck.location = Vector((0.0, 0.0, 0.0))
head_node.parent = neck
head_node.matrix_parent_inverse.identity()
head_node.location = Vector((0.0, 0.0, NECK_Z))
for tag in ("Arm_R", "Arm_L", "Leg_R", "Leg_L", "Tail"):
    ob = limb_of[tag]
    ob.parent = hips
    ob.matrix_parent_inverse.identity()


# =====================================================================
# 6. 动画：头的 Laugh / Fear（共用头自带）+ 身体的 Idle / Sit / Walk / Run
# =====================================================================
ARM_R = PREFIX + "_Arm_R"
ARM_L = PREFIX + "_Arm_L"
LEG_R = PREFIX + "_Leg_R"
LEG_L = PREFIX + "_Leg_L"
TAIL = PREFIX + "_Tail"
HIPS = PREFIX + "_Hips"
TORSO = PREFIX + "_Torso"
def action_fcurves(act):
    """Blender 4.4+ 的 slotted action：fcurve 在 channelbag 里。"""
    try:
        return list(act.fcurves)
    except Exception:
        out = []
        for layer in act.layers:
            for strip in layer.strips:
                for bag in strip.channelbags:
                    out.extend(bag.fcurves)
        return out

def key_clip(name, length, keys, loop=False):
    """keys: [(帧, {物体名: {"loc": (x,y,z), "rot": (x,y,z)}}]

    loop=True（走路 / 跑这类循环片段）：**末帧不强制回中性**，
    靠"最后一帧姿势 == 第一帧姿势"保证循环无缝；表情片段则相反
    （首末必须回静止位，否则循环播放时末帧会闪一下）。"""
    touched = set()
    for _, pose in keys:
        touched |= {k if isinstance(k, str) else k.name for k in pose}
    last = max(f for f, _ in keys) - 1
    for nm in sorted(touched):
        ob = bpy.data.objects[nm]
        base_l = Vector(ob.location)
        base_r = Vector(ob.rotation_euler)
        ad = ob.animation_data_create()
        act = bpy.data.actions.new("%s_%s" % (name, nm))
        act.use_fake_user = True
        ad.action = act
        pts = {0: {}}
        for f, pose in keys:
            p2 = {k if isinstance(k, str) else k.name: v for k, v in pose.items()}
            if nm in p2:
                pts[f - 1] = p2[nm]
        if not loop:
            pts[last] = {}
        for f in sorted(pts):
            p = pts[f]
            ob.location = base_l + Vector(p.get("loc", (0.0, 0.0, 0.0)))
            ob.rotation_euler = base_r + Vector(p.get("rot", (0.0, 0.0, 0.0)))
            ob.keyframe_insert("location", frame=f)
            ob.keyframe_insert("rotation_euler", frame=f)
        ad.action = None
        tr = ad.nla_tracks.new()
        tr.name = name
        st = tr.strips.new(name, 0, act)
        try:
            st.action_slot = act.slots[0]
        except Exception:
            pass
        # ⚠️ **strip 必须显式给帧范围**：`strips.new(name, 0, act)` 的默认
        # frame_end = 0，片段长度是 0 → 无论 scene.frame_set 到第几帧，
        # 永远停在第 0 帧的姿态（动画"不动"）。设置成片段长度才会真正播放。
        st.frame_start = 0
        st.frame_end = length
        tr.mute = True
        ob.location = base_l
        ob.rotation_euler = base_r

# 身体 Idle：尾巴左右摇 + 手臂轻微摆 + 身体起伏
arm_r = PREFIX + "_Arm_R"
arm_l = PREFIX + "_Arm_L"
tail = PREFIX + "_Tail"
IDLE = (48, [
    (1,  {tail: {"rot": (0.0, 0.0, -0.16)}, arm_r: {"rot": (0.0, 0.0, 0.05)},
          arm_l: {"rot": (0.0, 0.0, -0.05)}, hips: {"loc": (0.0, 0.0, 0.0)}}),
    (13, {tail: {"rot": (0.0, 0.0, 0.16)}, arm_r: {"rot": (0.0, 0.0, -0.05)},
          arm_l: {"rot": (0.0, 0.0, 0.05)}, hips: {"loc": (0.0, 0.0, 0.006)}}),
    (25, {tail: {"rot": (0.0, 0.0, -0.16)}, arm_r: {"rot": (0.0, 0.0, 0.05)},
          arm_l: {"rot": (0.0, 0.0, -0.05)}, hips: {"loc": (0.0, 0.0, 0.0)}}),
    (37, {tail: {"rot": (0.0, 0.0, 0.16)}, arm_r: {"rot": (0.0, 0.0, -0.05)},
          arm_l: {"rot": (0.0, 0.0, 0.05)}, hips: {"loc": (0.0, 0.0, 0.006)}}),
])

# 身体 Sit：两条腿向前转（参考图就是坐姿），手撑地
SIT = (48, [
    (1,  {PREFIX + "_Leg_R": {"rot": (1.05, 0.0, 0.0)}, PREFIX + "_Leg_L": {"rot": (1.05, 0.0, 0.0)},
          arm_r: {"rot": (0.55, 0.0, 0.0)}, arm_l: {"rot": (0.55, 0.0, 0.0)}}),
    (24, {PREFIX + "_Leg_R": {"rot": (1.05, 0.0, 0.0)}, PREFIX + "_Leg_L": {"rot": (1.05, 0.0, 0.0)},
          arm_r: {"rot": (0.55, 0.0, 0.0)}, arm_l: {"rot": (0.55, 0.0, 0.0)}}),
    (48, {PREFIX + "_Leg_R": {"rot": (1.05, 0.0, 0.0)}, PREFIX + "_Leg_L": {"rot": (1.05, 0.0, 0.0)},
          arm_r: {"rot": (0.55, 0.0, 0.0)}, arm_l: {"rot": (0.55, 0.0, 0.0)}}),
])

# 走路：48 帧 = 2 步（24 fps，一步 12 帧）
# 腿绕髋转 θ，脚的 z = 髋高 − 腿长·cosθ；θ=±24° 时脚离地 ≈13 mm，
# 所以**跨步时身体下沉**（髋 −13 mm）、并立时回 0 —— 脚才不会穿地 / 飘地
WALK = (49, [
    (1,  {LEG_R: {"rot": (0.42, 0, 0)}, LEG_L: {"rot": (-0.42, 0, 0)},
          ARM_R: {"rot": (-0.48, 0, 0)}, ARM_L: {"rot": (0.48, 0, 0)},
          HIPS: {"loc": (0.0, 0.0, 0.006)}, TAIL: {"rot": (0, 0, 0.10)}}),
    (13, {LEG_R: {"rot": (0.0, 0, 0)}, LEG_L: {"rot": (0.0, 0, 0)},
          ARM_R: {"rot": (0.0, 0, 0)}, ARM_L: {"rot": (0.0, 0, 0)},
          HIPS: {"loc": (0.0, 0.0, 0.0)}, TAIL: {"rot": (0, 0, -0.10)}}),
    (25, {LEG_R: {"rot": (-0.42, 0, 0)}, LEG_L: {"rot": (0.42, 0, 0)},
          ARM_R: {"rot": (0.48, 0, 0)}, ARM_L: {"rot": (-0.48, 0, 0)},
          HIPS: {"loc": (0.0, 0.0, 0.006)}, TAIL: {"rot": (0, 0, 0.10)}}),
    (37, {LEG_R: {"rot": (0.0, 0, 0)}, LEG_L: {"rot": (0.0, 0, 0)},
          ARM_R: {"rot": (0.0, 0, 0)}, ARM_L: {"rot": (0.0, 0, 0)},
          HIPS: {"loc": (0.0, 0.0, 0.0)}, TAIL: {"rot": (0, 0, -0.10)}}),
    (49, {LEG_R: {"rot": (0.42, 0, 0)}, LEG_L: {"rot": (-0.42, 0, 0)},
          ARM_R: {"rot": (-0.48, 0, 0)}, ARM_L: {"rot": (0.48, 0, 0)},
          HIPS: {"loc": (0.0, 0.0, 0.006)}, TAIL: {"rot": (0, 0, 0.10)}}),
])

# 跑：24 帧 = 2 步（比走路快一倍），步幅更大、身体前倾、摆臂更用力
RUN = (25, [
    (1,  {LEG_R: {"rot": (0.72, 0, 0)}, LEG_L: {"rot": (-0.62, 0, 0)},
          ARM_R: {"rot": (-0.80, 0, 0)}, ARM_L: {"rot": (0.80, 0, 0)},
          HIPS: {"loc": (0.0, 0.0, 0.002)}, TORSO: {"rot": (0.16, 0, 0)},
          TAIL: {"rot": (0, 0, 0.18)}}),
    (7,  {LEG_R: {"rot": (0.0, 0, 0)}, LEG_L: {"rot": (0.0, 0, 0)},
          ARM_R: {"rot": (0.0, 0, 0)}, ARM_L: {"rot": (0.0, 0, 0)},
          HIPS: {"loc": (0.0, 0.0, 0.0)}, TORSO: {"rot": (0.16, 0, 0)},
          TAIL: {"rot": (0, 0, -0.14)}}),
    (13, {LEG_R: {"rot": (-0.62, 0, 0)}, LEG_L: {"rot": (0.72, 0, 0)},
          ARM_R: {"rot": (0.80, 0, 0)}, ARM_L: {"rot": (-0.80, 0, 0)},
          HIPS: {"loc": (0.0, 0.0, 0.002)}, TORSO: {"rot": (0.16, 0, 0)},
          TAIL: {"rot": (0, 0, 0.18)}}),
    (19, {LEG_R: {"rot": (0.0, 0, 0)}, LEG_L: {"rot": (0.0, 0, 0)},
          ARM_R: {"rot": (0.0, 0, 0)}, ARM_L: {"rot": (0.0, 0, 0)},
          HIPS: {"loc": (0.0, 0.0, 0.0)}, TORSO: {"rot": (0.16, 0, 0)},
          TAIL: {"rot": (0, 0, -0.14)}}),
    (25, {LEG_R: {"rot": (0.72, 0, 0)}, LEG_L: {"rot": (-0.62, 0, 0)},
          ARM_R: {"rot": (-0.80, 0, 0)}, ARM_L: {"rot": (0.80, 0, 0)},
          HIPS: {"loc": (0.0, 0.0, 0.002)}, TORSO: {"rot": (0.16, 0, 0)},
          TAIL: {"rot": (0, 0, 0.18)}}),
])

key_clip("DSMonkey_Parts_Walk", WALK[0], WALK[1], loop=True)
key_clip("DSMonkey_Parts_Run", RUN[0], RUN[1], loop=True)
key_clip("DSMonkey_Parts_Idle", IDLE[0], IDLE[1])
key_clip("DSMonkey_Parts_Sit", SIT[0], SIT[1])

# 共用头的 Laugh / Fear：片段名加前缀，键表沿用（对象名要改成 M3F 前缀）
def rename_head_parts():
    """片段表里用的是共用头的**原名**（DSMonkeyXxx），这里映到新名。"""
    mp = {}
    for ob in MH.MESHES:
        suffix = ob.name.replace(PREFIX + "_", "")
        mp["DSMonkey" + suffix] = ob.name
    return mp

PART_MAP = rename_head_parts()

def remap_clip(clip):
    length, keys = clip
    out = []
    for f, pose in keys:
        np = {}
        for nm, p in pose.items():
            np[PART_MAP.get(nm, nm)] = p
        out.append((f, np))
    return (length, out)

for name, clip in MH.CLIPS.items():
    length, keys = remap_clip(clip)
    key_clip("DSMonkey_" + name, length, keys)

def activate_clip(name):
    """把某个片段的 action **直接挂回物体**，并把所有 NLA 轨静音。

    ⚠️ 为什么不用 NLA 轨本身：Blender 5.2 上 NLA strip 的求值时间**不随 scene.frame_set
    推进**（实测 strip 的 action 的 fcurve 在 0/12/24 帧分别是 0.42/0.0/−0.42，
    但物体上的实际变换一直是第 0 帧的值）—— 动画"不动"。
    action 本身评估是好的，所以预览 / 审计一律走 action；
    **导出仍然用 NLA 轨**（导出器按轨名合并片段，§2.1 记的那个坑）。"""
    for ob in bpy.context.scene.objects:
        ad = ob.animation_data
        if not ad:
            continue
        for t in ad.nla_tracks:
            t.mute = True
            for st in t.strips:
                st.mute = True
        ad.action = None
        for t in ad.nla_tracks:
            if t.name != name:
                continue
            for st in t.strips:
                if not st.action:
                    continue
                ad.action = st.action
                try:
                    ad.action_slot = st.action_slot
                except Exception:
                    pass


def clip_ground_audit(clip_names):
    """循环片段每帧扫一次脚底最低点：腿是整根摆动的，θ 越大脚抬得越高，
    身体必须同步下沉，否则脚会穿地或飘地。"""
    legs = [bpy.data.objects[PREFIX + "_Leg_R"], bpy.data.objects[PREFIX + "_Leg_L"]]
    for nm in clip_names:
        activate_clip(nm)
        frames = []
        length = 48 if "Walk" in nm else (24 if "Run" in nm else 48)
        worst = 9.9
        for f in range(1, length + 1):
            scene.frame_set(f)
            bpy.context.view_layer.update()
            dg = bpy.context.evaluated_depsgraph_get()
            # ⚠️ 用**真实顶点**而不是 bound_box：腿转起来之后，包围盒的角会比
            #    实际几何低好几毫米（盒子是轴对齐的，转了就不贴合了）
            zmin = min(min((ob.evaluated_get(dg).matrix_world @ v.co).z
                           for v in ob.data.vertices) for ob in legs)
            worst = min(worst, zmin)
            if f in (1, length // 4, length // 2, 3 * length // 4, length):
                frames.append((f, zmin))
        print("  %-22s 脚底最低 %+0.4f m  (%s)" % (
            nm, worst, "  ".join("f%d %+0.4f" % t for t in frames)))
        scene.frame_set(1)


scene.frame_end = 48
scene.frame_start = 1
scene.render.fps = 24


# =====================================================================
# 7. 重命名 + 父级整理
# =====================================================================
for ob in list(bpy.data.objects):
    if ob.name.startswith("DSMonkey") and not ob.name.startswith(PREFIX):
        ob.name = PREFIX + "_" + ob.name.replace("DSMonkey", "")

bpy.context.view_layer.update()

# =====================================================================
# 8. 导出
# =====================================================================
bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH)

bpy.ops.object.select_all(action='DESELECT')
for ob in bpy.context.scene.objects:
    ob.select_set(True)
bpy.context.view_layer.objects.active = torso
bpy.ops.export_scene.gltf(
    filepath=GLB_PATH,
    export_format='GLB',
    use_selection=True,
    export_apply=False,
    export_yup=True,
    export_animations=True,
    export_animation_mode='NLA_TRACKS',
    export_cameras=False,
    export_lights=False,
)
print("glb ->", GLB_PATH)

tris = 0
for ob in bpy.context.scene.objects:
    if ob.type == 'MESH':
        tris += sum(len(p.vertices) - 2 for p in ob.data.polygons)
print("M3F CHECK: tris %d  网格 %d" % (tris, len([o for o in bpy.context.scene.objects if o.type == 'MESH'])))
print("地面审计（循环片段每帧扫脚底）:")
clip_ground_audit(["DSMonkey_Parts_Walk", "DSMonkey_Parts_Run", "DSMonkey_Parts_Idle"])
for _n in ("M3FPartsMonkey_Leg_R", "M3FPartsMonkey_Leg_L", "M3FPartsMonkey_Hips"):
    _o = bpy.data.objects.get(_n)
    if _o:
        _bb = [_o.matrix_world @ Vector(c) for c in _o.bound_box]


# =====================================================================
# 9. 预览：四视图 + 接触表
# =====================================================================
TR.scene.render.film_transparent = False
TR.scene.render.image_settings.color_mode = 'RGBA'
TR.scene.view_settings.view_transform = 'Standard'

VIEWS = [("front", 0.0), ("side", -90.0), ("back", 180.0), ("q34", 35.0)]
W, H = 480, 600
TR.scene.render.resolution_x = W
TR.scene.render.resolution_y = H
target = Vector((0.0, 0.0, 0.33))
paths = []
for name, az in VIEWS:
    TR.aim_camera(TR.CAM, target, 3.0, 0.80, az)
    path = os.path.join(TR.RENDER_DIR, "m3f_%s.png" % name)
    TR.render_to(path)
    paths.append(path)

buf = np.ones((H * 2, W * 2, 4), dtype=np.float32)
for i, path in enumerate(paths):
    a = TR.load_rgba(path, W, H)
    r, c = divmod(i, 2)
    buf[r * H:r * H + H, c * W:(c + 1) * W] = a
TR.save_rgba(buf, PREVIEW_PNG, "m3f_parts_monkey")
print("preview ->", PREVIEW_PNG)

# ⚠️ NLA 轨默认静音（导出器照样读得到），**渲染**前必须放开对应的轨，
#    而且只放开身体那两段 —— 头部的 Laugh/Fear 也放开会和身体的姿势打架
for ob in bpy.context.scene.objects:
    ad = ob.animation_data
    if not ad:
        continue
    for tr in ad.nla_tracks:
        tr.mute = not tr.name.startswith("DSMonkey_Parts")

# 接触表：Idle / Sit 两段，各取 3 帧
FRAMES = [("DSMonkey_Parts_Walk", 1), ("DSMonkey_Parts_Walk", 13),
          ("DSMonkey_Parts_Run", 1), ("DSMonkey_Parts_Run", 13),
          ("DSMonkey_Parts_Sit", 1), ("DSMonkey_Parts_Idle", 25)]
TW, TH = 440, 550
TR.scene.render.resolution_x = TW
TR.scene.render.resolution_y = TH
buf2 = np.ones((TH * 2, TW * 3, 4), dtype=np.float32)
for i, (clip, frame) in enumerate(FRAMES):
    activate_clip(clip)
    scene.frame_set(frame)
    bpy.context.view_layer.update()      # ⚠️ 不刷新依赖图，渲染出来的还是上一帧
    TR.aim_camera(TR.CAM, target, 3.0, 0.80, 30.0)
    path = os.path.join(TR.RENDER_DIR, "m3f_anim_%d.png" % i)
    TR.render_to(path)
    a = TR.load_rgba(path, TW, TH)
    r, c = divmod(i, 3)
    buf2[r * TH:r * TH + TH, c * TW:(c + 1) * TW] = a
TR.save_rgba(buf2, ANIM_PNG, "m3f_parts_monkey_anim")
print("anim preview ->", ANIM_PNG)
scene.frame_set(1)

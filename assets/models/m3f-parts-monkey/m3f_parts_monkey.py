# -*- coding: utf-8 -*-
"""m3f-parts-monkey —— 用「零件」拼出来的整只猴（2026-11 重做：表情补全 + 造型修脸）

参考图：assets/models/ds-monkey-body/reference.png（2×2 四视图，基准 `simple-lowpoly-monkey_bg.png`）

四块零件拼起来：
  ① 头   —— `models/_shared/monkey_head.py`（共用头：颅骨 + 脸盘 + 呆毛 + 五官 + 2 段表情）
              **耳朵和 3 张嘴在本脚本里重做**（共用头那对耳朵是 8 边扁盘，像两枚别针；
              共用头的笑嘴 / 惊恐嘴是尖角多边形，渲染出来是一坨黑疙瘩）
  ② 身   —— 本脚本现建的车削躯干（梨形：胯宽肩窄，橘色肚皮一直连到胸口）
  ③ 四肢 —— `models/ds-monkey-trunk/ds_monkey_trunk.py` 的**放样工具**
              （路径 / 标架 / 放样函数全复用，但锚点、半径、手法全部重排）
              腿拆成 **大腿 + 小腿 + 脚掌** 三个节点 → 膝盖能弯
  ④ 尾巴 —— 同上

产物：
  m3f_parts_monkey.glb        一个网格层级 + **8 段动画**（每段都带表情）
  m3f_parts_monkey.blend
  m3f_parts_monkey_preview.png  四视图
  m3f_parts_monkey_anim.png     接触表（6 格，每格一个情绪）

规矩见 assets/AGENTS.md §1（米制、scale 恒 1、原点在摆放锚点）。

--------------------------------------------------------------------------
这一版改了什么（2026-11）
--------------------------------------------------------------------------
**A. 表情补全 —— 以前只有 Laugh / Fear 两段带脸，其余四段全是"木头脸"**

    片段                     以前                现在
    ------------------------------------------------------------------
    DSMonkey_Parts_Idle      无脸                浅笑 + 眨眼（帧 19~23）
    DSMonkey_Parts_Sit       无脸                放松微笑 + 慢眨
    DSMonkey_Parts_Walk      无脸                专注（下眉 + 抿嘴）+ 眨眼
    DSMonkey_Parts_Run       无脸                用力（张嘴喘 + 皱眉）
    DSMonkey_Parts_Cheer     ——（没有）          举手欢呼 + 大笑
    DSMonkey_Parts_Startle   ——（没有）          吓得跳起 + 惊恐
    DSMonkey_Laugh           只有头              保留（头 + 脸）
    DSMonkey_Fear            只有头              保留（头 + 脸）

    做法：**表情按情绪逐帧烘进每段动作**（和 `ds_lowpoly_monkey` 同一套路）——
    同一段动画里既有身体的键、也有脸的键，靠"NLA 轨名 = 片段名"在导出时并成一条。

    为了表情够用，本脚本在共用头之外**又补了 4 个表情件**：
      `EyeBlink_L/R`  闭眼线（共用头那对 `EyeShut` 是"开心眯眼"的向上弧，两种要分开）
      `MouthFlat`     抿嘴（走路 / 跑步的"专注"）
      `MouthPants`    小张嘴（跑步喘气）

**B. 造型修脸 —— 以前是"大圆脑袋 + 细杆四肢 + 铁丝尾巴"**

    | 部位 | 以前 | 现在 |
    | --- | --- | --- |
    | 头 / 身宽比 | 头（含耳）0.478 vs 身 0.270 = **1.77** | 0.374 vs 0.336 = **1.11**（参考图 1.13） |
    | 耳朵 | 8 边扁盘，两枚别针 | 12 边碗形，**嵌进颅骨**里，外沿只多探出 0.04 m |
    | 躯干 | 直筒（上下一样粗）+ 坦克背心式橘肚皮 | 梨形（胯 0.284 宽 → 肩 0.200 宽），橘色**从脸一路连到胸口** |
    | 脖子 | 独立圆管，和脑袋之间有一道环 | 躯干顶环直接升进颅骨底下，**没有接缝** |
    | 肩 / 胯 | 手臂是插进身里的细杆 | 肩球（r 0.047）与躯干**咬合**，看得出"肩膀从身体长出来" |
    | 脚 | 3 根方棱趾头互相叠 → **锯齿** | 短粗圆趾（间距 > 直径），不再叠 |
    | 尾巴 | r 0.015 的铁丝，翘成一个"提手" | r 0.028 → 0.010，7 棱，**垂下来再勾上去** |
    | 嘴 | 尖角多边形 → 一坨黑疙瘩 | 圆弧轮廓 + 暖色口腔 + 舌头 |
    | 站高 | 0.598 m | 0.604 m（脚底 z=0） |

**C. 腿有关节了** —— 以前整条腿是一根**刚性管**（大腿小腿一整根），走路像木棍，
   坐姿更是"站着把腿伸出去"。现在拆成 **大腿 / 小腿 / 脚掌** 三个节点：
   走路时膝盖会弯（摆动腿屈膝 0.30 rad）、坐姿时**大腿前伸 + 小腿下垂**，
   髋部整体下沉 → **屁股和脚掌同时着地**。

**D. 脚不再穿地** —— 髋部每帧的高度用 `solve_ground()` **算**出来：
   先摆腿 → 量脚底真实顶点 → 取负当髋高。循环片段因此永远"一只脚正好踩在地上"。
"""
import bpy
import bmesh
import math
import os
import sys

import numpy as np
from mathutils import Vector, Matrix

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS = os.path.dirname(HERE)
SHARED = os.path.join(MODELS, "_shared")
TRUNK = os.path.join(MODELS, "ds-monkey-trunk")

PREFIX = "M3FPartsMonkey"

BLEND_PATH = os.path.join(HERE, "m3f_parts_monkey.blend")
GLB_PATH = os.path.join(HERE, "m3f_parts_monkey.glb")
PREVIEW_PNG = os.path.join(HERE, "m3f_parts_monkey_preview.png")
ANIM_PNG = os.path.join(HERE, "m3f_parts_monkey_anim.png")


# =====================================================================
# 1. 比例（米）—— 全部集中在这里，改一个数就能整体调
# =====================================================================
# 头
HEAD_SCALE = 1.00            # 颅骨网格数据缩放（物体 scale 恒 1）
HEAD_C_Z = 0.440             # 颅心离地
NECK_Z = 0.295               # 头节点（脖子转轴）离地
PIVOT_Z = 0.150              # 躯干俯仰的枢轴高度（= 髋高）

# 躯干剖面（z, 半宽 rx, 半深 ry）—— 梨形：胯宽肩窄
TORSO_PROFILE = [
    (0.108, 0.080, 0.070),    # 底（收窄，两条腿从下面露出来）
    (0.132, 0.126, 0.106),
    (0.176, 0.142, 0.120),    # 最宽（胯）
    (0.216, 0.138, 0.117),
    (0.248, 0.128, 0.110),
    (0.276, 0.116, 0.102),    # 肩（宽，肩球埋得进去）
    (0.296, 0.088, 0.080),
    (0.310, 0.050, 0.048),    # 颈（升进颅骨底下）
    (0.322, 0.044, 0.042),
]
TORSO_COLS = 20              # 圆周分段（面块要大，低模的"干净"靠这个）
TORSO_RINGS = 14             # 高度环数（从下面的剖面表插值出来）
# 橘色"肚皮"：**只是正面身体的一小圈圆**（不是从脸一路铺到胸口的一大片）。
#   它不是逐面染色，而是独立的贴面壳（见 build_belly_patch）——
#   逐面染色的边界只能落在网格线上，永远是碎方块。
TAN_BELLY_R = 0.066            # 肚皮圆的半径（米）
TAN_BELLY_Z = 0.190            # 肚皮圆的圆心高度

# 关节锚点
SHOULDER_R = Vector((0.115, 0.000, 0.268))
ELBOW_R = Vector((0.148, 0.006, 0.216))
WRIST_R = Vector((0.156, 0.012, 0.160))
HIP_R = Vector((0.072, 0.000, 0.148))
KNEE_R = Vector((0.078, 0.006, 0.086))
ANKLE_R = Vector((0.082, 0.000, 0.034))
TAIL_BASE = Vector((0.000, -0.086, 0.148))

ARM_PATH = [SHOULDER_R,
            SHOULDER_R.lerp(ELBOW_R, 0.5),
            ELBOW_R,
            ELBOW_R.lerp(WRIST_R, 0.5),
            WRIST_R]
ARM_RADII = [0.0470, 0.0460, 0.0440, 0.0415, 0.0395,
              0.0370, 0.0345, 0.0315, 0.0290]
THIGH_PATH = [HIP_R, HIP_R.lerp(KNEE_R, 0.5), KNEE_R]
THIGH_RADII = [0.0520, 0.0510, 0.0498, 0.0482, 0.0468]
SHIN_PATH = [KNEE_R, KNEE_R.lerp(ANKLE_R, 0.5), ANKLE_R]
SHIN_RADII = [0.0468, 0.0452, 0.0430, 0.0400, 0.0358, 0.0316, 0.0280]
ARM_RINGS = 9
THIGH_RINGS = 5
SHIN_RINGS = 7

# 脚掌（单独一个节点，绕踝转）
FOOT_SECTIONS = [            # (相对踝的 Y, 半宽, 脚背高 z)
    (-0.030, 0.025, 0.020),
    (-0.004, 0.035, 0.040),
    (0.020, 0.034, 0.028),
    (0.034, 0.030, 0.012),
]
TOE_BASE_Y = 0.030
TOE_LEN = 0.011
TOE_R0, TOE_R1 = 0.0105, 0.0082
FOOT_SPLAY = math.radians(7.0)

# 尾巴：向后甩出去再**勾上来**（以前翘成一个"提手"，垂下来又像第五只脚）
TAIL_PTS = [
    (0.000, -0.086, 0.152),
    (0.030, -0.142, 0.150),
    (0.072, -0.188, 0.140),
    (0.114, -0.208, 0.136),
    (0.150, -0.198, 0.152),
    (0.164, -0.168, 0.176),
    (0.154, -0.140, 0.198),
]
TAIL_RADII = [0.0280, 0.0272, 0.0260, 0.0242, 0.0218,
              0.0190, 0.0158, 0.0126, 0.0105]
TAIL_SIDES = 7

# 耳朵（重做，不再用共用头那对 8 边扁盘）
EAR_X = 0.155                # 耳心离中线（耳盘靠外一点，才看得见"碗"）
EAR_Y = -0.028
EAR_Z = -0.008
EAR_RX = 0.058               # 耳盘半宽（沿耳盘横向）
EAR_RY = 0.052               # 耳盘半高
EAR_N = Vector((0.500, 0.866, 0.05))   # 耳盘法线（右耳；左耳镜像）
EAR_SEGS = 16


# =====================================================================
# 2. 零件导入
#    ⚠️ 顺序有讲究：`ds_monkey_trunk` 开头会 `read_homefile(use_empty=True)`
#    **清空场景**，所以先导它；共用头不清场，后导。
# =====================================================================
sys.path.insert(0, TRUNK)
import ds_monkey_trunk as TR              # STANDALONE=False → 只建几何 / 相机，不导出

sys.path.insert(0, SHARED)
sys.modules.pop("monkey_head", None)
import monkey_head as MH                  # 共用头（只往上加物体，不清场景）

scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'

# 四肢套件自带的 5 件（锚点是给 `ds-monkey-body` 用的）在这里用不上，删掉
for ob in list(TR.PARTS):
    bpy.data.objects.remove(ob, do_unlink=True)
TR.PARTS = []


# =====================================================================
# 3. 材质
# =====================================================================
def lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

def make_material(name, rgb, rough):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.use_backface_culling = False
    bsdf = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    bsdf.inputs["Base Color"].default_value = tuple(lin(c) for c in rgb) + (1.0,)
    bsdf.inputs["Roughness"].default_value = rough
    for prop in ("Specular IOR Level", "Specular"):
        if prop in bsdf.inputs:
            bsdf.inputs[prop].default_value = 0.20
            break
    m.diffuse_color = tuple(lin(c) for c in rgb) + (1.0,)
    return m


# 手脚 / 肚皮暗边用的深橘（比脸深一档，和 ds-monkey-body 的 tan_deep 同色）
MAT_TAN_DEEP = make_material(PREFIX + "_tan_deep", (0.788, 0.561, 0.341), 0.70)
MAT_FUR = MH.MATS["fur"]                  # #7A4527
MAT_FACE = MH.MATS["face"]                # #DBA86E

# 口腔改成**暖褐**而不是近黑 —— 近黑在橘色脸上就是一个"黑洞"
_mouth_bsdf = next(n for n in MH.MATS["mouth"].node_tree.nodes
                   if n.type == 'BSDF_PRINCIPLED')
_mouth_bsdf.inputs["Base Color"].default_value = \
    tuple(lin(c) for c in (0.300, 0.135, 0.115)) + (1.0,)
MH.MATS["mouth"].diffuse_color = tuple(lin(c) for c in (0.300, 0.135, 0.115)) + (1.0,)


def remap_materials(ob, mapping):
    """换材质（**保住每个面的槽位**）。

    ⚠️ `materials.clear()` 会把**所有面的 material_index 归零** ——
    清空再 append 之后，多槽物体的第二个槽就再没人用了：
    实测手臂 101 个面**全部**落回槽 0（毛色），
    拳头于是渲染成棕色而不是橘色（"手部的颜色不对"就是这么来的）。
    先把索引存下来，append 完再写回去。
    """
    me = ob.data
    keep = [p.material_index for p in me.polygons]
    mats = [mapping.get(m.name, m) if m else None for m in me.materials]
    me.materials.clear()
    for m in mats:
        me.materials.append(m)
    for p, i in zip(me.polygons, keep):
        p.material_index = i


TR_MAT_MAP = {
    "DSMonkeyTrunk_fur": MAT_FUR,
    "DSMonkeyTrunk_tan": MAT_TAN_DEEP,
}


# =====================================================================
# 4. 躯干（车削）+ 橘色肚皮/胸口（逐面换材质）
# =====================================================================
def lerp_table(table, x):
    if x <= table[0][0]:
        return table[0][1]
    if x >= table[-1][0]:
        return table[-1][1]
    for i in range(len(table) - 1):
        x0, v0 = table[i]
        x1, v1 = table[i + 1]
        if x0 <= x <= x1:
            t = (x - x0) / (x1 - x0) if x1 > x0 else 0.0
            return v0 + (v1 - v0) * t
    return table[-1][1]


def densify_profile(prof, n):
    """把剖面表插值成 n 环 —— 环太稀的话，橘色肚皮的边界会碎成方块。"""
    out = []
    for i in range(n):
        t = i * (len(prof) - 1) / float(n - 1)
        i0 = int(math.floor(t))
        i1 = min(len(prof) - 1, i0 + 1)
        f = t - i0
        z0, rx0, ry0 = prof[i0]
        z1, rx1, ry1 = prof[i1]
        out.append((z0 + (z1 - z0) * f, rx0 + (rx1 - rx0) * f, ry0 + (ry1 - ry0) * f))
    return out


def recalc_normals(ob):
    """重算法线朝外（**封闭**壳体用）。

    ⚠️ 车削出来的环向顺序决定面朝向，顺序写反了整块壳的法线就是**朝内**的：
    渲染时 Blender 会把"背面"的法线翻过来凑合着照，看起来还行，
    但换个角度就变味（而且贴面壳会整个埋进身体里 —— 肚皮就是这么没的）。
    """
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()


def flip_to_front(faces, verts):
    """把一组**开口**的面片翻成朝 +Y（贴脸 / 贴肚皮的壳用不了 recalc）。"""
    out = []
    for f in faces:
        f = list(f)
        a = Vector(verts[f[0]])
        b = Vector(verts[f[1]])
        c = Vector(verts[f[2]])
        if (b - a).cross(c - a).y < 0.0:
            f[1], f[2] = f[2], f[1]
        out.append(tuple(f))
    return out


def build_torso():
    verts, faces = [], []
    cols = TORSO_COLS
    rings = []
    for (z, rx, ry) in densify_profile(TORSO_PROFILE, TORSO_RINGS):
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
    # 顶盖（藏进颅骨里）
    top = len(verts)
    verts.append(Vector((0.0, 0.0, TORSO_PROFILE[-1][0] + 0.010)))
    for k in range(cols):
        faces.append((rings[-1][k], rings[-1][(k + 1) % cols], top))
    # 底盖（藏在两腿之间）
    bot = len(verts)
    verts.append(Vector((0.0, 0.0, TORSO_PROFILE[0][0] - 0.040)))
    for k in range(cols):
        faces.append((bot, rings[0][(k + 1) % cols], rings[0][k]))

    # ⚠️ 躯干**不再逐面染色**：肚皮改成独立的"贴面壳"（见 build_belly_patch），
    #    逐面染色的边界只能落在网格线上 → 永远是碎方块。
    me = bpy.data.meshes.new(PREFIX + "_Torso")
    me.from_pydata([tuple(v) for v in verts], [], faces)
    me.validate()
    me.materials.append(MAT_FUR)
    for poly in me.polygons:
        poly.use_smooth = False
    ob = bpy.data.objects.new(PREFIX + "_Torso", me)
    scene.collection.objects.link(ob)
    recalc_normals(ob)
    return ob


torso = build_torso()


def build_belly_patch():
    """橘色肚皮：正面身体**一小圈**，做成独立的**贴面壳**。

    为什么不用"逐面染色"：染色的边界只能落在网格线上，
    边界就永远是碎方块（看着像贴了张创可贴）。做成壳就能是一个**干净的圆**。

    壳 = 轮廓圈 + 内圈 + 中心点（每圈都**贴到躯干表面**再沿法线抬起），
    内圈是必须的：只有一圈的话，扇形的**弦**会切进鼓着的躯干里 → 中间露底。
    """
    import bmesh as _bmesh
    from mathutils.bvhtree import BVHTree
    bm = _bmesh.new()
    bm.from_mesh(torso.data)
    bm.transform(torso.matrix_world)
    bvh_t = BVHTree.FromBMesh(bm)
    bm.free()

    def surf(px, pz, off):
        loc, nor, _, _ = bvh_t.ray_cast(Vector((px, 1.0, pz)), Vector((0.0, -1.0, 0.0)))
        if loc is None:
            raise RuntimeError("belly ray miss")
        return loc + nor * off

    out = []
    CENTER_Z = TAN_BELLY_Z
    # ⚠️ **圈数要多**：壳是"贴面"的，但圈与圈之间是**弦** ——
    #    弦会切进鼓着的躯干里 → 躯干的格子从壳下面顶出来
    #    （看着像肚皮上画了张鬼脸）。4 圈同心环 + 中心点，
    #    每块三角形都短，弦就切不进去了。
    RINGS = [1.00, 0.76, 0.52, 0.28]
    for (tag, r, off, mat) in (("BellyRim", TAN_BELLY_R * 1.16, 0.0014, MAT_TAN_DEEP),
                              ("Belly", TAN_BELLY_R, 0.0030, MAT_FACE)):
        n = 24
        verts, faces = [], []
        rings = []
        for frac in RINGS:
            idx = []
            for k in range(n):
                a = 2.0 * math.pi * k / n
                px, pz = frac * r * math.cos(a), CENTER_Z + frac * r * math.sin(a)
                idx.append(len(verts))
                verts.append(surf(px, pz, off))
            rings.append(idx)
        ctr = len(verts)
        verts.append(surf(0.0, CENTER_Z, off))
        for k in range(n):
            j = (k + 1) % n
            faces.append((ctr, rings[-1][k], rings[-1][j]))
            for q in range(len(rings) - 1, 0, -1):
                faces.append((rings[q][k], rings[q][j], rings[q - 1][j]))
                faces.append((rings[q][k], rings[q - 1][j], rings[q - 1][k]))
        faces = flip_to_front(faces, verts)      # ⚠️ 必须在 from_pydata **之前**翻
        me = bpy.data.meshes.new(PREFIX + "_" + tag)
        me.from_pydata([tuple(v) for v in verts], [], faces)
        me.validate()
        me.materials.append(mat)
        for poly in me.polygons:
            poly.use_smooth = False
        ob = bpy.data.objects.new(PREFIX + "_" + tag, me)
        scene.collection.objects.link(ob)
        out.append(ob)
    return out


belly_parts = build_belly_patch()


# =====================================================================
# 5. 四肢 + 尾巴（复用 ds-monkey-trunk 的放样工具，锚点/半径全重排）
# =====================================================================
def smooth_path(ctrl, rings):
    return TR.resample(TR.catmull_rom_3d(ctrl, 6), rings)


def add_fist(b, wrist, tip):
    """腕 → 一颗**低模拳头**（不再要手指）。

    四肢套件给的是「3 根指头 + 拇指」的连指手套，在这种大小的模型上
    那几根小棍反而像毛刺 —— 换成一颗圆滚滚的拳头更干净。

    做法：沿手的轴放 4 环（拳根 → 拳面），每环 8 个点，越往拳面越小，
    最后用一个中心点封口 → 一个八棱的圆球（拳头的"指关节"就是它的棱）。
    """
    wrist = Vector(wrist)
    d = (Vector(tip) - wrist).normalized()
    u = Vector((1.0, 0.0, 0.0))
    u = (u - d * u.dot(d)).normalized()
    v = d.cross(u).normalized()
    c = wrist                             # ⚠️ 拳心**就在腕点**（不能往下推）
    # ⚠️ 「手悬空」就是这么来的：以前 `c = wrist + d * 0.020`，第一圈又只有 0.028
    #    （比腕处手臂半径 0.029 还细）→ 手臂在腕点收口、拳头从腕点**下方 20 mm**
    #    才起头，中间一段**什么也没有**（空隙 19.5 mm，渲染出来手是飘着的）。
    #    现在第一圈**往上咬进手臂里**（t = −0.018、半径 0.022 < 手臂 0.029 → 藏进去），
    #    出了腕点就比手臂粗 → 手和手臂是接上的。
    SECTIONS = [                          # (沿轴距离, 横向半径, 前后半径)
        (-0.018, 0.022, 0.021),           # 拳根：埋在手臂里
        (-0.008, 0.030, 0.029),           # 腕：已经比手臂粗
        (0.004, 0.034, 0.032),            # 拳面最宽
        (0.020, 0.032, 0.030),
        (0.034, 0.024, 0.022),
    ]
    rings = []
    for (t, rx, ry) in SECTIONS:
        rings.append([b.add(c + d * t + u * (rx * cx) + v * (ry * cy))
                      for (cx, cy) in TR.circle_pts(8, math.pi / 8.0)])
    TR.loft_rings(b, rings, "tan")
    tip_i = b.add(c + d * 0.042)           # 拳面中心
    for k in range(8):
        b.tri(tip_i, rings[-1][(k + 1) % 8], rings[-1][k], "tan")


def build_arm(side):
    """一条沿曲线放样的六棱管 + 一颗低模拳头。"""
    ctrl = [Vector((p.x * side, p.y, p.z)) for p in ARM_PATH]
    b = TR.Builder()
    TR.add_tube_path(b, smooth_path(ctrl, ARM_RINGS), ARM_RADII,
                     "fur", sides=6, round_start=True)
    wrist = ctrl[-1]
    tip = wrist + Vector((0.002 * side, 0.010, -0.046))
    add_fist(b, wrist, tip)
    return b


def build_thigh(side):
    """大腿：胯 → 膝（胯那头是半球圆头，正好当屁股）"""
    ctrl = [Vector((p.x * side, p.y, p.z)) for p in THIGH_PATH]
    b = TR.Builder()
    TR.add_tube_path(b, smooth_path(ctrl, THIGH_RINGS), THIGH_RADII,
                     "fur", sides=6, round_start=True)
    return b


def build_shin(side):
    """小腿：膝 → 踝（膝那头是半球圆头，把大腿的断口盖住）"""
    ctrl = [Vector((p.x * side, p.y, p.z)) for p in SHIN_PATH]
    b = TR.Builder()
    TR.add_tube_path(b, smooth_path(ctrl, SHIN_RINGS), SHIN_RADII,
                     "fur", sides=6, round_start=True)
    return b


def build_foot(side):
    """脚掌 = 平底楔形放样（脚底严格 z = 0）+ 3 根**短粗圆趾**。

    ⚠️ 趾头之间要留缝：间距 0.0225 > 直径 0.021。
    以前趾距 0.0195 而趾径 0.0244 → 三根方棱趾头互相叠，渲染出来是"锯齿"。
    """
    a = Vector((ANKLE_R.x * side, ANKLE_R.y, ANKLE_R.z))
    rot = Matrix.Rotation(FOOT_SPLAY * side, 3, 'Z')
    ex = rot @ Vector((1.0, 0.0, 0.0))
    ey = rot @ Vector((0.0, 1.0, 0.0))
    b = TR.Builder()

    def P(x, y, z):
        return a + ex * x + ey * y + Vector((0.0, 0.0, z - a.z))

    rings = []
    for (y, hw, top) in FOOT_SECTIONS:
        rings.append([b.add(P(-hw, y, 0.0)),
                      b.add(P(+hw, y, 0.0)),
                      b.add(P(+hw, y, top)),
                      b.add(P(-hw, y, top))])
    TR.loft_rings(b, rings, "tan")
    for xoff in (-0.0225, 0.0, 0.0225):
        base = P(xoff, TOE_BASE_Y, 0.0110)
        tdir = (ey + ex * (xoff * 1.1) + Vector((0.0, 0.0, 0.006))).normalized()
        TR.add_tube(b, base, base + tdir * TOE_LEN, TOE_R0, TOE_R1, "tan", sides=5)
    return b


def build_tail():
    b = TR.Builder()
    path = TR.resample(TR.catmull_rom_3d([Vector(p) for p in TAIL_PTS], 8),
                       len(TAIL_RADII))
    frames = TR.frames_along(path)
    rings = []
    for i, p in enumerate(path):
        u, v = frames[i]
        r = TAIL_RADII[i]
        rings.append([b.add(p + u * (r * cx) + v * (r * cy))
                      for (cx, cy) in TR.circle_pts(TAIL_SIDES)])
    TR.loft_rings(b, rings, "fur")
    return b


limb_of = {}
for tag, builder, anchor in (
        ("Arm_R", build_arm(+1), Vector((SHOULDER_R.x, SHOULDER_R.y, SHOULDER_R.z))),
        ("Arm_L", build_arm(-1), Vector((-SHOULDER_R.x, SHOULDER_R.y, SHOULDER_R.z))),
        ("Thigh_R", build_thigh(+1), Vector((HIP_R.x, HIP_R.y, HIP_R.z))),
        ("Thigh_L", build_thigh(-1), Vector((-HIP_R.x, HIP_R.y, HIP_R.z))),
        ("Shin_R", build_shin(+1), Vector((KNEE_R.x, KNEE_R.y, KNEE_R.z))),
        ("Shin_L", build_shin(-1), Vector((-KNEE_R.x, KNEE_R.y, KNEE_R.z))),
        ("Tail", build_tail(), TAIL_BASE)):
    ob = TR.make_part(PREFIX + "_" + tag, builder, anchor)
    remap_materials(ob, TR_MAT_MAP)
    limb_of[tag] = ob

# 脚掌：单独一个物体，枢轴在踝（**左脚要用镜像过的锚点**，
# 否则 make_part 会把网格按右踝去居中，左脚整个飞到旁边 0.2 m）
foot_of = {}
for tag, side in (("Foot_R", +1), ("Foot_L", -1)):
    anchor = Vector((ANKLE_R.x * side, ANKLE_R.y, ANKLE_R.z))
    ob = TR.make_part(PREFIX + "_" + tag, build_foot(side), anchor)
    remap_materials(ob, TR_MAT_MAP)
    foot_of[tag] = ob


# =====================================================================
# 6. 头：共用头 + **重做的耳朵 / 嘴** + **补的 4 个表情件**
# =====================================================================
head_root = MH.head

# --- 6.0 颅骨重建：共用头只有 12 环 × 8 列，脸盘侧边界是折线（"过分凌厉"）。
#     这里重建一份**加密的颅骨** —— 表面函数没变，只是采样更密，
#     所以五官零件照旧贴得住（它们是按射线打在这张曲面上的）。
def densify_rows(anchors, n):
    """把 (仰角°, 权重) 的锚点细分成 n 行。

    仰角线性细分，权重按锚点线性插值 —— 权重是"这一行往发际线方向偏多少"，
    插值出来的曲面和原来几乎一样，只是采样密了。
    """
    out = []
    deg0, deg1 = anchors[0][0], anchors[-1][0]
    for i in range(n):
        deg = deg0 + (deg1 - deg0) * i / float(n - 1)
        w = anchors[-1][1]
        for k in range(len(anchors) - 1):
            d0, w0 = anchors[k]
            d1, w1 = anchors[k + 1]
            if d1 <= deg <= d0:
                t = (d0 - deg) / (d0 - d1)
                w = w0 + (w1 - w0) * t
                break
        out.append((round(deg, 3), round(w, 4)))
    return out


ROWS_DENSE = [
    # ⚠️ 发际线环（None）**必须在索引 4** —— 共用头的 `HAIR_ROW = 4`，
    #    `build_skull` 按 `j + 1 > HAIR_ROW` 判"这一带是不是脸"，
    #    发际线环往下挪会把整个额头染成橘色（脸变成一张大面具）。
    #    发际线**上面**只能有 4 行（索引 0~3 是写死的）→ 加密只能加在下面，
    #    而脸的**侧边**正好在下面 ✓
    (76.0, 0.10), (66.0, 0.25), (48.0, 0.55), (33.0, 0.95),
    None,
] + densify_rows([(8.0, 0.75), (-8.0, 0.45), (-17.0, 0.32), (-26.0, 0.20),
                  (-46.0, 0.0), (-64.0, 0.0), (-79.0, 0.0)], 26)
# 环向列数 + **分布**。
# 共用头的 `col_az` 有两个毛病：
#   ① 脸的侧边（颞部 / 耳朵那一块）只有 4 列 → 每列跨 28°，
#      **头的侧面就只剩几个大面**（"头部的侧边面数太少"）；
#   ② 脑后那一段的列分布**不均匀**：最后那条闭合边跨了 57°，
#      整个后脑只有两个大面。
# 这里重写分布（`col_az_dense`）：
#   脸盘 12 列（每列 ~11°）+ 两侧毛区各 9 列（每列 ~13°），**均匀**，
#   环向总列数 = 2×9 + 12 + 1 = 31，后脑也是正常的一列一步。
NCOL_FACE_DENSE = 12
NCOL_FUR_DENSE = 9


def col_az_dense(i, A):
    """环向第 i 列的方位角（弧度）：脸盘 -A→+A，两侧毛区 -π→-A / +A→+π。"""
    nf = MH.NCOL_FUR
    nface = MH.NCOL_FACE
    if i < nf:                                  # 左毛区
        return -math.pi + (math.pi - A) * ((i + 0.5) / nf)
    if i <= nf + nface:                         # 脸盘
        return -A + 2.0 * A * ((i - nf) / float(nface))
    j = i - nf - nface - 1                      # 右毛区
    return A + (math.pi - A) * ((j + 0.5) / nf)

# ⚠️ **五官必须按新颅骨重建**：共用头是在它自己那份 12 环颅骨上按射线贴的，
#    加密之后曲面往外挪了 1~2 mm，旧的眼白 / 微笑弧会**埋进脸里**
#    （实测微笑弧直接看不见了）。所以先把旧五官删掉，再按新颅骨重新贴一遍。
FACE_PART_NAMES = ("DSMonkeyEye_L", "DSMonkeyEye_R", "DSMonkeyPupil_L", "DSMonkeyPupil_R",
                   "DSMonkeyEyeShut_L", "DSMonkeyEyeShut_R", "DSMonkeyMouthSmile",
                   "DSMonkeyMouthLaugh", "DSMonkeyMouthFear",
                   "DSMonkeyBrow_L", "DSMonkeyBrow_R", "DSMonkeyNostrils")
for ob in list(MH.MESHES):
    if ob.name in FACE_PART_NAMES:
        MH.MESHES.remove(ob)
        MH.OBJ.pop(ob.name, None)
        bpy.data.objects.remove(ob, do_unlink=True)

_old_head = head_root
_old_head.name = "DSMonkeyHead_old"      # 先把名字让出来，新颅骨才叫得上 "DSMonkeyHead"
# 脸盘**收窄**一圈：侧边界（方位角上限）整体 ×0.86，眼高处 ±66° → ±57°。
# 不收窄的话橘色是"铺满"整张正脸的，两侧看不到毛的轮廓。
FACE_NARROW = 0.86
MH.SIDE_LIMIT = [(el, az * FACE_NARROW) for (el, az) in MH.SIDE_LIMIT]

MH.ROWS[:] = ROWS_DENSE
MH.NCOL_FACE = NCOL_FACE_DENSE
MH.NCOL_FUR = NCOL_FUR_DENSE
MH.NCOL = 2 * NCOL_FUR_DENSE + NCOL_FACE_DENSE + 1
MH.col_az = col_az_dense            # 换掉共用头那个不均匀的列分布
head_root = MH.build_skull()
for ob in MH.MESHES:
    if ob is not _old_head:
        ob.parent = head_root          # 五官改挂到新颅骨
        ob.matrix_parent_inverse.identity()
MH.MESHES.remove(_old_head)
MH.MESHES.append(head_root)
bpy.data.objects.remove(_old_head, do_unlink=True)
MH.head = head_root
MH.OBJ = {ob.name: ob for ob in MH.MESHES}

# 脸盘边缘那一圈**整个四边形**染成过渡色。
# ⚠️ 共用头是**按对角线**把每个四边形拆成两个三角形再上色的，
#    所以脸盘的颜色边界落在**对角线**上 → 边界是"锯齿线"而不是干净的边。
#    这里把"脸盘最外一列 + 毛区最里一列"之间的那一圈整个染成同一种过渡色，
#    边界就回到四边形的边上（一条干净的线）+ 一圈柔和的过渡。
MAT_SHADOW = make_material(PREFIX + "_tan_shadow", (0.690, 0.478, 0.286), 0.71)


def shade_face_edge(head):
    """把脸盘边界**两侧**那一圈染成过渡色（毛→过渡→脸，三色过渡）。"""
    me = head.data
    ncols = MH.NCOL
    nrows = len(MH.ROWS)
    i_last_face = MH.NCOL_FUR + MH.NCOL_FACE       # 脸盘最外一列（+A 侧）
    pairs = set()
    for j in range(nrows):
        a = 1 + j * ncols + i_last_face
        pairs.add((a, a + 1))                     # +A 侧：脸盘最外一列 ↔ 毛区第一列
        b = 1 + j * ncols + (MH.NCOL_FUR - 1)      # -A 侧：毛区最后一列 ↔ 脸盘第一列
        pairs.add((b, b + 1))
    me.materials.append(MAT_SHADOW)
    shadow_idx = len(me.materials) - 1
    n = 0
    for poly in me.polygons:
        vs = list(poly.vertices)
        for a, b in pairs:
            if a in vs and b in vs:
                poly.material_index = shadow_idx
                n += 1
                break
    print("  脸盘边缘过渡带：%d 个面" % n)


shade_face_edge(head_root)

# 五官按**新颅骨**重新贴一遍（共用头自带的构建函数，接受 bvh 参数 ✓）
bvh = MH.make_bvh(head_root)
MH.MESHES.extend(MH.build_eye_parts(bvh))
MH.MESHES.extend(MH.build_mouth_parts(bvh))
MH.MESHES.extend(MH.build_mark_parts(bvh))
MH.OBJ = {ob.name: ob for ob in MH.MESHES}

# --- 6.1 删掉共用头那对 8 边扁盘耳朵 + 2 张尖角嘴（重做） ---
for ob in list(MH.MESHES):
    if ob.name in ("DSMonkeyEar_L", "DSMonkeyEar_R",
                   "DSMonkeyMouthLaugh", "DSMonkeyMouthFear"):
        MH.MESHES.remove(ob)
        MH.OBJ.pop(ob.name, None)
        bpy.data.objects.remove(ob, do_unlink=True)


def build_ear(side):
    """碗形耳朵：外圈厚毛边 + 凹进去的橘色耳窝 + 背面棕色封口。

    12 段（共用头那对只有 8 段 → 读成一个八角形别针）。
    橘色耳窝只占内圈 55 %（共用头占 66 % → 整个耳朵读成一个橘色月牙）。
    耳心放在颅骨**里面**（EAR_X 0.135 < 颅骨半宽 0.138），
    外沿只探出 0.045 m —— 以前那对整个飘在头外面 0.09 m。
    """
    n = Vector((EAR_N.x * side, EAR_N.y, EAR_N.z)).normalized()
    up = Vector((0.0, 0.0, 1.0))
    e2 = (up - n * up.dot(n)).normalized()
    e1 = e2.cross(n).normalized()
    C = Vector((EAR_X * side, EAR_Y, EAR_Z))

    rings = [(1.00, 1.00, -0.012),     # 外缘（毛边最厚）
             (1.00, 1.00, 0.006),      # 外缘翻到正面
             (0.94, 0.95, 0.014),      # 毛边的内唇
             (0.80, 0.84, 0.012),      # 碗壁
             (0.62, 0.68, 0.004),
             (0.40, 0.46, 0.000)]
    slot_of = ["fur", "fur_light", "fur_light", "fur_light", "ear_in", "ear_in"]
    verts, faces, ring_idx = [], [], []
    for (fx, fy, d) in rings:
        idx = []
        for k in range(EAR_SEGS):
            a = 2.0 * math.pi * k / EAR_SEGS
            idx.append(len(verts))
            verts.append(C + e1 * (EAR_RX * fx * math.cos(a))
                         + e2 * (EAR_RY * fy * math.sin(a)) + n * d)
        ring_idx.append(idx)
    ctr = len(verts)
    verts.append(C + n * 0.002)
    for j in range(len(rings) - 1):
        for k in range(EAR_SEGS):
            k2 = (k + 1) % EAR_SEGS
            faces.append(((ring_idx[j][k], ring_idx[j][k2],
                           ring_idx[j + 1][k2], ring_idx[j + 1][k]), slot_of[j]))
    for k in range(EAR_SEGS):
        k2 = (k + 1) % EAR_SEGS
        faces.append(((ring_idx[-1][k], ring_idx[-1][k2], ctr), "ear_in"))
    # 背面封口（不然从脑后能看见碗底的橘耳窝）
    back = len(verts)
    verts.append(C - n * 0.004)
    for k in range(EAR_SEGS):
        k2 = (k + 1) % EAR_SEGS
        faces.append(((back, ring_idx[0][k2], ring_idx[0][k]), "fur"))
    ob = MH.build_object("DSMonkeyEar_" + ("L" if side < 0 else "R"), verts, faces)
    recalc_normals(ob)
    return ob


MH.MESHES.extend([build_ear(-1), build_ear(+1)])

# --- 6.2 补表情件（共用头只有 3 张嘴 / 1 对眯眼，够不着用） ---
#     bvh 已在 6.0 建好（对着**新颅骨**）


def build_blink_arcs():
    """闭眼线：一条**平缓向下**的弧（眨眼）。
    共用头那对 `EyeShut` 是**向上**拱的弧 = 开心眯眼；两种要分开。"""
    out = []
    for side in (1, -1):
        tag = "L" if side < 0 else "R"
        x = MH.EYE_X * side
        verts, faces = [], []
        arc = [(-0.0225, -0.0062), (-0.011, -0.0020), (0.0, 0.0),
               (0.011, -0.0020), (0.0225, -0.0062)]
        path = [MH.front_point(bvh, x + dx, MH.EYE_Z + dz, -0.0022)
                for dx, dz in arc]
        MH.tube(verts, faces, path, 0.0040, "mark", sides=4)
        out.append(MH.make_part("DSMonkeyEyeBlink_" + tag, verts, faces,
                                MH.surf_at(bvh, x, MH.EYE_Z), recalc=True))
    return out


def build_mouth_flat():
    """抿嘴：一条平直略带弧的线（走路 / 跑步的"专注"）。"""
    pts = [(0.048, -0.088), (0.026, -0.095), (0.0, -0.097),
           (-0.026, -0.095), (-0.048, -0.088)]
    verts, faces = [], []
    path = [MH.front_point(bvh, q[0], q[1], -0.0022)
            for q in MH.catmull_rom(pts, 2)]
    n = len(path)
    radius = [0.0038 * (0.72 + 0.28 * math.sin(math.pi * i / (n - 1.0)))
              for i in range(n)]
    MH.tube(verts, faces, path, radius, "mark", sides=4)
    c = Vector((0.0, 0.0, 0.0))
    for q in path:
        c += q
    return MH.make_part("DSMonkeyMouthFlat", verts, faces, c / n, recalc=True)


def build_mouth_mesh(name, outline, rim_r=0.0040, tongue=None, pivot=None):
    """贴脸的"洞"：腔底 + 外圈描边 + 可选舌头。

    ⚠️ 共用头那张嘴的腔底是「一圈点 + 中心点」的**单圈扇面**：
    扇形的**弦**会切进鼓着的颅骨里 → 中间露出**脸色的面**，
    渲染出来是一朵"花瓣"，嘴看着特别怪。
    这里腔底用**两圈**贴面点（轮廓圈 + 内圈）+ 中心点，
    每块三角形都短，弦切不进颅骨 → 口腔是一整片深色 ✓

    顶点一律"打到颅面上再沿法线抬起"，所以腔底是**贴着脸鼓出来的**，
    不是一块平板。
    """
    verts, faces, slots = [], [], []

    pts = [Vector((q[0], q[1])) for q in outline]
    area = 0.0
    for i in range(len(pts)):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % len(pts)]
        area += x0 * y1 - x1 * y0
    if area < 0.0:                       # 顺时针 → 翻过来，保证填充面朝 +Y
        pts.reverse()
    cc = Vector((0.0, 0.0))
    for q in pts:
        cc += q
    cc /= len(pts)

    def surf(px, pz, off=0.0022):
        loc, nor = MH.hit(bvh, Vector((px, 1.5, pz)), Vector((0.0, -1.0, 0.0)))
        return loc + nor * off

    def fill_ring(poly, off=0.0022):
        """把一圈 (x,z) 贴成颅面上的点，返回顶点索引。"""
        idx = []
        for q in poly:
            idx.append(len(verts))
            verts.append(surf(q.x, q.y, off))
        return idx

    outer = fill_ring(pts)
    inner = fill_ring([cc + (q - cc) * 0.55 for q in pts])
    ctr = len(verts)
    verts.append(surf(cc.x, cc.y))
    n = len(pts)
    for i in range(n):
        j = (i + 1) % n
        faces.append(((ctr, inner[i], inner[j])))
        slots.append("mouth")
        faces.append(((inner[i], outer[i], outer[j])))
        slots.append("mouth")
        faces.append(((inner[i], outer[j], inner[j])))
        slots.append("mouth")

    # 外圈描边（细管）—— ⚠️ `MH.tube` 追加的是 `(面, 槽名)` 二元组，
    #    这里要拆开摊平成"面 + 槽名列表"（本脚本的建物体是自己写的）。
    #    管子两端**收细**，端盖才不会被看成嘴角上两个小疙瘩。
    path = [MH.front_point(bvh, q.x, q.y, -0.0016) for q in pts]
    radii = [rim_r * (0.28 + 0.72 * math.sin(math.pi * i / max(1, len(pts) - 1.0)))
             for i in range(len(pts))]
    n0 = len(faces)
    MH.tube(verts, faces, path, radii, "mark", sides=4)
    new = faces[n0:]
    del faces[n0:]
    for idx_tuple, slot_name in new:
        faces.append(tuple(idx_tuple))
        slots.append(slot_name)

    # 舌头：同样是两圈贴面点的小椭圆。
    # ⚠️ 舌头要比腔底**更靠前**（+4.5 mm vs 腔底 +2.2 mm），
    #    否则两张面共面 → z-fighting → 舌头被咬掉一半（渲染出来是两瓣碎粉色）。
    if tongue:
        tpts = [Vector(q) for q in tongue]
        tcc = Vector((0.0, 0.0))
        for q in tpts:
            tcc += q
        tcc /= len(tpts)
        t_outer = fill_ring(tpts, 0.0046)
        t_inner = fill_ring([tcc + (q - tcc) * 0.55 for q in tpts], 0.0046)
        t_ctr = len(verts)
        verts.append(surf(tcc.x, tcc.y, 0.0046))
        m = len(tpts)
        for i in range(m):
            j = (i + 1) % m
            faces.append(((t_ctr, t_inner[i], t_inner[j])))
            slots.append("tongue")
            faces.append(((t_inner[i], t_outer[i], t_outer[j])))
            slots.append("tongue")
            faces.append(((t_inner[i], t_outer[j], t_inner[j])))
            slots.append("tongue")

    faces = flip_to_front(faces, verts)

    # 建物体（材质槽按首次出现顺序）
    used = []
    for s in slots:
        if s not in used:
            used.append(s)
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], faces)
    me.validate()
    for s in used:
        me.materials.append(MH.MATS[s])
    idx_of = {s: i for i, s in enumerate(used)}
    for poly, s in zip(me.polygons, slots):
        poly.material_index = idx_of[s]
        poly.use_smooth = False
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    # 枢轴挪到口腔中心（动画要绕它转）
    p = surf(cc.x, cc.y) if pivot is None else Vector(pivot)
    for v in ob.data.vertices:
        v.co -= p
    ob.location = p
    return ob


def build_mouth_laugh():
    """大笑：宽嘴（16 点圆弧轮廓）+ 舌头。共用头那张是尖角多边形 → 一坨黑疙瘩。"""
    # 嘴角是**圆角**（20 点）—— 尖角的话描边管子在那里急转弯，
    # 会留下两个"小犄角"（管子的端盖露出来）
    outline = [
        (0.050, -0.082), (0.044, -0.075), (0.034, -0.069), (0.021, -0.065),
        (0.000, -0.063), (-0.021, -0.065), (-0.034, -0.069), (-0.044, -0.075),
        (-0.050, -0.082), (-0.052, -0.088), (-0.051, -0.094),
        (-0.046, -0.101), (-0.036, -0.108), (-0.020, -0.112), (0.000, -0.114),
        (0.020, -0.112), (0.036, -0.108), (0.046, -0.101),
        (0.051, -0.094), (0.052, -0.088),
    ]
    # 舌头：一个规规矩矩的小椭圆（共用头那张是尖角多边形 → 渲染出来像粉色蝴蝶结）
    tongue = [(0.023 * math.cos(a), -0.100 + 0.007 * math.sin(a))
              for a in (2.0 * math.pi * k / 10.0 for k in range(10))]
    ob = build_mouth_mesh("DSMonkeyMouthLaugh", outline, 0.0042, tongue=tongue)
    return ob


def build_mouth_fear():
    """惊恐：竖长的小 O（12 点椭圆）。"""
    outline = []
    for k in range(12):
        a = 2.0 * math.pi * k / 12.0
        outline.append((0.0155 * math.cos(a), -0.0890 + 0.0195 * math.sin(a)))
    return build_mouth_mesh("DSMonkeyMouthFear", outline, 0.0038)


def build_mouth_pants():
    """小张嘴（跑步喘气）：一个竖长的小椭圆暗腔。"""
    outline = [(0.000, -0.078), (0.015, -0.090), (0.018, -0.102),
               (0.000, -0.116), (-0.018, -0.102), (-0.015, -0.090)]
    return build_mouth_mesh("DSMonkeyMouthPants", outline, 0.0036)


extra = build_blink_arcs() + [build_mouth_flat(), build_mouth_laugh(),
                              build_mouth_fear(), build_mouth_pants()]
MH.MESHES.extend(extra)

# --- 6.3 改名 + 摆到脖子上 ---
for ob in MH.MESHES:
    ob.name = PREFIX + "_" + ob.name.replace("DSMonkey", "")
MH.OBJ = {ob.name: ob for ob in MH.MESHES}

off = Vector((0.0, 0.0, HEAD_C_Z - NECK_Z))
for ob in MH.MESHES:
    if ob is head_root:
        continue
    ob.location = off + Vector(ob.location) * HEAD_SCALE
    for v in ob.data.vertices:
        v.co = v.co * HEAD_SCALE
for v in head_root.data.vertices:
    v.co += off
head_root.location = Vector((0.0, 0.0, 0.0))

# 新加的表情件默认藏进颅骨（位置，不是 scale）
# ⚠️ **重做的嘴（MouthLaugh / MouthFear）也要藏** —— 它们顶掉了共用头那两张，
#    而共用头是在自己的模块里藏的，本脚本新做的这几张没人藏 →
#    大笑嘴会**一直挂在脸上**，和微笑弧叠在一起（"嘴巴重叠"就是这么来的）。
EXTRA_HIDDEN = [PREFIX + "_EyeBlink_L", PREFIX + "_EyeBlink_R",
                PREFIX + "_EyeShut_L", PREFIX + "_EyeShut_R",
                PREFIX + "_MouthLaugh", PREFIX + "_MouthFear",
                PREFIX + "_MouthFlat", PREFIX + "_MouthPants"]
PARK = Vector((0.0, -0.060, 0.0))
for nm in EXTRA_HIDDEN:
    MH.OBJ[nm].location = MH.OBJ[nm].location + PARK


# =====================================================================
# 7. 骨架层级
#    Root → Hips（整体起伏）→ Torso（绕髋俯仰）→ Head → 颅骨 + 五官
#                 ├ Arm_R / Arm_L（挂躯干，跟着俯仰）
#                 ├ Thigh_R / Thigh_L → Shin_R / Shin_L → Foot_R / Foot_L
#                 └ Tail
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
hips = empty("Hips", root, (0.0, 0.0, 0.0))

# 躯干网格按**世界 z** 建的 → 把它挪成"以髋为原点的局部坐标"，
# 这样躯干绕自己的原点转 = 绕髋俯仰（跑步前倾 / 坐姿后靠）
for v in torso.data.vertices:
    v.co.z -= PIVOT_Z
torso.parent = hips
torso.matrix_parent_inverse.identity()
torso.location = Vector((0.0, 0.0, PIVOT_Z))

# 肚皮壳：网格同样是"世界 z − 枢轴高"，但**位置留在原点**
# （它是躯干的子物体，躯干那个 +PIVOT_Z 的平移已经算在父级里了）
for ob in belly_parts:
    for v in ob.data.vertices:
        v.co.z -= PIVOT_Z
    ob.parent = torso
    ob.matrix_parent_inverse.identity()
    ob.location = Vector((0.0, 0.0, 0.0))

head_node = empty("HeadNode", torso, (0.0, 0.0, NECK_Z - PIVOT_Z))
head_root.parent = head_node
head_root.matrix_parent_inverse.identity()
for ob in MH.MESHES:
    if ob is not head_root:
        ob.parent = head_root
        ob.matrix_parent_inverse.identity()

for tag in ("Arm_R", "Arm_L"):
    ob = limb_of[tag]
    ob.parent = torso
    ob.matrix_parent_inverse.identity()
    ob.location = Vector((SHOULDER_R.x * (-1 if tag.endswith("L") else 1),
                          SHOULDER_R.y, SHOULDER_R.z)) - Vector((0.0, 0.0, PIVOT_Z))

for tag in ("Thigh_R", "Thigh_L", "Tail"):
    ob = limb_of[tag]
    ob.parent = hips
    ob.matrix_parent_inverse.identity()

# 小腿挂在大腿下面（枢轴 = 膝），脚掌挂在小腿下面（枢轴 = 踝）
for tag, thightag in (("Shin_R", "Thigh_R"), ("Shin_L", "Thigh_L")):
    ob = limb_of[tag]
    ob.parent = limb_of[thightag]
    ob.matrix_parent_inverse.identity()
    sx = -1 if thightag.endswith("L") else 1
    ob.location = Vector((KNEE_R.x * sx, KNEE_R.y, KNEE_R.z)) - \
        Vector((HIP_R.x * sx, HIP_R.y, HIP_R.z))

for tag, shintag in (("Foot_R", "Shin_R"), ("Foot_L", "Shin_L")):
    ob = foot_of[tag]
    ob.parent = limb_of[shintag]
    ob.matrix_parent_inverse.identity()
    sx = -1 if shintag.endswith("L") else 1
    ob.location = Vector((ANKLE_R.x * sx, ANKLE_R.y, ANKLE_R.z)) - \
        Vector((KNEE_R.x * sx, KNEE_R.y, KNEE_R.z))

bpy.context.view_layer.update()

# **静止位快照** —— 换片段时必须把物体恢复到这个状态。
# ⚠️ Blender 里"action 被撤下"**不会**把属性退回静止值：上一段动画求值过的
# rotation_euler 会**留在物体上**（实测：切到 Idle 之后腿还留着上一段的 0.69 rad，
# 脚底离地 8 mm）。所以这里显式存一份静止位，换片段时显式写回去。
REST = {}
for ob in bpy.context.scene.objects:
    REST[ob.name] = (Vector(ob.location), Vector(ob.rotation_euler))

ARM_R = PREFIX + "_Arm_R"
ARM_L = PREFIX + "_Arm_L"
THIGH_R = PREFIX + "_Thigh_R"
THIGH_L = PREFIX + "_Thigh_L"
SHIN_R = PREFIX + "_Shin_R"
SHIN_L = PREFIX + "_Shin_L"
FOOT_R = PREFIX + "_Foot_R"
FOOT_L = PREFIX + "_Foot_L"
TAIL = PREFIX + "_Tail"
HIPS = PREFIX + "_Hips"
TORSO = PREFIX + "_Torso"
HEAD = PREFIX + "_Head"          # 颅骨本体（绕颅心转 = 歪头）

FEET = [bpy.data.objects[FOOT_R], bpy.data.objects[FOOT_L]]
LEGS_OBJS = [bpy.data.objects[THIGH_R], bpy.data.objects[THIGH_L],
             bpy.data.objects[SHIN_R], bpy.data.objects[SHIN_L]]

# 脸 / 耳的零件（表情要动的就是这些）
FACE = [PREFIX + "_" + s for s in (
    "Eye_L", "Eye_R", "Pupil_L", "Pupil_R",
    "EyeShut_L", "EyeShut_R", "EyeBlink_L", "EyeBlink_R",
    "MouthSmile", "MouthLaugh", "MouthFear", "MouthFlat", "MouthPants",
    "Brow_L", "Brow_R", "Ear_L", "Ear_R")]
# 位置通道要"瞬切"的（换脸 / 睁闭眼），其余走平滑插值
CONST_LOC = set(PREFIX + "_" + s for s in (
    "Eye_L", "Eye_R", "Pupil_L", "Pupil_R",
    "EyeShut_L", "EyeShut_R", "EyeBlink_L", "EyeBlink_R",
    "MouthSmile", "MouthLaugh", "MouthFear", "MouthFlat", "MouthPants"))


# =====================================================================
# 8. 动画
# =====================================================================
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


def key_clip(name, length, keys, loop=False, hold=False):
    """keys: [(帧, {物体名: {"loc": (x,y,z), "rot": (x,y,z)}}]

    每个被点名的物体各建一个 action + **一条同名 NLA 轨**；
    导出器按轨名把各物体的动画并成一条 glTF animation（§2.1 记的坑）。

    loop=True（走路 / 跑 / 待机这类循环片段）：**末帧不强制回中性**，
    靠"最后一帧姿势 == 第一帧姿势"保证循环无缝；
    hold=True（坐姿这种"摆好不动"的片段）：同样不回中性，末帧保持姿势；
    其余（一次性动作）：末帧回静止位。
    """
    touched = set()
    for _, pose in keys:
        touched |= set(pose)
    last = length - 1
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
            if nm in pose:
                pts[f - 1] = pose[nm]
        if not loop and not hold:
            pts.setdefault(last, {})
        # ⚠️ **导出器会把"整段不变"的通道整个丢掉**（实测：旧版 Run 的躯干前倾
        #    0.16 rad 根本没进 .glb；旧版 Sit 的腿也只剩 4 条通道）。
        #    嘴要是整段不动（走路一直抿嘴），通道被丢 → "换嘴"失效，
        #    中性微笑会一直挂在脸上。所以给嘴加一点**下颌微动**（2.2 mm，看不出来），
        #    让通道有变化。眼睛的弧线太细，抖一下就看得见，不加。
        if nm.startswith(PREFIX + "_Mouth"):
            vals = set()
            for f, p in pts.items():
                vals.add(tuple(round(x, 6) for x in p.get("loc", (0.0, 0.0, 0.0))))
            if len(vals) == 1:
                for f in sorted(pts):
                    p = dict(pts[f])
                    loc = list(p.get("loc", (0.0, 0.0, 0.0)))
                    loc[2] += 0.0022 * math.sin(2.0 * math.pi * f / 12.0)
                    p["loc"] = tuple(loc)
                    pts[f] = p
        for f in sorted(pts):
            p = pts[f]
            ob.location = base_l + Vector(p.get("loc", (0.0, 0.0, 0.0)))
            ob.rotation_euler = base_r + Vector(p.get("rot", (0.0, 0.0, 0.0)))
            ob.keyframe_insert("location", frame=f)
            ob.keyframe_insert("rotation_euler", frame=f)
        ad.action = None
        if nm in CONST_LOC:
            # 换脸要**瞬切**（CONSTANT），否则两个嘴在过渡帧会同时露一半
            for fc in action_fcurves(act):
                if fc.data_path == "location":
                    for kp in fc.keyframe_points:
                        kp.interpolation = 'CONSTANT'
        tr = ad.nla_tracks.new()
        tr.name = name
        st = tr.strips.new(name, 0, act)
        try:
            st.action_slot = act.slots[0]
        except Exception:
            pass
        # ⚠️ **strip 必须显式给帧范围**：默认 frame_end = 0 → 片段长度是 0，
        # 无论 frame_set 到第几帧永远停在第 0 帧（动画"不动"）。
        st.frame_start = 0
        st.frame_end = length
        tr.mute = True
        ob.location = base_l
        ob.rotation_euler = base_r


# ---------------------------------------------------------------------
# 8.1 表情小工具
#     每一次调用都会把**所有**眼 / 嘴零件都点名一遍，
#     否则"只点了要变的那个"会让上一个表情的状态粘住（§2.11 记的坑）。
# ---------------------------------------------------------------------
SHOW = (0.0, 0.060, 0.0)        # 从颅骨里推到脸上
HIDE = (0.0, -0.060, 0.0)       # 推进颅骨里藏起来

MOUTH_MAP = {"smile": "MouthSmile", "laugh": "MouthLaugh", "fear": "MouthFear",
             "flat": "MouthFlat", "pants": "MouthPants"}
MOUTH_PARTS = ["MouthSmile", "MouthLaugh", "MouthFear", "MouthFlat", "MouthPants"]


def merge(*dicts):
    out = {}
    for d in dicts:
        out.update(d)
    return out


def brow(side, dz, tilt):
    tag = "L" if side < 0 else "R"
    return {PREFIX + "_Brow_" + tag: {"loc": (0.0, 0.0, dz),
                                     "rot": (0.0, tilt * side, 0.0)}}


def eyes(open_=True, shut=False, blink=False):
    """睁 / 眯 / 眨：眼白、瞳孔、两条弧线**六个零件一起**换。"""
    p = {}
    for s in ("L", "R"):
        p[PREFIX + "_Eye_" + s] = {"loc": (0.0, 0.0, 0.0)} if open_ else {"loc": HIDE}
        p[PREFIX + "_Pupil_" + s] = {"loc": (0.0, 0.0, 0.0)} if open_ else {"loc": HIDE}
        p[PREFIX + "_EyeShut_" + s] = {"loc": SHOW} if shut else {"loc": HIDE}
        p[PREFIX + "_EyeBlink_" + s] = {"loc": SHOW} if blink else {"loc": HIDE}
    return p


def mouth(which):
    """which: smile / laugh / fear / flat / pants —— 只有一张嘴露在外面。"""
    p = {}
    for nm in MOUTH_PARTS:
        p[PREFIX + "_" + nm] = {"loc": HIDE}
    if which == "smile":
        p[PREFIX + "_MouthSmile"] = {"loc": (0.0, 0.0, 0.0)}   # 微笑是静止位
    else:
        p[PREFIX + "_" + MOUTH_MAP[which]] = {"loc": SHOW}
    return p


def head_pose(rot=(0.0, 0.0, 0.0)):
    return {HEAD: {"rot": rot}}


def ears(pose):
    return {PREFIX + "_Ear_L": pose[0], PREFIX + "_Ear_R": pose[1]}


def legs_pose(thigh_r, shin_r, foot_r, thigh_l, shin_l, foot_l):
    """一条腿的姿态：大腿 / 小腿 / 脚掌 三个角度（绕各自的 X 轴）。"""
    return {THIGH_R: (thigh_r, 0.0, 0.0),
            SHIN_R: (shin_r, 0.0, 0.0),
            FOOT_R: (foot_r, 0.0, 0.0),
            THIGH_L: (thigh_l, 0.0, 0.0),
            SHIN_L: (shin_l, 0.0, 0.0),
            FOOT_L: (foot_l, 0.0, 0.0)}


# ---------------------------------------------------------------------
# 8.2 地面求解器：髋高**算**出来，循环片段永远有一只脚正好踩在地上
# ---------------------------------------------------------------------
def foot_min_z():
    dg = bpy.context.evaluated_depsgraph_get()
    best = 1e9
    for ob in FEET:
        ev = ob.evaluated_get(dg)
        for v in ob.data.vertices:
            z = (ev.matrix_world @ v.co).z
            best = min(best, z)
    return best


def solve_ground(frames_poses):
    """frames_poses: {帧: {腿/脚名: (rx,ry,rz)}} → {帧: 髋部 z 偏移}

    先摆腿 → 量脚底**真实顶点** → 取负当髋高。
    ⚠️ 必须用真实顶点而不是 bound_box：腿转起来之后，轴对齐的包围盒角
    会比实际几何低好几毫米（盒子不跟着转），会报出假的穿地。
    """
    out = {}
    saved = {ob.name: ob.rotation_euler.copy() for ob in FEET + LEGS_OBJS}
    for f in sorted(frames_poses):
        for nm, r in frames_poses[f].items():
            bpy.data.objects[nm].rotation_euler = Vector(r)
        bpy.context.view_layer.update()
        out[f] = -foot_min_z()
    for nm, r in saved.items():
        bpy.data.objects[nm].rotation_euler = r
    bpy.context.view_layer.update()
    return out


# ---------------------------------------------------------------------
# 8.3 各段动作
# ---------------------------------------------------------------------
# --- Idle：待机（49 帧 = 2 秒，末帧 == 首帧 → 循环无缝） ---
IDLE_LEN = 49
IDLE = [
    (1, {TAIL: {"rot": (0.0, 0.0, -0.16)}, ARM_R: {"rot": (0.0, 0.0, 0.05)},
         ARM_L: {"rot": (0.0, 0.0, -0.05)}, HIPS: {"loc": (0.0, 0.0, 0.0)},
         **merge(eyes(), mouth("smile"), brow(-1, 0.0, 0.0), brow(+1, 0.0, 0.0))}),
    (13, {TAIL: {"rot": (0.0, 0.0, 0.16)}, ARM_R: {"rot": (0.0, 0.0, -0.05)},
          ARM_L: {"rot": (0.0, 0.0, 0.05)}, HIPS: {"loc": (0.0, 0.0, 0.005)},
          **merge(eyes(), mouth("smile"))}),
    # 眨眼：帧 19~23 闭眼线出来，帧 24 睁回来
    (19, merge(eyes(open_=False, blink=True))),
    (23, merge(eyes(open_=False, blink=True))),
    (24, merge(eyes(), mouth("smile"))),
    (25, {TAIL: {"rot": (0.0, 0.0, -0.16)}, ARM_R: {"rot": (0.0, 0.0, 0.05)},
          ARM_L: {"rot": (0.0, 0.0, -0.05)}, HIPS: {"loc": (0.0, 0.0, 0.0)},
          **merge(eyes(), mouth("smile"))}),
    (37, {TAIL: {"rot": (0.0, 0.0, 0.16)}, ARM_R: {"rot": (0.0, 0.0, -0.05)},
          ARM_L: {"rot": (0.0, 0.0, 0.05)}, HIPS: {"loc": (0.0, 0.0, 0.005)},
          **merge(eyes(), mouth("smile"))}),
    (49, {TAIL: {"rot": (0.0, 0.0, -0.16)}, ARM_R: {"rot": (0.0, 0.0, 0.05)},
          ARM_L: {"rot": (0.0, 0.0, -0.05)}, HIPS: {"loc": (0.0, 0.0, 0.0)},
          **merge(eyes(), mouth("smile"), brow(-1, 0.0, 0.0), brow(+1, 0.0, 0.0))}),
]

# --- Sit：坐姿 —— 大腿前伸 + 小腿垂下 + 脚掌回平，髋部整体下沉（地面求解器算）
#     → 屁股和脚掌同时着地。**姿势从"刚开始坐"慢慢落到"坐定"**，
#       不然整段姿势一模一样 → 导出器会把这条通道丢掉，坐姿就没了。
SIT_LEN = 48
SIT_LEGS_A = legs_pose(1.62, -1.06, -0.62, 1.62, -1.06, -0.62)
SIT_LEGS_B = legs_pose(1.57, -1.00, -0.57, 1.57, -1.00, -0.57)
sit_frames = {1: dict(SIT_LEGS_A), 24: dict(SIT_LEGS_B), 48: dict(SIT_LEGS_B)}
SIT = [
    (1, {ARM_R: {"rot": (0.36, 0.0, 0.0)}, ARM_L: {"rot": (0.36, 0.0, 0.0)},
         TAIL: {"rot": (0.0, 0.0, 0.06)}, TORSO: {"rot": (0.10, 0.0, 0.0)},
         **merge(eyes(), mouth("smile"), head_pose((0.06, 0.0, 0.0)))}),
    (20, merge(eyes(open_=False, blink=True))),
    (24, merge(eyes(), mouth("smile"))),
    (48, {ARM_R: {"rot": (0.44, 0.0, 0.0)}, ARM_L: {"rot": (0.44, 0.0, 0.0)},
          TAIL: {"rot": (0.0, 0.0, 0.14)}, TORSO: {"rot": (0.16, 0.0, 0.0)},
          **merge(eyes(), mouth("smile"), head_pose((0.10, 0.0, 0.0)))}),
]

# --- Walk：49 帧 2 步；脸 = 专注（下眉 + 抿嘴）+ 眨眼 ---
WALK_LEN = 49
walk_legs = {
    1: legs_pose(0.42, -0.16, 0.10, -0.42, 0.00, -0.30),
    13: legs_pose(0.00, -0.30, 0.00, 0.00, -0.30, 0.00),
    25: legs_pose(-0.42, 0.00, -0.30, 0.42, -0.16, 0.10),
    37: legs_pose(0.00, -0.30, 0.00, 0.00, -0.30, 0.00),
    49: legs_pose(0.42, -0.16, 0.10, -0.42, 0.00, -0.30),
}
WALK_FOCUS = merge(eyes(), mouth("flat"),
                   brow(-1, -0.007, 0.12), brow(+1, -0.007, -0.12))
# 过腿相那一瞬间眉头松开一点 —— 眉毛也要**有变化**，否则整段不变的通道会被丢掉
WALK_PASS = merge(eyes(), mouth("flat"),
                  brow(-1, -0.002, 0.05), brow(+1, -0.002, -0.05))
WALK = [
    (1, {ARM_R: {"rot": (-0.48, 0, 0)}, ARM_L: {"rot": (0.48, 0, 0)},
         TAIL: {"rot": (0, 0, 0.10)}, **WALK_FOCUS}),
    (13, {ARM_R: {"rot": (0.0, 0, 0)}, ARM_L: {"rot": (0.0, 0, 0)},
          TAIL: {"rot": (0, 0, -0.10)}, **WALK_PASS}),
    (17, merge(eyes(open_=False, blink=True))),
    (19, merge(eyes(open_=False, blink=True))),
    (20, merge(eyes(), mouth("flat"))),
    (25, {ARM_R: {"rot": (0.48, 0, 0)}, ARM_L: {"rot": (-0.48, 0, 0)},
          TAIL: {"rot": (0, 0, 0.10)}, **WALK_FOCUS}),
    (37, {ARM_R: {"rot": (0.0, 0, 0)}, ARM_L: {"rot": (0.0, 0, 0)},
          TAIL: {"rot": (0, 0, -0.10)}, **WALK_PASS}),
    (41, merge(eyes(open_=False, blink=True))),
    (43, merge(eyes(open_=False, blink=True))),
    (44, merge(eyes(), mouth("flat"))),
    (49, {ARM_R: {"rot": (-0.48, 0, 0)}, ARM_L: {"rot": (0.48, 0, 0)},
          TAIL: {"rot": (0, 0, 0.10)}, **WALK_FOCUS}),
]

# --- Run：25 帧 2 步；脸 = 用力（张嘴喘 + 皱眉） ---
RUN_LEN = 25
run_legs = {
    1: legs_pose(0.72, -0.55, -0.18, -0.62, 0.00, -0.40),
    7: legs_pose(0.25, -0.95, 0.00, -0.20, -0.20, 0.00),
    13: legs_pose(-0.62, 0.00, -0.40, 0.72, -0.55, -0.18),
    19: legs_pose(-0.20, -0.20, 0.00, 0.25, -0.95, 0.00),
    25: legs_pose(0.72, -0.55, -0.18, -0.62, 0.00, -0.40),
}
RUN_PANT = merge(eyes(), mouth("pants"),
                 brow(-1, -0.012, 0.18), brow(+1, -0.012, -0.18))
# 腾空那一下眉头松开一点（眉毛通道也要有变化）
RUN_EASE = merge(eyes(), mouth("pants"),
                 brow(-1, -0.005, 0.09), brow(+1, -0.005, -0.09))
RUN = [
    (1, {ARM_R: {"rot": (-0.80, 0, 0)}, ARM_L: {"rot": (0.80, 0, 0)},
         TORSO: {"rot": (0.16, 0, 0)}, TAIL: {"rot": (0, 0, 0.18)}, **RUN_PANT}),
    (7, {ARM_R: {"rot": (0.0, 0, 0)}, ARM_L: {"rot": (0.0, 0, 0)},
         TORSO: {"rot": (0.13, 0, 0)}, TAIL: {"rot": (0, 0, -0.14)}, **RUN_EASE}),
    (13, {ARM_R: {"rot": (0.80, 0, 0)}, ARM_L: {"rot": (-0.80, 0, 0)},
          TORSO: {"rot": (0.16, 0, 0)}, TAIL: {"rot": (0, 0, 0.18)}, **RUN_PANT}),
    (19, {ARM_R: {"rot": (0.0, 0, 0)}, ARM_L: {"rot": (0.0, 0, 0)},
          TORSO: {"rot": (0.13, 0, 0)}, TAIL: {"rot": (0, 0, -0.14)}, **RUN_EASE}),
    (25, {ARM_R: {"rot": (-0.80, 0, 0)}, ARM_L: {"rot": (0.80, 0, 0)},
          TORSO: {"rot": (0.16, 0, 0)}, TAIL: {"rot": (0, 0, 0.18)}, **RUN_PANT}),
]

# --- Cheer：举手欢呼 + 大笑 ---
CHEER_LEN = 48
CHEER_HAPPY = merge(eyes(open_=False, shut=True), mouth("laugh"),
                    brow(-1, 0.012, -0.16), brow(+1, 0.012, -0.16))
CHEER = [
    (1, {ARM_R: {"rot": (-0.20, 0, 0.30)}, ARM_L: {"rot": (-0.20, 0, -0.30)},
         TAIL: {"rot": (0, 0, -0.20)},
         **merge(eyes(), mouth("smile"), head_pose((0.0, 0, 0)))}),
    (5, {ARM_R: {"rot": (-2.35, 0, 0.42)}, ARM_L: {"rot": (-2.35, 0, -0.42)},
         TAIL: {"rot": (0, 0, 0.20)}, **CHEER_HAPPY,
         **head_pose((-0.08, 0, 0)),
         **ears(({"rot": (0.0, 0.18, 0.0)}, {"rot": (0.0, -0.18, 0.0)}))}),
    (12, {ARM_R: {"rot": (-2.30, 0, 0.42)}, ARM_L: {"rot": (-2.30, 0, -0.42)},
          TAIL: {"rot": (0, 0, 0.20)},
          **merge(eyes(open_=False, shut=True), mouth("laugh"),
                  head_pose((0.06, 0, 0)),
                  ears(({"rot": (0.0, 0.10, 0.0)}, {"rot": (0.0, -0.10, 0.0)})))}),
    (20, {ARM_R: {"rot": (-2.35, 0, 0.42)}, ARM_L: {"rot": (-2.35, 0, -0.42)},
          TAIL: {"rot": (0, 0, 0.20)}, **CHEER_HAPPY,
          **head_pose((-0.08, 0, 0)),
          **ears(({"rot": (0.0, 0.18, 0.0)}, {"rot": (0.0, -0.18, 0.0)}))}),
    (28, {ARM_R: {"rot": (-2.30, 0, 0.42)}, ARM_L: {"rot": (-2.30, 0, -0.42)},
          TAIL: {"rot": (0, 0, 0.20)},
          **merge(eyes(open_=False, shut=True), mouth("laugh"),
                  head_pose((0.06, 0, 0)),
                  ears(({"rot": (0.0, 0.10, 0.0)}, {"rot": (0.0, -0.10, 0.0)})))}),
    (36, {ARM_R: {"rot": (-2.35, 0, 0.42)}, ARM_L: {"rot": (-2.35, 0, -0.42)},
          TAIL: {"rot": (0, 0, 0.20)}, **CHEER_HAPPY,
          **head_pose((-0.08, 0, 0)),
          **ears(({"rot": (0.0, 0.18, 0.0)}, {"rot": (0.0, -0.18, 0.0)}))}),
    (44, {ARM_R: {"rot": (-2.30, 0, 0.42)}, ARM_L: {"rot": (-2.30, 0, -0.42)},
          TAIL: {"rot": (0, 0, 0.20)},
          **merge(eyes(open_=False, shut=True), mouth("laugh"),
                  head_pose((0.06, 0, 0)))}),
    (48, {ARM_R: {"rot": (-0.20, 0, 0.30)}, ARM_L: {"rot": (-0.20, 0, -0.30)},
          TAIL: {"rot": (0, 0, -0.20)}, **merge(eyes(), mouth("smile"))}),
]

# --- Startle：吓得跳起 + 惊恐 ---
STARTLE_LEN = 24
STARTLE_SCARED = merge(eyes(), mouth("fear"),
                        brow(-1, 0.020, -0.44), brow(+1, 0.020, 0.44))
STARTLE = [
    (1, {ARM_R: {"rot": (0.0, 0, 0)}, ARM_L: {"rot": (0.0, 0, 0)},
         **merge(eyes(), mouth("smile"))}),
    (3, {ARM_R: {"rot": (-1.85, 0, 0.34)}, ARM_L: {"rot": (-1.85, 0, -0.34)},
         TAIL: {"rot": (0, 0, 0.0)}, **STARTLE_SCARED,
         **head_pose((-0.12, 0, 0)),
         **ears(({"rot": (0.0, -0.34, 0.24)}, {"rot": (0.0, 0.34, -0.24)})),
         **{PREFIX + "_Pupil_L": {"loc": (0.005, 0.0, 0.003)},
            PREFIX + "_Pupil_R": {"loc": (-0.005, 0.0, 0.003)}}}),
    (8, {ARM_R: {"rot": (-1.95, 0, 0.36)}, ARM_L: {"rot": (-1.95, 0, -0.36)},
         **merge(STARTLE_SCARED, head_pose((-0.12, 0, 0.02)))}),
    (16, {ARM_R: {"rot": (-1.85, 0, 0.34)}, ARM_L: {"rot": (-1.85, 0, -0.34)},
          **merge(STARTLE_SCARED, head_pose((-0.12, 0, -0.02)))}),
    (22, {ARM_R: {"rot": (-0.60, 0, 0.20)}, ARM_L: {"rot": (-0.60, 0, -0.20)},
          **merge(eyes(), mouth("fear"),
                  brow(-1, 0.012, -0.24), brow(+1, 0.012, 0.24),
                  head_pose((-0.06, 0, 0)))}),
    (24, {ARM_R: {"rot": (0.0, 0, 0)}, ARM_L: {"rot": (0.0, 0, 0)},
          **merge(eyes(), mouth("smile"))}),
]


# ---------------------------------------------------------------------
# 8.4 把身体和脸拼成片段
# ---------------------------------------------------------------------
def build_body_clip(name, length, body_keys, leg_frames, loop=False, hold=False):
    """身体片段：解地面 → 加髋部位移键 → 打关键帧。"""
    offs = solve_ground(leg_frames) if leg_frames else {}
    poses = {}
    for f, pose in body_keys:
        poses.setdefault(f, {}).update(pose)
    for f, rot in leg_frames.items():
        poses.setdefault(f, {}).update({nm: {"rot": r} for nm, r in rot.items()})
    for f, off in offs.items():
        poses.setdefault(f, {})[HIPS] = {"loc": (0.0, 0.0, off)}
    key_clip(name, length, sorted(poses.items()), loop=loop, hold=hold)
    return offs


build_body_clip("DSMonkey_Parts_Idle", IDLE_LEN, IDLE, {}, loop=True)
build_body_clip("DSMonkey_Parts_Sit", SIT_LEN, SIT, sit_frames, hold=True)
build_body_clip("DSMonkey_Parts_Walk", WALK_LEN, WALK, walk_legs, loop=True)
build_body_clip("DSMonkey_Parts_Run", RUN_LEN, RUN, run_legs, loop=True)
build_body_clip("DSMonkey_Parts_Cheer", CHEER_LEN, CHEER, {})
build_body_clip("DSMonkey_Parts_Startle", STARTLE_LEN, STARTLE, {})

# 共用头的 Laugh / Fear：片段名加前缀，键表里的对象名要映到新名
PART_MAP = {}
for ob in MH.MESHES:
    PART_MAP["DSMonkey" + ob.name.replace(PREFIX + "_", "")] = ob.name


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
    **导出仍然用 NLA 轨**（导出器按轨名合并片段）。"""
    for ob in bpy.context.scene.objects:
        ad = ob.animation_data
        if not ad:
            continue
        for t in ad.nla_tracks:
            t.mute = True
            for st in t.strips:
                st.mute = True
        ad.action = None
        if ob.name in REST:          # ← 撤下 action 不会自动退回静止位（见 REST 那段注释）
            ob.location = Vector(REST[ob.name][0])
            ob.rotation_euler = Vector(REST[ob.name][1])
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


scene.frame_end = 48
scene.frame_start = 1
scene.render.fps = 24


# =====================================================================
# 9. 自检：尺寸 / 地面 / 表情通道
# =====================================================================
def bbox_world(objs):
    """世界包围盒 —— 用**求值后**的矩阵，导出器动过动画时 matrix_world 可能是旧值。"""
    dg = bpy.context.evaluated_depsgraph_get()
    lo = Vector((1e9, 1e9, 1e9))
    hi = Vector((-1e9, -1e9, -1e9))
    for ob in objs:
        mw = ob.evaluated_get(dg).matrix_world
        for v in ob.data.vertices:
            p = mw @ v.co
            for i in range(3):
                lo[i] = min(lo[i], p[i])
                hi[i] = max(hi[i], p[i])
    return lo, hi


def clip_ground_audit(clip_names):
    """循环片段每帧扫一次脚底最低点。"""
    lengths = {"DSMonkey_Parts_Walk": 49, "DSMonkey_Parts_Run": 25,
               "DSMonkey_Parts_Idle": 49, "DSMonkey_Parts_Sit": 48,
               "DSMonkey_Parts_Cheer": 48, "DSMonkey_Parts_Startle": 24}
    for nm in clip_names:
        activate_clip(nm)
        length = lengths.get(nm, 48)
        worst = 9.9
        frames = []
        for f in range(1, length + 1):
            scene.frame_set(f)
            bpy.context.view_layer.update()
            dg = bpy.context.evaluated_depsgraph_get()
            zmin = 1e9
            for ob in FEET:
                ev = ob.evaluated_get(dg)
                for v in ob.data.vertices:
                    zmin = min(zmin, (ev.matrix_world @ v.co).z)
            worst = min(worst, zmin)
            if f in (1, length // 4, length // 2, 3 * length // 4, length):
                frames.append((f, zmin))
        print("  %-26s 脚底最低 %+0.4f m  (%s)" % (
            nm, worst, "  ".join("f%d %+0.4f" % t for t in frames)))
        scene.frame_set(1)


def face_channel_audit():
    """每一段动画都必须有**脸**的通道 —— 这一版的核心诉求。"""
    names = sorted({t.name for ob in bpy.context.scene.objects
                    if ob.animation_data for t in ob.animation_data.nla_tracks})
    print("  片段                        脸通道数  身体通道数")
    for nm in names:
        face = body = 0
        for ob in bpy.context.scene.objects:
            ad = ob.animation_data
            if not ad:
                continue
            if not any(t.name == nm for t in ad.nla_tracks):
                continue
            if ob.name in FACE:
                face += 1
            else:
                body += 1
        print("  %-26s %5d      %5d   %s" % (nm, face, body,
                                             "OK" if face else "!! 没有表情"))
        assert face, "%s 没有表情通道" % nm


# =====================================================================
# 10. 导出
# =====================================================================
tris = 0
for ob in bpy.context.scene.objects:
    if ob.type == 'MESH':
        tris += sum(len(p.vertices) - 2 for p in ob.data.polygons)
meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
print("M3F CHECK: tris %d  网格 %d  节点 %d  材质 %d"
      % (tris, len(meshes), len(bpy.context.scene.objects),
         len({m.name for ob in meshes for m in ob.data.materials})))

# 尺寸按**静止位**量（导出器会动动画，导出后量到的可能是某帧的姿势）
bpy.context.view_layer.update()
lo, hi = bbox_world(meshes)
print("尺寸（Blender 轴 X×Y×Z）: %.3f × %.3f × %.3f   最低点 z = %+.4f"
      % (hi.x - lo.x, hi.y - lo.y, hi.z - lo.z, lo.z))

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

print("地面审计（每帧扫脚底真实顶点）:")
clip_ground_audit(["DSMonkey_Parts_Walk", "DSMonkey_Parts_Run",
                    "DSMonkey_Parts_Idle", "DSMonkey_Parts_Sit"])
print("表情通道审计:")
face_channel_audit()


# =====================================================================
# 11. 预览：四视图 + 接触表
# =====================================================================
TR.scene.render.film_transparent = False
TR.scene.render.image_settings.color_mode = 'RGBA'
TR.scene.view_settings.view_transform = 'Standard'

VIEWS = [("front", 0.0), ("side", -90.0), ("back", 180.0), ("q34", 35.0)]
W, H = 480, 600
TR.scene.render.resolution_x = W
TR.scene.render.resolution_y = H
target = Vector((0.0, 0.0, 0.31))
paths = []
for name, az in VIEWS:
    TR.aim_camera(TR.CAM, target, 3.0, 0.86, az)
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

# 接触表：每格一个情绪（都带脸）
FRAMES = [("DSMonkey_Parts_Idle", 1), ("DSMonkey_Parts_Sit", 1),
          ("DSMonkey_Parts_Walk", 1), ("DSMonkey_Parts_Run", 1),
          ("DSMonkey_Parts_Cheer", 6), ("DSMonkey_Parts_Startle", 4)]
TW, TH = 440, 550
TR.scene.render.resolution_x = TW
TR.scene.render.resolution_y = TH
buf2 = np.ones((TH * 2, TW * 3, 4), dtype=np.float32)
for i, (clip, frame) in enumerate(FRAMES):
    activate_clip(clip)
    scene.frame_set(frame)
    bpy.context.view_layer.update()      # ⚠️ 不刷新依赖图，渲染出来的还是上一帧
    TR.aim_camera(TR.CAM, Vector((0.0, 0.0, 0.31)), 3.0, 0.86, 30.0)
    path = os.path.join(TR.RENDER_DIR, "m3f_anim_%d.png" % i)
    TR.render_to(path)
    a = TR.load_rgba(path, TW, TH)
    r, c = divmod(i, 3)
    buf2[r * TH:r * TH + TH, c * TW:(c + 1) * TW] = a
TR.save_rgba(buf2, ANIM_PNG, "m3f_parts_monkey_anim")
print("anim preview ->", ANIM_PNG)
scene.frame_set(1)

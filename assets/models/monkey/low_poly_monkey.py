# Blender 建模脚本：低多边形猴子（带 7 段内置动作动画）
#
# 用法:
#   /Applications/Blender.app/Contents/MacOS/Blender --background --python low_poly_monkey.py
#   ... --python low_poly_monkey.py -- --nopreview     # 只出 glb/blend，不渲染
#
# 产物（写入本目录）:
#   low_poly_monkey.blend / .glb / _preview.png / _anim.png
#
# ---------------------------------------------------------------------------
# 结构（全部按米建模，+Z 向上，地面 z = 0，原点 = 脚底地面中心，猴面朝 +Y）
# ---------------------------------------------------------------------------
#   MonkeyRoot                ← 空物体，原点 = 落地锚点
#     └─ Monkey_Hips
#          ├─ Monkey_Torso
#          │    ├─ Monkey_Head ── Monkey_Ear_R / Monkey_Ear_L
#          │    ├─ Monkey_Arm_R_Upper ─ Fore ─ Hand ─ Fingers
#          │    └─ Monkey_Arm_L_Upper ─ Fore ─ Hand ─ Fingers
#          ├─ Monkey_Leg_R_Thigh ─ Shin ─ Foot
#          ├─ Monkey_Leg_L_Thigh ─ Shin ─ Foot
#          └─ Monkey_Tail_1 ─ Tail_2 ─ Tail_3
#
# **用节点层级做骨架，不用 armature + 权重**：每个肢体是一块独立网格，物体原点
# 就在关节枢轴上（和大门 `Gate_Door_L/R` 同一套路），于是动画 = 关键帧物体
# 局部变换，导出 glTF 后 Godot 的 AnimationPlayer 直接就能播，不需要处理
# 权重、骨骼命名、骨骼 rest pose 这些跨软件最容易翻车的环节。
#
# 代价：网格之间靠"互相插进去"藏接缝（关节处留一段重叠），不是焊接成一整块。
# 对低多边形风格没问题，也省掉了一整类权重错误。
#
# ---------------------------------------------------------------------------
# 造型取向：参考图那只是**大头娃娃身的卡通猴**（chibi），不是写实猿
# ---------------------------------------------------------------------------
#   1) 头**巨大**：颅宽 0.30 m，比躯干宽（0.23 m）还宽一大截，颅高 0.33 m
#   2) 脸是**前下方一大片暖橘色**（和棕色毛帽是同一个曲面上的两片颜色，不是贴片），
#      配色**直接照参考图采样**（0.90 / 0.68 / 0.45），不是凭感觉调的奶白
#   3) 下方鼓出**尖吻**（椭球 + deform 变形，不是外挂一个球）
#   4) 眼睛**又大又圆**：黑眼珠占眼白直径的一半，还带一点高光（卡通感全靠它）
#   5) 粗眉 / 两个小鼻孔 / 一条翘起的笑嘴，全部贴着曲面造
#   6) 耳朵**又大又圆**（直径 ≈ 颅高的 3 成），明显凸出脑袋侧影
#   7) 身体**小而圆**，肚皮一块橘色；手脚也是橘色（比脸略暗）
#   8) 四肢用 12 边圆管，关节处不出现台阶；尾巴每段做成**圆弧**（不是竹节）
#
# 形体工具只有 5 个（都在本文件里）：
#   ellipsoid() 低模椭球，支持**逐面换色** / **basis**（换轴向）/ **deform**（改形）
#   tube()       两点之间的 n 棱锥台（脖子 / 四肢）
#   tube_path()  沿折线包 n 棱管（嘴巴 / 眉毛 / 尾巴的弧段）
#   spike()      四棱锥（头顶呆毛）
#   ball()       各向同半径的球（关节专用）
#
# ---------------------------------------------------------------------------
# 动画（内置，随 glb 导出，Godot 里 AnimationPlayer 直接播）
# ---------------------------------------------------------------------------
#   Monkey_Run        跑（原地跑循环，24 帧 = 0.8 s @30fps）
#   Monkey_Startle    受惊吓原地蹦（1.0 s）
#   Monkey_Tremble    害怕发抖（1.6 s，5 Hz 高频小幅抖动）
#   Monkey_ThrowOne   单手投掷（1.0 s）
#   Monkey_ThrowTwo   双手投掷（1.0 s）
#   Monkey_Clap       鼓掌（1.4 s，4 次）
#   Monkey_Snatch     抢东西（1.0 s）
#
# 导出用 `export_animation_mode='ACTIONS'`：**每个片段一个 Action**，Action 里
# 每个被驱动的物体各占一个 slot（Blender 4.4+ 的分层 Action）。
# 实测（Blender 5.2.2）：
#   · 'NLA_TRACKS' 模式下 NLA strip **根本不驱动变换**（frame_set 之后物体纹丝
#     不动），导出结果 0 条动画；
#   · 'ACTIONS' 模式只认两种来源：物体身上的 active action，或者 **NLA track 里的
#     strip**（检查的是 `strip.mute`，不是 `track.mute`）。
# 所以做法是：每个物体挂 7 条同名 NLA track（名字 = 片段名），导出器按 track 名
# 把各物体的动画合并成一条 glTF animation。
#   ⚠️ `strip.action_slot` 必须显式指向"本物体在这个 Action 里的那个 slot"，
#      否则导出器找不到 channelbag，整个片段会被丢掉。
#   ⚠️ track 可以静音（`.blend` 打开时猴子是静止站姿），strip 不能静音。
# 每个 Action 开 use_fake_user，导出前把所有物体的 active action 清掉。
#
# ---------------------------------------------------------------------------
# 旋转正负号约定（+X = 绕 X 轴，角度单位度）
#   （Blender 的 XYZ 欧拉 = R = Rz·Ry·Rx，所以"绕 Y 外张"是**先**转、
#    "绕 Z 内收"是**后**转，写混了手就会缩回身体里）
# ---------------------------------------------------------------------------
#   肢体（手臂/腿，几何朝 −Z 伸出去）：+X = 向前摆，−X = 向后摆
#   躯干/头（几何朝 +Z 长）：              +X = 向后仰/抬头，−X = 前倾/低头
#   肩部绕 Y：右臂外展 = 负值（左手 = 镜像取反）
#   肩部绕 Z：右臂内收（拍掌时往中间靠）= 负值（左手 = 镜像取反）
#   尾段（几何朝 −Y）：绕 X 正值 = 尾巴往下压，绕 Z 正值 = 尾巴甩向 +X
#
# 颜色（顶点色 COLOR_0，线性空间，5 个材质槽：毛 / 肤 / 奶油 / 深 / 眼）
# ---------------------------------------------------------------------------
# 与其它资产同一套：**按棱面（共面片）上色**，一个平面 = 一块颜色
# （assets/AGENTS.md §6.9）；相邻棱面叠一点随机明暗差，免得糊成一片。
import math
import os
import sys

import bpy
from mathutils import Quaternion, Vector

# 共享构件库：网格构建器 / 调色 / 预览机位都在这里（见 assets/models/_shared/）
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "_shared"))
from ruin_kit import (  # noqa: E402
    MeshBuilder, PreviewRig, clear_scene, hash01, make_material, shade, srgb2lin, stitch_images,
)

# ==========================================================================
# CONFIG —— 所有尺寸单位都是米
# ==========================================================================
OUT_DIR = os.path.dirname(os.path.abspath(__file__))
NAME = "low_poly_monkey"

FPS = 30
SEED = 20260716

# --- 骨架尺寸（基准表用这一组数）---------------------------------------
# 站立全高 ≈ 0.90 m —— 侏罗纪岛里介于草（0.7 m）和矮香蕉树（2.66 m）
# 之间，正好是"比玩家矮一截、但比植被高一截"的野生动物体型。
#
# 比例照参考图（2×2 卡通猴四视图）量出来，是**大头娃娃身的小猴**而不是写实猿：
#   1) 头**巨大**：颅宽 0.32 m，比躯干宽（0.19 m）还宽一大截，颅高 0.32 m
#      占全高的 35%（参考图正面看头接近全高的一半）
#   2) 脸是**前下方一大片暖橘色**，棕毛只盖住头顶和脑后
#   3) 眼睛**又大又圆**：瞳孔占眼白直径的 6 成，还带一点高光
#   4) 耳朵**又大又圆**（直径 ≈ 颅高的 3 成），明显凸出脑袋侧影
#   5) 身体**小而圆**，腿短，四肢短粗
#   6) 尾巴在背后**甩成一个 S 形大卷**（REST_ROT 里三段依次上翘再甩开）
HIPS_Z_M = 0.262          # 骨盆枢轴
WAIST_Z_M = 0.295         # 腰（躯干枢轴）
SHOULDER_X_M = 0.072      # 肩关节离中线
SHOULDER_Z_M = 0.412
NECK_Z_M = 0.462          # 颈（头枢轴）—— 要低于躯干顶，才能接上脖子
HIP_X_M = 0.056           # 髋关节离中线（要够宽，两腿之间才分得开）
HIP_Z_M = 0.262           # 大腿枢轴

UPPER_ARM_M = 0.108       # 大臂长
FOREARM_M = 0.098         # 小臂长
HAND_M = 0.075            # 手（掌 + 指）总长
THIGH_M = 0.104
SHIN_M = 0.096
ANKLE_Z_M = 0.062         # 踝高 = 脚掌厚
TAIL_SEG_M = (0.170, 0.150, 0.130)   # 三段尾巴，总长 0.45 m

# --- 头的形状（**相对颈根的局部坐标**，头物体原点 = 颈根）--------------
HEAD_CZ = 0.192                       # 颅球中心离颈根的高度
# 颅球半径（X 宽 / Y 厚 / Z 高）。参考图正面量下来脑袋**比宽要高**：
# 宽 143 px、高 165 px，所以 X 比 Z 小一大截 —— 做成正圆球会太"方"。
HEAD_R = (0.152, 0.156, 0.164)
EYE_AZ = 0.540                        # 眼睛方位角（弧度；0 = 正前方，+ = 猴的右侧）
EYE_EL = -0.040                       # 眼睛仰角（弧度；负 = 略低于颅心）
EYE_R = (0.036, 0.040)                # 眼白半径（X 宽 / Z 高）
PUPIL_R = 0.020                       # 瞳孔半径（≈ 眼白直径的 55%）
EAR_X = 0.132                         # 耳根离中线（耳廓从脑袋侧面长出来）
EAR_Y = -0.070                        # 耳根前后位置（参考图里耳朵明显靠后）
EAR_Z = -0.010                        # 耳根高度（相对颅心）
EAR_TILT = 5.0                        # 耳廓外倾角（耳朵朝前外侧，不是正对镜头）

# 脚掌几何（算"脚底最低点"用，见 crouch_depth / _run_leg_state）
#
# 脚绕 X 转 phi 之后**最低点落在哪**，用椭圆的"支撑函数"精确算：
#   椭圆 (中心 cy,cz；半轴 ry,rz) 上的点 (cy+ry·cos t, cz+rz·sin t)
#   绕 X 转 phi 后 z = y·sinφ + z·cosφ
#   → 最小值 = cy·sinφ + cz·cosφ − √((ry·sinφ)² + (rz·cosφ)²)
#
# 早前版本只拿"脚尖 / 脚跟"两个点估，脚掌一转到某个角度就会算穿地
# （实测跑动循环脚底插进地面 1.8 cm）。这是自检 `clip_ground_audit()` 抓出来的。
SOLE_Z = -ANKLE_Z_M         # 脚底相对踝关节的高度
FOOT_PARTS = (              # (y 中心, z 中心, y 半轴, z 半轴)
    (0.036, -0.028, 0.070, 0.034),      # 脚掌
    (0.090, -0.044, 0.023, 0.016),      # 脚趾
)
FOOT_BALL = (0.0, 0.012, 0.040)        # 踝关节球 (y, z, r)


def foot_lowest_z(phi):
    """脚掌绕 X 转 phi 之后，最低点相对踝关节的 z。"""
    s, c = math.sin(phi), math.cos(phi)
    best = 1e9
    for cy, cz, ry, rz in FOOT_PARTS:
        v = cy * s + cz * c - math.sqrt((ry * s) ** 2 + (rz * c) ** 2)
        best = min(best, v)
    cy, cz, r = FOOT_BALL
    best = min(best, cy * s + cz * c - r)
    return best

# --- 静止姿势里的"驼背 / 卷尾 / 张臂" ------------------------------------
# 这些是**造型的一部分**，写进静止姿势里；所有动画的角度都是相对它们的增量
# （Pose.r() 会自动加上这里的基准值）。
REST_ROT = {
    "Monkey_Torso": (-8.0, 0.0, 0.0),         # 前倾 8°（小驼背）
    "Monkey_Head": (5.0, 0.0, 0.0),            # 抵消躯干前倾
    # ⚠️ 外张是**绕 Y**（手臂垂着，绕 Z 转不动它）：右臂外展取负值。
    "Monkey_Arm_R_Upper": (8.0, -10.0, 0.0),   # 手臂略前伸、微微外张
    "Monkey_Arm_L_Upper": (8.0, 10.0, 0.0),
    # 耳朵朝前外侧（绕 Z 转向 +Y，绕 Y 让耳廓上缘往外撇）。
    # 镜像：左手这两个角都要取反（镜像会把 Y/Z 旋转角变号）。
    "Monkey_Ear_R": (0.0, 3.0, EAR_TILT),
    "Monkey_Ear_L": (0.0, -3.0, -EAR_TILT),
    # 尾巴在背后甩成一个大 S 钩（参考图侧视：后 → 下 → 上 → 翻过来钩住）。
    # 绕 X 正 = 往下压；绕 Z 正 = 甩向 +X（猴子的右侧）。
    # 每个关节只转 40° 左右 —— 转多了三根直管会接成"竹节"，不像一条尾巴。
    "Monkey_Tail_1": (-25.0, 0.0, 35.0),
    "Monkey_Tail_2": (-40.0, 0.0, 0.0),
    "Monkey_Tail_3": (-40.0, 0.0, 0.0),
}

# ==========================================================================
# 调色板（sRGB → 线性，assets/AGENTS.md §6.6）
# ==========================================================================
# 数值直接从参考图上采样（Blender 里读 JPEG 像素）：
#   毛（受光面）0.58 / 0.32 / 0.19      肚皮+脸 0.90 / 0.68 / 0.45
#   手 / 脚（比脸暗一档）0.81 / 0.57 / 0.38
#
# ⚠️ 脸是**暖橘棕**，不是奶白。第一版把脸调成 (0.95, 0.84, 0.68)，
# 渲染出来是一张惨白的面具，和参考图的"橘色脸盘"完全两回事。
PAL = {
    "fur": srgb2lin([0.58, 0.32, 0.19]),     # 主毛色（暖棕：头顶 / 背 / 四肢）
    "fur_d": srgb2lin([0.44, 0.23, 0.14]),   # 深棕（发际中缝 / 呆毛）
    "tan": srgb2lin([0.90, 0.68, 0.45]),     # 脸 / 肚皮
    "cream": srgb2lin([0.81, 0.57, 0.38]),   # 手 / 脚（比脸略暗，才不像白手套）
    "tan_d": srgb2lin([0.84, 0.62, 0.40]),   # 略深肤（吻部阴影）
    "dark": srgb2lin([0.30, 0.19, 0.16]),    # 深棕（眉 / 嘴 / 鼻孔）
    "pupil": srgb2lin([0.17, 0.14, 0.18]),   # 瞳孔（带一点紫，不是纯黑）
    "eye": srgb2lin([0.97, 0.96, 0.94]),     # 眼白
}

SLOT_FUR, SLOT_TAN, SLOT_CREAM, SLOT_DARK, SLOT_EYE = "Fur", "Tan", "Cream", "Dark", "Eye"


def make_materials():
    """四个顶点色材质槽（generic make_material 在 _shared/ruin_kit.py）。"""
    return {
        SLOT_FUR: make_material(NAME + "Fur", 0.92),
        SLOT_TAN: make_material(NAME + "Tan", 0.88),
        SLOT_CREAM: make_material(NAME + "Cream", 0.88),
        SLOT_DARK: make_material(NAME + "Dark", 0.72),
        SLOT_EYE: make_material(NAME + "Eye", 0.30),
    }


# ==========================================================================
# 网格小工具
# ==========================================================================
def _add_face(b, pts, slot, color, outward=None):
    """加一个面；给了 outward 就自动纠正绕序，保证法线朝外。"""
    n = (Vector(pts[1]) - Vector(pts[0])).cross(Vector(pts[2]) - Vector(pts[0]))
    if outward is not None and n.dot(Vector(outward)) < 0.0:
        pts = list(reversed(pts))
    b.add(pts, slot, color)


def _basis(axis):
    """正交基 (u, v, w)，w = axis。u 水平、v 竖直（axis 接近 ±Y 时成立）。"""
    w = Vector(axis).normalized()
    ref = Vector((0.0, 0.0, 1.0)) if abs(w.z) < 0.9 else Vector((1.0, 0.0, 0.0))
    u = ref.cross(w).normalized()
    v = w.cross(u).normalized()
    return u, v, w


def ellipsoid(b, center, radii, slot, color, segs=12, rings=7, color_fn=None, seed=0.0,
              basis=None, deform=None):
    """低多边形椭球（UV 球，平面着色）。

    color_fn(face_center, face_normal, dir) -> (slot, color) 时**逐面换色**。
    `dir` 是该面在球面上的**参数方向**（相对球心的单位向量）——分色规则
    必须按它算，因为"脸 / 肚皮"的边界是按角度量的，不是按 x/z 切的。
    参考图里的"橘色脸盘 + 棕色毛帽"就是**同一个曲面上分色**，
    不是另贴一层皮 —— 贴片做法边界生硬，还会在脸上鼓一个包。

    `basis` 给 (u, v, w) 正交基，把椭球的三个轴映射到世界方向（眼睛用）。
    `deform(d, p)` 在建点时改写坐标（吻部前突用）。
    """
    c = Vector(center)
    rx, ry, rz = radii
    u, v, w = basis if basis is not None else (
        Vector((1.0, 0.0, 0.0)), Vector((0.0, 1.0, 0.0)), Vector((0.0, 0.0, 1.0)))
    slot = b.slot(slot)
    verts = []
    dirs = []

    def put(d):
        p = Vector((rx * d.x, ry * d.y, rz * d.z))
        if deform is not None:
            p = deform(d, p)
        verts.append(c + u * p.x + v * p.y + w * p.z)
        dirs.append(d)

    # 纬向环（不建极点环，单独用极点顶点封口 —— 否则极点会多出一圈退化面）
    nlat = max(2, rings)
    for j in range(1, nlat):
        th = math.pi * j / nlat
        for i in range(segs):
            ph = 2.0 * math.pi * i / segs
            put(Vector((math.sin(th) * math.cos(ph),
                        math.sin(th) * math.sin(ph),
                        math.cos(th))))
    top = len(verts)
    put(Vector((0.0, 0.0, 1.0)))
    bot = len(verts)
    put(Vector((0.0, 0.0, -1.0)))

    def emit(idx):
        pts = [verts[k] for k in idx]
        ctr = sum(pts, Vector()) / len(pts)
        nrm = ctr - c
        nrm = nrm.normalized() if nrm.length > 1e-9 else Vector((0.0, 0.0, 1.0))
        if color_fn is not None:
            d = sum((dirs[k] for k in idx), Vector())
            sl, cl = color_fn(ctr, nrm, d.normalized() if d.length > 1e-9 else nrm)
            sl = b.slot(sl)          # color_fn 给的是**槽名**，要换成下标
        else:
            sl, cl = slot, color
        _add_face(b, pts, sl, shade(cl, hash01(seed, idx[0])), nrm)

    for i in range(segs):
        i2 = (i + 1) % segs
        emit([top, i2, i])
    for j in range(nlat - 2):
        r0 = j * segs
        r1 = (j + 1) * segs
        for i in range(segs):
            i2 = (i + 1) % segs
            emit([r0 + i, r0 + i2, r1 + i2, r1 + i])
    base = (nlat - 2) * segs
    for i in range(segs):
        i2 = (i + 1) % segs
        emit([bot, base + i, base + i2])


def ball(b, center, r, slot, color, segs=12, seed=0.0):
    """低多边形**球**（关节用）。

    关节必须是球，原因：
      · 肢体是棱柱，末端是平的；直接怼到下一段就是一道**硬折角**，
        渲染出来像"竹节"，一点都不像卡通角色的关节。
      · 球 + 锥台管的半径要**递减**（球的半径 > 管的半径），
        管子从球里"长出来"，轮廓才是连续圆润的。
    segs 要和管的棱数一致，棱面走向才对得上。
    """
    ellipsoid(b, center, (r, r, r), slot, color,
              segs=segs, rings=max(4, segs // 2), seed=seed)


def tube(b, p0, p1, r0, r1, n, slot, color, seed=0.0, phase=0.0):
    """从一个中心点到另一个中心点的 n 棱锥台（脖子 / 尾巴用）。"""
    p0, p1 = Vector(p0), Vector(p1)
    slot = b.slot(slot)
    u, v, w = _basis(p1 - p0)
    rings = []
    for p, r in ((p0, r0), (p1, r1)):
        rings.append([p + u * (math.cos(phase + 2.0 * math.pi * i / n) * r)
                      + v * (math.sin(phase + 2.0 * math.pi * i / n) * r)
                      for i in range(n)])
    mid = (p0 + p1) * 0.5
    for i in range(n):
        j = (i + 1) % n
        quad = [rings[0][i], rings[0][j], rings[1][j], rings[1][i]]
        ctr = sum(quad, Vector()) / 4.0
        _add_face(b, quad, slot, shade(color, hash01(seed, 1, i)), ctr - mid)
    _add_face(b, rings[0][::-1], slot, shade(color, hash01(seed, 2)), p0 - p1)
    _add_face(b, rings[1], slot, shade(color, hash01(seed, 3)), p1 - p0)


def tube_path(b, pts, radii, n, slot, color, seed=0.0, caps=True, phase=0.0):
    """沿一条折线生成 n 棱管（嘴巴 / 眉毛用）。

    参考图里的嘴是一条**贴着脸的弧线**，用直管拼不出来；
    沿曲面采样出来的折线再包成管子，弧线才跟得住脸。
    radii 可以是标量，也可以是逐点的半径列表（嘴的两端略粗）。
    """
    pts = [Vector(p) for p in pts]
    if not isinstance(radii, (list, tuple)):
        radii = [radii] * len(pts)
    slot = b.slot(slot)
    tans = []
    for i in range(len(pts)):
        if i == 0:
            t = pts[1] - pts[0]
        elif i == len(pts) - 1:
            t = pts[-1] - pts[-2]
        else:
            t = pts[i + 1] - pts[i - 1]
        tans.append(t.normalized())
    ref = Vector((0.0, 0.0, 1.0))
    if abs(tans[0].dot(ref)) > 0.9:
        ref = Vector((1.0, 0.0, 0.0))
    nrm = (ref - tans[0] * ref.dot(tans[0])).normalized()
    rings = []
    prev_t = tans[0]
    for i, p in enumerate(pts):
        t = tans[i]
        if i > 0:
            axis = prev_t.cross(t)
            if axis.length > 1e-9:
                nrm = Quaternion(axis.normalized(), prev_t.angle(t)) @ nrm
        nrm = (nrm - t * nrm.dot(t)).normalized()
        bnm = t.cross(nrm)
        r = radii[i]
        rings.append([p + nrm * (math.cos(phase + 2.0 * math.pi * k / n) * r)
                      + bnm * (math.sin(phase + 2.0 * math.pi * k / n) * r)
                      for k in range(n)])
        prev_t = t
    for i in range(len(rings) - 1):
        for k in range(n):
            k2 = (k + 1) % n
            quad = [rings[i][k], rings[i][k2], rings[i + 1][k2], rings[i + 1][k]]
            ctr = sum(quad, Vector()) / 4.0
            _add_face(b, quad, slot, shade(color, hash01(seed, i, k)), ctr - pts[i])
    if caps:
        _add_face(b, rings[0][::-1], slot, shade(color, hash01(seed, 90)), pts[0] - tans[0])
        _add_face(b, rings[-1], slot, shade(color, hash01(seed, 91)), pts[-1] - tans[-1])


def spike(b, base, apex, slot, color, seed=0.0):
    """四棱锥（头顶呆毛）。base = 底面 4 点（逆时针）。"""
    slot = b.slot(slot)
    n = len(base)
    for i in range(n):
        j = (i + 1) % n
        tri = [base[i], base[j], apex]
        ctr = sum([Vector(p) for p in tri], Vector()) / 3.0
        _add_face(b, tri, slot, shade(color, hash01(seed, i)), ctr - Vector(apex))



# ==========================================================================
# 身体部件（**局部坐标**，物体原点 = 关节枢轴）
# ==========================================================================
# --- 分色规则：橘色的"脸"和"肚皮"画在同一个曲面上 ---------------------
# 参考图里棕色毛帽盖住头顶 + 脑后，脸是**前下方一大片暖橘色**。
# 分界线（发际线）按**仰角**量：直接在 x/z 平面上切，边界在脑袋两侧会变成
# 两条**竖直硬边**，渲染出来像往脸上糊了张面具。改成"离水平面多少度"来量，
# 边界才会顺着颅骨的弧线走。
#
# 脸盘的判据 = 仰角低于发际线 **且** 方位角没超过耳后。
# 额头正中还有一道**中缝**（参考图里两块毛片对接的地方），用一条窄棕条还原。
HAIR_AZ_LIMIT = 1.62          # 超过这个方位角（耳后）全是棕毛
HAIR_EL = 0.500               # 发际线基准仰角（额头正前方）
HAIR_DROP = 0.750             # 往两侧发际线压下去多少（越靠后越低）
BELLY_AZ = 0.85               # 肚皮左右半张角
BELLY_EL = 0.62               # 肚皮上下半张角
BELLY_CZ = -0.18              # 肚皮中心仰角（略偏下）


def _head_color(ctr, nrm, d):
    """头的分色：棕色毛帽 + 暖橘色脸盘（**同一个曲面上分色**）。

    发际线随方位角起伏 2~3 个周期 —— 死板的边界像猴头戴了个头箍。
    """
    el = math.asin(max(-1.0, min(1.0, d.z)))
    az = math.atan2(d.x, d.y)
    # 发际线：正前方高，往两侧一路压到下颌 —— 参考图正视图是"额头一道
    # 横线"，侧视图是"额头斜着压到吻部"，同一个公式两边都对。
    k = min(1.0, abs(az) / HAIR_AZ_LIMIT)
    h = HAIR_EL - HAIR_DROP * k * k
    h += 0.055 * math.sin(2.3 * az + 0.6) + 0.035 * math.sin(5.1 * az + 2.0)
    if el > h:
        return SLOT_FUR, PAL["fur"]
    if abs(az) > HAIR_AZ_LIMIT:
        return SLOT_FUR, PAL["fur"]
    # 额头正中那道中缝
    if abs(az) < 0.115 and el > -0.05:
        return SLOT_FUR, PAL["fur_d"]
    return SLOT_TAN, PAL["tan"]


def _belly_color(ctr, nrm, d):
    """躯干的分色：前下方一块**竖长的橘色肚皮**，其余棕色。

    参考图的肚皮是"上宽下尖"的椭圆，边界要顺着躯干曲面的棱线走，
    所以按方位角 + 仰角双重限制判。
    """
    el = math.asin(max(-1.0, min(1.0, d.z)))
    az = math.atan2(d.x, d.y)
    dh = az / BELLY_AZ
    dv = (el - BELLY_CZ) / BELLY_EL
    if dh * dh + dv * dv < 1.0:
        return SLOT_TAN, PAL["tan"]
    return SLOT_FUR, PAL["fur"]


# --- 头部的"吻部"（侧视图里明显前突的猪鼻嘴）--------------------------
# 参考图侧面：额头是圆的，但下方**鼓出一个尖吻**，嘴和鼻孔都在吻上。
# 用「椭球 + 一个前突变形」来做，比外挂一个球好：
#   · 外挂球会在下巴处留下一块诡异的浅色斑；
#   · 变形是同一个曲面，分色自然跟着走，边界不会生硬。
MUZZLE_DIR = Vector((0.0, 0.94, -0.34)).normalized()   # 吻的正前方（朝前偏下）
MUZZLE_ANG = 0.70          # 吻部影响半角（弧度）
MUZZLE_FWD = 0.060         # 吻部前突量（米）
MUZZLE_DOWN = 0.016        # 吻部下压量（米）


def _head_deform(d, p):
    """吻部前突变形（只有 ellipsoid 的 deform 回调用得到）。"""
    ang = math.acos(max(-1.0, min(1.0, d.dot(MUZZLE_DIR))))
    if ang >= MUZZLE_ANG:
        return p
    m = 1.0 - (ang / MUZZLE_ANG) ** 2
    p.x *= (1.0 - 0.18 * m)          # 吻部比脑袋窄
    p.y += MUZZLE_FWD * m
    p.z -= MUZZLE_DOWN * m
    # 下半颗头收窄：参考图的脸是"上宽下尖"，不是一颗鸡蛋
    lo = max(0.0, -d.z)
    p.x *= (1.0 - 0.20 * lo * lo)
    p.y *= (1.0 - 0.10 * lo * lo)
    return p


def head_point(d):
    """方向 d（单位向量）对应的头部表面点（头局部坐标，原点 = 颈根）。"""
    d = Vector(d).normalized()
    p = Vector((HEAD_R[0] * d.x, HEAD_R[1] * d.y, HEAD_R[2] * d.z))
    p = _head_deform(d, p)
    return Vector((0.0, 0.0, HEAD_CZ)) + p


def head_normal(d):
    """方向 d 处的表面法线（椭球法线，够用了）。"""
    d = Vector(d).normalized()
    n = Vector((d.x / HEAD_R[0], d.y / HEAD_R[1], d.z / HEAD_R[2]))
    return n.normalized()


def dir_from(az, el):
    """方位角 az（绕 Y 轴，+ = 猴的右侧）+ 仰角 el → 单位方向。"""
    ce = math.cos(el)
    return Vector((math.sin(az) * ce, math.cos(az) * ce, math.sin(el)))


def _tangent_frame(nrm):
    """在法线 nrm 的切平面上建一个右手基 (u, v, nrm)：u 朝"屏幕左"，v 朝上。"""
    v = Vector((0.0, 0.0, 1.0)) - nrm * nrm.z
    v = v.normalized() if v.length > 1e-6 else Vector((0.0, 1.0, 0.0))
    u = v.cross(nrm).normalized()
    return u, v



def _bezier(t, p0, p1, p2, p3):
    """三次贝塞尔（嘴的弧线用）。"""
    u = 1.0 - t
    return u * u * u * p0 + 3 * u * u * t * p1 + 3 * u * t * t * p2 + t * t * t * p3


def build_hips():
    """骨盆 / 屁股。枢轴 = 髋关节中心（世界 z 0.262）。"""
    b = MeshBuilder()
    ellipsoid(b, (0.0, -0.004, -0.012), (0.092, 0.085, 0.072),
              SLOT_FUR, PAL["fur"], segs=14, rings=9, seed=1.0)
    return b


def build_torso():
    """胸腹。枢轴 = 腰（世界 z 0.295），几何从腰往上到肩。

    躯干是**一个圆润的团块**（椭球），参考图侧视里这个团块又深又圆，
    几乎是个球 —— 做成细长的桶形会立刻变成"瘦长猿"。
    橘色的肚皮直接**画在同一个表面上**（见 _belly_color），
    这样人和肚子之间没有接缝，也没有一圈硬边。
    """
    b = MeshBuilder()
    ellipsoid(b, (0.0, 0.0, 0.040), (0.115, 0.100, 0.110),
              SLOT_FUR, PAL["fur"], segs=16, rings=11,
              color_fn=_belly_color, seed=2.0)
    # 脖子：根部一个球（颈关节），上面细一点直接插进脑袋里
    ball(b, (0.0, 0.004, 0.100), 0.058, SLOT_FUR, PAL["fur"], segs=12, seed=6.0)
    tube(b, (0.0, 0.004, 0.104), (0.0, 0.006, 0.190), 0.048, 0.044, 12,
         SLOT_FUR, PAL["fur"], seed=7.0)
    return b


def build_head():
    """头。枢轴 = 颈根（世界 z 0.520），脸朝 +Y。

    参考图的头 = 一个**低模圆球**，前下方鼓出一个**尖吻**；棕色毛帽盖住
    头顶和脑后，前下方是一大片橘色脸盘；上面摆着两只大眼睛、两道粗眉、
    两个小鼻孔和一条咧开的笑嘴；头顶一撮呆毛。
    """
    b = MeshBuilder()
    ellipsoid(b, (0.0, 0.0, HEAD_CZ), HEAD_R, SLOT_FUR, PAL["fur"], segs=20, rings=14,
              color_fn=_head_color, seed=10.0, deform=_head_deform)

    for s in (1, -1):
        # ---- 眼睛 ----
        d = dir_from(s * EYE_AZ, EYE_EL)
        surf = head_point(d)
        nrm = head_normal(d)
        u, v = _tangent_frame(nrm)
        # 眼白：扁椭球，薄轴沿法线（贴在脸上，不是外挂的球）
        eye_c = surf - nrm * 0.008
        ellipsoid(b, eye_c, (EYE_R[0], EYE_R[1], 0.016), SLOT_EYE, PAL["eye"],
                  segs=18, rings=12, seed=12.0 + s, basis=(u, v, nrm))
        # 瞳孔：贴在眼白表面的扁球，黑眼珠占眼白直径的一半（参考图的关键特征）
        pup_c = eye_c + nrm * 0.012
        ellipsoid(b, pup_c, (PUPIL_R, PUPIL_R * 1.05, 0.006), SLOT_DARK, PAL["pupil"],
                  segs=16, rings=10, seed=14.0 + s, basis=(u, v, nrm))
        # 高光：瞳孔左上角的一小点白（两颗眼高光都在"屏幕左"上 —— 光从左上来）
        hl = Vector((-1.0, 0.0, 0.0))
        hl = (hl - nrm * hl.dot(nrm)).normalized()
        ellipsoid(b, pup_c + hl * 0.009 + v * 0.010 + nrm * 0.005,
                  (0.0075, 0.0075, 0.004), SLOT_EYE, PAL["eye"],
                  segs=8, rings=6, seed=16.0 + s, basis=(u, v, nrm))

        # ---- 眉毛：贴着额头的一道粗弧（内端高、外端低）----
        brow = []
        for k in range(5):
            t = k / 4.0
            brow.append(head_point(dir_from(s * (0.26 + 0.28 * t), 0.275 - 0.080 * t)))
        tube_path(b, brow, [0.0082, 0.0078, 0.0072, 0.0064, 0.0056], 8,
                  SLOT_DARK, PAL["dark"], seed=17.0 + s)

        # ---- 鼻孔：吻部上两个小暗点 ----
        dn = dir_from(s * 0.20, -0.30)
        sn = head_point(dn)
        nn = head_normal(dn)
        un, vn = _tangent_frame(nn)
        ellipsoid(b, sn - nn * 0.002, (0.0085, 0.0045, 0.0045), SLOT_DARK, PAL["dark"],
                  segs=10, rings=7, seed=18.0 + s, basis=(un, vn, nn))

    # ---- 嘴：一条咧开的笑弧（参考图是"翘嘴角"的 smirk）----
    mouth = []
    for k in range(9):
        t = k / 8.0
        az = -0.40 + 0.80 * t
        el = _bezier(t, -0.44, -0.63, -0.60, -0.31)
        mouth.append(head_point(dir_from(az, el)))
    tube_path(b, mouth, [0.0050, 0.0045, 0.0040, 0.0037, 0.0035,
                          0.0037, 0.0040, 0.0044, 0.0040], 8,
              SLOT_DARK, PAL["dark"], seed=20.0)

    # 呆毛（顶上小小一撮）
    spike(b, [(-0.016, -0.012, 0.344), (0.010, -0.012, 0.344),
              (0.010, 0.014, 0.344), (-0.016, 0.014, 0.344)],
          (0.000, -0.006, 0.382), SLOT_FUR, PAL["fur_d"], seed=22.0)
    return b


def _ear_color(ctr, nrm, d):
    """耳朵分色：朝外的那一坨是橘色耳窝，其余是棕毛。"""
    if d.x > 0.72:
        return SLOT_TAN, PAL["tan"]
    return SLOT_FUR, PAL["fur"]


def build_ear():
    """耳朵。枢轴 = 耳根（贴在颅骨侧面，眼高处），几何向 +X 伸。

    参考图的耳朵**又大又圆**（直径 ≈ 颅高的 3 成），耳廓明显凸出侧影，
    耳窝只是中间一小块橘色 —— 早前版本把耳朵做小了，整个陷进脑袋里，
    渲染出来像个"窟窿"。
    """
    b = MeshBuilder()
    # 耳廓：法线沿 X 的鼓包。正视图里它是一个**又大又圆的鼓包**，
    # 侧视图里是脑袋侧面一个凸起 —— 所以是"鼓出来的"而不是"薄薄一片"。
    # 耳窝用**逐面分色**画在耳廓同一个曲面上：外挂一个浅色球会和耳廓
    # 正面重合，渲染出来是一道道条纹（Z-fighting）。
    ellipsoid(b, (0.030, 0.0, 0.0), (0.032, 0.038, 0.048),
              SLOT_FUR, PAL["fur"], segs=12, rings=9, seed=30.0,
              color_fn=_ear_color)
    return b


def build_upper_arm():
    """大臂。枢轴 = 肩，肘在局部 z = -UPPER_ARM_M。"""
    b = MeshBuilder()
    # 肩关节球（枢轴正好落在躯干表面，球往里外各吃一半）
    ball(b, (0.0, 0.0, 0.010), 0.054, SLOT_FUR, PAL["fur"], segs=12, seed=40.0)
    # 大臂：管子从球里长出来，半径比球小 → 轮廓连续
    tube(b, (0.0, 0.0, 0.012), (0.0, 0.0, -UPPER_ARM_M), 0.048, 0.038, 12,
         SLOT_FUR, PAL["fur"], seed=41.0)
    return b


def build_forearm():
    """小臂。枢轴 = 肘，腕在局部 z = -FOREARM_M。"""
    b = MeshBuilder()
    # 肘关节球
    ball(b, (0.0, 0.0, 0.004), 0.046, SLOT_FUR, PAL["fur"], segs=12, seed=42.0)
    tube(b, (0.0, 0.0, 0.010), (0.0, 0.0, -FOREARM_M), 0.038, 0.030, 12,
         SLOT_FUR, PAL["fur"], seed=43.0)
    return b


def build_hand():
    """手掌。枢轴 = 腕；掌心朝 +Y，手指从 z=-0.046 处接出去。

    参考图的手是**橘色的圆手套**（不是深色）：手心圆、手指短粗，
    拇指从侧面鼓出来一个大钩子（侧视图里看得很清楚）。
    """
    b = MeshBuilder()
    # 腕关节球：接住小臂的圆管，别让掌根顶出一个硬台阶
    ball(b, (0.0, 0.0, 0.004), 0.032, SLOT_CREAM, PAL["cream"], segs=12, seed=43.5)
    ellipsoid(b, (0.0, 0.0, -0.026), (0.046, 0.034, 0.036),
              SLOT_CREAM, PAL["cream"], segs=12, rings=9, seed=44.0)
    # 拇指（靠身体一侧；左手由 mirror_x 翻到另一边）
    ellipsoid(b, (-0.040, 0.004, -0.034), (0.019, 0.019, 0.025),
              SLOT_CREAM, PAL["cream"], segs=10, rings=7, seed=45.0)
    return b


def build_fingers():
    """手指。枢轴 = 指根（腕下 0.046），几何朝 -Z；绕 X 正向旋转 = 握拳。

    参考图的手是**圆手套**：四根手指短粗、圆头，挤在一起像一排小圆丘。
    早前版本用的是细长圆管，渲染出来像螃蟹钳子。
    """
    b = MeshBuilder()
    for i, x in enumerate((-0.026, -0.009, 0.009, 0.026)):
        ln = 0.032 if i != 1 else 0.038
        tube(b, (x, 0.0, 0.006), (x, 0.0, -ln), 0.016, 0.014, 8,
             SLOT_CREAM, PAL["cream"], seed=50.0 + i)
        ball(b, (x, 0.0, -ln), 0.014, SLOT_CREAM, PAL["cream"], segs=8, seed=54.0 + i)
    return b


def build_thigh():
    """大腿。枢轴 = 髋，膝在局部 z = -THIGH_M。"""
    b = MeshBuilder()
    # 胯关节球（塞进骨盆里，骨盆的髋部因此是圆的）
    ball(b, (0.0, 0.0, 0.012), 0.062, SLOT_FUR, PAL["fur"], segs=12, seed=60.0)
    tube(b, (0.0, 0.0, 0.016), (0.0, 0.0, -THIGH_M), 0.054, 0.044, 12,
         SLOT_FUR, PAL["fur"], seed=61.0)
    return b


def build_shin():
    """小腿。枢轴 = 膝，踝在局部 z = -SHIN_M。"""
    b = MeshBuilder()
    # 膝关节球
    ball(b, (0.0, 0.0, 0.004), 0.050, SLOT_FUR, PAL["fur"], segs=12, seed=62.0)
    tube(b, (0.0, 0.0, 0.010), (0.0, 0.0, -SHIN_M), 0.042, 0.034, 12,
         SLOT_FUR, PAL["fur"], seed=63.0)
    return b


def build_foot():
    """脚。枢轴 = 踝，底面在局部 z = -ANKLE_Z_M = 脚底贴地。

    参考图的脚是**橘色的扁脚掌**（像小鞋），前面几颗小趾头。
    脚尖 / 脚跟的 y 必须和 TOE_Y / HEEL_Y 对上 —— 地面审计就是按这两个数
    反解"脚底最低点"的。
    """
    b = MeshBuilder()
    # 脚掌：一个圆润的团块，底面正好落在 -ANKLE_Z_M
    ellipsoid(b, (0.0, 0.036, -0.028), (0.052, 0.070, 0.034),
              SLOT_CREAM, PAL["cream"], segs=12, rings=9, seed=70.0)
    # 三颗脚趾
    for i, x in enumerate((-0.025, 0.0, 0.025)):
        ellipsoid(b, (x, 0.090, -0.044), (0.016, 0.023, 0.016),
                  SLOT_CREAM, PAL["cream"], segs=8, rings=7, seed=72.0 + i)
    # 踝关节球：接住小腿的圆管
    ball(b, (0.0, 0.0, 0.012), 0.040, SLOT_FUR, PAL["fur"], segs=12, seed=76.0)
    return b


def build_tail_seg(idx):
    """尾巴第 idx 段（0..2）。枢轴 = 该段起点，几何朝 -Y 伸。

    每段是一段**圆弧**而不是直管：三根直管接起来是"竹节"，
    弧段接起来才是一条平滑的 S 形尾巴（参考图侧视那条大弯钩）。
    弧的起点切线比 -Y 低 20°、终点抬 20°，于是每段自转 40°；
    关节处再补 -40°，接缝的切线就对上了，看不出折角。
    """
    b = MeshBuilder()
    t = idx / 2.0
    r0 = 0.036 - 0.007 * t
    r1 = 0.036 - 0.007 * (t + 0.5)
    ln = TAIL_SEG_M[idx]
    # 二次贝塞尔：P0 = 原点，控制点在弦下方 → 弧线向"转弯内侧"凹
    p1 = Vector((0.0, -0.500 * ln, -0.182 * ln))
    p2 = Vector((0.0, -ln, 0.0))
    pts, radii = [], []
    for k in range(9):
        u = k / 8.0
        pts.append(p1 * (2.0 * u * (1.0 - u)) + p2 * (u * u))
        radii.append(r0 + (r1 - r0) * u)
    tube_path(b, pts, radii, 12, SLOT_FUR, PAL["fur"], seed=80.0 + idx, phase=0.26)
    return b


# ==========================================================================
# 骨架层级：name → (parent, 世界枢轴)
# ==========================================================================
def rig_table():
    """整只猴子的节点表。R = 右边 = +X（猴面朝 +Y，故其右手在 +X 侧）。"""
    ear_z = NECK_Z_M + HEAD_CZ + EAR_Z
    t = [
        ("Monkey_Hips", "MonkeyRoot", (0.0, 0.0, HIPS_Z_M)),
        ("Monkey_Torso", "Monkey_Hips", (0.0, 0.0, WAIST_Z_M)),
        ("Monkey_Head", "Monkey_Torso", (0.0, 0.008, NECK_Z_M)),
        ("Monkey_Ear_R", "Monkey_Head", (EAR_X, EAR_Y, ear_z)),
        ("Monkey_Ear_L", "Monkey_Head", (-EAR_X, EAR_Y, ear_z)),
    ]
    for s, m in (("R", 1.0), ("L", -1.0)):
        t += [
            ("Monkey_Arm_%s_Upper" % s, "Monkey_Torso",
             (m * SHOULDER_X_M, 0.0, SHOULDER_Z_M)),
            ("Monkey_Arm_%s_Fore" % s, "Monkey_Arm_%s_Upper" % s,
             (m * SHOULDER_X_M, 0.0, SHOULDER_Z_M - UPPER_ARM_M)),
            ("Monkey_Arm_%s_Hand" % s, "Monkey_Arm_%s_Fore" % s,
             (m * SHOULDER_X_M, 0.0, SHOULDER_Z_M - UPPER_ARM_M - FOREARM_M)),
            ("Monkey_Arm_%s_Fingers" % s, "Monkey_Arm_%s_Hand" % s,
             (m * SHOULDER_X_M, 0.0, SHOULDER_Z_M - UPPER_ARM_M - FOREARM_M - 0.044)),
            ("Monkey_Leg_%s_Thigh" % s, "Monkey_Hips", (m * HIP_X_M, 0.0, HIP_Z_M)),
            ("Monkey_Leg_%s_Shin" % s, "Monkey_Leg_%s_Thigh" % s,
             (m * HIP_X_M, 0.0, HIP_Z_M - THIGH_M)),
            ("Monkey_Leg_%s_Foot" % s, "Monkey_Leg_%s_Shin" % s,
             (m * HIP_X_M, 0.0, HIP_Z_M - THIGH_M - SHIN_M)),
        ]
    ty = -0.070
    prev = "Monkey_Hips"
    for i in range(3):
        nm = "Monkey_Tail_%d" % (i + 1)
        t.append((nm, prev, (0.0, ty, HIPS_Z_M)))
        ty -= TAIL_SEG_M[i]
        prev = nm
    return t


RIG = rig_table()
RIG_NAMES = [r[0] for r in RIG]


def build_monkey(mats):
    """建出全部部件并接好层级。返回 {name: object}。"""
    objs = {}
    pivot = {nm: pv for nm, _, pv in RIG}

    def build(name, fn, mirror=False):
        b = fn()
        if mirror:
            b.mirror_x()
        return b.build(name, mats)

    objs["Monkey_Hips"] = build("Monkey_Hips", build_hips)
    objs["Monkey_Torso"] = build("Monkey_Torso", build_torso)
    objs["Monkey_Head"] = build("Monkey_Head", build_head)
    objs["Monkey_Ear_R"] = build("Monkey_Ear_R", build_ear)
    objs["Monkey_Ear_L"] = build("Monkey_Ear_L", build_ear, mirror=True)
    for s in ("R", "L"):
        objs["Monkey_Arm_%s_Upper" % s] = build("Monkey_Arm_%s_Upper" % s, build_upper_arm)
        objs["Monkey_Arm_%s_Fore" % s] = build("Monkey_Arm_%s_Fore" % s, build_forearm)
        objs["Monkey_Arm_%s_Hand" % s] = build("Monkey_Arm_%s_Hand" % s, build_hand)
        objs["Monkey_Arm_%s_Fingers" % s] = build("Monkey_Arm_%s_Fingers" % s, build_fingers)
        objs["Monkey_Leg_%s_Thigh" % s] = build("Monkey_Leg_%s_Thigh" % s, build_thigh)
        objs["Monkey_Leg_%s_Shin" % s] = build("Monkey_Leg_%s_Shin" % s, build_shin)
        objs["Monkey_Leg_%s_Foot" % s] = build("Monkey_Leg_%s_Foot" % s, build_foot)
    for i in range(3):
        objs["Monkey_Tail_%d" % (i + 1)] = build("Monkey_Tail_%d" % (i + 1),
                                                  lambda i=i: build_tail_seg(i))

    root = bpy.data.objects.new("MonkeyRoot", None)
    root.empty_display_size = 0.25
    bpy.context.scene.collection.objects.link(root)
    objs["MonkeyRoot"] = root

    for name, parent, pv in RIG:
        ob = objs[name]
        ob.parent = objs[parent]
        ob.location = Vector(pv) - (Vector(pivot[parent]) if parent != "MonkeyRoot" else Vector((0, 0, 0)))
        ob.rotation_mode = 'XYZ'
        ob.rotation_euler = tuple(math.radians(v) for v in REST_ROT.get(name, (0.0, 0.0, 0.0)))
        ob.scale = (1.0, 1.0, 1.0)
    return objs


# ==========================================================================
# 姿势系统
# ==========================================================================
def rest_rot(name):
    """静止姿势里该部件的基准角度。"""
    return REST_ROT.get(name, (0.0, 0.0, 0.0))


class Pose:
    """一个姿势：每个部件的局部欧拉角（度）+ 位置偏移（米）。

    写进去的角度是**相对静止姿势的增量**：Pose.r() 会自动加上 REST_ROT 基准，
    所以"驼背 12°"这种造型只写在 REST_ROT 里一处，动画里不用重复扣。
    """

    __slots__ = ("rot", "loc")

    def __init__(self):
        self.rot = {}
        self.loc = {}

    def r(self, name, rx=0.0, ry=0.0, rz=0.0):
        base = rest_rot(name)
        self.rot[name] = (base[0] + rx, base[1] + ry, base[2] + rz)
        return self

    def a(self, name, rx=0.0, ry=0.0, rz=0.0):
        """**绝对**角度（不叠 REST_ROT）—— 给 IK 算出来的关节角用。"""
        self.rot[name] = (rx, ry, rz)
        return self

    def l(self, name, lx=0.0, ly=0.0, lz=0.0):
        self.loc[name] = (lx, ly, lz)
        return self


def full_pose(rot=None, loc=None):
    """一份"完整姿势"：所有部件都出现（没写的都是静止基准）。

    每个片段的第 0 帧都必须是完整姿势 —— 烘焙时"没出现就沿用上一次"的规则
    依赖这一点，否则某个部件会在片段中途突然从静止跳到第一个关键帧。
    """
    p = Pose()
    for nm in RIG_NAMES:
        p.rot[nm] = rest_rot(nm)
        p.loc[nm] = (0.0, 0.0, 0.0)
    for nm, v in (rot or {}).items():
        p.r(nm, *v)
    for nm, v in (loc or {}).items():
        p.l(nm, *v)
    return p


def arm(p, side, upper=0.0, elbow=0.0, wrist=0.0, fingers=0.0, uy=0.0, uz=0.0):
    """摆一条手臂。uy / uz 左右镜像（左手取反）。"""
    m = 1.0 if side == "R" else -1.0
    p.r("Monkey_Arm_%s_Upper" % side, upper, uy * m, uz * m)
    p.r("Monkey_Arm_%s_Fore" % side, elbow)
    p.r("Monkey_Arm_%s_Hand" % side, wrist)
    p.r("Monkey_Arm_%s_Fingers" % side, fingers)
    return p


def leg(p, side, thigh=0.0, knee=0.0, ankle=0.0, ty=0.0, tz=0.0):
    """摆一条腿。ty / tz 左右镜像。"""
    m = 1.0 if side == "R" else -1.0
    p.r("Monkey_Leg_%s_Thigh" % side, thigh, ty * m, tz * m)
    p.r("Monkey_Leg_%s_Shin" % side, knee)
    p.r("Monkey_Leg_%s_Foot" % side, ankle)
    return p


def tail(p, x1=0.0, z1=0.0, x2=0.0, z2=0.0, x3=0.0, z3=0.0):
    p.r("Monkey_Tail_1", x1, 0.0, z1)
    p.r("Monkey_Tail_2", x2, 0.0, z2)
    p.r("Monkey_Tail_3", x3, 0.0, z3)
    return p


def head(p, rx=0.0, ry=0.0, rz=0.0):
    p.r("Monkey_Head", rx, ry, rz)
    return p


def torso(p, rx=0.0, ry=0.0, rz=0.0):
    p.r("Monkey_Torso", rx, ry, rz)
    return p


def hips(p, rx=0.0, ry=0.0, rz=0.0, lx=0.0, ly=0.0, lz=0.0):
    p.r("Monkey_Hips", rx, ry, rz)
    p.l("Monkey_Hips", lx, ly, lz)
    return p


def stance_offset(*legs):
    """几条腿同时着地时的髋部偏移（正 = 抬高）。

    每个 (大腿, 膝, 踝) 算一条腿"不插地所需的最低髋高"，取**最大值** ——
    取 max 才是"都不插地"，取 min 会让其中一条腿陷进地面。
    """
    h = -1e9
    for thigh, knee, ankle in legs:
        t = math.radians(thigh)
        drop = THIGH_M * math.cos(t) + SHIN_M * math.cos(t + math.radians(knee))
        z_min = foot_lowest_z(math.radians(thigh + knee + ankle))
        h = max(h, drop - z_min)
    return h - HIP_Z_M


def crouch_depth(thigh_deg, knee_deg, ankle_deg=0.0):
    """给定大腿/膝/踝角度，算"髋要下沉多少"才能让脚底正好还贴着地。

    垂直落差 = 大腿长·cos(大腿角) + 小腿长·cos(大腿角 + 膝角)
    脚掌绕 X 转过 (大腿+膝+踝) 之后，脚尖/脚跟谁更低会变；
    髋高 = 落差 − 脚掌最低点；下沉量 = 站立髋高 − 髋高
    """
    t = math.radians(thigh_deg)
    k = math.radians(knee_deg)
    drop = THIGH_M * math.cos(t) + SHIN_M * math.cos(t + k)
    z_min = foot_lowest_z(math.radians(thigh_deg + knee_deg + ankle_deg))
    return HIP_Z_M - (drop - z_min)


# ==========================================================================
# 片段 1：跑（循环）
# ==========================================================================
# 一条腿的 4 个相位：(大腿, 膝, 踝)
#   大腿 +X = 向前；膝角度 = 小腿相对大腿的偏转（负 = 屈膝，脚跟往后）
#   踝角度 = 脚相对小腿的偏转（负 = 脚尖下压）
#
# 这四个相位是**按"脚底始终贴地"反解出来的**，不是拍脑袋填的：
#   脚底离地高 = 髋高 − 垂直落差 + 脚掌最低点（脚转了角度后最低点会变）
#   垂直落差 = 大腿长·cos(大腿角) + 小腿长·cos(大腿角 + 膝角)
#   脚掌最低点 = min(脚尖, 脚跟) 绕 X 转过 (大腿+膝+踝) 之后的 z
# 取髋高 = 0.552 m（比站立低 8 mm）反解，得到下面这组角：
#   触地   落差 0.480 脚掌平   → 脚底 +2 mm
#   支撑   落差 0.472 脚掌平   → 脚底 +10 mm
#   过渡   落差 0.315 脚尖下压 → 脚底 +109 mm（腾空 ✓）
#   蹬离   落差 0.415 脚尖下压 → 脚底 0 mm
# 之前那组角（22/-8/-14 之类）脚底会插进地面 7 cm，是自检
# `clip_ground_audit()` 抓出来的。
RUN_LEG_KEYS = [
    (14.0, -6.0, -8.0),      # 0.00 触地：腿前伸接近伸直，脚掌平贴地
    (-10.0, 30.0, -20.0),    # 0.25 支撑：髋落后、膝盖顶到脚前方，吸收冲击
    (-30.0, -8.0, -2.0),     # 0.50 蹬离：腿后伸蹬地，脚尖下压（身体最高）
    (-16.0, -55.0, 39.0),    # 0.75 过渡：大腿后摆、膝收起，腿甩回前方（腾空）
]

def _smooth(t):
    return t * t * (3.0 - 2.0 * t)


def _run_leg(t):
    """在 4 个相位之间做平滑插值，返回 (大腿, 膝, 踝)。"""
    n = len(RUN_LEG_KEYS)
    x = (t % 1.0) * n
    i = int(x) % n
    f = _smooth(x - int(x))
    a, b = RUN_LEG_KEYS[i], RUN_LEG_KEYS[(i + 1) % n]
    return tuple(a[k] + (b[k] - a[k]) * f for k in range(3))


def _run_leg_state(phase):
    """这条腿在给定相位时的 (垂直落差, 脚掌最低点相对踝关节的 z)。

    垂直落差 = 大腿长·cos(大腿角) + 小腿长·cos(大腿角+膝角)
    脚掌最低点 = 脚尖 / 脚跟绕 X 转过 (大腿+膝+踝) 之后的 z 取小
    """
    thigh, knee, ankle = _run_leg(phase)
    t = math.radians(thigh)
    drop = THIGH_M * math.cos(t) + SHIN_M * math.cos(t + math.radians(knee))
    return drop, foot_lowest_z(math.radians(thigh + knee + ankle))


def _run_hips_height(p):
    """跑动时的髋部高度。

    取**两条腿需求的最大值**：每条腿各自算"要让这只脚刚好踩在地上，
    髋得有多高"（落差 − 脚掌最低点），髋高取两者的 max。
    只按一条腿算会漏掉跑动里"两脚同时着地"的那一瞬（错身位）：
    蹬离腿脚尖扎地、要的髋比另一条腿高 2 cm，只按触地腿算，
    蹬离那只脚就会插进地面 1.9 cm —— 是 `clip_ground_audit()` 抓出来的。
    """
    p = p % 1.0
    d1, z1 = _run_leg_state(p)
    d2, z2 = _run_leg_state(p + 0.5)
    return max(d1 - z1, d2 - z2)


def run_pose(phase):
    """给定循环相位（0..1）返回一帧姿势。"""
    p = full_pose()
    tr, kr, ar = _run_leg(phase)
    tl, kl, al = _run_leg(phase + 0.5)
    leg(p, "R", tr, kr, ar, tz=4.0)
    leg(p, "L", tl, kl, al, tz=4.0)
    # 手臂与**对侧**腿反相
    arm(p, "R", upper=-1.15 * tl, elbow=58.0 + 0.30 * tl, wrist=-8.0)
    arm(p, "L", upper=-1.15 * tr, elbow=58.0 + 0.30 * tr, wrist=-8.0)
    hips(p, rz=0.30 * tr, lx=0.010 * math.sin(2 * math.pi * phase),
         ly=0.014 * math.sin(2 * math.pi * phase),
         lz=_run_hips_height(phase) - HIP_Z_M)
    torso(p, rx=-4.0, ry=2.0 * math.sin(2 * math.pi * phase), rz=-0.20 * tr)
    head(p, rx=2.0, ry=-1.5 * math.sin(2 * math.pi * phase), rz=0.15 * tr)
    tail(p,
         x1=6.0 * math.sin(2 * math.pi * phase),
         z1=13.0 * math.sin(2 * math.pi * phase + 0.5),
         x2=7.0 * math.sin(2 * math.pi * phase + 0.4),
         z2=10.0 * math.sin(2 * math.pi * phase + 1.0),
         x3=8.0 * math.sin(2 * math.pi * phase + 0.8),
         z3=9.0 * math.sin(2 * math.pi * phase + 1.5))
    return p


CLIP_RUN = [(f, run_pose(f / 24.0)) for f in range(25)]


# ==========================================================================
# 片段 2：受惊吓原地蹦
# ==========================================================================
def _startle_crouch(thigh_deg, knee_deg):
    """下蹲姿势：髋下沉量由几何算出来，保证脚底还贴地。"""
    p = full_pose()
    for s in ("R", "L"):
        leg(p, s, thigh=thigh_deg, knee=knee_deg, ankle=30.0, tz=6.0)
        arm(p, s, upper=-18.0, elbow=68.0, wrist=-6.0)
    hips(p, lz=-crouch_depth(thigh_deg, knee_deg, 30.0))
    torso(p, rx=10.0)
    head(p, rx=6.0)
    tail(p, x1=-14.0, z1=16.0, x2=-10.0, z2=12.0)
    return p


CLIP_STARTLE = [
    (0, full_pose()),
    # 1) 愣一下：抬头、耳朵立起、手臂微张
    (5, full_pose(rot={
        "Monkey_Head": (14.0, 0.0, 0.0), "Monkey_Torso": (-4.0, 0.0, 0.0),
        "Monkey_Arm_R_Upper": (-6.0, 0.0, 0.0), "Monkey_Arm_L_Upper": (-6.0, 0.0, 0.0),
        "Monkey_Arm_R_Fore": (34.0, 0.0, 0.0), "Monkey_Arm_L_Fore": (34.0, 0.0, 0.0),
        "Monkey_Tail_1": (-16.0, 0.0, 0.0),
    })),
    # 2) 蓄力下蹲
    (9, _startle_crouch(28.0, -62.0)),
    # 3) 蹬地腾空：髋抬起来、腿收起、手举过头
    (14, full_pose(rot={
        "Monkey_Leg_R_Thigh": (34.0, 0.0, 5.0), "Monkey_Leg_R_Shin": (-74.0, 0.0, 0.0),
        "Monkey_Leg_R_Foot": (30.0, 0.0, 0.0),
        "Monkey_Leg_L_Thigh": (30.0, 0.0, -5.0), "Monkey_Leg_L_Shin": (-70.0, 0.0, 0.0),
        "Monkey_Leg_L_Foot": (30.0, 0.0, 0.0),
        "Monkey_Arm_R_Upper": (150.0, 0.0, 0.0), "Monkey_Arm_L_Upper": (146.0, 0.0, 0.0),
        "Monkey_Arm_R_Fore": (26.0, 0.0, 0.0), "Monkey_Arm_L_Fore": (30.0, 0.0, 0.0),
        "Monkey_Torso": (-16.0, 0.0, 0.0), "Monkey_Head": (22.0, 0.0, 0.0),
        "Monkey_Tail_1": (-38.0, 0.0, 0.0), "Monkey_Tail_2": (-22.0, 0.0, 0.0),
    }, loc={"Monkey_Hips": (0.0, 0.0, 0.190)})),
    # 4) 下落（腿伸出去准备着地）
    (18, full_pose(rot={
        "Monkey_Leg_R_Thigh": (16.0, 0.0, 5.0), "Monkey_Leg_R_Shin": (-30.0, 0.0, 0.0),
        "Monkey_Leg_R_Foot": (10.0, 0.0, 0.0),
        "Monkey_Leg_L_Thigh": (14.0, 0.0, -5.0), "Monkey_Leg_L_Shin": (-28.0, 0.0, 0.0),
        "Monkey_Leg_L_Foot": (10.0, 0.0, 0.0),
        "Monkey_Arm_R_Upper": (96.0, 0.0, 0.0), "Monkey_Arm_L_Upper": (92.0, 0.0, 0.0),
        "Monkey_Arm_R_Fore": (44.0, 0.0, 0.0), "Monkey_Arm_L_Fore": (48.0, 0.0, 0.0),
        "Monkey_Torso": (-8.0, 0.0, 0.0), "Monkey_Head": (12.0, 0.0, 0.0),
        "Monkey_Tail_1": (-26.0, 0.0, 0.0),
    }, loc={"Monkey_Hips": (0.0, 0.0, 0.095)})),
    # 5) 落地缓冲（深蹲）
    (21, _startle_crouch(34.0, -76.0)),
    # 6) 缓过来，缩着身子
    (26, full_pose(rot={
        "Monkey_Leg_R_Thigh": (16.0, 0.0, 4.0), "Monkey_Leg_R_Shin": (-34.0, 0.0, 0.0),
        "Monkey_Leg_L_Thigh": (16.0, 0.0, -4.0), "Monkey_Leg_L_Shin": (-34.0, 0.0, 0.0),
        "Monkey_Arm_R_Upper": (-26.0, 0.0, 0.0), "Monkey_Arm_L_Upper": (-26.0, 0.0, 0.0),
        "Monkey_Arm_R_Fore": (86.0, 0.0, 0.0), "Monkey_Arm_L_Fore": (86.0, 0.0, 0.0),
        "Monkey_Torso": (16.0, 0.0, 0.0), "Monkey_Head": (10.0, 0.0, 0.0),
        "Monkey_Tail_1": (-18.0, 0.0, 0.0),
    }, loc={"Monkey_Hips": (0.0, 0.0, -crouch_depth(16.0, -34.0, 0.0))})),
    (30, full_pose()),
]


# ==========================================================================
# 片段 3：害怕发抖
# ==========================================================================
TREMBLE_FRAMES = 49          # 1.6 s
TREMBLE_HZ = 5.0


def tremble_pose(frame):
    """蜷缩着发抖：基姿势固定，叠一个 5 Hz 的小幅抖动。"""
    t = frame / float(FPS)
    w = 2.0 * math.pi * TREMBLE_HZ

    def jit(phase, amp):
        return amp * math.sin(w * t + phase)

    p = full_pose()
    for s in ("R", "L"):
        leg(p, s, thigh=20.0, knee=-46.0, ankle=16.0, tz=7.0)
        arm(p, s, upper=-38.0, elbow=104.0, wrist=-10.0, fingers=26.0,
            uy=6.0, uz=-10.0)
    hips(p, rx=4.0,
         lx=jit(0.0, 0.013), ly=jit(1.9, 0.010), lz=-crouch_depth(20.0, -46.0, 16.0) + jit(0.7, 0.007))
    torso(p, rx=20.0, ry=jit(2.6, 2.6), rz=jit(1.2, 3.2))
    head(p, rx=16.0, ry=jit(3.3, 4.5), rz=jit(2.1, 5.0))
    p.r("Monkey_Arm_R_Upper", -38.0 + jit(0.4, 5.0), 6.0, -10.0 + jit(1.5, 4.0))
    p.r("Monkey_Arm_L_Upper", -38.0 + jit(0.9, 5.0), -6.0, 10.0 + jit(2.0, 4.0))
    p.r("Monkey_Tail_1", -30.0 + jit(2.8, 7.0), 0.0, jit(1.7, 8.0))
    p.r("Monkey_Tail_2", -20.0 + jit(3.4, 6.0), 0.0, jit(2.3, 7.0))
    p.r("Monkey_Tail_3", -12.0 + jit(4.0, 5.0), 0.0, jit(2.9, 6.0))
    return p


CLIP_TREMBLE = [(f, tremble_pose(f)) for f in range(TREMBLE_FRAMES)]


# ==========================================================================
# 片段 4：单手投掷
# ==========================================================================
CLIP_THROW_ONE = [
    (0, full_pose()),
    # 1) 举石预备：右臂后摆、转身
    (8, full_pose(rot={
        "Monkey_Arm_R_Upper": (-72.0, -14.0, -18.0), "Monkey_Arm_R_Fore": (96.0, 0.0, 0.0),
        "Monkey_Arm_R_Hand": (-14.0, 0.0, 0.0), "Monkey_Arm_R_Fingers": (58.0, 0.0, 0.0),
        "Monkey_Arm_L_Upper": (24.0, 0.0, 0.0), "Monkey_Arm_L_Fore": (62.0, 0.0, 0.0),
        "Monkey_Torso": (-8.0, 0.0, 26.0), "Monkey_Head": (2.0, 0.0, 16.0),
        "Monkey_Hips": (0.0, 0.0, 12.0),
        "Monkey_Tail_1": (-10.0, 0.0, -14.0),
    })),
    # 2) 甩出去：右臂前挥、手指张开、身体转回
    (13, full_pose(rot={
        "Monkey_Arm_R_Upper": (74.0, -6.0, 6.0), "Monkey_Arm_R_Fore": (14.0, 0.0, 0.0),
        "Monkey_Arm_R_Hand": (-8.0, 0.0, 0.0), "Monkey_Arm_R_Fingers": (-14.0, 0.0, 0.0),
        "Monkey_Arm_L_Upper": (-26.0, 0.0, 0.0), "Monkey_Arm_L_Fore": (74.0, 0.0, 0.0),
        "Monkey_Torso": (-14.0, 0.0, -22.0), "Monkey_Head": (-4.0, 0.0, -12.0),
        "Monkey_Hips": (0.0, 0.0, -10.0),
        "Monkey_Leg_R_Thigh": (18.0, 0.0, 4.0), "Monkey_Leg_R_Shin": (-22.0, 0.0, 0.0),
        "Monkey_Leg_L_Thigh": (-16.0, 0.0, -4.0), "Monkey_Leg_L_Shin": (-26.0, 0.0, 0.0),
        "Monkey_Tail_1": (-18.0, 0.0, 16.0),
    }, loc={"Monkey_Hips": (0.0, 0.0, 0.024)})),
    # 3) 随挥
    (17, full_pose(rot={
        "Monkey_Arm_R_Upper": (96.0, -2.0, 10.0), "Monkey_Arm_R_Fore": (8.0, 0.0, 0.0),
        "Monkey_Arm_R_Fingers": (-6.0, 0.0, 0.0),
        "Monkey_Torso": (-8.0, 0.0, -28.0), "Monkey_Head": (0.0, 0.0, -14.0),
        "Monkey_Hips": (0.0, 0.0, -14.0),
        "Monkey_Leg_R_Thigh": (22.0, 0.0, 4.0), "Monkey_Leg_R_Shin": (-16.0, 0.0, 0.0),
        "Monkey_Tail_1": (-12.0, 0.0, 18.0),
    })),
    # 4) 收势
    (24, full_pose(rot={
        "Monkey_Arm_R_Upper": (34.0, 0.0, 4.0), "Monkey_Arm_R_Fore": (46.0, 0.0, 0.0),
        "Monkey_Torso": (-4.0, 0.0, -8.0), "Monkey_Hips": (0.0, 0.0, -4.0),
    })),
    (30, full_pose()),
]


# ==========================================================================
# 片段 5：双手投掷
# ==========================================================================
CLIP_THROW_TWO = [
    (0, full_pose()),
    # 1) 双臂举到身后、屈膝蓄力
    (8, full_pose(rot={
        "Monkey_Arm_R_Upper": (-84.0, -20.0, -26.0), "Monkey_Arm_R_Fore": (104.0, 0.0, 0.0),
        "Monkey_Arm_R_Hand": (-16.0, 0.0, 0.0), "Monkey_Arm_R_Fingers": (64.0, 0.0, 0.0),
        "Monkey_Arm_L_Upper": (-84.0, 20.0, 26.0), "Monkey_Arm_L_Fore": (104.0, 0.0, 0.0),
        "Monkey_Arm_L_Hand": (-16.0, 0.0, 0.0), "Monkey_Arm_L_Fingers": (64.0, 0.0, 0.0),
        "Monkey_Torso": (12.0, 0.0, 0.0), "Monkey_Head": (10.0, 0.0, 0.0),
        "Monkey_Leg_R_Thigh": (-14.0, 0.0, 5.0), "Monkey_Leg_R_Shin": (34.0, 0.0, 0.0),
        "Monkey_Leg_R_Foot": (-18.0, 0.0, 0.0),
        "Monkey_Leg_L_Thigh": (-14.0, 0.0, -5.0), "Monkey_Leg_L_Shin": (34.0, 0.0, 0.0),
        "Monkey_Leg_L_Foot": (-18.0, 0.0, 0.0),
        "Monkey_Tail_1": (-30.0, 0.0, 0.0),
    }, loc={"Monkey_Hips": (0.0, 0.0, -crouch_depth(-14.0, 34.0, -18.0))})),
    # 2) 双手前挥
    (13, full_pose(rot={
        "Monkey_Arm_R_Upper": (86.0, -6.0, 10.0), "Monkey_Arm_R_Fore": (16.0, 0.0, 0.0),
        "Monkey_Arm_R_Hand": (-10.0, 0.0, 0.0), "Monkey_Arm_R_Fingers": (-16.0, 0.0, 0.0),
        "Monkey_Arm_L_Upper": (86.0, 6.0, -10.0), "Monkey_Arm_L_Fore": (16.0, 0.0, 0.0),
        "Monkey_Arm_L_Hand": (-10.0, 0.0, 0.0), "Monkey_Arm_L_Fingers": (-16.0, 0.0, 0.0),
        "Monkey_Torso": (-24.0, 0.0, 0.0), "Monkey_Head": (-10.0, 0.0, 0.0),
        "Monkey_Leg_R_Thigh": (20.0, 0.0, 5.0), "Monkey_Leg_R_Shin": (-18.0, 0.0, 0.0),
        "Monkey_Leg_L_Thigh": (20.0, 0.0, -5.0), "Monkey_Leg_L_Shin": (-18.0, 0.0, 0.0),
        "Monkey_Tail_1": (-34.0, 0.0, 0.0),
    }, loc={"Monkey_Hips": (0.0, 0.0, 0.030)})),
    # 3) 随挥 + 重心前倾
    (17, full_pose(rot={
        "Monkey_Arm_R_Upper": (104.0, -2.0, 14.0), "Monkey_Arm_R_Fore": (6.0, 0.0, 0.0),
        "Monkey_Arm_R_Fingers": (-4.0, 0.0, 0.0),
        "Monkey_Arm_L_Upper": (104.0, 2.0, -14.0), "Monkey_Arm_L_Fore": (6.0, 0.0, 0.0),
        "Monkey_Arm_L_Fingers": (-4.0, 0.0, 0.0),
        "Monkey_Torso": (-30.0, 0.0, 0.0), "Monkey_Head": (-14.0, 0.0, 0.0),
        "Monkey_Leg_R_Thigh": (26.0, 0.0, 5.0), "Monkey_Leg_R_Shin": (-12.0, 0.0, 0.0),
        "Monkey_Leg_L_Thigh": (26.0, 0.0, -5.0), "Monkey_Leg_L_Shin": (-12.0, 0.0, 0.0),
        "Monkey_Tail_1": (-26.0, 0.0, 0.0),
    }, loc={"Monkey_Hips": (0.0, 0.0, 0.055)})),
    (23, full_pose(rot={
        "Monkey_Arm_R_Upper": (40.0, 0.0, 6.0), "Monkey_Arm_R_Fore": (40.0, 0.0, 0.0),
        "Monkey_Arm_L_Upper": (40.0, 0.0, -6.0), "Monkey_Arm_L_Fore": (40.0, 0.0, 0.0),
        "Monkey_Torso": (-8.0, 0.0, 0.0),
    })),
    (30, full_pose()),
]


# ==========================================================================
# 片段 6：鼓掌
# ==========================================================================
# 拍一次掌 = 双手在胸前合拢 → 弹开 → 再合拢。
#
# **这里必须用 2 连杆 IK**，不能手填肩肘角：手是"链"末梢，手腕到肩膀
# 0.64 m，要凑到胸前 0.20 m 处就得把肘折起来，手填角度凑不准，
# 表现出来就是"两只手怎么都碰不到一起"。
#
# IK 全程在**躯干局部坐标系**里算（躯干是手臂的父级），所以躯干转多少
# 都不用另外补偿，手也跟着躯干走。
CLAP_TOGETHER_WRIST = (0.012, 0.105, 0.030)   # 躯干局部：合拢时右手腕位置
CLAP_APART_WRIST = (0.080, 0.090, 0.020)      # 躯干局部：张开时右手腕位置


def _aim_quat(d):
    """把肢体的自然下垂方向 (0,0,-1) 转到方向 d 的四元数（最小旋转）。"""
    d = Vector(d).normalized()
    base = Vector((0.0, 0.0, -1.0))
    axis = base.cross(d)
    if axis.length < 1e-8:
        return Quaternion((1.0, 0.0, 0.0, 0.0)) if base.dot(d) > 0 else Quaternion((0.0, 1.0, 0.0, 0.0))
    axis.normalize()
    return Quaternion(axis, base.angle(d))


def _two_link_ik(root, target, l1, l2, pole):
    """2 连杆 IK：给定根、目标、两段长度和"肘往哪边偏"的方向，解出肘的位置。"""
    root = Vector(root)
    target = Vector(target)
    d = target - root
    dist = min(max(d.length, abs(l1 - l2) + 1e-4), l1 + l2 - 1e-4)
    u = d.normalized()
    p = Vector(pole)
    p = p - u * p.dot(u)
    if p.length < 1e-6:
        p = Vector((0.0, 1.0, 0.0)) - u * u.y
    p.normalize()
    a = (l1 * l1 - l2 * l2 + dist * dist) / (2.0 * dist)
    h = math.sqrt(max(0.0, l1 * l1 - a * a))
    return root + u * a + p * h


def _clap_pose(open_amt):
    """open_amt = 0（合拢）.. 1（张开）。"""
    p = full_pose()
    wrist = Vector(CLAP_TOGETHER_WRIST).lerp(Vector(CLAP_APART_WRIST), open_amt)
    for side, m in (("R", 1.0), ("L", -1.0)):
        sh = Vector((m * SHOULDER_X_M, 0.0, SHOULDER_Z_M - WAIST_Z_M))   # 躯干局部
        tgt = Vector((m * wrist.x, wrist.y, wrist.z))
        elbow = _two_link_ik(sh, tgt, UPPER_ARM_M, FOREARM_M, (m * 0.2, 0.0, -1.0))
        up = _aim_quat(elbow - sh)
        fo = _aim_quat(tgt - elbow)
        # to_euler 返回的是**弧度**，姿势系统统一用度数，这里要换算
        p.a("Monkey_Arm_%s_Upper" % side, *[math.degrees(v) for v in up.to_euler('XYZ')])
        p.a("Monkey_Arm_%s_Fore" % side, *[math.degrees(v) for v in fo.to_euler('XYZ')])
        p.r("Monkey_Arm_%s_Hand" % side, -12.0)
        p.r("Monkey_Arm_%s_Fingers" % side, 14.0)
    torso(p, rx=-6.0, rz=2.0 * (1.0 - open_amt))
    head(p, rx=6.0)
    hips(p, lz=-0.004, rx=1.5 * (1.0 - open_amt))
    return p


CLIP_CLAP = [(0, _clap_pose(1.0))]
for i in range(4):
    f0 = 3 + i * 10
    CLIP_CLAP += [
        (f0, _clap_pose(0.0)),
        (f0 + 3, _clap_pose(1.0)),
        (f0 + 6, _clap_pose(0.35)),
    ]
CLIP_CLAP.append((43, _clap_pose(1.0)))


# ==========================================================================
# 片段 7：抢东西
# ==========================================================================
CLIP_SNATCH = [
    (0, full_pose()),
    # 1) 蓄势：压低身体
    (5, full_pose(rot={
        "Monkey_Torso": (14.0, 0.0, 0.0), "Monkey_Head": (8.0, 0.0, 0.0),
        "Monkey_Leg_R_Thigh": (-10.0, 0.0, 5.0), "Monkey_Leg_R_Shin": (26.0, 0.0, 0.0),
        "Monkey_Leg_L_Thigh": (-10.0, 0.0, -5.0), "Monkey_Leg_L_Shin": (26.0, 0.0, 0.0),
        "Monkey_Arm_R_Upper": (-30.0, 0.0, 0.0), "Monkey_Arm_L_Upper": (-30.0, 0.0, 0.0),
        "Monkey_Arm_R_Fore": (58.0, 0.0, 0.0), "Monkey_Arm_L_Fore": (58.0, 0.0, 0.0),
        "Monkey_Tail_1": (-24.0, 0.0, 0.0),
    }, loc={"Monkey_Hips": (0.0, 0.0, -crouch_depth(-10.0, 26.0))})),
    # 2) 猛伸手：双臂笔直前伸
    (10, full_pose(rot={
        "Monkey_Arm_R_Upper": (86.0, -10.0, -8.0), "Monkey_Arm_R_Fore": (6.0, 0.0, 0.0),
        "Monkey_Arm_R_Hand": (-16.0, 0.0, 0.0), "Monkey_Arm_R_Fingers": (-12.0, 0.0, 0.0),
        "Monkey_Arm_L_Upper": (86.0, 10.0, 8.0), "Monkey_Arm_L_Fore": (6.0, 0.0, 0.0),
        "Monkey_Arm_L_Hand": (-16.0, 0.0, 0.0), "Monkey_Arm_L_Fingers": (-12.0, 0.0, 0.0),
        "Monkey_Torso": (-20.0, 0.0, 0.0), "Monkey_Head": (-8.0, 0.0, 0.0),
        "Monkey_Leg_R_Thigh": (22.0, 0.0, 5.0), "Monkey_Leg_R_Shin": (-16.0, 0.0, 0.0),
        "Monkey_Leg_L_Thigh": (16.0, 0.0, -5.0), "Monkey_Leg_L_Shin": (-14.0, 0.0, 0.0),
        "Monkey_Tail_1": (-40.0, 0.0, 0.0), "Monkey_Tail_2": (-24.0, 0.0, 0.0),
    }, loc={"Monkey_Hips": (0.0, 0.0, stance_offset((22.0, -16.0, 0.0), (16.0, -14.0, 0.0)))})),
    # 3) 抓住：手指扣拢
    (13, full_pose(rot={
        "Monkey_Arm_R_Upper": (88.0, -10.0, -8.0), "Monkey_Arm_R_Fore": (10.0, 0.0, 0.0),
        "Monkey_Arm_R_Hand": (-22.0, 0.0, 0.0), "Monkey_Arm_R_Fingers": (72.0, 0.0, 0.0),
        "Monkey_Arm_L_Upper": (88.0, 10.0, 8.0), "Monkey_Arm_L_Fore": (10.0, 0.0, 0.0),
        "Monkey_Arm_L_Hand": (-22.0, 0.0, 0.0), "Monkey_Arm_L_Fingers": (72.0, 0.0, 0.0),
        "Monkey_Torso": (-22.0, 0.0, 0.0), "Monkey_Head": (-10.0, 0.0, 0.0),
        "Monkey_Leg_R_Thigh": (24.0, 0.0, 5.0), "Monkey_Leg_R_Shin": (-18.0, 0.0, 0.0),
        "Monkey_Leg_L_Thigh": (18.0, 0.0, -5.0), "Monkey_Leg_L_Shin": (-16.0, 0.0, 0.0),
        "Monkey_Tail_1": (-44.0, 0.0, 0.0), "Monkey_Tail_2": (-26.0, 0.0, 0.0),
    }, loc={"Monkey_Hips": (0.0, 0.0, stance_offset((24.0, -18.0, 0.0), (18.0, -16.0, 0.0)))})),
    # 4) 抢到手拽回来
    (18, full_pose(rot={
        "Monkey_Arm_R_Upper": (52.0, -14.0, -18.0), "Monkey_Arm_R_Fore": (78.0, 0.0, 0.0),
        "Monkey_Arm_R_Hand": (-18.0, 0.0, 0.0), "Monkey_Arm_R_Fingers": (76.0, 0.0, 0.0),
        "Monkey_Arm_L_Upper": (52.0, 14.0, 18.0), "Monkey_Arm_L_Fore": (78.0, 0.0, 0.0),
        "Monkey_Arm_L_Hand": (-18.0, 0.0, 0.0), "Monkey_Arm_L_Fingers": (76.0, 0.0, 0.0),
        "Monkey_Torso": (10.0, 0.0, 0.0), "Monkey_Head": (12.0, 0.0, 0.0),
        "Monkey_Leg_R_Thigh": (16.0, 0.0, 5.0), "Monkey_Leg_R_Shin": (-28.0, 0.0, 0.0),
        "Monkey_Leg_L_Thigh": (16.0, 0.0, -5.0), "Monkey_Leg_L_Shin": (-28.0, 0.0, 0.0),
        "Monkey_Tail_1": (-20.0, 0.0, 0.0), "Monkey_Tail_2": (-12.0, 0.0, 0.0),
    }, loc={"Monkey_Hips": (0.0, 0.0, stance_offset((16.0, -28.0, 0.0), (16.0, -28.0, 0.0)))})),
    # 5) 得意地晃一下
    (23, full_pose(rot={
        "Monkey_Arm_R_Upper": (58.0, -16.0, -22.0), "Monkey_Arm_R_Fore": (86.0, 0.0, 0.0),
        "Monkey_Arm_R_Fingers": (74.0, 0.0, 0.0),
        "Monkey_Arm_L_Upper": (58.0, 16.0, 22.0), "Monkey_Arm_L_Fore": (86.0, 0.0, 0.0),
        "Monkey_Arm_L_Fingers": (74.0, 0.0, 0.0),
        "Monkey_Torso": (6.0, 0.0, -6.0), "Monkey_Head": (8.0, 0.0, 6.0),
        "Monkey_Hips": (0.0, 0.0, -6.0),
        "Monkey_Tail_1": (-30.0, 0.0, 12.0), "Monkey_Tail_2": (-18.0, 0.0, 8.0),
    }, loc={"Monkey_Hips": (0.0, 0.0, stance_offset((16.0, -28.0, 0.0), (16.0, -28.0, 0.0)))})),
    (30, full_pose()),
]


CLIPS = [
    ("Monkey_Run", CLIP_RUN, [0, 8, 16]),
    ("Monkey_Startle", CLIP_STARTLE, [9, 14, 21]),
    ("Monkey_Tremble", CLIP_TREMBLE, [1, 4, 8]),
    ("Monkey_ThrowOne", CLIP_THROW_ONE, [8, 13, 17]),
    ("Monkey_ThrowTwo", CLIP_THROW_TWO, [8, 13, 17]),
    ("Monkey_Clap", CLIP_CLAP, [3, 6, 13]),
    ("Monkey_Snatch", CLIP_SNATCH, [5, 13, 18]),
]


# ==========================================================================
# 烘焙动画
# ==========================================================================
def act_fcurves(act):
    """Blender 4.4+ 的分层 Action：fcurve 在 layer → strip → channelbag 里。"""
    if getattr(act, "layers", None):
        for layer in act.layers:
            for strip in layer.strips:
                for slot in act.slots:
                    cb = strip.channelbag(slot)
                    if cb:
                        for fc in cb.fcurves:
                            yield fc
    else:
        for fc in getattr(act, "fcurves", []):
            yield fc


def resolve_poses(keys):
    """把 [(帧, 姿势)] 展开成 {部件名: {帧: (rot, loc)}}。

    规则：**没出现的部件沿用上一个关键帧的值**（片段开头则用后面第一个值）。
    烘焙和预览渲染共用这一份，保证"渲染出来的姿势"和"导出的动画"一致。
    """
    frames = [fr for fr, _ in keys]
    names = set()
    for _fr, p in keys:
        names |= set(p.rot)
    out = {nm: {} for nm in names}
    for fr in frames:
        for nm in names:
            rot, loc = None, None
            for f2, p in keys:
                if f2 <= fr:
                    if nm in p.rot:
                        rot = p.rot[nm]
                    if nm in p.loc:
                        loc = p.loc[nm]
            if rot is None:
                for f2, p in keys:
                    if f2 > fr and nm in p.rot:
                        rot = p.rot[nm]
                        break
            if loc is None:
                for f2, p in keys:
                    if f2 > fr and nm in p.loc:
                        loc = p.loc[nm]
                        break
            out[nm][fr] = (rot or rest_rot(nm), loc or (0.0, 0.0, 0.0))
    return out, frames


def apply_pose(objs, rest_loc, rot, loc):
    """把一份姿势直接摆到物体上（预览渲染用，不经过 Action）。"""
    for nm, r in rot.items():
        ob = objs[nm]
        ob.rotation_euler = tuple(math.radians(v) for v in r)
        l = loc.get(nm, (0.0, 0.0, 0.0))
        base = rest_loc[nm]
        ob.location = Vector((base[0] + l[0], base[1] + l[1], base[2] + l[2]))


def bake_clip(name, keys, objs, rest_loc):
    """把一个片段烘焙成一个 Action。

    一个 Action 覆盖多个物体 → 每个物体在 Action 里各占一个 slot
    （Blender 4.4+ 分层 Action 的默认行为：keyframe_insert 会自动建 slot）。
    """
    frames = [fr for fr, _ in keys]
    assert frames == sorted(frames), "%s 的帧号必须递增" % name
    assert frames[0] == 0, "%s 必须从第 0 帧开始" % name

    posed, _frames = resolve_poses(keys)
    acted = set(posed)
    # 第 0 帧必须是完整姿势，否则中途会出现"部件突然跳一下"
    first = keys[0][1]
    missing = sorted(acted - set(first.rot))
    assert not missing, "%s 第 0 帧缺这些部件：%s" % (name, missing)

    act = bpy.data.actions.new(name)
    act.use_fake_user = True
    slots = {}
    for nm in sorted(acted):
        ob = objs[nm]
        ad = ob.animation_data_create()
        ad.action = act
        for fr in frames:
            rot, loc = posed[nm][fr]
            ob.rotation_euler = tuple(math.radians(v) for v in rot)
            ob.keyframe_insert("rotation_euler", frame=fr)
            base = rest_loc[nm]
            ob.location = Vector((base[0] + loc[0], base[1] + loc[1], base[2] + loc[2]))
            ob.keyframe_insert("location", frame=fr)
        slots[nm] = ad.action_slot
        ad.action = None
        # 每个物体一条**同名 NLA track**（名字 = 片段名）。
        # 这是 glTF 导出器唯一认的"片段分组"依据：它按 track 名把各物体的
        # 动画合并成一条 glTF animation（见 io_scene_gltf2/blender/exp/animation/action.py
        # 的 exists_action_slot_target / merge_tracks_perform）。
        # ⚠️ strip.action_slot 必须显式指向"本物体在这个 Action 里的那个 slot"，
        #    否则导出器找不到对应的 channelbag，片段会被整个丢掉。
        track = ad.nla_tracks.new()
        track.name = name
        strip = track.strips.new(name, 0, act)
        strip.name = name
        if hasattr(strip, "action_slot") and slots[nm] is not None:
            strip.action_slot = slots[nm]
    for fc in act_fcurves(act):
        for kp in fc.keyframe_points:
            kp.interpolation = 'BEZIER'
            kp.handle_left_type = kp.handle_right_type = 'AUTO_CLAMPED'
        fc.update()
    print("ANIM  %-18s objects=%-3d fcurves=%d"
          % (name, len(slots), len(list(act_fcurves(act)))))
    return act, slots


def restore_rest(objs, rest_loc, rest_rot_map):
    for nm, ob in objs.items():
        ob.rotation_euler = rest_rot_map[nm]
        ob.location = Vector(rest_loc[nm])
        ob.scale = (1.0, 1.0, 1.0)


def mute_tracks(objs, mute=True):
    """静音所有 NLA track。

    只静音 **track**，不动 **strip**：glTF 导出器在 ACTIONS 模式下收集片段时
    检查的是 `strip.mute`，不是 `track.mute`。所以 track 静音（.blend 打开时
    猴子是静止站姿）不会让 .glb 少掉任何片段。
    """
    for ob in objs.values():
        if ob.animation_data:
            for track in ob.animation_data.nla_tracks:
                track.mute = mute


# ==========================================================================
# 预览渲染
# ==========================================================================
def render_preview(objs, rest_loc, rest_rot_map):
    """出两张图：

    1) _preview.png  站姿四视图
    2) _anim.png     动画接触表（7 行 = 7 个片段，每行 3 个代表帧）

    姿势是**直接摆到物体上**再渲染的，不走 Action 求值 —— 这样渲染出来的
    姿势和导出的动画用的是同一份数据（resolve_poses），不会两处对不上。
    """
    rig = PreviewRig(ground_size=30.0)
    tgt = (0.0, 0.0, 0.46)

    # 站姿四视图
    shots = [("front34", 42, 10, 2.45), ("front", 90, 4, 2.35),
             ("side", 2, 6, 2.35), ("back34", 138, 12, 2.45)]
    rig.contact_sheet(os.path.join(OUT_DIR, NAME + "_preview.png"), tgt, shots,
                      res=(420, 520), cols=4)

    # 动画接触表
    tmp = []
    k = 0
    for name, keys, frames in CLIPS:
        posed, _all_frames = resolve_poses(keys)
        for fr in frames:
            rot = {nm: posed[nm][fr][0] for nm in posed}
            loc = {nm: posed[nm][fr][1] for nm in posed}
            apply_pose(objs, rest_loc, rot, loc)
            bpy.context.view_layer.update()
            p = "/tmp/monkey_anim_%02d.png" % k
            rig.shoot(p, 44, 8, 2.45, tgt, res=(340, 400))
            tmp.append(p)
            k += 1
    stitch_images(tmp, os.path.join(OUT_DIR, NAME + "_anim.png"), 3)

    # 还原成静止站姿
    for ob in objs.values():
        if ob.animation_data:
            ob.animation_data.action = None
    mute_tracks(objs, True)
    restore_rest(objs, rest_loc, rest_rot_map)
    bpy.context.scene.frame_set(0)


# ==========================================================================
# 导出 + 自检
# ==========================================================================
def glb_report(path):
    """直接读 .glb 的 JSON chunk：动画片段名 + 每段的通道目标节点。"""
    import json
    import struct
    with open(path, "rb") as fh:
        data = fh.read()
    off, js = 12, None
    while off < len(data):
        clen, ctype = struct.unpack("<II", data[off:off + 8])
        if ctype == 0x4E4F534A:
            js = json.loads(data[off + 8:off + 8 + clen])
        off += 8 + clen
    nodes = js.get("nodes", [])
    out = {}
    for a in js.get("animations", []):
        chans = []
        for c in a.get("channels", []):
            idx = c.get("target", {}).get("node")
            nm = nodes[idx].get("name") if idx is not None and idx < len(nodes) else None
            chans.append(nm)
        out[a.get("name")] = chans
    return out, js


def clip_ground_audit(objs, rest_loc):
    """逐片段检查动画过程中**脚底有没有插进地面**。

    站立姿势的 min z 必须是 0（脚底贴地）；动画里允许一点点穿模
    （高速动作里没人看得出来），但超过 3 cm 就说明姿势角度配错了。
    """
    worst = {}
    for name, keys, _frames in CLIPS:
        posed, _all = resolve_poses(keys)
        lo = 1e9
        for fr in sorted(posed[RIG_NAMES[0]]):
            rot = {nm: posed[nm][fr][0] for nm in posed}
            loc = {nm: posed[nm][fr][1] for nm in posed}
            apply_pose(objs, rest_loc, rot, loc)
            bpy.context.view_layer.update()
            for ob in objs.values():
                if ob.type != 'MESH':
                    continue
                for v in ob.data.vertices:
                    z = (ob.matrix_world @ v.co).z
                    if z < lo:
                        lo = z
        worst[name] = lo
    restore_rest(objs, rest_loc, {nm: tuple(objs[nm].rotation_euler) for nm in objs})
    return worst


def self_check(objs, rest_loc, rest_rot_map, glb, blend):
    scene = bpy.context.scene
    meshes = [o for o in objs.values() if o.type == 'MESH']
    allv = [o.matrix_world @ v.co for o in meshes for v in o.data.vertices]
    xs = [v.x for v in allv]
    ys = [v.y for v in allv]
    zs = [v.z for v in allv]
    print("=" * 66)
    print("%s  objects=%d  verts=%d  polys=%d"
          % (NAME, len(meshes), sum(len(o.data.vertices) for o in meshes),
             sum(len(o.data.polygons) for o in meshes)))
    print("BBOX  X %.3f  Y %.3f  Z %.3f..%.3f m   (站立全高 %.3f m)"
          % (max(xs) - min(xs), max(ys) - min(ys), min(zs), max(zs), max(zs)))
    assert abs(min(zs)) < 0.02, "脚底必须落在 z=0（min z=%.4f）" % min(zs)
    for o in meshes:
        for v in o.scale:
            assert abs(v - 1.0) < 1e-4, "%s 的 scale 不是 1" % o.name
        for i in range(3):
            assert abs(o.rotation_euler[i] - rest_rot_map[o.name][i]) < 1e-6, \
                "%s 的静止姿态应等于 REST_ROT" % o.name

    # 动画过程中的地面穿透
    worst = clip_ground_audit(objs, rest_loc)
    print("GLB   各片段动画最低点 (m, 应 ≈ 0):")
    for name, _keys, _fr in CLIPS:
        print("      %-18s %+.3f" % (name, worst[name]))
        assert worst[name] > -0.03, "%s 动画里脚底插进地面 %.3f m" % (name, -worst[name])

    # 动画片段必须真的写进 .glb
    anims, js = glb_report(glb)
    print("GLB   动画片段:")
    for name, _keys, _fr in CLIPS:
        chans = anims.get(name)
        assert chans, ".glb 里缺少动画 %s（实际：%s）" % (name, sorted(anims))
        print("      %-18s 通道 %d 条 → %d 个节点" % (name, len(chans), len(set(chans))))
    extra = sorted(set(anims) - set(n for n, _, _ in CLIPS))
    assert not extra, ".glb 里多出没预期的动画：%s" % extra

    # 导出节点里不能有非 1 的 scale（assets/AGENTS.md §6.7）
    bad = [(n.get("name"), n.get("scale")) for n in js.get("nodes", [])
           if n.get("scale") and any(abs(v - 1.0) > 1e-4 for v in n["scale"])]
    print("GLB   非 1 缩放节点：", bad if bad else "none")
    assert not bad, "导出节点里混进了非 1 的缩放：%s" % bad
    print("saved:", glb)
    print("saved:", blend)


# ==========================================================================
# MAIN
# ==========================================================================
def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    do_render = "--nopreview" not in argv

    clear_scene()
    # clear_scene 只清"没人用"的 action；我们上一轮建的 action 带 fake user，
    # 会留下来 → 新建的同名 action 会被 Blender 加后缀（Monkey_Run.001），
    # 于是 .glb 里的片段名就不叫 Monkey_Run 了。这里**全清**。
    for a in list(bpy.data.actions):
        bpy.data.actions.remove(a)
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1.0
    scene.render.fps = FPS
    scene.frame_start = 0
    scene.frame_end = TREMBLE_FRAMES

    mats = make_materials()
    objs = build_monkey(mats)

    rest_loc = {nm: tuple(objs[nm].location) for nm in objs}
    rest_rot_map = {nm: tuple(objs[nm].rotation_euler) for nm in objs}

    clip_slots = {}
    for name, keys, _frames in CLIPS:
        act, slots = bake_clip(name, keys, objs, rest_loc)
        clip_slots[name] = slots
    # 静音所有 track → .blend 打开、Godot 里还没播动画时，猴子是静止站姿。
    mute_tracks(objs, True)
    restore_rest(objs, rest_loc, rest_rot_map)
    scene.frame_set(0)

    # ---- 导出（先导出，再搭预览台，避免地面/灯光混进 glb）----
    glb = os.path.join(OUT_DIR, NAME + ".glb")
    bpy.ops.export_scene.gltf(
        filepath=glb, export_format='GLB', use_selection=False,
        export_apply=False, export_yup=True,
        export_normals=True,
        export_vertex_color='MATERIAL',
        export_animations=True, export_animation_mode='ACTIONS',
        export_force_sampling=False,
        export_optimize_animation_size=False)

    if do_render:
        render_preview(objs, rest_loc, rest_rot_map)

    blend = os.path.join(OUT_DIR, NAME + ".blend")
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=blend)

    self_check(objs, rest_loc, rest_rot_map, glb, blend)


if __name__ == "__main__":
    main()

# Blender 建模脚本：侏罗纪公园入口大门（年久失修 / 破败风，low-poly）
#
# 用法:
#   /Applications/Blender.app/Contents/MacOS/Blender --background --python low_poly_jurassic_gate.py
#   ... --python low_poly_jurassic_gate.py -- --nopreview     # 只出 glb/blend，不渲染
#   ... --python low_poly_jurassic_gate.py -- --seed 7        # 换一套破败随机
#
# 产物（写入本目录）:
#   low_poly_jurassic_gate.blend / .glb / _preview.png
#
# ---------------------------------------------------------------------------
# 结构（全部按米建模，+Z 向上，地面 z = 0，原点 = 门洞中线 × 地面）
# ---------------------------------------------------------------------------
#   GateRoot                 ← 空物体，原点 = 门洞地面中线
#     ├─ ArchStone           拱 + 两侧墩（一块整网格）
#     ├─ SignBoard           "dinosaur" 招牌匾额（拱上，前倾 + 缺角）
#     ├─ Wall_L / Wall_R     左右各一段破败矮墙（墙身 + 压顶 + 崩塌缺口）
#     ├─ Ivy                 藤蔓 / 苔藓块 / 墙脚杂草
#     ├─ Shrubs              墙头长出来的小树
#     ├─ Gate_Door_L         ← 枢轴在左门轴；门扇网格朝 +X（即朝门洞中心）
#     └─ Gate_Door_R         ← 枢轴在右门轴；门扇网格朝 −X
#
# 两扇门是**独立节点**，网格都在自己坐标系里朝门洞中心伸出（左 +X / 右 −X），
# 所以开合 = 本地绕 Z 旋转：左门 −θ、右门 **+θ**（镜像网格 → 转角必须反号），
# 两扇都朝 −Y（门外）摆出去。符号写错会变成两扇门朝同一侧"推倒"。
#
# ---------------------------------------------------------------------------
# 动画（内置，随 glb 导出，Godot 里 AnimationPlayer 直接播）
# ---------------------------------------------------------------------------
#   Gate_Open   0.00s 合(0°)  → 0.40s 开(±88°) → 保持到 1.20s   双门朝门外开
#   Gate_Close  0.00s 开(±88°) → 0.40s 合(0°)   → 保持到 1.20s
# 两段都是 36 帧 = 1.2 s @30fps（12 帧行程 + 24 帧保持），所以
# 播 Gate_Open 会在 0.4 s 开完，剩余时间是静止保持，不会"播完又转回去"。
#
# ---------------------------------------------------------------------------
# 颜色（顶点色 COLOR_0，线性空间，4 个材质槽：石 / 木 / 铁 / 植物）
# ---------------------------------------------------------------------------
# 与 low_poly_rock.py 同一套：**按棱面（共面片）上色**，一个平面 = 一块颜色；
# 按三角面上色会让面内碎切渲染成脏斑、棱线糊成一团（assets/AGENTS.md §6.9）。
# 破败感靠三件事，都不靠贴图：
#   1) 形体：逐块砖 / 逐块石决定存废 → 崩塌缺口、残墙、缺角、门板豁口、残缺瓦顶
#   2) 分色：整块棱面变色 —— 苔藓、锈斑、泛白的旧补丁
#   3) 分层：墙身上浅下深、门板低处翻出暗锈、招牌字底挖深
import math
import os
import random
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Vector

# 公共废墟构件库（矮墙的唯一实现）。大门两翼的矮墙和独立破墙模型共用它，
# 这样两者的基座 / 错缝 / 压顶剖面天然一致，拼在一起才不会有台阶。
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "_shared"))
from ruin_kit import (  # noqa: E402
    BOX_FACES, PAL, COPING_H_M, COPING_OUT_M, MeshBuilder, PLINTH_M, PLINTH_OUT_M,
    WALL_BAY_M, WALL_H_M, WALL_ROWS, WALL_T_M,
    box, build_wall_segment, clear_scene, extrude_y, hash01, lerp3,
    make_materials as _make_materials, shade,
)

# ==========================================================================
# CONFIG —— 所有尺寸单位都是米
# ==========================================================================
OUT_DIR = os.path.dirname(os.path.abspath(__file__))
NAME = "low_poly_jurassic_gate"
SEED = 20260715

# --- 总体 ------------------------------------------------------------------
# 墙体尺寸（WALL_T_M / WALL_H_M / PLINTH_M / PLINTH_OUT_M / WALL_ROWS /
# COPING_H_M / COPING_OUT_M / WALL_BAY_M）由 _shared/ruin_kit.py 统一提供，
# 大门两翼和独立破墙模型共用同一份，这里**不要再写第二遍**（见文件头 import 段）。
BASE_W_M = 2.15          # 两侧墩 / 墙身半宽（X）
OPEN_W_M = 1.60          # 门洞半宽（X）→ 门洞净宽 3.20 m
CLEAR_H_M = 2.95         # 门洞直墙段高度（拱起脚点 Z）
ARCH_R_M = OPEN_W_M      # 拱半径 = 门洞半宽 → 半圆拱，拱顶 4.55 m
ARCH_H_M = CLEAR_H_M + ARCH_R_M
ARCH_RINGS = 6           # 拱券环数（low-poly：环少才有块面感）
# 拱券径向厚度 **由几何定死**：外缘正好落在墩子外侧面，于是"拱脚 → 墩身"
# 是一条连续的直边，不会在起脚处鼓出一个错台（之前的 0.62 > 0.55 就是这个问题）。
ARCH_BAND_M = 2.15 - 1.60   # = BASE_W_M − OPEN_W_M = 0.55
HAUNCH_ROW_H_M = 0.30
SPANDREL_TOP_M = 0.0     # 由 derive_sign_height() 按拱顶算出，勿手填
WING_M = 2.90            # 墙从墩子往外延伸长度
PIER_SEGS = 4            # 墩身分层石砌数

# --- 招牌 ------------------------------------------------------------------
# 匾额坐在拱券之上的实墙顶（不是塞在拱洞里），所以拱顶恒为 4.55 m —— 不再让"门楣牌"
# 之类的构件和它抢同一段高度。
#
# 文字是英文 "dinosaur"（8 个字母，w/h ≈ 5.8，比 3 个方块字宽得多），
# 所以匾额从 3.40 加宽到 4.20 m —— 正好卡在拱肩实墙宽度（2×BASE_W_M = 4.30）之内。
SIGN_TEXT = "dinosaur"
SIGN_FONT = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
SIGN_SIZE_M = 0.78
SIGN_EMBOSS_M = 0.020    # 字面相对匾额正面再凸出的高度（凸字比凹刻读得清）
SIGN_BOARD_W_M = 4.20
SIGN_BOARD_H_M = 0.95
SIGN_BOARD_T_M = 0.40
SIGN_TILT_DEG = -5.0     # 前倾（松垮感）
SIGN_Y_OFF_M = -0.50     # 匾额贴面深度（正面朝外凸出拱券正面）
SIGN_LAP_M = 0.17        # 匾额下沿压在拱冠上的搭接量（不留悬空缝）
SIGN_Z_M = 0.0           # 由 derive_sign_height() 按拱顶算出，勿手填

# 拱券外形复核（招牌高度全靠这里推）：
#   拱内顶 = CLEAR_H_M + OPEN_W_M               = 4.55 m
#   拱外顶 = CLEAR_H_M + OPEN_W_M + ARCH_BAND_M = 5.17 m
# 招牌坐在拱冠上、下沿压进拱冠 0.17 m，两端各垫一块牛腿顶到拱背 ——
# 于是"招牌架在拱上"是几何上真的搭着，不是飘着。总高 ≈ 6.06 m。

# --- 门扇 ------------------------------------------------------------------
DOOR_HINGE_X_M = 1.62    # 门轴 |X|
DOOR_LEAF_W_M = 1.56     # 门扇宽（朝门洞中心伸出）→ 合拢中缝 0.12 m
DOOR_H_M = 2.85          # 门扇高
DOOR_FRAME_M = 0.11      # 边框 / 横档宽
DOOR_T_M = 0.09          # 门扇厚
DOOR_RAIL_N = 2          # 中横档数
PICKET_STEP_M = 0.245    # 铁栅间距
PICKET_W_M = 0.075       # 铁栅宽
HINGE_PIN_M = 0.13       # 门轴柱半径

# --- 破败 / 植被 ------------------------------------------------------------
IVY_STRANDS = 10
IVY_SEGS = 9
GRASS_TUFTS = 30
MOSS_PATCHES = 16

FPS = 30
FR_OPEN = 12             # 开 / 关行程帧数（12 帧 @30fps = 0.4 s）
FR_HOLD = 24             # 保持帧数（0.8 s）→ 片段总长 36 帧 = 1.2 s

# ==========================================================================
# 1) 墩 + 拱（ArchStone）
# ==========================================================================
def build_arch(b, rng):
    S = b.slot("Stone")
    y0, y1 = -WALL_T_M * 0.5, WALL_T_M * 0.5
    x_in, x_out = OPEN_W_M, BASE_W_M

    # 墩脚基座
    for sx in (-1, 1):
        xa, xb = sorted((sx * x_in, sx * x_out))
        box(b, xa - PLINTH_OUT_M, xb + PLINTH_OUT_M, y0 - PLINTH_OUT_M, y1 + PLINTH_OUT_M,
            0.0, PLINTH_M, S, {"top": shade(PAL["stone_m"], 0.45),
                               "side": shade(PAL["stone_d"], 0.5),
                               "bottom": PAL["stone_x"]})

    # 墩身：PIER_SEGS 层石砌，最上一层（贴拱肩）可能崩塌
    seg_h = (CLEAR_H_M - PLINTH_M) / PIER_SEGS
    for sx in (-1, 1):
        for k in range(PIER_SEGS):
            z0 = PLINTH_M + k * seg_h
            z1 = z0 + seg_h
            if k == PIER_SEGS - 1 and rng.random() < 0.5:
                z1 -= seg_h * rng.uniform(0.30, 0.62)
                if z1 <= z0 + 0.05:
                    continue
            t = k / (PIER_SEGS - 1.0)
            xi = sx * (x_in + 0.05 * t)
            xo = sx * (x_out - 0.05 * t)
            xa, xb = sorted((xi, xo))
            c = lerp3(PAL["stone_d"], PAL["stone_m"], 0.20 + 0.55 * t)
            if rng.random() < 0.30:
                c = lerp3(c, PAL["stone_x"], 0.45)
            if rng.random() < 0.16:
                c = lerp3(c, PAL["moss_m"], 0.55)
            box(b, xa, xb, y0, y1, z0, z1, S, shade(c, hash01(sx, k, 3)))
            if k > 0:                                   # 石缝
                box(b, xa, xb, y0 - 0.012, y1 + 0.012, z0 - 0.02, z0, S, PAL["stone_x"])

    # 拱券：ARCH_RINGS 块楔形石。外缘 = 墩子外侧面（同宽），所以拱与墩是**一条连续
    # 的直边**；厚度方向也给足（y 向外挑 0.08），让"拱券"作为一层凸出来。
    r_in, r_out = OPEN_W_M, BASE_W_M
    z_c = CLEAR_H_M
    angs = [math.pi * i / ARCH_RINGS for i in range(ARCH_RINGS + 1)]
    for i in range(ARCH_RINGS):
        a0, a1 = angs[i], angs[i + 1]
        if 0 < i < ARCH_RINGS and rng.random() < 0.06:      # 崩掉一块环石
            continue
        pts = []
        steps = 3
        for s in range(steps + 1):
            a = a0 + (a1 - a0) * s / steps
            pts.append((math.cos(a) * r_in, math.sin(a) * r_in + z_c))
        for s in range(steps, -1, -1):
            a = a0 + (a1 - a0) * s / steps
            pts.append((math.cos(a) * r_out, math.sin(a) * r_out + z_c))
        # 亮度沿拱"由脚到顶"渐亮：单一灰度递变，一眼就是一个整体
        c = lerp3(PAL["stone_d"], PAL["stone_l"], 0.15 + 0.75 * i / (ARCH_RINGS - 1.0))
        if rng.random() < 0.22:
            c = lerp3(c, PAL["moss_m"], 0.40)
        cf = (lambda col: (lambda pts_: shade(col, hash01(round(pts_[0].z, 3), 11))))(c)
        extrude_y(b, y0 - 0.08, y1 + 0.08, pts, S, cf)

    # 拱肩实墙 + 横梁墙：拱脚到拱顶之间把"拱背 → 墩子外侧面"的三角区填实，
    # 拱顶以上到实墙顶（SPANDREL_TOP_M）再砌一段**贯通的横梁墙**，
    # 招牌压在横梁墙上。缺石概率整体压低：这里要的是"实墙带洞"，
    # 不是"一面筛子"——破败感交给墙头、压顶、苔藓和缺口去表达。
    for sx in (-1, 1):
        # (a) 拱脚 → 拱顶：三角区填充
        n_row = max(1, int(round(BASE_W_M / HAUNCH_ROW_H_M)))
        for row in range(n_row):
            z0 = CLEAR_H_M + row * HAUNCH_ROW_H_M
            z1 = min(z0 + HAUNCH_ROW_H_M, CLEAR_H_M + BASE_W_M)
            if z1 - z0 < 0.05:
                break
            xa_ = arch_x_at_z(z0) + 0.02             # 从拱背往外砌
            xb_ = BASE_W_M
            if xb_ - xa_ < 0.06:
                continue
            n = max(1, int(round((xb_ - xa_) / 0.32)))
            for i in range(n):
                cx0 = xa_ + (xb_ - xa_) * i / n
                cx1 = xa_ + (xb_ - xa_) * (i + 1) / n
                if rng.random() < 0.05:               # 偶尔缺一块，透光
                    continue
                box(b, min(sx * cx0, sx * cx1), max(sx * cx0, sx * cx1),
                    y0, y1, z0, z1, S,
                    shade(lerp3(PAL["stone_m"], PAL["stone_d"], 0.2 + 0.45 * rng.random()),
                          hash01(sx, row, i, 5)))

    # (b) 拱顶 → 实墙顶：贯通横梁墙（两级错缝，看得出是砌起来的）
    band_h = SPANDREL_TOP_M - (CLEAR_H_M + BASE_W_M)
    for row in range(2):
        z0 = CLEAR_H_M + BASE_W_M + row * band_h / 2.0
        z1 = z0 + band_h / 2.0
        if z1 - z0 < 0.04:
            continue
        n = 6
        off = 0.0 if row % 2 == 0 else (2 * BASE_W_M / n) * 0.5
        for i in range(-1, n + 1):
            cx0 = -BASE_W_M + i * (2 * BASE_W_M) / n + off
            cx1 = cx0 + (2 * BASE_W_M) / n
            cx0c, cx1c = max(cx0, -BASE_W_M), min(cx1, BASE_W_M)
            if cx1c - cx0c < 0.05:
                continue
            c = lerp3(PAL["stone_m"], PAL["stone_d"], 0.15 + 0.5 * rng.random())
            if rng.random() < 0.26:
                c = lerp3(c, PAL["moss_m"], 0.45)
            box(b, cx0c, cx1c, y0, y1, z0, z1, S, shade(c, hash01(row, i, 8)))


def arch_x_at_z(z):
    """拱背（半径 BASE_W_M）在高度 z 处的 |x|；z 超出拱顶则返回 0。"""
    z_c = CLEAR_H_M
    if z >= z_c + BASE_W_M:
        return 0.0
    if z <= z_c:
        return BASE_W_M
    return math.sqrt(max(0.0, BASE_W_M ** 2 - (z - z_c) ** 2))


# ==========================================================================
# 2) 左右破败矮墙（Wall_L / Wall_R）
# ==========================================================================
def build_wall(b, rng, side):
    """大门一侧的破败矮墙 —— 几何全部交给 _shared/ruin_kit.build_wall_segment()。

    接缝端是**朝外那一端**（远离拱门）：基座不外扩、压顶必留一片、墙头强制满高。
    于是独立破墙模型可以一路往外怼着加长，接缝处不会出现台阶或洞 ——
    这正是"拼接加长过渡要自然"的落点。

    靠拱门那一端不接受接缝（被拱墩堵住），所以 decay_end 指向拱门一侧：
    越贴近拱墩越残破，远离大门的方向反而保持较高 —— 视线顺着墙往外看是"还在"，
    回头看门是"已经塌了"，两种观感都比通篇均匀残破有层次。
    """
    xa, xb = sorted((side * BASE_W_M, side * (BASE_W_M + WING_M)))
    # side=-1：xa=-5.05（外） xb=-2.15（拱门）
    # side=+1：xa=+2.15（拱门） xb=+5.05（外）
    joint_end = "start" if side < 0 else "end"
    return build_wall_segment(
        b, rng, xa, xb,
        tag=side, joint_ends=(joint_end,),
        decay=0.16, decay_slope=0.45, moss=0.20,
        decay_end="end" if side < 0 else "start",
    )



# ==========================================================================
# 3) 招牌（SignBoard）
#   "dinosaur" 是**凸字**（不是凹刻的阴文）：匾额正面压暗成槽底，
#   字面再往外凸 20 mm，于是光从上方斜打时字的下缘永远挂一条阴影缝 ——
#   低多边形、无贴图的情况下，这一串字母也必须一眼认得出。
# ==========================================================================
def derive_sign_height():
    """招牌坐在拱肩实墙顶上：先定实墙顶，再让匾额下沿搭上去 SIGN_LAP_M。"""
    global SIGN_Z_M, SPANDREL_TOP_M
    arch_top = CLEAR_H_M + BASE_W_M              # 拱背顶点（= 半圆拱外顶）
    # 实墙顶比拱背顶点再高出一截，招牌才有地方坐
    SPANDREL_TOP_M = arch_top + 0.34
    SIGN_Z_M = SPANDREL_TOP_M - SIGN_LAP_M + SIGN_BOARD_H_M * 0.5
    return arch_top


def sign_parts():
    """招牌 / 托梁 / 斜撑共用的坐标（保证它们真的互相搭着，不是各写各的）。"""
    hw, hh = SIGN_BOARD_W_M * 0.5, SIGN_BOARD_H_M * 0.5
    tilt = math.radians(SIGN_TILT_DEG)
    y_slot = -SIGN_BOARD_T_M * 0.5
    y_back = SIGN_BOARD_T_M * 0.5

    def place(x, y, z):
        """匾额局部坐标 → 前倾 → 抬到 SIGN_Z_M 的世界坐标（面朝 −Y）。"""
        y2 = y * math.cos(tilt) - z * math.sin(tilt)
        z2 = y * math.sin(tilt) + z * math.cos(tilt)
        return (x, y2 + SIGN_Y_OFF_M, z2 + SIGN_Z_M)

    return hw, hh, y_slot, y_back, place


def build_sign(b, rng):
    S = b.slot("Wood")
    hw, hh, y_slot, y_back, place = sign_parts()
    arch_top = CLEAR_H_M + OPEN_W_M + ARCH_BAND_M

    # ---- 匾额本体：右端缺角（年久失修）----
    z_hi_r = hh - 0.10
    outline = [(-hw, 0, -hh), (hw, 0, -hh), (hw, 0, z_hi_r),
               (hw * 0.55, 0, hh), (-hw, 0, hh)]
    n = len(outline)
    base = len(b.verts)
    b.verts.extend(place(x, y_slot, z) for (x, _, z) in outline)
    b.verts.extend(place(x, y_back, z) for (x, _, z) in outline)
    # 正面：整片是"槽底"，所以压暗 → 凸出来的字才会亮出来
    b.faces.append((tuple(range(base, base + n)), S, lerp3(PAL["stone_x"], PAL["wood_d"], 0.5)))
    b.faces.append((tuple(range(base + n, base + 2 * n)), S, PAL["wood_d"]))
    for i in range(n):
        j = (i + 1) % n
        b.faces.append(((base + i, base + j, base + n + j, base + n + i), S,
                        shade(PAL["wood_m"], hash01(i, 4))))

    # ---- 匾额底托：横贯实墙顶的一条厚木，把招牌"托"住（也是实墙的压顶）----
    ledge_z0 = SPANDREL_TOP_M - 0.12
    ledge_z1 = SPANDREL_TOP_M + 0.06
    box(b, -BASE_W_M - 0.04, BASE_W_M + 0.04,
        SIGN_Y_OFF_M - 0.30, SIGN_Y_OFF_M + 0.22,
        ledge_z0, ledge_z1, S,
        {"top": shade(PAL["wood_d"], 0.5), "side": shade(PAL["wood_d"], 0.3),
         "bottom": PAL["stone_x"]})

    # ---- 牛腿：两端各一小段斜木，从实墙顶斜撑到匾额下沿 ----
    sign_bottom = SIGN_Z_M - hh
    for sx in (-1, 1):
        for k in range(3):
            t0, t1 = k / 3.0, (k + 1) / 3.0
            x0 = hw * 0.52 + (hw * 0.92 - hw * 0.52) * t0
            x1 = hw * 0.52 + (hw * 0.92 - hw * 0.52) * t1
            z0 = ledge_z1 + (sign_bottom - ledge_z1) * t0
            z1 = ledge_z1 + (sign_bottom - ledge_z1) * t1
            box(b, min(sx * x0, sx * x1) - 0.09, max(sx * x0, sx * x1) + 0.09,
                SIGN_Y_OFF_M - 0.26, SIGN_Y_OFF_M + 0.18,
                min(z0, z1) - 0.04, max(z0, z1) + 0.04, S,
                shade(PAL["wood_d"], hash01(sx, k, 13)))

    # ---- "dinosaur" 凸字：字面从槽底向外凸 SIGN_EMBOSS_M ----
    tverts, tfaces, ok = text_mesh()
    if not ok:
        return
    txs = [v[0] for v in tverts]
    tys = [v[1] for v in tverts]
    tzs = [v[2] for v in tverts]
    word_w = max(txs) - min(txs)          # 文本局部 X = 字宽
    word_h = max(tys) - min(tys)          # 文本局部 Y = 字高（文本躺在 XY 平面）
    depth = max(tzs) - min(tzs)           # 文本局部 Z = 挤出厚度
    scale = min((SIGN_BOARD_W_M - 0.30) / max(1e-6, word_w),
                (SIGN_BOARD_H_M - 0.24) / max(1e-6, word_h))

    # 字形要"立"起来面朝 −Y：文本局部 (x, y, z) → 匾额局部 (x, −z, y)。
    # 这是一个纯旋转（行列式 +1，不镜像），所以字母从左到右读是对的。
    # 字的 +Z 面（法线 → −Y，正对观众）落在最前面：
    #   字面 y = y_slot − SIGN_EMBOSS_M（比匾额正面再凸出 20 mm，边角自然挂阴影）
    #   字背 y = 字面 + depth*scale（埋进匾额里，不留缝）
    y_face_glyph = y_slot - SIGN_EMBOSS_M
    z_front = max(tzs)

    def place_glyph(v):
        return place(v[0] * scale,
                     y_face_glyph + (z_front - v[2]) * scale,
                     v[1] * scale)

    base_i = len(b.verts)
    b.verts.extend(place_glyph(v) for v in tverts)
    for f in tfaces:
        pts = [Vector(tverts[i]) for i in f]
        nrm = (pts[1] - pts[0]).cross(pts[2] - pts[0])
        if nrm.length < 1e-9:
            continue
        nrm.normalize()
        if nrm.z > 0.3:
            # 字面（法线 +Z → 转换后 −Y）：整块亮石色，远看就是白字
            col = lerp3(PAL["stone_l"], PAL["moss_m"], 0.18 * hash01(pts[0].x * 9, pts[0].y * 9))
        elif abs(nrm.z) < 0.3:
            col = shade(PAL["stone_d"], hash01(pts[0].x * 5, pts[0].y * 5))   # 侧壁 → 字厚
        else:
            col = PAL["stone_x"]                                              # 背面（看不见）
        b.faces.append((tuple(base_i + i for i in f), S, col))
    print("SIGN  「%s」verts=%d polys=%d 字宽=%.2f 字高=%.2f 厚=%.3f 缩放=%.3f "
          "匾额中心 z=%.2f 总高=%.2f"
          % (SIGN_TEXT, len(tverts), len(tfaces), word_w, word_h, depth, scale,
             SIGN_Z_M, SIGN_Z_M + SIGN_BOARD_H_M * 0.5))


def arch_extrados_z(x_abs):
    """拱背（外缘，半径 r_out）在 |x| 处的高度；超出拱脚则落到墩顶。"""
    r_out = OPEN_W_M + ARCH_BAND_M
    x = min(abs(x_abs), r_out)
    return CLEAR_H_M + math.sqrt(max(0.0, r_out * r_out - x * x))


def text_mesh():
    """招牌文本 → 低多边形网格（返回 顶点, 面, 是否成功）。"""
    try:
        font = bpy.data.fonts.load(SIGN_FONT)
    except Exception as exc:
        print("WARN  中文字体加载失败(%s)，改用默认字体（可能缺字形）" % exc)
        font = None
    bpy.ops.object.text_add()
    tob = bpy.context.active_object
    tb = tob.data
    if font is not None:
        tb.font = font
    tb.body = SIGN_TEXT
    tb.align_x = 'CENTER'
    tb.align_y = 'CENTER'
    tb.size = SIGN_SIZE_M
    tb.extrude = 0.05
    tb.resolution_u = 1
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(tob.evaluated_get(dg))
    bpy.data.objects.remove(tob, do_unlink=True)
    if len(me.vertices) == 0:
        bpy.data.meshes.remove(me)
        return [], [], False
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(2.0),
                             verts=bm.verts[:], edges=bm.edges[:])
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    bm.verts.ensure_lookup_table()
    verts = [tuple(v.co) for v in bm.verts]
    faces = [tuple(v.index for v in f.verts) for f in bm.faces]
    bm.free()
    bpy.data.meshes.remove(me)
    return verts, faces, True


# ==========================================================================
# 4) 铁门（每扇独立对象，枢轴在门轴）
# ==========================================================================
def door_geometry(rng):
    """一扇门的几何。只按"左门"写一次：枢轴在原点、门扇朝 **+X** 伸出。

    右门由调用方 mirror_x() 得到 —— 这样两扇的锈迹、断栅、斜撑位置**完全对称**，
    不会出现"两扇门各随机一遍、看着像两种门"的问题。
    """
    b = MeshBuilder()
    I = b.slot("Iron")
    y0, y1 = -DOOR_T_M * 0.5, DOOR_T_M * 0.5
    fr = DOOR_FRAME_M

    def rust(k, hue):
        c = lerp3(PAL["iron_m"], PAL["rust"], k)
        if hue < 0.30:
            c = lerp3(c, PAL["rust_d"], 0.45 * (1.0 - hue / 0.30))
        elif hue > 0.78:
            c = lerp3(c, PAL["rust_l"], 0.32)
        return shade(c, hash01(k * 7.1, hue * 3.3))

    # 门轴柱 + 上下铰链（轴柱在 |X| 处，两个铰链让它"确实是转轴"）
    box(b, -HINGE_PIN_M, 0.0, -HINGE_PIN_M, HINGE_PIN_M, 0.0, DOOR_H_M + 0.14, I,
        shade(PAL["rust_d"], 0.4))
    for zz in (0.30, DOOR_H_M - 0.30):
        box(b, -HINGE_PIN_M - 0.035, 0.035, -HINGE_PIN_M - 0.035, HINGE_PIN_M + 0.035,
            zz - 0.075, zz + 0.075, I, shade(PAL["rust"], hash01(zz, 1)))

    # 边框
    box(b, 0.0, fr, y0, y1, 0.0, DOOR_H_M, I, rust(0.55, 0.50))
    box(b, DOOR_LEAF_W_M - fr, DOOR_LEAF_W_M, y0, y1, 0.0, DOOR_H_M, I, rust(0.60, 0.42))
    box(b, fr, DOOR_LEAF_W_M - fr, y0, y1, DOOR_H_M - fr, DOOR_H_M, I, rust(0.50, 0.95))
    box(b, fr, DOOR_LEAF_W_M - fr, y0, y1, 0.0, fr, I, rust(0.72, 0.05))

    # 中横档
    for i in range(DOOR_RAIL_N):
        t = (i + 1) / (DOOR_RAIL_N + 1)
        z = DOOR_H_M * t
        hh = fr * 0.7
        box(b, fr, DOOR_LEAF_W_M - fr, y0 - 0.012, y1 + 0.012, z - hh, z + hh, I,
            rust(0.42 + 0.34 * rng.random(), t))

    # 铁栅：逐根，部分断裂 / 歪斜
    n = max(2, int((DOOR_LEAF_W_M - 2 * fr) / PICKET_STEP_M))
    step = (DOOR_LEAF_W_M - 2 * fr) / n
    for i in range(1, n):
        x = fr + i * step
        if rng.random() < 0.12:
            continue
        lean = rng.uniform(-0.045, 0.045) if rng.random() < 0.35 else 0.0
        z_top = DOOR_H_M - fr - 0.02
        c = rust(0.35 + 0.55 * rng.random(), (i % 3) / 3.0)
        v = [(x - PICKET_W_M * 0.5, y0, fr), (x + PICKET_W_M * 0.5, y0, fr),
             (x + PICKET_W_M * 0.40, y0, z_top), (x - PICKET_W_M * 0.40, y0, z_top),
             (x - PICKET_W_M * 0.5, y1, fr), (x + PICKET_W_M * 0.5, y1, fr),
             (x + PICKET_W_M * 0.40, y1, z_top), (x - PICKET_W_M * 0.40, y1, z_top)]
        for idx in BOX_FACES:
            b.add([v[i] for i in idx], I, c, (lean, 0.0, 0.0)) if False else b.add(
                [(v[i][0] + lean, v[i][1], v[i][2]) for i in idx], I, c)

    # 门板豁口：右下角缺一块板，露出深色断面
    box(b, DOOR_LEAF_W_M - fr - 0.36, DOOR_LEAF_W_M - fr, y0 - 0.006, y1 + 0.006,
        fr + 0.14, fr + 0.40, I, PAL["rust_d"])
    return b


# ==========================================================================
# 5) 植被 / 破败细节
# ==========================================================================
def build_ivy(b, rng):
    P = b.slot("Plant")
    # 墙上垂下的藤蔓（每节一块斜置的叶片四边形）
    for k in range(IVY_STRANDS):
        side = -1 if k % 2 == 0 else 1
        x = side * rng.uniform(BASE_W_M + 0.2, BASE_W_M + WING_M * 0.95)
        y = rng.choice([-WALL_T_M * 0.5 - 0.05, WALL_T_M * 0.5 + 0.05])
        z_top = rng.uniform(WALL_H_M * 0.70, WALL_H_M)
        z_bot = rng.uniform(0.25, max(0.3, z_top - 0.5))
        for i in range(IVY_SEGS):
            t = i / (IVY_SEGS - 1.0)
            zz = z_top + (z_bot - z_top) * t
            xx = x + math.sin(t * 5.0 + k) * 0.12
            w = 0.13 * (1.0 - 0.7 * t)
            c = lerp3(PAL["leaf_d"], PAL["leaf_m"], 0.3 + 0.5 * rng.random())
            if rng.random() < 0.25:
                c = lerp3(c, PAL["moss_d"], 0.4)
            leaf = [(xx - w, y - w * 0.5, zz), (xx + w, y - w * 0.5, zz),
                    (xx + w * 0.6, y + w * 0.5, zz + 0.11),
                    (xx - w * 0.6, y + w * 0.5, zz + 0.11)]
            b.add(leaf, P, shade(c, hash01(xx, zz, 3)))

    # 苔藓块：整块贴在墙面 / 拱面上（一个平面一块色）
    for k in range(MOSS_PATCHES):
        if rng.random() < 0.4:
            a = math.radians(rng.uniform(20, 160))
            r = OPEN_W_M + ARCH_BAND_M * rng.uniform(0.15, 0.95)
            x = math.cos(a) * r
            z = math.sin(a) * r + CLEAR_H_M
        else:
            side = -1 if rng.random() < 0.5 else 1
            x = side * rng.uniform(BASE_W_M + 0.1, BASE_W_M + WING_M * 0.9)
            z = rng.uniform(PLINTH_M, WALL_H_M - 0.15)
        y = rng.choice([-WALL_T_M * 0.5, WALL_T_M * 0.5])
        sgn = -0.045 if y < 0 else 0.045
        w, h = rng.uniform(0.22, 0.55), rng.uniform(0.18, 0.45)
        c = lerp3(PAL["moss_d"], PAL["moss_l"], 0.25 + 0.6 * rng.random())
        box(b, x - w * 0.5, x + w * 0.5, min(y, y + sgn), max(y, y + sgn),
            z - h * 0.5, z + h * 0.5, P, shade(c, hash01(x, z, 7)))

    # 墙脚杂草丛（每丛 3~5 片三角叶）
    for k in range(GRASS_TUFTS):
        if rng.random() < 0.3:
            x = rng.uniform(-OPEN_W_M + 0.2, OPEN_W_M - 0.2)
            y = rng.uniform(-WALL_T_M * 0.6, WALL_T_M * 0.6)
        else:
            side = -1 if rng.random() < 0.5 else 1
            x = side * rng.uniform(BASE_W_M * 0.5, BASE_W_M + WING_M)
            y = rng.uniform(-WALL_T_M * 0.7, WALL_T_M * 0.7)
        h = rng.uniform(0.16, 0.44)
        w = rng.uniform(0.10, 0.24)
        blades = rng.randint(3, 5)
        for j in range(blades):
            a = j / blades * math.pi
            dx, dy = math.cos(a) * w, math.sin(a) * w * 0.5
            tip = rng.uniform(0.5, 1.0) * h
            c = lerp3(PAL["grass_d"], PAL["grass_m"], 0.3 + 0.6 * rng.random())
            b.add([(x + dx * 0.3, y + dy, 0.0), (x - dx * 0.3, y - dy, 0.0),
                   (x + dx * 3.0, y + dy * 2.0, tip)], P,
                  shade(c, hash01(x, y, j)))


def build_shrubs(rng):
    """墙头 / 拱肩长出来的小树（树干 + 三团低多边形叶）。"""
    b = MeshBuilder()
    P = b.slot("Plant")
    spots = [(-1, -BASE_W_M + 0.35, CLEAR_H_M - 0.15, 0.95),
             (1, BASE_W_M - 0.35, CLEAR_H_M - 0.25, 1.20)]
    for sx, base_x, base_z, sc in spots:
        if rng.random() < 0.25:
            continue
        h = rng.uniform(0.9, 1.5) * sc
        box(b, base_x - 0.05, base_x + 0.05, -0.05, 0.05, base_z, base_z + h, P, PAL["bark"])
        for k in range(3):
            ang = k * 2.1 + sx
            ox = base_x + math.cos(ang) * 0.20 * sc
            oy = math.sin(ang) * 0.20 * sc
            oz = base_z + h + rng.uniform(-0.08, 0.24)
            w = rng.uniform(0.28, 0.46) * sc
            c = lerp3(PAL["leaf_d"], PAL["leaf_m"], 0.3 + 0.5 * rng.random())
            box(b, ox - w, ox + w, oy - w * 0.7, oy + w * 0.7,
                oz - w * 0.6, oz + w * 0.6, P, shade(c, hash01(ox, oy, oz)))
    return b


# ==========================================================================
# 动画
#   **一个 Action = 一个 glTF 片段，左右两扇门共用同一个 Action**（各占一个 slot），
#   于是 Godot 里 `AnimationPlayer.play("Gate_Open")` 一次就同时驱动两扇门，
#   不需要在 Godot 侧另写代码把两个片段对齐。
#
#   导出用 `export_animation_mode='NLA_TRACKS'`：每个 Action 放进一条**同名 NLA track**
#   （两扇门各一条）。实测这是唯一能稳定导出「多个片段」的方式 ——
#   `export_animation_mode='ACTIONS'` 只导出**最后赋给物体的那个 action**，
#   配 use_fake_user 也照样丢（实测 Gate_Open 整个消失）。
#
#   静止状态 = 关门：所有 NLA track 都 mute，并把两扇门摆回 0°，
#   这样 .blend 一打开、Godot 里还没播动画时，门都是"合"的。
# ==========================================================================
OPEN_DEG = 88.0          # 开门角度（略小于 90°，避免门扇完全贴到墙上）


def pose_doors(doors, angle_l, angle_r):
    """给两扇门摆姿势。

    两扇门的网格是**互相镜像**的（左门门扇朝 +X、右门朝 −X），所以要让它们
    都朝 −Y（门外）开，绕 Z 的转角必须**反号**：
        左门门扇在 +X：绕 Z 转 −θ 时 y' = x·sin(−θ) < 0 → 朝 −Y  ✓
        右门门扇在 −X：要 y' = x·sin(θ) < 0 需要 sinθ > 0 → +θ
    符号写错的话，两扇门会朝同一侧平移式地甩过去，看着像整扇门被推倒。
    """
    doors[0].rotation_euler = (0.0, 0.0, math.radians(-angle_l))
    doors[1].rotation_euler = (0.0, 0.0, math.radians(+angle_r))


def make_action(doors, name, keys):
    """建 Action（两扇门共用、各一个 slot），再给每扇门挂一条同名 NLA track。"""
    act = bpy.data.actions.new(name)
    act.use_fake_user = True
    for ob in doors:
        ad = ob.animation_data_create()
        ad.action = act
        for fr, aL, aR in keys:
            pose_doors(doors, aL, aR)
            ob.keyframe_insert("rotation_euler", index=2, frame=fr)
    for fc in act_fcurves(act):
        for kp in fc.keyframe_points:
            kp.interpolation = 'BEZIER'
        fc.update()
    # 放进 NLA（每个物体一条同名 track），然后摘掉当前 action
    for ob in doors:
        ad = ob.animation_data
        track = ad.nla_tracks.new()
        track.name = name
        strip = track.strips.new(name, 0, act)
        strip.name = name
        ad.action = None
    return act


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
    else:                                        # 旧版 API 兜底
        for fc in getattr(act, "fcurves", []):
            yield fc


def build_animations(doors):
    make_action(doors, "Gate_Open",
                [(0, 0.0, 0.0), (FR_OPEN, OPEN_DEG, OPEN_DEG),
                 (FR_OPEN + FR_HOLD, OPEN_DEG, OPEN_DEG)])
    make_action(doors, "Gate_Close",
                [(0, OPEN_DEG, OPEN_DEG), (FR_OPEN, 0.0, 0.0),
                 (FR_OPEN + FR_HOLD, 0.0, 0.0)])
    # 静止姿势：mute 掉所有 NLA track 并把门摆回 0° → 默认就是"合"
    for ob in doors:
        for track in ob.animation_data.nla_tracks:
            track.mute = True
        ob.rotation_euler = (0.0, 0.0, 0.0)
    bpy.context.scene.frame_set(0)
    for a in bpy.data.actions:
        print("ANIM  %-12s slots=%d fcurves=%d"
              % (a.name, len(getattr(a, "slots", [])), len(list(act_fcurves(a)))))


# ==========================================================================
# 预览渲染
# ==========================================================================
def setup_preview():
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
    bg.inputs[0].default_value = (0.60, 0.73, 0.86, 1.0)
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
    s = 30.0
    me.from_pydata([(-s, -s, -0.01), (s, -s, -0.01), (s, s, -0.01), (-s, s, -0.01)],
                   [], [(0, 1, 2, 3)])
    me.update()
    gm = bpy.data.materials.new("GroundPreviewMat")
    gm.use_nodes = True
    bsdf = next(n for n in gm.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    bsdf.inputs['Base Color'].default_value = (0.15, 0.23, 0.10, 1.0)
    bsdf.inputs['Roughness'].default_value = 0.95
    me.materials.append(gm)
    ground = bpy.data.objects.new("GroundPreview", me)
    scene.collection.objects.link(ground)

    cam_data = bpy.data.cameras.new("PreviewCam")
    cam_data.lens = 50.0
    cam = bpy.data.objects.new("PreviewCam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    return cam


def render_shot(cam, path, az_deg, el_deg, dist, target, res=(660, 580)):
    scene = bpy.context.scene
    scene.render.resolution_x, scene.render.resolution_y = res
    az, el = math.radians(az_deg), math.radians(el_deg)
    tgt = Vector(target)
    cam.location = tgt + Vector((math.cos(az) * math.cos(el),
                                 math.sin(az) * math.cos(el),
                                 math.sin(el))) * dist
    cam.rotation_euler = (tgt - cam.location).to_track_quat('-Z', 'Y').to_euler()
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


def stitch(paths, out_path, cols):
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


# ==========================================================================
# MAIN
# ==========================================================================
MATS = None


def activate(ob):
    for o in bpy.context.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob


def main():
    global SEED, MATS
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    do_render = "--nopreview" not in argv
    if "--seed" in argv:
        SEED = int(argv[argv.index("--seed") + 1])

    rng = random.Random(SEED)
    random.seed(SEED)
    clear_scene()
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1.0
    scene.render.fps = FPS
    scene.frame_start = 0
    scene.frame_end = FR_OPEN + FR_HOLD
    MATS = _make_materials("Gate")
    print("GEO   拱内顶=%.2f 拱背顶=%.2f 实墙顶=%.2f 招牌中心=%.2f 总高=%.2f m"
          % (CLEAR_H_M + OPEN_W_M, derive_sign_height(), SPANDREL_TOP_M, SIGN_Z_M,
             SIGN_Z_M + SIGN_BOARD_H_M * 0.5))

    ba = MeshBuilder()
    build_arch(ba, rng)
    arch_ob = ba.build("ArchStone", MATS)

    bw = MeshBuilder()
    build_wall(bw, rng, -1)
    wall_l = bw.build("Wall_L", MATS)
    bw = MeshBuilder()
    build_wall(bw, rng, 1)
    wall_r = bw.build("Wall_R", MATS)

    bs = MeshBuilder()
    build_sign(bs, rng)
    sign_ob = bs.build("SignBoard", MATS)

    bv = MeshBuilder()
    build_ivy(bv, rng)
    ivy_ob = bv.build("Ivy", MATS)
    shr = build_shrubs(rng)
    shrub_ob = shr.build("Shrubs", MATS)

    # ⚠️ 两扇门必须来自**同一次** door_geometry 求值：先按左门建一次几何，
    # 再把同一份几何镜像成右门（MeshBuilder.build() 不改自身，可以建两次）。
    # 分别调用两次 door_geometry(rng) 会因为 rng 状态继续推进而抽出两套不同的
    # 断栅 / 锈色，破掉"对称的双开门"（实测 polys 84 vs 78）。
    door_b = door_geometry(rng)
    door_l = MeshBuilder()
    door_l.verts = list(door_b.verts)
    door_l.faces = list(door_b.faces)
    door_l.slots = list(door_b.slots)
    door_l.build("Gate_Door_L", MATS)
    door_b.mirror_x()
    door_b.build("Gate_Door_R", MATS)
    doors = [bpy.data.objects["Gate_Door_L"], bpy.data.objects["Gate_Door_R"]]

    # ---- 层级 ----
    root = bpy.data.objects.new("GateRoot", None)
    root.empty_display_size = 1.0
    scene.collection.objects.link(root)
    statics = [arch_ob, wall_l, wall_r, sign_ob, ivy_ob, shrub_ob]
    for ob in statics:
        ob.parent = root
    # 左门枢轴在 −X 侧、右门在 +X 侧；两扇门扇都朝门洞中心伸出
    doors[0].location = (-DOOR_HINGE_X_M, 0.0, 0.0)
    doors[1].location = (DOOR_HINGE_X_M, 0.0, 0.0)
    for ob in doors:
        ob.rotation_mode = 'XYZ'
        ob.parent = root

    # ---- 烘焙变换：静态件 rotation/scale 归零；门扇只归 scale（保留枢轴位移）----
    for ob in statics:
        activate(ob)
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    for ob in doors:
        activate(ob)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

    build_animations(doors)

    # ---- 导出 ----
    glb = os.path.join(OUT_DIR, NAME + ".glb")
    bpy.ops.export_scene.gltf(
        filepath=glb, export_format='GLB', use_selection=False,
        export_apply=False, export_yup=True,
        export_normals=True,
        export_vertex_color='MATERIAL',
        export_animations=True, export_animation_mode='NLA_TRACKS',
        export_nla_strips=True, export_force_sampling=False,
        export_optimize_animation_size=False)

    if do_render:
        cam = setup_preview()
        shots = []
        for i, (az, el, d) in enumerate([(252, 14, 16.5), (300, 10, 16.5),
                                         (88, 7, 15.0), (268, 36, 15.5)]):
            p = "/tmp/gate_shot_%d.png" % i
            render_shot(cam, p, az, el, d, (0.0, 0.0, 2.6))
            shots.append(p)
        stitch(shots, os.path.join(OUT_DIR, NAME + "_preview.png"), 4)

        # 动画接触表：把 Gate_Open 播到 0 / 0.2 / 0.4 s，证明门内置动画真的会开。
        # 注意：平时 NLA track 是 mute 的（静止=关门），渲染前必须临时解开，
        # 只留 Gate_Open 一条，否则 frame_set 不会驱动任何东西。
        anim_shots = []
        for ob in doors:
            for tr in ob.animation_data.nla_tracks:
                tr.mute = (tr.name != "Gate_Open")
        for fr in (0, int(FR_OPEN * 0.5), FR_OPEN):
            scene.frame_set(fr)
            bpy.context.view_layer.update()
            p = "/tmp/gate_anim_%d.png" % fr
            render_shot(cam, p, 258, 15, 15.0, (0.0, 0.0, 2.6))
            anim_shots.append(p)
        stitch(anim_shots, os.path.join(OUT_DIR, NAME + "_anim.png"), 3)
        # 还原成"静止=关门"
        for ob in doors:
            for tr in ob.animation_data.nla_tracks:
                tr.mute = True
            ob.rotation_euler = (0.0, 0.0, 0.0)
        scene.frame_set(0)

    blend = os.path.join(OUT_DIR, NAME + ".blend")
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=blend)

    self_check(scene, glb, blend)


def self_check(scene, glb, blend):
    meshes = [o for o in scene.objects if o.type == 'MESH'
              and not o.name.startswith(("GroundPreview",))]
    allv = [o.matrix_world @ v.co for o in meshes for v in o.data.vertices]
    xs = [v.x for v in allv]
    ys = [v.y for v in allv]
    zs = [v.z for v in allv]
    print("=" * 62)
    print("%s  objects=%d  verts=%d  polys=%d" % (
        NAME, len(meshes), sum(len(o.data.vertices) for o in meshes),
        sum(len(o.data.polygons) for o in meshes)))
    print("BBOX  X %.3f  Y %.3f  Z %.3f..%.3f m  (min z 应≈0)"
          % (max(xs) - min(xs), max(ys) - min(ys), min(zs), max(zs)))
    for o in sorted(meshes, key=lambda o: o.name):
        print("   %-14s verts=%-5d polys=%-5d scale=%s loc=%s"
              % (o.name, len(o.data.vertices), len(o.data.polygons),
                 tuple(round(v, 4) for v in o.scale),
                 tuple(round(v, 3) for v in o.location)))
    for o in meshes:
        for v in o.scale:
            assert abs(v - 1.0) < 1e-4, "%s 的 scale 不是 1 (%s)" % (o.name, o.scale)
    assert abs(min(zs)) < 0.02, "整体必须落在 z=0（min z=%.4f）" % min(zs)

    # 动画必须真的写进 .glb（踩过的坑：把 action 从物体上摘掉，导出就是 0 条）
    names = glb_animation_names(glb)
    print("GLB   动画片段:", names)
    for want in ("Gate_Open", "Gate_Close"):
        assert want in names, ".glb 里缺少动画 %s（实际：%s）" % (want, names)
    print("saved:", glb)
    print("saved:", blend)


def glb_animation_names(path):
    """直接读 .glb 的 JSON chunk，确认动画真的被导出了（不信导出器的返回值）。"""
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
    return [a.get("name") for a in (js or {}).get("animations", [])]


if __name__ == "__main__":
    main()
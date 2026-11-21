#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""m3f_banana.py —— 低多边形香蕉树（**树体与果串分离**）程序化生成脚本。

参考图：`reference.png`（2x2 四个变体，同一棵树的四种摆法）。

产物（全部落在本脚本所在目录）：

| 文件 | 内容 | 原点 |
| --- | --- | --- |
| `m3f_banana_tree.glb` | 树体：假茎 + 叶冠（18 片）+ 根部草被 | 地面中心 (0,0,0) |
| `m3f_banana_bunch.glb` | 果串：果柄 + 16 根香蕉（每根独立网格） | 果柄与树体相连的一端 |
| `m3f_banana_tree.blend` / `m3f_banana_bunch.blend` | Blender 源文件 | — |
| `m3f_banana_tree_preview.png` / `m3f_banana_bunch_preview.png` | 四视图预览 | — |
| `m3f_banana_assembled_preview.png` | 树 + 果串拼起来的效果（果串挂在 `BUNCH_ATTACH`） | — |

尺寸基准（米，1 Blender unit = 1 m，见 `assets/AGENTS.md` §1）：

* 树总高 **2.81**（地面 z=0 → 最高叶尖），冠幅 **2.43**（W/H = 0.87，参考图实测 0.86~0.98）
* 假茎：底半径 **0.125** → 顶半径 **0.088**，高 **1.52**，微 S 形
* 根部草被：高 **0.50**、半径 **0.62**（独立网格 `M3FBanana_Grass`，可删）
* 果串：高 **0.65**、宽 **0.66**；单根香蕉长 **0.30~0.36**、直径 **0.12~0.14**
* 果串挂树位置：**树体局部坐标 (0.060, 0, 1.45)**（常量 `BUNCH_ATTACH`）
  —— 果柄根部埋进假茎侧面，果串垂在树干外侧

配色全部取自参考图实测（sRGB 十六进制），不凭感觉调：

| 用途 | 实测色 |
| --- | --- |
| 叶（亮 / 中 / 暗 / 背光） | `#90B060` `#709848` `#385820` `#2F5127` |
| 假茎（亮 / 本色 / 暗） | `#A06D45` `#8A5C39` `#5E4028` |
| 香蕉（亮 / 中 / 暗） | `#E3B92C` `#CFA326` `#B98C1E` |
| 草（亮 / 中 / 暗） | `#7B9A56` `#5C8340` `#44682F` |

运行（必须用 Blender 5.2 的 Python）：

```bash
/Applications/Blender.app/Contents/MacOS/Blender --background --python m3f_banana.py
```
"""

import math
import os
import random

import bpy

# --------------------------------------------------------------------------
# 路径 / 种子
# --------------------------------------------------------------------------
HERE = os.path.dirname(os.path.abspath(__file__))
SEED = 20261117

TREE_GLB = os.path.join(HERE, "m3f_banana_tree.glb")
TREE_BLEND = os.path.join(HERE, "m3f_banana_tree.blend")
TREE_PREVIEW = os.path.join(HERE, "m3f_banana_tree_preview.png")

BUNCH_GLB = os.path.join(HERE, "m3f_banana_bunch.glb")
BUNCH_BLEND = os.path.join(HERE, "m3f_banana_bunch.blend")
BUNCH_PREVIEW = os.path.join(HERE, "m3f_banana_bunch_preview.png")

ASSEMBLED_PREVIEW = os.path.join(HERE, "m3f_banana_assembled_preview.png")

# --------------------------------------------------------------------------
# 尺寸基准（米）
# --------------------------------------------------------------------------
TREE_H = 2.80          # 地面 z=0 → 最高叶尖
STALK_H = 1.52         # 假茎高度（叶冠从这里长出来）
STALK_R0 = 0.125       # 假茎底半径
STALK_R1 = 0.088       # 假茎顶半径
GRASS_H = 0.50         # 根部草被高度
GRASS_R = 0.62         # 根部草被半径

LEAF_COUNT = 13
LEAF_STATIONS = 8      # 沿叶长的站点数
LEAF_COLS = (-1.0, -0.55, 0.0, 0.55, 1.0)   # 横向列位置（-1 = 叶缘）
LEAF_WPROF = (0.22, 0.58, 0.86, 1.00, 1.00, 0.96, 0.82, 0.50)  # 半宽沿叶长（叶尖是钝圆，不是尖针）
LEAF_FOLD = 0.20       # 叶缘相对主脉的下垂量（× 叶全宽）

BUNCH_H = 0.65         # 果串总高（自果柄顶端往下量）
BUNCH_RACHIS = 0.66    # 果柄长度（从假茎伸到果串）
RACHIS_STATIONS = 9    # 果柄路径的站点数
RACHIS_A0 = 18.0       # 果柄起始切线角（度，几乎水平往外）
RACHIS_A1 = 92.0       # 果柄末端切线角（度，垂直向下）
BANANA_COUNT = 16
# 果串挂在树上的位置（树体局部坐标，米）：假茎 +X 侧、冠下
BUNCH_ATTACH = (0.060, 0.0, 1.45)

# --------------------------------------------------------------------------
# 配色（sRGB）
# --------------------------------------------------------------------------
PALETTE = {
    "leaf_light": "#90B060",
    "leaf_mid": "#709848",
    "leaf_dark": "#4A7A3E",
    "leaf_deep": "#3A6432",
    "stalk_light": "#A06D45",
    "stalk_main": "#8A5C39",
    "stalk_dark": "#5E4028",
    "banana_light": "#E3B92C",
    "banana_mid": "#CFA326",
    "banana_dark": "#B98C1E",
    "stem_dark": "#4A3A18",
    "grass_light": "#7B9A56",
    "grass_mid": "#5C8340",
    "grass_dark": "#44682F",
    "ground_dark": "#3B5A2E",
}

# 材质槽顺序（导出后 Godot 里就是这些名字）
MATS = [
    ("leaf_light", "M3FBanana_leaf_light"),
    ("leaf_mid", "M3FBanana_leaf_mid"),
    ("leaf_dark", "M3FBanana_leaf_dark"),
    ("leaf_deep", "M3FBanana_leaf_deep"),
    ("stalk_light", "M3FBanana_stalk_light"),
    ("stalk_main", "M3FBanana_stalk_main"),
    ("stalk_dark", "M3FBanana_stalk_dark"),
    ("banana_light", "M3FBanana_banana_light"),
    ("banana_mid", "M3FBanana_banana_mid"),
    ("banana_dark", "M3FBanana_banana_dark"),
    ("stem_dark", "M3FBanana_stem_dark"),
    ("grass_light", "M3FBanana_grass_light"),
    ("grass_mid", "M3FBanana_grass_mid"),
    ("grass_dark", "M3FBanana_grass_dark"),
    ("ground_dark", "M3FBanana_ground_dark"),
]
MI = {key: i for i, (key, _name) in enumerate(MATS)}


# --------------------------------------------------------------------------
# 通用工具
# --------------------------------------------------------------------------
def srgb_to_linear(c):
    """sRGB 0~1 → 线性 0~1（材质 base color 必须线性，否则 Godot 里发灰）。"""
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hex_to_linear_rgba(h):
    h = h.lstrip("#")
    rgb = [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    return tuple(srgb_to_linear(v) for v in rgb) + (1.0,)


def reset_scene():
    bpy.ops.wm.read_homefile(use_empty=True, use_factory_startup=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0
    return scene


def make_materials():
    mats = []
    for key, name in MATS:
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True
        bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
        rgba = hex_to_linear_rgba(PALETTE[key])
        bsdf.inputs["Base Color"].default_value = rgba
        bsdf.inputs["Roughness"].default_value = 0.85
        if "Specular IOR Level" in bsdf.inputs:
            bsdf.inputs["Specular IOR Level"].default_value = 0.15
        mat.diffuse_color = rgba          # 视口用
        mat.roughness = 0.85
        mats.append(mat)
    return mats


def new_object(name, verts, faces, face_mats, mats):
    """建一个网格物体。verts: [(x,y,z)]，faces: [(i,j,k,l)]，face_mats: 每面材质槽号。"""
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    for mat in mats:
        ob.data.materials.append(mat)
    for poly, idx in zip(me.polygons, face_mats):
        poly.material_index = idx
        poly.use_smooth = False
    return ob


def merge(meshes):
    """把 [(verts, faces, mats)] 合成一份（保持面材质）。"""
    verts, faces, fmats = [], [], []
    for v, f, m in meshes:
        base = len(verts)
        verts.extend(v)
        for face, mi in zip(f, m):
            faces.append(tuple(i + base for i in face))
            fmats.append(mi)
    return verts, faces, fmats


def lerp(a, b, t):
    return a + (b - a) * t


def smoothstep(t):
    return t * t * (3.0 - 2.0 * t)


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def tri_count(ob):
    return sum(len(p.vertices) - 2 for p in ob.data.polygons)


def bbox(objs):
    lo = [1e9] * 3
    hi = [-1e9] * 3
    for ob in objs:
        for v in ob.data.vertices:
            for k in range(3):
                lo[k] = min(lo[k], v.co[k])
                hi[k] = max(hi[k], v.co[k])
    return lo, hi


# --------------------------------------------------------------------------
# 假茎（pseudostem）
# --------------------------------------------------------------------------
def build_stalk(mats):
    """一叠卷起来的叶鞘：每带底边外翻出一圈唇口（半径 ×1.07），侧影上一层层台阶。"""
    rng = random.Random(SEED + 1)
    sides = 9
    bands = 4
    # 每个周向分点的固定半径系数（整根统一 → 竖向棱边是直的，不拧）
    side_f = [1.0 + rng.uniform(-0.045, 0.045) for _ in range(sides)]

    # 高度 → 半径
    def radius_at(z):
        t = z / STALK_H
        return lerp(STALK_R0, STALK_R1, t ** 0.92)

    # 高度 → 中轴横向偏移（微 S 形）
    def axis_at(z):
        t = z / STALK_H
        return (0.050 * math.sin(t * 2.1) - 0.022 * t, 0.018 * math.sin(t * 1.5))

    rings = []
    for i in range(bands):
        zb = STALK_H * i / bands
        zt = STALK_H * (i + 1) / bands
        rb = radius_at(zb)
        rt = radius_at(zt)
        # (z, 半径系数) —— 底唇口外翻，台阶面向内收
        if i > 0:
            rings.append((zb + 0.012, rb * 1.045, "lip"))
        rings.append((zb + 0.055, rb, "body"))
        rings.append((zt - 0.060, rt * 1.02, "body"))
        rings.append((zt - 0.004, rt, "body"))
    # 顶封口（叶冠盖住，但保持闭合）
    rings.append((STALK_H + 0.01, STALK_R1 * 0.92, "top"))
    # 底裙（微喇叭口，落在 z=0）
    rings.insert(0, (0.0, STALK_R0 * 1.13, "base"))

    verts = []
    for z, r, _kind in rings:
        ax, ay = axis_at(z)
        for j in range(sides):
            a = 2.0 * math.pi * j / sides
            verts.append((ax + math.cos(a) * r * side_f[j],
                          ay + math.sin(a) * r * side_f[j],
                          z))

    faces, fmats = [], []
    for i in range(len(rings) - 1):
        kind = rings[i][2]
        for j in range(sides):
            j2 = (j + 1) % sides
            a = i * sides + j
            b = i * sides + j2
            c = (i + 1) * sides + j2
            d = (i + 1) * sides + j
            faces.append((a, b, c, d))
            if kind in ("lip", "base"):
                fmats.append(MI["stalk_main"] if kind == "lip" else MI["stalk_dark"])
            elif kind == "top":
                fmats.append(MI["stalk_dark"])
            else:
                fmats.append(MI["stalk_main"] if j % 3 else MI["stalk_light"])
    # 顶盖
    top = len(verts)
    ax, ay = axis_at(STALK_H + 0.01)
    verts.append((ax, ay, STALK_H + 0.01))
    for j in range(sides):
        j2 = (j + 1) % sides
        base = (len(rings) - 1) * sides
        faces.append((base + j, base + j2, top))
        fmats.append(MI["stalk_dark"])
    # 底盖
    bot = len(verts)
    ax, ay = axis_at(0.0)
    verts.append((ax, ay, 0.0))
    for j in range(sides):
        j2 = (j + 1) % sides
        faces.append((j2, j, bot))
        fmats.append(MI["stalk_dark"])

    return new_object("M3FBanana_Stalk", verts, faces, fmats, mats)


# --------------------------------------------------------------------------
# 叶片
# --------------------------------------------------------------------------
def build_leaf(mats, idx, az, length, half_w, elev0, elev1, tier, base_mat):
    """一片蕉叶：沿一条上升后下垂的弧线放样，横截面是 V 形折（主脉最高、叶缘下垂）。

    配色（照参考图）：**整片叶一个底色**（不要逐面棋盘格 —— 那样叶子会碎成一
    堆细条，看着不像叶子）；只有①叶缘一圈暗边 ②朝下的背面用暗绿。
    """
    rng = random.Random(SEED + 100 + idx)
    n = LEAF_STATIONS
    ts = [i / (n - 1) for i in range(n)]

    # --- 主脉路径（竖直面内的弧） ---
    pts = [(0.0, 0.0, 0.0)]
    step = length / (n - 1)
    for i in range(1, n):
        t = ts[i]
        s = smoothstep(t)
        elev = math.radians(lerp(elev0, elev1, s))
        x, y, z = pts[-1]
        pts.append((x + math.cos(az) * math.cos(elev) * step,
                    y + math.sin(az) * math.cos(elev) * step,
                    z + math.sin(elev) * step))

    # --- 叶片宽度轮廓 + 边缘碎口 ---
    edge = []
    for t in ts:
        e = {}
        for s in (-1, 1):
            u = 1.0
            if t > 0.25:                        # 外半段：边缘随机撕开（参考图的破叶）
                u = 1.0 - rng.uniform(0.0, 0.20)
                if rng.random() < 0.28:         # 啃一个 V 形缺口
                    u -= rng.uniform(0.12, 0.30)
            if t > 0.62:                        # 叶尖再碎一点
                u = min(u, 1.0 - rng.uniform(0.0, 0.22))
            e[s] = max(u, 0.25)
        edge.append(e)

    twist = math.radians(rng.uniform(-14.0, 14.0))
    verts, faces, fmats = [], [], []
    col_u = []
    for i, t in enumerate(ts):
        p = pts[i]
        # 切线
        if i == 0:
            tan = (pts[1][0] - p[0], pts[1][1] - p[1], pts[1][2] - p[2])
        elif i == n - 1:
            tan = (p[0] - pts[-2][0], p[1] - pts[-2][1], p[2] - pts[-2][2])
        else:
            tan = (pts[i + 1][0] - pts[i - 1][0], pts[i + 1][1] - pts[i - 1][1],
                   pts[i + 1][2] - pts[i - 1][2])
        tl = math.sqrt(sum(c * c for c in tan)) or 1.0
        tan = tuple(c / tl for c in tan)
        # 横向（水平面内垂直于叶的方位角）与法向
        side = (-math.sin(az), math.cos(az), 0.0)
        dot = sum(side[k] * tan[k] for k in range(3))
        side = tuple(side[k] - dot * tan[k] for k in range(3))
        sl = math.sqrt(sum(c * c for c in side)) or 1.0
        side = tuple(c / sl for c in side)
        nrm = (tan[1] * side[2] - tan[2] * side[1],
               tan[2] * side[0] - tan[0] * side[2],
               tan[0] * side[1] - tan[1] * side[0])
        # 沿叶长轻微扭转
        ang = twist * t
        ca, sa = math.cos(ang), math.sin(ang)
        side2 = tuple(side[k] * ca + nrm[k] * sa for k in range(3))
        nrm2 = tuple(nrm[k] * ca - side[k] * sa for k in range(3))
        side, nrm = side2, nrm2

        hw = half_w * LEAF_WPROF[i]
        fold = LEAF_FOLD * (2.0 * half_w)
        for c in LEAF_COLS:
            u = c
            if c < -0.9:
                u = -edge[i][-1]
            elif c > 0.9:
                u = edge[i][1]
            # 主脉最高、叶缘下垂（V 形折）
            h = -fold * (u * u)
            verts.append((p[0] + side[0] * u * hw + nrm[0] * h,
                          p[1] + side[1] * u * hw + nrm[1] * h,
                          p[2] + side[2] * u * hw + nrm[2] * h))
            col_u.append(u)

    nc = len(LEAF_COLS)
    for i in range(n - 1):
        for j in range(nc - 1):
            a = i * nc + j
            b = i * nc + j + 1
            c = (i + 1) * nc + j + 1
            d = (i + 1) * nc + j
            faces.append((a, b, c, d))
            umid = (col_u[a] + col_u[d]) * 0.5
            # 背面（法线朝下）用暗绿
            e1 = (verts[b][0] - verts[a][0], verts[b][1] - verts[a][1], verts[b][2] - verts[a][2])
            e2 = (verts[d][0] - verts[a][0], verts[d][1] - verts[a][1], verts[d][2] - verts[a][2])
            nz = (e1[1] * e2[2] - e1[2] * e2[1],
                  e1[2] * e2[0] - e1[0] * e2[2],
                  e1[0] * e2[1] - e1[1] * e2[0])
            nl = math.sqrt(sum(c * c for c in nz)) or 1.0
            if abs(umid) > 0.86:
                fmats.append(MI["leaf_deep"])        # 叶缘暗边
            elif nz[2] / nl < -0.22:
                fmats.append(MI["leaf_dark"])        # 背面
            else:
                fmats.append(base_mat)
    return verts, faces, fmats


def build_leaves(mats):
    """外圈 13 片 + 内圈 5 片（把冠心填满，参考图的冠是一团密叶，不是一圈辐条）。

    冠幅按参考图量：树高 2.80 m 时**冠幅 2.40 m**、冠高 1.30 m（不是一个大圆盘）。
    配色：**整片叶一个底色**（高冠偏亮、外圈偏暗），叶缘一圈暗边、背面用暗绿。
    """
    rng = random.Random(SEED + 2)
    parts = []
    tiers = ["high"] * 4 + ["mid"] * 5 + ["low"] * 4
    base_az = [i * (360.0 / LEAF_COUNT) for i in range(LEAF_COUNT)]
    for i in range(LEAF_COUNT):
        tier = tiers[i]
        az = math.radians(base_az[i] + rng.uniform(-12.0, 12.0))
        if tier == "high":
            length = rng.uniform(1.48, 1.62)
            half_w = rng.uniform(0.215, 0.255)
            elev0 = rng.uniform(82.0, 88.0)
            elev1 = rng.uniform(30.0, 40.0)
        elif tier == "mid":
            length = rng.uniform(1.26, 1.40)
            half_w = rng.uniform(0.275, 0.315)
            elev0 = rng.uniform(45.0, 58.0)
            elev1 = rng.uniform(4.0, 14.0)
        else:
            length = rng.uniform(1.22, 1.36)
            half_w = rng.uniform(0.285, 0.325)
            elev0 = rng.uniform(10.0, 22.0)
            elev1 = rng.uniform(-28.0, -16.0)
        # 整片叶的底色
        if tier == "high":
            base_mat = MI["leaf_light"] if rng.random() < 0.55 else MI["leaf_mid"]
        elif tier == "mid":
            r = rng.random()
            base_mat = MI["leaf_mid"] if r < 0.62 else (MI["leaf_light"] if r < 0.80 else MI["leaf_dark"])
        else:
            base_mat = MI["leaf_mid"] if rng.random() < 0.45 else MI["leaf_dark"]
        v, f, m = build_leaf(mats, i, az, length, half_w, elev0, elev1, tier, base_mat)
        # 叶根从假茎顶长出来（略微外移 + 高度抖动）
        ox = math.cos(az) * rng.uniform(0.02, 0.07)
        oy = math.sin(az) * rng.uniform(0.02, 0.07)
        oz = STALK_H + rng.uniform(-0.06, 0.03)
        v = [(x + ox, y + oy, z + oz) for x, y, z in v]
        parts.append((v, f, m))

    # --- 内圈：5 片短叶，几乎直立，填住冠心 ---
    for k in range(5):
        az = math.radians(k * (360.0 / 5) + 36.0 + rng.uniform(-14.0, 14.0))
        length = rng.uniform(0.72, 1.00)
        half_w = rng.uniform(0.170, 0.215)
        elev0 = rng.uniform(68.0, 84.0)
        elev1 = rng.uniform(38.0, 56.0)
        base_mat = MI["leaf_light"] if rng.random() < 0.6 else MI["leaf_mid"]
        v, f, m = build_leaf(mats, 100 + k, az, length, half_w, elev0, elev1, "inner", base_mat)
        ox = math.cos(az) * rng.uniform(0.01, 0.04)
        oy = math.sin(az) * rng.uniform(0.01, 0.04)
        oz = STALK_H + rng.uniform(-0.10, -0.01)
        v = [(x + ox, y + oy, z + oz) for x, y, z in v]
        parts.append((v, f, m))

    verts, faces, fmats = merge(parts)
    return new_object("M3FBanana_Leaves", verts, faces, fmats, mats)


# --------------------------------------------------------------------------
# 根部草被
# --------------------------------------------------------------------------
def build_grass(mats):
    """根部草被：三层密的扁叶（参考图里是一丛宽叶的草，不是几根细草）。"""
    rng = random.Random(SEED + 3)
    verts, faces, fmats = [], [], []

    # 地面圆盘（藏在草叶底下）
    disc_r = GRASS_R * 0.82
    seg = 14
    base = len(verts)
    verts.append((0.0, 0.0, 0.002))
    for j in range(seg):
        a = 2.0 * math.pi * j / seg
        verts.append((math.cos(a) * disc_r, math.sin(a) * disc_r, 0.002))
    for j in range(seg):
        j2 = (j + 1) % seg
        faces.append((base, base + 1 + j, base + 1 + j2))
        fmats.append(MI["ground_dark"])

    # 草叶：宽扁的尖叶，三圈（参考图里是一丛宽叶的草）
    blades = 46
    for b in range(blades):
        ring = 0 if b < 15 else (1 if b < 31 else 2)
        r0 = (0.10, 0.26, 0.44)[ring] + rng.uniform(-0.06, 0.06)
        a = rng.uniform(0.0, 2.0 * math.pi)
        h = (0.48, 0.40, 0.30)[ring] * rng.uniform(0.78, 1.16)
        w = rng.uniform(0.105, 0.165)          # 宽叶
        lean = rng.uniform(0.22, 0.62)          # 外倾（参考图里是放射状摊开）
        bx, by = math.cos(a) * r0, math.sin(a) * r0
        wx, wy = -math.sin(a), math.cos(a)       # 叶宽方向
        stations = (0.0, 0.36, 0.70, 1.0)
        widths = (1.0, 0.86, 0.55, 0.06)
        idx0 = len(verts)
        for t, wf in zip(stations, widths):
            out = lean * h * t * t
            cx = bx + math.cos(a) * out
            cy = by + math.sin(a) * out
            cz = h * (t - 0.18 * t * t)           # 顶端略收
            hw = w * wf * 0.5
            verts.append((cx - wx * hw, cy - wy * hw, cz))
            verts.append((cx + wx * hw, cy + wy * hw, cz))
        mi = (MI["grass_light"], MI["grass_mid"], MI["grass_mid"], MI["grass_dark"])[rng.choice((0, 1, 1, 2))]
        for s in range(len(stations) - 1):
            a0 = idx0 + s * 2
            faces.append((a0, a0 + 1, a0 + 3, a0 + 2))
            fmats.append(mi)

    return new_object("M3FBanana_Grass", verts, faces, fmats, mats)


# --------------------------------------------------------------------------
# 香蕉 / 果串
# --------------------------------------------------------------------------
def build_banana(mats, name, length, r_max, radial_az, tilt_deg, curve_deg, seed):
    """一根香蕉：沿弧线放样的六棱管，截面略扁，内侧带棱。"""
    rng = random.Random(seed)
    n = 7
    sides = 6
    rprof = (0.34, 0.76, 0.96, 1.0, 0.98, 0.84, 0.52)
    side_f = (1.0, 0.84, 0.92, 1.0, 0.92, 0.84)

    R = (math.cos(radial_az), math.sin(radial_az), 0.0)
    pts = [(0.0, 0.0, 0.0)]
    dirs = []
    for i in range(n):
        t = i / (n - 1)
        ang = math.radians(tilt_deg + curve_deg * t)
        dirs.append((R[0] * math.sin(ang), R[1] * math.sin(ang), -math.cos(ang)))
    step = length / (n - 1)
    for i in range(1, n):
        p = pts[-1]
        d = dirs[i]
        pts.append((p[0] + d[0] * step, p[1] + d[1] * step, p[2] + d[2] * step))

    verts = []
    for i in range(n):
        t = i / (n - 1)
        T = dirs[i]
        # 横向：R 去掉沿 T 的分量
        dot = R[0] * T[0] + R[1] * T[1] + R[2] * T[2]
        S = (R[0] - dot * T[0], R[1] - dot * T[1], R[2] - dot * T[2])
        sl = math.sqrt(sum(c * c for c in S)) or 1.0
        S = tuple(c / sl for c in S)
        N = (T[1] * S[2] - T[2] * S[1], T[2] * S[0] - T[0] * S[2], T[0] * S[1] - T[1] * S[0])
        r = r_max * rprof[i]
        p = pts[i]
        for j in range(sides):
            a = 2.0 * math.pi * j / sides
            rr = r * side_f[j]
            verts.append((p[0] + S[0] * math.cos(a) * rr + N[0] * math.sin(a) * rr * 0.86,
                          p[1] + S[1] * math.cos(a) * rr + N[1] * math.sin(a) * rr * 0.86,
                          p[2] + S[2] * math.cos(a) * rr + N[2] * math.sin(a) * rr * 0.86))
    # 端点封口
    tip = len(verts)
    verts.append((pts[-1][0], pts[-1][1], pts[-1][2]))
    faces, fmats = [], []
    for i in range(n - 1):
        for j in range(sides):
            j2 = (j + 1) % sides
            a = i * sides + j
            b = i * sides + j2
            c = (i + 1) * sides + j2
            d = (i + 1) * sides + j
            faces.append((a, b, c, d))
            # 按面心相对果轴的径向位置分三档（朝外的亮、朝内的暗）——
            # **不要棋盘格**，否则香蕉会碎成一片小方块
            ax = (verts[a][0] + verts[c][0]) * 0.5
            ay = (verts[a][1] + verts[c][1]) * 0.5
            az = (verts[a][2] + verts[c][2]) * 0.5
            px, py, pz = pts[i]
            rad = (ax - px) * R[0] + (ay - py) * R[1]
            if rad > 0.012:
                fmats.append(MI["banana_light"])
            elif rad < -0.012:
                fmats.append(MI["banana_dark"])
            else:
                fmats.append(MI["banana_mid"])
    base = (n - 1) * sides
    for j in range(sides):
        j2 = (j + 1) % sides
        faces.append((base + j, base + j2, tip))
        fmats.append(MI["banana_dark"])
    return new_object(name, verts, faces, fmats, mats)


def rachis_points():
    """果轴（果柄）的路径：起点贴着假茎，**先往外甩、再往下垂**，末端挂果。

    切线角从 [const RACHIS_A0]（几乎水平）转到 [const RACHIS_A1]（垂直向下），
    所以果柄是一段**真正的弧**——挂到树上时果柄根部埋进树干，果串垂在树干侧面。

    返回 [(x, z)]，x 是往外（+X）的距离，z 是向下的距离（都是局部坐标）。
    """
    pts = []
    px, pz = 0.0, 0.0
    ds = BUNCH_RACHIS / (RACHIS_STATIONS - 1)
    for i in range(RACHIS_STATIONS):
        t = i / (RACHIS_STATIONS - 1)
        ang = math.radians(lerp(RACHIS_A0, RACHIS_A1, smoothstep(t)))
        if i > 0:
            px += math.cos(ang) * ds
            pz += math.sin(ang) * ds
        pts.append((px, pz))
    return pts


def rachis_at(t: float):
    """果轴上参数 t（0~1）处的点。"""
    pts = rachis_points()
    f = clamp(t, 0.0, 1.0) * (len(pts) - 1)
    i = int(f)
    if i >= len(pts) - 1:
        return pts[-1]
    k = f - i
    a, b = pts[i], pts[i + 1]
    return (lerp(a[0], b[0], k), lerp(a[1], b[1], k))


def build_bunch_stem(mats):
    """果柄：从假茎伸出的一段弧，末端是挂果的地方。

    根部粗（贴着树干那头），越往下越细；末端带一小截花蒂残留。
    """
    n = RACHIS_STATIONS
    sides = 6
    rprof = (0.034, 0.032, 0.029, 0.026, 0.022, 0.016, 0.011, 0.008, 0.006)
    verts = []
    pts = rachis_points()
    for i in range(n):
        x, z = pts[i]
        for j in range(sides):
            a = 2.0 * math.pi * j / sides
            r = rprof[i]
            verts.append((x + math.cos(a) * r, math.sin(a) * r, -z))
    faces, fmats = [], []
    for i in range(n - 1):
        for j in range(sides):
            j2 = (j + 1) % sides
            a = i * sides + j
            b = i * sides + j2
            c = (i + 1) * sides + j2
            d = (i + 1) * sides + j
            faces.append((a, b, c, d))
            fmats.append(MI["stalk_dark"] if j % 2 else MI["stalk_main"])
    # 底端小蒂（花蒂残留）
    bot = len(verts)
    verts.append((pts[-1][0] + 0.010, 0.0, -pts[-1][1] - 0.045))
    base = (n - 1) * sides
    for j in range(sides):
        j2 = (j + 1) % sides
        faces.append((base + j, base + j2, bot))
        fmats.append(MI["stem_dark"])
    return new_object("M3FBanana_BunchStem", verts, faces, fmats, mats)


def build_bunch(mats):
    """果串：3 层共 16 根香蕉。

    关键：香蕉**几乎竖直地垂下来**（外倾角只有 8~16°），靠"沿果轴分层 + 逐层
    往外挪"形成上宽下窄的果串剪影；香蕉尖端再微微向外弯，像参考图那样。
    """
    rng = random.Random(SEED + 4)
    objs = [build_bunch_stem(mats)]
    tiers = (
        # (沿果轴的位置, 数量, 外倾角, 长度, 半径, 环半径, 方位角基准)
        (0.42, 6, 8.0, 0.33, 0.066, 0.125, 0.0),
        (0.62, 5, 12.0, 0.36, 0.068, 0.160, 9.0),
        (0.82, 5, 16.0, 0.32, 0.062, 0.130, -12.0),
    )
    idx = 0
    for t_pos, count, tilt, blen, brad, ring_r, az0 in tiers:
        for k in range(count):
            az = math.radians(az0 + k * (360.0 / count) + rng.uniform(-12.0, 12.0))
            tilt_j = tilt + rng.uniform(-4.0, 4.0)
            L = blen * rng.uniform(0.92, 1.08)
            R = brad * rng.uniform(0.92, 1.08)
            ob = build_banana(mats, "M3FBanana_Fruit_%02d" % (idx + 1), L, R, az,
                              tilt_j, rng.uniform(16.0, 26.0), SEED + 500 + idx)
            # 摆到果轴上
            ax, az_z = rachis_at(t_pos)
            ox = ax + math.cos(az) * ring_r
            oy = math.sin(az) * ring_r
            for v in ob.data.vertices:
                v.co.x += ox
                v.co.y += oy
                v.co.z -= az_z
            objs.append(ob)
            idx += 1
    return objs


# --------------------------------------------------------------------------
# 导出 / 预览
# --------------------------------------------------------------------------
def select_only(objs):
    bpy.ops.object.select_all(action="DESELECT")
    for ob in objs:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]


def export_glb(path, objs):
    select_only(objs)
    bpy.ops.export_scene.gltf(
        filepath=path,
        export_format="GLB",
        use_selection=True,
        export_apply=True,
        export_yup=True,
        export_materials="EXPORT",
        export_cameras=False,
        export_lights=False,
        export_extras=False,
    )
    print("EXPORTED %s (%.1f KB)" % (path, os.path.getsize(path) / 1024.0))


def look_at(obj, target):
    import mathutils
    d = mathutils.Vector(target) - obj.location
    obj.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


def preview_rig(scene, targets, azimuths, elevation, dist, target_z, with_ground=True):
    """临时搭一套灯光 + 相机（+ 地面），用来渲预览。

    ⚠️ 果串是**悬挂物**（整串都在 z=0 以下），有地面的话会被地面挡住 —— 渲果串
    必须 `with_ground=False`。
    """
    rig = []
    # 地面
    if with_ground:
        me = bpy.data.meshes.new("PreviewGround")
        s = 6.0
        me.from_pydata([(-s, -s, 0), (s, -s, 0), (s, s, 0), (-s, s, 0)], [], [(0, 1, 2, 3)])
        me.update()
        g = bpy.data.objects.new("PreviewGround", me)
        bpy.context.collection.objects.link(g)
        gm = bpy.data.materials.new("PreviewGroundMat")
        gm.use_nodes = True
        bsdf = next(n for n in gm.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
        bsdf.inputs["Base Color"].default_value = hex_to_linear_rgba("#E8E8E4")
        bsdf.inputs["Roughness"].default_value = 0.9
        g.data.materials.append(gm)
        rig.append(g)

    # 太阳（与参考图同向：左上偏前）
    sun_data = bpy.data.lights.new("PreviewSun", type="SUN")
    sun_data.energy = 2.1
    sun_data.angle = math.radians(14.0)
    sun_data.color = (1.0, 0.97, 0.90)
    sun = bpy.data.objects.new("PreviewSun", sun_data)
    bpy.context.collection.objects.link(sun)
    sun.rotation_euler = (math.radians(48.0), 0.0, math.radians(38.0))
    rig.append(sun)

    # 世界光（白底）
    world = bpy.data.worlds.new("PreviewWorld")
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (1.0, 1.0, 1.0, 1.0)
        bg.inputs[1].default_value = 0.45
    scene.world = world

    cam_data = bpy.data.cameras.new("PreviewCam")
    cam_data.lens = 55.0
    cam = bpy.data.objects.new("PreviewCam", cam_data)
    bpy.context.collection.objects.link(cam)
    scene.camera = cam
    rig.append(cam)

    lo, hi = bbox(targets)
    center = ((lo[0] + hi[0]) * 0.5, (lo[1] + hi[1]) * 0.5, (lo[2] + hi[2]) * 0.5)
    cx, cy, cz = center
    cam.location = (cx + dist * math.cos(math.radians(elevation)) * math.cos(math.radians(azimuths[0])),
                    cy + dist * math.cos(math.radians(elevation)) * math.sin(math.radians(azimuths[0])),
                    cz + dist * math.sin(math.radians(elevation)))
    look_at(cam, (cx, cy, target_z))
    return rig, cam


def render_preview(scene, prefix, rig, cam, azimuths, elevation, dist, target_z, res=512):
    """渲 4 个方位，存临时 PNG（后面再拼成一张四视图）。"""
    lo, hi = bbox([o for o in scene.objects if o.type == "MESH" and o.name.startswith("M3FBanana")])
    cx, cy = (lo[0] + hi[0]) * 0.5, (lo[1] + hi[1]) * 0.5
    outs = []
    for i, az in enumerate(azimuths):
        cam.location = (cx + dist * math.cos(math.radians(elevation)) * math.cos(math.radians(az)),
                        cy + dist * math.cos(math.radians(elevation)) * math.sin(math.radians(az)),
                        target_z + dist * math.sin(math.radians(elevation)))
        look_at(cam, (cx, cy, target_z))
        out = os.path.join(HERE, "_tmp_%s_%d.png" % (prefix, i))
        scene.render.filepath = out
        bpy.ops.render.render(write_still=True)
        outs.append(out)
    return outs


def make_sheet(view_paths, out_path):
    """把 4 张视图拼成一张 2x2 四视图 PNG。"""
    import numpy as np
    imgs = [bpy.data.images.load(p) for p in view_paths]
    w, h = imgs[0].size
    arrs = []
    for im in imgs:
        a = np.empty(w * h * 4, dtype=np.float32)
        im.pixels.foreach_get(a)
        arrs.append(a.reshape(h, w, 4))
    sheet = np.ones((h * 2, w * 2, 4), dtype=np.float32)
    for i, a in enumerate(arrs):
        r, c = divmod(i, 2)
        sheet[(1 - r) * h:(2 - r) * h, c * w:(c + 1) * w, :] = a
    out = bpy.data.images.new("sheet", w * 2, h * 2, alpha=False, float_buffer=True)
    out.pixels.foreach_set(sheet.ravel())
    out.filepath_raw = out_path
    out.file_format = "PNG"
    out.save()
    for im in imgs:
        bpy.data.images.remove(im)
    # 中间产物：拼完就删，别留在资产目录里被 Godot 当资源导进去
    for path in view_paths:
        try:
            os.remove(path)
        except OSError:
            pass
    print("SHEET %s" % out_path)


def setup_render(scene, res=512):
    engines = [e.identifier for e in
               bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items]
    for eng in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE", "CYCLES"):
        if eng in engines:
            try:
                scene.render.engine = eng
                break
            except TypeError:
                continue
    print("RENDER ENGINE =", scene.render.engine)
    scene.render.resolution_x = res
    scene.render.resolution_y = res
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.film_transparent = False
    try:
        scene.view_settings.view_transform = "Standard"
    except TypeError:
        pass
    if scene.render.engine == "CYCLES":
        scene.cycles.samples = 48
        scene.cycles.use_denoising = True
        scene.cycles.device = "CPU"


# --------------------------------------------------------------------------
# 自检
# --------------------------------------------------------------------------
def check(objs, label, expect_h=None, ground=True):
    lo, hi = bbox(objs)
    size = [hi[k] - lo[k] for k in range(3)]
    tris = sum(tri_count(o) for o in objs)
    verts = sum(len(o.data.vertices) for o in objs)
    mats = set()
    for o in objs:
        for i, p in enumerate(o.data.polygons):
            mats.add(o.data.materials[p.material_index].name)
    print("=== %s CHECK ===" % label)
    print("  objects   : %s" % ", ".join(o.name for o in objs))
    print("  bbox min  : (%.4f, %.4f, %.4f)" % (lo[0], lo[1], lo[2]))
    print("  bbox max  : (%.4f, %.4f, %.4f)" % (hi[0], hi[1], hi[2]))
    print("  size XYZ  : %.3f x %.3f x %.3f m" % (size[0], size[1], size[2]))
    print("  tris/verts: %d / %d" % (tris, verts))
    print("  materials : %d (%s)" % (len(mats), ", ".join(sorted(mats))))
    for o in objs:
        assert tuple(round(v, 6) for v in o.scale) == (1.0, 1.0, 1.0), "scale 必须为 1: " + o.name
        assert tuple(round(v, 6) for v in o.rotation_euler) == (0.0, 0.0, 0.0), "rotation 必须为 0: " + o.name
        assert tuple(round(v, 6) for v in o.location) == (0.0, 0.0, 0.0), "location 必须为 0: " + o.name
    if ground:
        assert abs(lo[2]) < 0.02, "根部必须落在 z=0（实测 %.4f）" % lo[2]
    if expect_h is not None:
        assert abs(size[2] - expect_h) < 0.05, "高度漂了：%.3f != %.3f" % (size[2], expect_h)
    print("  OK")


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def main():
    import sys
    no_render = "--no-render" in sys.argv
    scene = reset_scene()
    mats = make_materials()

    # ---------------- 树 ----------------
    stalk = build_stalk(mats)
    leaves = build_leaves(mats)
    grass = build_grass(mats)
    tree_objs = [stalk, leaves, grass]
    check(tree_objs, "TREE", expect_h=TREE_H)
    export_glb(TREE_GLB, tree_objs)
    bpy.ops.wm.save_as_mainfile(filepath=TREE_BLEND)

    if not no_render:
        setup_render(scene)
        # 树
        rig, cam = preview_rig(scene, tree_objs, (0.0,), 8.0, 6.0, 1.35)
        views = render_preview(scene, "tree", rig, cam,
                               (0.0, 45.0, 90.0, 135.0), 10.0, 6.2, 1.35)
        make_sheet(views, TREE_PREVIEW)
        for o in rig:
            bpy.data.objects.remove(o, do_unlink=True)

    # ---------------- 果串（单独场景，.blend 里只有果串） ----------------
    for ob in list(tree_objs):
        bpy.data.objects.remove(ob, do_unlink=True)
    for mat in list(bpy.data.materials):     # 清掉树体的材质，免得果串材质名带 .001
        bpy.data.materials.remove(mat)
    mats = make_materials()
    bunch_objs = build_bunch(mats)
    check(bunch_objs, "BUNCH", ground=False)
    export_glb(BUNCH_GLB, bunch_objs)
    bpy.ops.wm.save_as_mainfile(filepath=BUNCH_BLEND)

    if not no_render:
        setup_render(scene)
        # 果串（悬挂物：不要地面，否则会被地面挡住）
        rig, cam = preview_rig(scene, bunch_objs, (0.0,), 4.0, 1.6, -0.32, with_ground=False)
        views = render_preview(scene, "bunch", rig, cam,
                               (0.0, 45.0, 90.0, 135.0), 4.0, 1.6, -0.32)
        make_sheet(views, BUNCH_PREVIEW)
        for o in rig:
            bpy.data.objects.remove(o, do_unlink=True)

        # 组合效果（果串挂到树上：证明两个资产怎么拼）
        mats = make_materials()
        tree_objs = [build_stalk(mats), build_leaves(mats), build_grass(mats)]
        for ob in bunch_objs:
            for v in ob.data.vertices:
                v.co.x += BUNCH_ATTACH[0]
                v.co.y += BUNCH_ATTACH[1]
                v.co.z += BUNCH_ATTACH[2]
        rig, cam = preview_rig(scene, tree_objs, (0.0,), 8.0, 6.0, 1.35)
        views = render_preview(scene, "assembled", rig, cam,
                               (0.0, 45.0, 90.0, 135.0), 10.0, 6.2, 1.35)
        make_sheet(views, ASSEMBLED_PREVIEW)
        for o in rig:
            bpy.data.objects.remove(o, do_unlink=True)

    print("ALL DONE")


if __name__ == "__main__":
    main()

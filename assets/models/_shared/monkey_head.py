# -*- coding: utf-8 -*-
"""
monkey_head.py —— 猴头（共用零件）：颅骨 + 脸盘 + 呆毛 + 耳朵 + 可动五官 + 两段表情。

被两个资产复用：
* `assets/models/ds-monkey-head/ds_monkey_head.py`   （只做头）
* `assets/models/m3-high-lowpoly-monkey/…`          （整只猴）
所以这里是**纯几何 + 材质 + 片段数据**，不含"清场景 / 存盘 / 导出"这些流程，
由调用方自己决定。

导入方式（Blender 里跑时不能直接 import 同级目录）：
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "_shared"))
    import monkey_head as MH
导入即在当前场景里建出头部各零件（MH.MESHES / MH.OBJ）。
"""

import bpy
import bmesh
import math
import os

from mathutils import Vector
from mathutils.bvhtree import BVHTree

# =====================================================================
# 1. 尺寸常量（米）—— 参考图正面 171 px = 0.300 m
# =====================================================================
PX_M = 0.300 / 171.0
RZ = 0.1528                     # 颅骨半高（总高 0.3056 m：参考图 高/宽 ≈ 1.01）

NCOL_FACE = 4                   # 脸盘横跨的列数（脸盘 4 列不能减 —— 分色边界靠它）
NCOL_FUR = 2                    # 每侧毛区列数（3→2 省面；脸盘列数不变，发际线的 V 不受影响）
NCOL = NCOL_FUR + NCOL_FACE + NCOL_FUR      # 每环 10 个顶点

# 正面半宽（z_norm -> 半宽 m），量自正面视图轮廓
PROFILE = [
    (1.000, 0.000),
    (0.930, 0.052),
    (0.860, 0.049),
    (0.700, 0.118),
    (0.520, 0.129),
    (0.320, 0.146),
    (0.120, 0.149),
    (-0.080, 0.1505),
    (-0.280, 0.1510),
    (-0.480, 0.1520),
    (-0.660, 0.1480),
    (-0.820, 0.1170),
    (-0.940, 0.0920),
    (-1.000, 0.0680),
]
# 脸中线上的「前」深度（z_norm -> +y m），量自侧视图；-0.28 ~ -0.70 就是吻部
FRONT = [                      # 颅骨基础「前」深度（不含吻部凸起）
    (1.000, 0.030),
    (0.860, 0.090),
    (0.700, 0.118),
    (0.520, 0.135),
    (0.320, 0.145),
    (0.120, 0.151),
    (-0.080, 0.152),
    (-0.280, 0.151),
    (-0.480, 0.149),
    (-0.660, 0.146),
    (-0.820, 0.132),
    (-0.940, 0.106),
    (-1.000, 0.060),
]
MUZZLE = [
    (-1.000, 0.020),
    (-0.900, 0.038),
    (-0.780, 0.048),
    (-0.660, 0.052),
    (-0.540, 0.050),
    (-0.430, 0.040),
    (-0.360, 0.032),
    (-0.300, 0.024),
    (-0.250, 0.016),
    (-0.205, 0.009),
    (-0.165, 0.004),
    (-0.130, 0.001),
    (-0.100, 0.000),
    (0.200, 0.000),
]
MUZZLE_AZ = 0.46                # 吻部沿方位角的高斯半宽（rad）
# 脸的横截面形状：y = fb · |cos(az)|^FACE_ROUND_P
#   p = 1 → 纯椭圆（正圆截面）；p < 1 → 比圆**更饱满**（颊部鼓出来）
#   p = 0.80 时中心处的曲率半径 ≈ 0.19 m（微凸，不平），两颊却比正圆鼓 10%
FACE_ROUND_P = 0.70
# 吻部前突的整体缩放（1.0 = 原样）：参考图的吻没有鼓那么厉害，嘴巴不该顶出来
MUZZLE_SCALE = 0.66
# 面罩隆起：脸的正面整体比毛皮往前鼓一点，到颞骨处收到 0（参考图的脸就是一块浮在毛皮上的面罩）
FACE_LIFT = 0.010
FACE_LIFT_AZ = 1.05          # 隆起在 |az| 到这个值时归零

# 后脑深度（z_norm -> |y| m），量自侧视图
BACK = [
    (1.000, 0.030),
    (0.860, 0.068),
    (0.700, 0.111),
    (0.520, 0.126),
    (0.320, 0.137),
    (0.120, 0.147),
    (-0.080, 0.150),
    (-0.280, 0.145),
    (-0.480, 0.132),
    (-0.660, 0.114),
    (-0.820, 0.096),
    (-0.940, 0.072),
    (-1.000, 0.040),
]

# 分色：发际线 / 脸的侧边界
HAIR_EL = 0.545                 # 发际线基准仰角（两侧）= 31.2°
HAIR_PEAK = 0.155               # 正中棕毛楔形往下压的量 = 8.9°
HAIR_W = 0.22                   # 楔形的方位角宽度（0.22 = 眉心处一个尖角）
# 脸盘侧边界：el(rad) -> |az| 上限。
# ⚠️ 这张表是**从参考图逐行量出来的**（量橘色脸盘每行的半宽，换算成该高度的颅骨半宽，
#    再 asin 回去），不是手调的。量的时候要排除耳朵（耳朵的橘色耳窝也在图里）。
#    旧表在眉毛以上（el > 0.35）收得太狠 → 脸盘上窄下宽，正面看像个梯形。
SIDE_LIMIT = [
    (-1.5708, 0.88),
    (-1.30, 0.79),
    (-1.05, 0.76),
    (-0.96, 0.83),
    (-0.82, 0.71),
    (-0.66, 0.62),
    (-0.52, 0.76),
    (-0.38, 0.94),
    (-0.23, 1.00),
    (-0.09, 1.03),
    (0.05, 1.10),
    (0.19, 1.14),
    (0.35, 1.15),
    (0.49, 1.15),
    (0.63, 1.10),
    (0.75, 1.00),
]

# 环线： (仰角°, V 形下垂权重)；None = 发际线环（仰角随方位角变化）
ROWS = [
    (76.0, 0.10),
    (62.0, 0.30),
    (46.0, 0.70),
    (33.0, 0.95),
    None,
    (8.0, 0.75),
    (-8.0, 0.45),
    (-17.0, 0.32),
    (-26.0, 0.20),
    (-46.0, 0.00),
    (-64.0, 0.00),
    (-79.0, 0.00),
]
HAIR_ROW = 4

# 正面五官（参考图像素位置换算成米；x 用「屏幕左 = +X」）
EYE_X = 0.0675
EYE_Z = -0.0115
SCLERA_R = 0.0312               # 眼白半径（参考图 32 px；但弯面贴片的可见白只有 25 px，故放大）
PUPIL_R = 0.0188
PUPIL_IN = 0.0075               # 瞳孔向鼻梁内偏
GLINT_R = 0.0052
GLINT_OFF = (0.0050, 0.0053)    # 高光在瞳孔的「屏幕左上」（+X / +Z，两只眼同向）

BROW_X = 0.0846
BROW_Z = 0.0395
BROW_LEN = 0.0300
BROW_THICK = 0.0094
BROW_TILT = math.radians(21.0)  # 外端低、内端高

NOSTRIL_X = 0.0170
NOSTRIL_Z = -0.0490

# 控制点比「够用」更稀：Catmull-Rom 会补出中间点，多写的控制点在成品里根本看不出来，
# 只是白白把笑脸那段管子拉成 50 多环（曾经 636 三角面，占整颗头预算的 3 成）。
MOUTH_PTS = [                   # 左角(角色右) → 下弧 → 右角(角色左) → 小钩
    (0.0553, -0.0895),
    (0.0272, -0.1017),
    (-0.0009, -0.1043),
    (-0.0289, -0.0991),
    (-0.0500, -0.0886),
    (-0.0553, -0.0780),
    (-0.0605, -0.0737),
    (-0.0658, -0.0728),
    (-0.0705, -0.0757),
    (-0.0702, -0.0705),
]
MOUTH_R = 0.0042

# 耳朵
EAR_X = 0.172
EAR_Y = -0.042
EAR_Z = -0.008
EAR_RX = 0.0612
EAR_RY = 0.0440                      # 耳朵高度实测：参考图 0.082 m（原 0.059 太大，耳朵像两片大桨）
# 盘面法线（右耳；左耳镜像）：离 +Y 轴 30°（正对前方偏外）。
# 由参考图两个投影量反解：正面 x 向投影 0.106 m、侧面 y 向投影 0.061 m
#   x 向投影 = 2·rx·√(1−n_x²)，y 向投影 = 2·rx·√(1−n_y²)  →  tan φ = 0.061/0.106
EAR_N = Vector((0.500, 0.866, 0.05))

# ⚠️ lerp_table 要求 x 升序
PROFILE.sort()
FRONT.sort()
BACK.sort()
MUZZLE.sort()
SIDE_LIMIT.sort()


# =====================================================================
# 2. 调色板（sRGB，采自参考图）
# =====================================================================
# 调色板：**参考图取色**（simple-lowpoly-monkey.jpeg，按色相聚类统计）
#   橘(脸/肚/手脚) #CE9A6C  ·  棕(毛) #79412A  ·  深色(眉/瞳/嘴) #2F242A
# 层次：头盖比四肢**浅一档**（参考图正视里头明显比胳膊亮）→ 多一档 fur_light。
PAL = {
    "fur":      (0.478, 0.271, 0.153),   # #7A4527 身体 / 四肢 / 尾巴的棕
    "fur_light":(0.541, 0.322, 0.200),   # #8A5233 头盖、耳朵外圈（浅一档）
    "fur_dark": (0.306, 0.173, 0.114),   # #4E2C1D 发际线正中的深楔形、耳廓外沿
    "face":     (0.859, 0.659, 0.431),   # #DBA86E 脸盘 / 肚皮 / 手掌 / 脚掌
    "ear_in":   (0.769, 0.475, 0.290),   # #C4794A 耳窝（比脸略深）
    "sclera":   (0.955, 0.930, 0.885),
    "pupil":    (0.185, 0.155, 0.200),
    "glint":    (1.000, 1.000, 1.000),
    "mark":     (0.184, 0.141, 0.165),
    "mouth":    (0.120, 0.062, 0.058),      # 口腔（几乎黑，张嘴时才看得到）
    "tongue":   (0.760, 0.420, 0.360),
}
ROUGH = {"fur": 0.72, "fur_light": 0.72, "fur_dark": 0.74, "face": 0.70, "ear_in": 0.72,
         "sclera": 0.45, "pupil": 0.40, "glint": 0.20, "mark": 0.66,
         "mouth": 0.80, "tongue": 0.62}


def srgb2lin(c):
    def f(u):
        return u / 12.92 if u <= 0.04045 else ((u + 0.055) / 1.055) ** 2.4
    return (f(c[0]), f(c[1]), f(c[2]), 1.0)


def make_materials():
    mats = {}
    for key, rgb in PAL.items():
        mat = bpy.data.materials.new("DS_" + key)
        mat.use_nodes = True
        mat.use_backface_culling = False
        bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
        lin = srgb2lin(rgb)
        bsdf.inputs["Base Color"].default_value = lin
        bsdf.inputs["Roughness"].default_value = ROUGH[key]
        for prop in ("Specular IOR Level", "Specular"):
            if prop in bsdf.inputs:
                bsdf.inputs[prop].default_value = 0.20
                break
        mat.diffuse_color = lin
        mats[key] = mat
    return mats


MATS = make_materials()


# =====================================================================
# 3. 网格工具
# =====================================================================
def build_object(name, verts, faces, recalc=True):
    """verts: [Vector]；faces: [(idx_tuple, slot_key)]"""
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], [f[0] for f in faces])
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)

    used = []
    for _, key in faces:
        if key not in used:
            used.append(key)
    for key in used:
        me.materials.append(MATS[key])
    idx = {k: i for i, k in enumerate(used)}
    for poly, (_, key) in zip(me.polygons, faces):
        poly.use_smooth = False
        poly.material_index = idx[key]

    if recalc:
        bm = bmesh.new()
        bm.from_mesh(me)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(me)
        bm.free()

    me.validate(verbose=False)
    me.update()
    return ob


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


def catmull_rom(pts, samples_per_seg=4):
    P = [Vector((p[0], p[1])) for p in pts]
    P = [P[0]] + P + [P[-1]]
    out = []
    for i in range(len(P) - 3):
        p0, p1, p2, p3 = P[i], P[i + 1], P[i + 2], P[i + 3]
        for s in range(samples_per_seg):
            t = s / float(samples_per_seg)
            t2, t3 = t * t, t * t * t
            q = 0.5 * ((2 * p1) + (-p0 + p2) * t
                       + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2
                       + (-p0 + 3 * p1 - 3 * p2 + p3) * t3)
            out.append(q)
    out.append(P[-2])
    return out


# =====================================================================
# 4. 颅骨（脸盘是独立的一圈列 + 发际线是一条环线）
# =====================================================================
def hairline(az):
    return HAIR_EL - HAIR_PEAK * math.exp(-(az / HAIR_W) ** 2)


def smoothstep(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0))) if e1 != e0 else 0.0
    return t * t * (3.0 - 2.0 * t)


def skull_point(az, el):
    """颅骨表面：圆颅 + **圆脸正面** + 吻部前突。

    * 正面横截面 = `fb · |cos(az)|^FACE_ROUND_P`（p < 1 = 比正圆更饱满）。
      以前这里是"一块平板（平盾）+ 两侧后退的斜面"，正面看两颊就是凹的；
      改成圆截面后整张脸是**鼓的**，颊部自然圆。
    * p 不能太小：p → 0 会退化成"平脸 + 尖角"，而且中心曲率半径 R = hw²/(fb·p)
      变小后，56 mm 的眼白贴片两边会陷进脸里（眼白是贴棱面的 shell，瞳孔是平圆片）。
      p = 0.80 时 R ≈ 0.19 m，瞳孔外缘仍在眼白前面 3 mm，安全。
    * 吻部前突按 `MUZZLE_SCALE` 缩量（参考图的嘴没有鼓那么厉害）。
    """
    zn = max(-0.999, min(0.999, math.sin(el)))
    hw = lerp_table(PROFILE, zn)
    fb = lerp_table(FRONT, zn)
    mz = lerp_table(MUZZLE, zn)
    bk = lerp_table(BACK, zn)
    ca, sa = math.cos(az), math.sin(az)
    x = hw * sa
    if ca >= 0.0:
        # 正面 = **圆脸**：横截面是饱满的超椭圆（p<1 比正圆更鼓），
        # 不再是"一块平板 + 两侧后退的斜面"—— 后者正面看两颊就是凹的。
        y = fb * (abs(ca) ** FACE_ROUND_P)
        # 面罩隆起（额头到下巴都鼓一点，两侧收到 0）
        la = abs(az)
        if la < FACE_LIFT_AZ:
            y += FACE_LIFT * (1.0 - (la / FACE_LIFT_AZ) ** 2)
        # 吻部前突（整体缩量，嘴巴不再顶出来）
        y += MUZZLE_SCALE * mz * math.exp(-(az / MUZZLE_AZ) ** 2)
    else:
        y = bk * ca
    return Vector((x, y, RZ * zn))


def col_az(i, A):
    """环上第 i 个顶点的方位角：左毛区(0..NCOL_FUR) → 脸盘 → 右毛区"""
    if i <= NCOL_FUR:
        return -math.pi + (math.pi - A) * (i / float(NCOL_FUR))
    if i <= NCOL_FUR + NCOL_FACE:
        j = i - NCOL_FUR
        return -A + 2.0 * A * (j / float(NCOL_FACE))
    j = i - NCOL_FUR - NCOL_FACE
    return A + (math.pi - A) * (j / float(NCOL_FUR))


def row_el(row, az):
    if row is None:                      # 发际线环
        return hairline(az)
    deg, w = row
    return math.radians(deg) + (hairline(az) - hairline(0.0)) * w


def is_face_col(i):
    return NCOL_FUR <= i < NCOL_FUR + NCOL_FACE


def build_skull():
    verts = [Vector((0.0, 0.0, RZ))]        # 0: 顶点
    rings = []
    for j, row in enumerate(ROWS):
        base_el = hairline(0.0) if row is None else math.radians(row[0])
        A = lerp_table(SIDE_LIMIT, base_el)
        idx = []
        for i in range(NCOL):
            az = col_az(i, A)
            el = row_el(row, az)
            idx.append(len(verts))
            verts.append(skull_point(az, el))
        rings.append(idx)
    bot = len(verts)
    verts.append(Vector((0.0, 0.0, -RZ * 0.986)))

    faces = []
    # 顶扇
    r0 = rings[0]
    for i in range(NCOL):
        faces.append(((0, r0[i], r0[(i + 1) % NCOL]), "fur_light"))

    # 环带
    for j in range(len(rings) - 1):
        ra, rb = rings[j], rings[j + 1]
        face_row = (j + 1) > HAIR_ROW          # 这一带是否在发际线之下
        for i in range(NCOL):
            i2 = (i + 1) % NCOL
            A_ = ra[i]
            B_ = ra[i2]
            C_ = rb[i2]
            D_ = rb[i]
            slot = "face" if (face_row and is_face_col(i)) else "fur_light"
            if (i + j) % 2 == 0:
                faces.append(((A_, B_, C_), slot))
                faces.append(((A_, C_, D_), slot))
            else:
                faces.append(((A_, B_, D_), slot))
                faces.append(((B_, C_, D_), slot))

    # 底盖
    rl = rings[-1]
    for i in range(NCOL):
        i2 = (i + 1) % NCOL
        slot = "face" if is_face_col(i) else "fur_light"
        faces.append(((bot, rl[i2], rl[i]), slot))

    return build_object("DSMonkeyHead", verts, faces)


def build_tuft():
    """头顶呆毛：一片**宽而低的「脊」**（不是细尖刺）。
    参考图正视里那撮毛有 36 px 宽（≈0.063 m）、只比头顶高 1~2 cm，侧视里是前后拉长的一片，
    所以做成「左右两片斜面收到一条脊线」的形状：正视是宽三角，侧视是带缺口的尖。"""
    ridge = [                      # (y, 脊线 z, 基座半宽)
        (0.092, 0.1435, 0.020),
        (0.058, 0.1690, 0.030),
        (0.030, 0.1480, 0.033),
        (0.004, 0.1665, 0.033),
        (-0.026, 0.1465, 0.030),
        (-0.044, 0.1330, 0.022),
    ]
    xoff = -0.008
    base_z = 0.1265
    verts, faces = [], []
    L, R, T = [], [], []
    for (y, zt, half) in ridge:
        L.append(len(verts))
        verts.append(Vector((xoff - half, y, base_z)))
        R.append(len(verts))
        verts.append(Vector((xoff + half, y, base_z)))
        T.append(len(verts))
        verts.append(Vector((xoff, y, zt)))
    for i in range(len(ridge) - 1):
        faces.append(((L[i], T[i], T[i + 1], L[i + 1]), "fur_light"))
        faces.append(((R[i], R[i + 1], T[i + 1], T[i]), "fur_light"))
    # 两端封口（埋在颅骨里，看不见，但保证是封闭体）
    faces.append(((L[0], R[0], T[0]), "fur_light"))
    faces.append(((L[-1], T[-1], R[-1]), "fur_light"))
    # 底面（同样埋进颅骨）
    n = len(ridge)
    for i in range(n - 1):
        faces.append(((L[i], L[i + 1], R[i + 1], R[i]), "fur_light"))
    faces.append(((L[0], R[0], R[-1], L[-1]), "fur_light"))
    return build_object("DSMonkeyTuft", verts, faces)


# =====================================================================
# 5. 表面查询（五官全部贴到真正的低模棱面上）
# =====================================================================
def make_bvh(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.transform(ob.matrix_world)
    bvh = BVHTree.FromBMesh(bm)
    bm.free()
    return bvh


def hit(bvh, origin, direction):
    loc, nor, idx, dist = bvh.ray_cast(origin, direction)
    if loc is None:
        raise RuntimeError("ray miss")
    if nor.dot(direction) > 0:
        nor = -nor
    return loc, nor


def front_point(bvh, x, z, off):
    """正面平行投影打到颅骨上，再沿 +Y（朝镜头）抬起 off。
    ⚠️ +Y 才是"脸外面"；写成 −Y 会把细线半埋、把纯平面填充整块埋进去。"""
    loc, nor = hit(bvh, Vector((x, 1.5, z)), Vector((0.0, -1.0, 0.0)))
    return loc + Vector((0.0, 1.0, 0.0)) * off


def face_plane(bvh, x, z, r):
    """在 (x,z) 附近扫一圈，返回 (贴片中心, 平均法线)。
    法线用一圈采样平均 —— 贴片按这个平面倾斜，才能贴着脸又不陷进去。"""
    ctr, _ = hit(bvh, Vector((x, 1.5, z)), Vector((0.0, -1.0, 0.0)))
    ns = Vector((0.0, 0.0, 0.0))
    for k in range(16):
        a = 2.0 * math.pi * k / 16.0
        for rr in (0.5, 1.0):
            _, nor = hit(bvh, Vector((x + r * rr * math.cos(a), 1.5,
                                      z + r * rr * math.sin(a))),
                         Vector((0.0, -1.0, 0.0)))
            ns += nor
    return ctr, ns.normalized()


def plane_frame(n):
    """贴片平面标架：u≈+X、v≈+Z，并把 u/v 拉长到「正面投影正好是单位长度」，
    于是斜着贴的圆片在正面视图里仍然是正圆。"""
    u = Vector((1.0, 0.0, 0.0))
    u = (u - n * u.dot(n)).normalized()
    v = Vector((0.0, 0.0, 1.0))
    v = (v - n * v.dot(n)).normalized()
    u *= 1.0 / max(0.35, math.hypot(u.x, u.z))
    v *= 1.0 / max(0.35, math.hypot(v.x, v.z))
    return u, v


def shell_disc(verts, faces, bvh, x, z, radius, off, slot, segs=24,
               rings=(0.42, 0.72, 1.0)):
    """正面投影的圆片（单面，法线朝 +Y）：每个顶点先打到颅骨真实棱面上、再沿法线抬起 off。
    正面轮廓严格是圆，同时贴着脸走 —— 三层用不同 off 就绝不会互相穿插。"""
    def ring_pt(px, pz):
        loc, nor = hit(bvh, Vector((px, 1.5, pz)), Vector((0.0, -1.0, 0.0)))
        return loc + nor * off

    ctr_i = len(verts)
    verts.append(ring_pt(x, z))
    prev = []
    first = None
    for rr in rings:
        cur = []
        for k in range(segs):
            a = 2.0 * math.pi * k / segs
            cur.append(len(verts))
            verts.append(ring_pt(x + radius * rr * math.cos(a),
                                 z + radius * rr * math.sin(a)))
        if first is None:
            first = cur
            for k in range(segs):
                faces.append(((ctr_i, cur[(k + 1) % segs], cur[k]), slot))
        else:
            for k in range(segs):
                k2 = (k + 1) % segs
                faces.append(((prev[k], prev[k2], cur[k2], cur[k]), slot))
        prev = cur


def flat_disc(verts, faces, x, z, y, radius, slot, segs=20):
    """纯平圆片（朝 +Y）：瞳孔 / 高光用，轮廓是干净的正圆、不会有棱面明暗块"""
    ctr = len(verts)
    verts.append(Vector((x, y, z)))
    ring = []
    for k in range(segs):
        a = 2.0 * math.pi * k / segs
        ring.append(len(verts))
        verts.append(Vector((x + radius * math.cos(a), y, z + radius * math.sin(a))))
    for k in range(segs):
        faces.append(((ctr, ring[(k + 1) % segs], ring[k]), slot))


def surface_front_y(bvh, x, z, r):
    """(x,z) 周围一圈里**最靠前**（+Y 最大）的颅面 y —— 平面贴片放它前面就绝不会被顶穿。
    ⚠️ 相机在 +Y 看向 −Y，所以 +Y 才是「前面」；写反了贴片会整块埋进脸里。"""
    best = -1e9
    for k in range(20):
        a = 2.0 * math.pi * k / 20.0
        for rr in (0.0, 0.5, 0.85, 1.0):
            loc, _ = hit(bvh, Vector((x + r * rr * math.cos(a), 1.5,
                                      z + r * rr * math.sin(a))),
                         Vector((0.0, -1.0, 0.0)))
            best = max(best, loc.y)
    return best


def flat_plate(verts, faces, ctr, n, u, v, half_len, half_thick, ang, slot, depth=0.0018):
    ca, sa = math.cos(ang), math.sin(ang)
    inner, outer = [], []
    for lx, lz in ((-half_len, -half_thick), (half_len, -half_thick),
                   (half_len, half_thick), (-half_len, half_thick)):
        p = ctr + u * (lx * ca - lz * sa) + v * (lx * sa + lz * ca)
        inner.append(len(verts))
        verts.append(p + n * 0.0008)
        outer.append(len(verts))
        verts.append(p + n * depth)
    faces.append((tuple(inner), slot))
    for i in range(4):
        i2 = (i + 1) % 4
        faces.append(((inner[i], inner[i2], outer[i2], outer[i]), slot))


def recenter(ob, pivot):
    """把网格顶点平移到以 pivot 为原点，并把物体放到 pivot。
    这样每个五官零件都有自己的枢轴，动画可以直接转它 / 移它。"""
    p = Vector(pivot)
    for v in ob.data.vertices:
        v.co -= p
    ob.location = p
    return ob


def make_part(name, verts, faces, pivot, recalc=True):
    return recenter(build_object(name, verts, faces, recalc=recalc), pivot)


def surf_at(bvh, x, z):
    return hit(bvh, Vector((x, 1.5, z)), Vector((0.0, -1.0, 0.0)))[0]


def build_eye_parts(bvh):
    """眼白 / 瞳孔+高光 各做一个物体（左右分开），笑的时候整只换成「眯眼弧」。"""
    out = []
    for side in (1, -1):
        tag = "L" if side < 0 else "R"
        x = EYE_X * side
        verts, faces = [], []
        # ⚠️ 抬高量不能只有 1.5 mm：脸是**曲面**，眼白外缘（半径 28 mm）比中心
        # 靠后约 1.9 mm（r²/2R，R≈0.21 m），1.5 mm 的抬高会让**外缘被脸切掉**，
        # 眼睛看着比参考图小一圈、边缘发暗。抬到 3.5 mm，整片眼白才完整露出来。
        shell_disc(verts, faces, bvh, x, EYE_Z, SCLERA_R, 0.0035, "sclera",
                   segs=10, rings=(0.62, 1.0))
        out.append(make_part("DSMonkeyEye_" + tag, verts, faces,
                             surf_at(bvh, x, EYE_Z), recalc=False))

        px = x - PUPIL_IN * side
        y0 = surface_front_y(bvh, px, EYE_Z, PUPIL_R)
        verts, faces = [], []
        flat_disc(verts, faces, px, EYE_Z, y0 + 0.0036, PUPIL_R, "pupil", segs=10)
        flat_disc(verts, faces, px + GLINT_OFF[0], EYE_Z + GLINT_OFF[1],
                  y0 + 0.0046, GLINT_R, "glint", segs=6)
        out.append(make_part("DSMonkeyPupil_" + tag, verts, faces,
                             (px, y0 + 0.0036, EYE_Z), recalc=False))

        # 眯眼弧（笑）：向上拱的一道短弧，比眼白窄一点
        verts, faces = [], []
        arc = [(-0.024, -0.0030), (-0.013, 0.0056), (0.0, 0.0090),
               (0.013, 0.0056), (0.024, -0.0030)]
        path = [front_point(bvh, x + dx, EYE_Z + dz, -0.0022) for dx, dz in arc]
        tube(verts, faces, path, 0.0042, "mark", sides=4)
        out.append(make_part("DSMonkeyEyeShut_" + tag, verts, faces,
                             surf_at(bvh, x, EYE_Z), recalc=True))
    return out


def build_mouth_parts(bvh):
    """三个嘴：中性微笑（常驻）/ 大笑张开 / 惊恐 O 型。后两个静止时停在颅骨里面。"""
    out = []

    # --- 中性微笑：原来的弧线 ---
    verts, faces = [], []
    path = [front_point(bvh, q.x, q.y, -0.0022) for q in catmull_rom(MOUTH_PTS, 2)]
    n = len(path)
    radius = [MOUTH_R * (0.70 + 0.30 * math.sin(math.pi * i / (n - 1.0)))
              for i in range(n)]
    tube(verts, faces, path, radius, "mark", sides=4)
    c = Vector((0.0, 0.0, 0.0))
    for q in path:
        c += q
    out.append(make_part("DSMonkeyMouthSmile", verts, faces, c / n, recalc=True))

    # --- 大笑张开：宽嘴，外圈描边 + 暗腔 + 舌头 ---
    laugh = [(0.050, -0.087), (0.038, -0.075), (0.020, -0.067), (0.0, -0.064),
             (-0.020, -0.067), (-0.038, -0.075), (-0.050, -0.087),
             (-0.044, -0.105), (-0.026, -0.119), (0.0, -0.124),
             (0.026, -0.119), (0.044, -0.105)]
    out.append(make_part("DSMonkeyMouthLaugh",
                         *mouth_mesh(bvh, laugh, "mouth", "mark", 0.0042,
                                     tongue=[(0.028, -0.106), (0.012, -0.118),
                                             (-0.012, -0.118), (-0.028, -0.106),
                                             (0.0, -0.111)]),
                         surf_at(bvh, 0.0, -0.094)))

    # --- 惊恐：竖 O 型 ---
    fear = [(0.0, -0.068), (0.016, -0.080), (0.019, -0.096), (0.010, -0.108),
            (-0.010, -0.108), (-0.019, -0.096), (-0.016, -0.080)]
    out.append(make_part("DSMonkeyMouthFear",
                         *mouth_mesh(bvh, fear, "mouth", "mark", 0.0040),
                         surf_at(bvh, 0.0, -0.088)))
    return out


def tube(verts, faces, path, radii, slot, sides=5):
    """沿一条折线扫 n 棱管（半径给标量或逐点列表），两端用扇面封口。"""
    pts = [Vector(p) for p in path]
    if isinstance(radii, (int, float)):
        radii = [float(radii)] * len(pts)
    rings = []
    for i, p in enumerate(pts):
        if i == 0:
            t = pts[1] - pts[0]
        elif i == len(pts) - 1:
            t = pts[-1] - pts[-2]
        else:
            t = pts[i + 1] - pts[i - 1]
        t = t.normalized()
        ref = Vector((0.0, 0.0, 1.0))
        if abs(t.dot(ref)) > 0.9:
            ref = Vector((0.0, 1.0, 0.0))
        u = t.cross(ref).normalized()
        v = t.cross(u).normalized()
        r = radii[i]
        idx = []
        for k in range(sides):
            a = 2.0 * math.pi * k / sides
            idx.append(len(verts))
            verts.append(p + u * (r * math.cos(a)) + v * (r * math.sin(a)))
        rings.append(idx)
    for j in range(len(rings) - 1):
        ra, rb = rings[j], rings[j + 1]
        for k in range(sides):
            k2 = (k + 1) % sides
            faces.append(((ra[k], ra[k2], rb[k2], rb[k]), slot))
    ci = len(verts)
    verts.append(pts[0])
    for k in range(sides):
        faces.append(((ci, rings[0][(k + 1) % sides], rings[0][k]), slot))
    ci = len(verts)
    verts.append(pts[-1])
    for k in range(sides):
        faces.append(((ci, rings[-1][k], rings[-1][(k + 1) % sides]), slot))


def mouth_mesh(bvh, outline, slot_fill, slot_lip, rim, tongue=None):
    """把一张 (x, z) 轮廓做成"贴脸上的洞"：腔底 + 外圈描边 + 可选舌头。"""
    verts, faces = [], []
    pts = [Vector(q) for q in outline]
    # 有向面积 < 0 说明是顺时针，翻过来，保证填充面朝 +Y
    area = 0.0
    for i in range(len(pts)):
        x0, z0 = pts[i]
        x1, z1 = pts[(i + 1) % len(pts)]
        area += x0 * z1 - x1 * z0
    if area < 0.0:
        pts.reverse()
    # 腔底：每个轮廓点打到颅面，**朝镜头方向**抬一点点。
    # ⚠️ 写成负的（往里压）整块暗腔会埋进脸里，渲染出来只剩一圈描边。
    # ⚠️ 填充用**中心扇形**而不是一个大 n 边形：轮廓点落在曲面上不是共面的，
    #    一个 12 边形让 Blender 自由三角化会得到乱糟糟的形状。
    fill = []
    for q in pts:
        loc, nor = hit(bvh, Vector((q.x, 1.5, q.y)), Vector((0.0, -1.0, 0.0)))
        fill.append(len(verts))
        verts.append(loc + nor * 0.0012)
    cc = Vector((0.0, 0.0))
    for q in pts:
        cc += q
    cc /= len(pts)
    loc, nor = hit(bvh, Vector((cc.x, 1.5, cc.y)), Vector((0.0, -1.0, 0.0)))
    ci = len(verts)
    verts.append(loc + nor * 0.0012)
    n = len(fill)
    for i in range(n):
        faces.append(((ci, fill[i], fill[(i + 1) % n]), slot_fill))
    # 外圈描边：沿轮廓扫一根细管
    path = [front_point(bvh, q.x, q.y, -0.0016) for q in pts]
    tube(verts, faces, path, rim, slot_lip, sides=4)
    # 舌头：比腔底浅一点
    if tongue:
        tfill = []
        for q in tongue:
            loc, nor = hit(bvh, Vector((q[0], 1.5, q[1])), Vector((0.0, -1.0, 0.0)))
            tfill.append(len(verts))
            verts.append(loc + nor * 0.0022)
        tc = Vector((0.0, 0.0))
        for q in tongue:
            tc += Vector(q)
        tc /= len(tongue)
        loc, nor = hit(bvh, Vector((tc.x, 1.5, tc.y)), Vector((0.0, -1.0, 0.0)))
        ci = len(verts)
        verts.append(loc + nor * 0.0022)
        n = len(tfill)
        for i in range(n):
            faces.append(((ci, tfill[i], tfill[(i + 1) % n]), "tongue"))
    return verts, faces


def build_mark_parts(bvh):
    """眉毛（贴面的细管）+ 鼻孔（两片小扁片）。"""
    out = []
    for side in (1, -1):
        tag = "L" if side < 0 else "R"
        verts, faces = [], []
        # 内端高、外端低的一道斜杠（参考图眉毛就是斜的）
        dz = math.tan(BROW_TILT) * BROW_LEN * 0.5
        arc = []
        for i in range(5):
            u = i / 4.0
            x = BROW_X * side + (u - 0.5) * BROW_LEN * side
            z = BROW_Z + dz * (1.0 - 2.0 * u)
            arc.append(front_point(bvh, x, z, -0.0016))
        tube(verts, faces, arc, BROW_THICK * 0.5, "mark", sides=4)
        c = Vector((0.0, 0.0, 0.0))
        for q in arc:
            c += q
        out.append(make_part("DSMonkeyBrow_" + tag, verts, faces, c / len(arc),
                             recalc=True))
    # 鼻孔：两片小扁片
    verts, faces = [], []
    for side in (1, -1):
        c = front_point(bvh, NOSTRIL_X * side, NOSTRIL_Z, 0.0)
        flat_plate(verts, faces, c, Vector((0.0, 1.0, 0.0)),
                   Vector((1.0, 0.0, 0.0)), Vector((0.0, 0.0, 1.0)),
                   0.0068, 0.0028, math.radians(-14.0 * side), "mark", 0.0014)
    out.append(make_part("DSMonkeyNostrils", verts, faces,
                         (0.0, 0.0, NOSTRIL_Z), recalc=True))
    return out


# =====================================================================
# 6. 耳朵（挖了坑的盘：外圈厚毛边 + 凹进去的橘色盘底）
# =====================================================================
def build_ear(side):
    """挖了坑的盘：外圈厚毛边 + 凹进去的橘色盘底。
    轮廓半径逐段微抖（EAR_VAR），避免读成一个规整的多边形垫圈；
    盘底整体往上偏一点，于是下缘的毛边比上缘厚 —— 和参考图一致。"""
    n = Vector((EAR_N.x * side, EAR_N.y, EAR_N.z)).normalized()
    up = Vector((0.0, 0.0, 1.0))
    e2 = (up - n * up.dot(n)).normalized()
    e1 = e2.cross(n).normalized()
    C = Vector((EAR_X * side, EAR_Y, EAR_Z))

    # (椭圆 x 系数, y 系数, 沿法线的深度)：耳窝是**竖长**的（参考图投影 0.04 x 0.08 m）
    rings = [(1.00, 1.00, -0.014), (1.00, 1.00, 0.002), (0.95, 0.96, 0.010),
             (0.88, 0.92, 0.014), (0.76, 0.86, 0.008), (0.56, 0.80, 0.003)]
    slot_of = ["fur", "fur_light", "fur_light", "fur_light", "ear_in"]
    EAR_VAR = [1.00, 0.975, 1.02, 0.985, 1.015, 0.99, 1.005, 0.97, 1.01]
    NSEG = 8
    UP_SHIFT = 0.14                        # 盘底往上偏（相对 EAR_RY）
    verts, faces, ring_idx = [], [], []
    for (fx, fy, d) in rings:
        idx = []
        lift = UP_SHIFT * EAR_RY * max(0.0, (1.0 - fy) / 0.6)
        for k in range(NSEG):
            a = 2.0 * math.pi * k / NSEG
            var = EAR_VAR[k % len(EAR_VAR)]
            idx.append(len(verts))
            verts.append(C + e1 * (EAR_RX * fx * var * math.cos(a))
                         + e2 * (EAR_RY * fy * var * math.sin(a) + lift) + n * d)
        ring_idx.append(idx)
    ctr = len(verts)
    verts.append(C + e2 * (UP_SHIFT * EAR_RY) + n * 0.0020)
    for j in range(len(rings) - 1):
        for k in range(NSEG):
            k2 = (k + 1) % NSEG
            faces.append(((ring_idx[j][k], ring_idx[j][k2],
                           ring_idx[j + 1][k2], ring_idx[j + 1][k]), slot_of[j]))
    for k in range(NSEG):
        k2 = (k + 1) % NSEG
        faces.append(((ring_idx[-1][k], ring_idx[-1][k2], ctr), "ear_in"))
    # ⚠️ **背面必须封口**：耳朵是个"碗"，碗口朝前（+n）。不封背面的话，
    # 从脑后看进去直接看见碗底的**橘色耳窝**，耳朵正反面分不清（实测）。
    # 封一个朝 −n 的棕色（fur）扇面：背面 = 棕毛，正面 = 橘耳窝。
    back = len(verts)
    verts.append(C + e2 * (UP_SHIFT * EAR_RY) - n * 0.004)
    for k in range(NSEG):
        k2 = (k + 1) % NSEG
        faces.append(((back, ring_idx[0][k2], ring_idx[0][k]), "fur"))

    name = "DSMonkeyEar_L" if side < 0 else "DSMonkeyEar_R"
    return build_object(name, verts, faces)


# =====================================================================
# 7. 组装（五官拆成可动零件）+ 表情动画
# =====================================================================
head = build_skull()
tuft = build_tuft()
bvh = make_bvh(head)
eye_parts = build_eye_parts(bvh)
mouth_parts = build_mouth_parts(bvh)
mark_parts = build_mark_parts(bvh)
ear_l = build_ear(-1)
ear_r = build_ear(+1)

STATIC = [head, tuft, ear_l, ear_r]
HIDDEN = ["DSMonkeyMouthLaugh", "DSMonkeyMouthFear",
          "DSMonkeyEyeShut_L", "DSMonkeyEyeShut_R"]     # 静止时藏在颅骨内部
PARK = Vector((0.0, -0.060, 0.0))                       # 往脑袋里退 6 cm = 看不见

MESHES = STATIC + eye_parts + mouth_parts + mark_parts
OBJ = {ob.name: ob for ob in MESHES}
for ob in MESHES:
    if ob is not head:
        ob.parent = head
for nm in HIDDEN:                                       # 默认藏起来（位置，不是 scale）
    ob = OBJ[nm]
    ob.location = ob.location + PARK

bpy.ops.object.select_all(action='DESELECT')
for ob in MESHES:
    ob.select_set(True)
bpy.context.view_layer.objects.active = head
bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)


# ---------------------------------------------------------------
# 7.1 两段表情动画：DSMonkey_Laugh（笑）/ DSMonkey_Fear（惊恐）
# ---------------------------------------------------------------
SHOW = (0.0, 0.060, 0.0)          # 从颅骨里推到脸上（和 PARK 相反）
HIDE = (0.0, -0.060, 0.0)

def nod(a):
    return {"rot": (a, 0.0, 0.0)}

def brow_up(side, dz, tilt):
    tag = "L" if side < 0 else "R"
    return {"loc": (0.0, 0.0, dz), "rot": (0.0, tilt * side, 0.0)}

# 笑：3 次「哈」，头跟着点、耳朵抖、眼睛眯成弧、嘴换成张开的笑
LAUGH = (48, [
    (1, {}),
    (3, {"DSMonkeyMouthSmile": {"loc": HIDE}, "DSMonkeyMouthLaugh": {"loc": SHOW},
         "DSMonkeyEye_L": {"loc": HIDE}, "DSMonkeyEye_R": {"loc": HIDE},
         "DSMonkeyPupil_L": {"loc": HIDE}, "DSMonkeyPupil_R": {"loc": HIDE},
         "DSMonkeyEyeShut_L": {"loc": SHOW}, "DSMonkeyEyeShut_R": {"loc": SHOW},
         "DSMonkeyBrow_L": brow_up(-1, 0.011, -0.14),
         "DSMonkeyBrow_R": brow_up(+1, 0.011, -0.14),
         "DSMonkeyEar_L": {"rot": (0.0, 0.16, 0.0)},
         "DSMonkeyEar_R": {"rot": (0.0, -0.16, 0.0)},
         "DSMonkeyHead": nod(-0.075)}),
    (7, {"DSMonkeyHead": nod(0.035),
         "DSMonkeyEar_L": {"rot": (0.0, 0.06, 0.0)},
         "DSMonkeyEar_R": {"rot": (0.0, -0.06, 0.0)}}),
    (11, {"DSMonkeyMouthLaugh": {"loc": SHOW}, "DSMonkeyHead": nod(-0.075),
          "DSMonkeyEar_L": {"rot": (0.0, 0.16, 0.0)},
          "DSMonkeyEar_R": {"rot": (0.0, -0.16, 0.0)}}),
    (15, {"DSMonkeyHead": nod(0.035),
          "DSMonkeyEar_L": {"rot": (0.0, 0.06, 0.0)},
          "DSMonkeyEar_R": {"rot": (0.0, -0.06, 0.0)}}),
    (19, {"DSMonkeyMouthLaugh": {"loc": SHOW}, "DSMonkeyHead": nod(-0.070),
          "DSMonkeyEar_L": {"rot": (0.0, 0.15, 0.0)},
          "DSMonkeyEar_R": {"rot": (0.0, -0.15, 0.0)}}),
    (23, {"DSMonkeyHead": nod(0.030),
          "DSMonkeyEar_L": {"rot": (0.0, 0.05, 0.0)},
          "DSMonkeyEar_R": {"rot": (0.0, -0.05, 0.0)}}),
    (27, {"DSMonkeyMouthLaugh": {"loc": SHOW}, "DSMonkeyHead": nod(-0.055),
          "DSMonkeyEar_L": {"rot": (0.0, 0.10, 0.0)},
          "DSMonkeyEar_R": {"rot": (0.0, -0.10, 0.0)}}),
    (33, {"DSMonkeyHead": nod(-0.010)}),
    (40, {"DSMonkeyBrow_L": brow_up(-1, 0.004, -0.05),
          "DSMonkeyBrow_R": brow_up(+1, 0.004, -0.05)}),
    (47, {}),                                   # 回到静止（嘴/眼自动换回去）
])

# 惊恐：眉毛窜高、嘴变 O、耳朵向后压、头往后仰 + 发抖
FEAR = (36, [
    (1, {}),
    (3, {"DSMonkeyMouthSmile": {"loc": HIDE}, "DSMonkeyMouthFear": {"loc": SHOW},
         "DSMonkeyBrow_L": {"loc": (0.0, 0.0, 0.019), "rot": (0.0, -0.42, 0.0)},
         "DSMonkeyBrow_R": {"loc": (0.0, 0.0, 0.019), "rot": (0.0, 0.42, 0.0)},
         "DSMonkeyPupil_L": {"loc": (0.004, 0.0, 0.002)},
         "DSMonkeyPupil_R": {"loc": (-0.004, 0.0, 0.002)},
         "DSMonkeyEar_L": {"rot": (0.0, -0.34, 0.25)},
         "DSMonkeyEar_R": {"rot": (0.0, 0.34, -0.25)},
         "DSMonkeyHead": {"rot": (-0.10, 0.0, 0.0)}}),
    (6, {"DSMonkeyHead": {"rot": (-0.10, 0.0, 0.018)}}),
    (9, {"DSMonkeyHead": {"rot": (-0.10, 0.0, -0.018)}}),
    (12, {"DSMonkeyHead": {"rot": (-0.10, 0.0, 0.016)}}),
    (15, {"DSMonkeyHead": {"rot": (-0.10, 0.0, -0.016)}}),
    (18, {"DSMonkeyHead": {"rot": (-0.10, 0.0, 0.014)},
          "DSMonkeyEar_L": {"rot": (0.0, -0.34, 0.18)},
          "DSMonkeyEar_R": {"rot": (0.0, 0.34, -0.18)}}),
    (21, {"DSMonkeyHead": {"rot": (-0.10, 0.0, -0.014)},
          "DSMonkeyEar_L": {"rot": (0.0, -0.34, 0.30)},
          "DSMonkeyEar_R": {"rot": (0.0, 0.34, -0.30)}}),
    (24, {"DSMonkeyHead": {"rot": (-0.10, 0.0, 0.010)}}),
    (30, {"DSMonkeyHead": {"rot": (-0.06, 0.0, 0.0)}}),
    (35, {}),
])

CLIPS = {"Laugh": LAUGH, "Fear": FEAR}      # 片段名由调用方加前缀

for act in list(bpy.data.actions):
    bpy.data.actions.remove(act)

def action_fcurves(act):
    """Blender 4.4+ 的 slotted action：fcurve 在 channelbag 里，不在 act.fcurves"""
    try:
        return list(act.fcurves)
    except Exception:
        pass
    out = []
    for layer in act.layers:
        for strip in layer.strips:
            for cb in strip.channelbags:
                out.extend(cb.fcurves)
    return out


def build_clip(name, length, keys):
    """每个物体**只在自己被点名的那几帧**打关键帧；首帧和末帧各补一帧回中性。

    ⚠️ 千万不能"这一帧没点名就回静止"：笑嘴在第 3 帧被藏进去，如果第 7 帧没点名又给
    它打回静止位，笑嘴就会从脸里滑回来 —— 表现出来正是「张嘴的笑 + 中性笑弧」两张嘴同框。
    换脸用 CONSTANT 插值（瞬切），否则两个嘴在过渡的那一帧会同时露一半。"""
    last = max(f for f, _ in keys) - 1
    touched = set()
    for _, pose in keys:
        touched |= set(pose)
    for nm in sorted(touched):
        ob = OBJ[nm]
        base_l = Vector(ob.location)
        base_r = Vector(ob.rotation_euler)
        pts = {}
        for f, pose in keys:
            if nm in pose:
                pts[f - 1] = pose[nm]
        pts.setdefault(0, {})
        pts[last] = {}
        ad = ob.animation_data_create()
        act = bpy.data.actions.new("%s_%s" % (name, nm))
        act.use_fake_user = True
        ad.action = act
        for f in sorted(pts):
            p = pts[f]
            ob.location = base_l + Vector(p.get("loc", (0.0, 0.0, 0.0)))
            ob.rotation_euler = base_r + Vector(p.get("rot", (0.0, 0.0, 0.0)))
            ob.keyframe_insert("location", frame=f)
            ob.keyframe_insert("rotation_euler", frame=f)
        ad.action = None
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
        tr.mute = True
        ob.location = base_l
        ob.rotation_euler = base_r


def build_clips(clipmap=None):
    """clipmap: {片段名: (帧数, 关键帧表)}；默认用本模块的 CLIPS。
    片段名同时是 NLA track 名 = 导出后 Godot 里的 AnimationPlayer 动画名。"""
    clipmap = clipmap or CLIPS
    for nm, (length, keys) in clipmap.items():
        build_clip(nm, length, keys)
    bpy.context.scene.frame_end = max(l[0] for l in clipmap.values())
    return clipmap


REST_LOC = {ob.name: Vector(ob.location) for ob in MESHES}
REST_ROT = {ob.name: Vector(ob.rotation_euler) for ob in MESHES}


def apply_pose(pose):
    """把某个关键帧的姿势直接摆上去（预览表情用）"""
    for ob in MESHES:
        ob.location = REST_LOC[ob.name]
        ob.rotation_euler = REST_ROT[ob.name]
    for nm, p in pose.items():
        ob = OBJ[nm]
        ob.location = ob.location + Vector(p.get("loc", (0.0, 0.0, 0.0)))
        r = p.get("rot", (0.0, 0.0, 0.0))
        ob.rotation_euler.x += r[0]
        ob.rotation_euler.y += r[1]
        ob.rotation_euler.z += r[2]



# =====================================================================

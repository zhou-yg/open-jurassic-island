"""Low-poly 鸟巢山 (nest mountain) generator.

用法:
    blender --background --python low_poly_nest_mountain.py
    blender --background --python low_poly_nest_mountain.py -- --nopreview
    blender --background --python low_poly_nest_mountain.py -- --nonest

产物（写入本目录）:
    low_poly_nest_mountain.blend
    low_poly_nest_mountain.glb          <- 只有山体（山顶留了鸟巢坑）
    low_poly_nest_mountain_preview.png  <- 2x2 拼图：3/4 视角（有/无占位鸟巢）/ 俯视 / 洞口特写
    low_poly_nest_mountain_cave.png     <- 山脚 + 山腰两个洞口
    low_poly_nest_mountain_top.png      <- 山顶鸟巢预留区俯视

> 复现性：高度场用固定种子的 fbm，造型是**逐位可复现**的（两次运行的
> POSITION / NORMAL / COLOR_0 完全一致）。但导出的 .glb **字节可能不同** ——
> bmesh 的 remove_doubles / triangulate 的遍历顺序取决于内部哈希，
> 所以三角面索引的排列每次会变。几何与颜色一样，只是面的顺序不同。

造型（对照 assets/AGENTS.md §1 的米制约定）
--------------------------------------------
* 山脚占地 ≈ 97 m，主峰(山顶边缘岩唇) ≈ 53 m，海/地面 z = 0，原点在山体中心。
* 由下到上分四层，每层之间是陡岩壁（低多边形的平顶台地感）：
    1. 山脚 0–8 m    沙滩 + 草坡，岩壁上有 **山脚山洞**（洞口中心 ≈ z 9.7）
    2. 山腰 8–24 m   梯田式草台，台缘为裸岩；**山腰山洞**开在这里（洞口中心 ≈ z 19.5）
    3. 上层 24–46 m  裸岩陡壁 + 几条草脊
    4. 山顶 46–51.5 m 一整块平顶，中间是 **鸟巢预留坑**（口 Ø 11.5 m，深 7.5 m）

这一版解决的问题（"颜色很突兀 + 整体形状很刺眼"）
--------------------------------------------------
**颜色**：上一版是"奶油白岩冠 + 饱和草绿"的硬碰硬 —— 两族颜色各自都好看，
撞在一起就刺眼；而且山脚最暗 0.21、峰顶最亮 0.74，明度跨度 0.53，
整座山的明度骨架读成"一根锥子"。现在：
    - **压饱和**：所有色的 chroma 收到 ≈0.13~0.15。林子是鼠尾草绿，
      石头是被晒过的暖灰砂岩（不再往奶油白走）。
    - **收明度跨度**：最深 0.23、最亮 0.66，跨度 0.43。
    - **加过渡带**：绿和石之间插一段灌丛（rock → scrub → veg 三段混合），
      台地边缘不再是"绿色地毯拍在米色石头上"。
    - **林线下移到 30~38 m**：38 m 以上是裸岩，山因此分成"上岩壁 / 下林坡"两段，
      峰顶不再是一整块土黄的糊状色块。
    - 斑驳 / 等高层理 / 冷暖分离的幅度全部收窄，避免"一圈圈描边"。

**形状**：上一版的剪影是个圆滑的钟形（"面包山"），台地立面 71° 陡坎
被减面切成一圈圈碎齿，岸线处还挂着一排又长又薄的"鱼鳍"三角。现在：
    - 剖面重排：峰顶岩唇下面立刻跟上 57° 的崖（峰是"削"出来的），
      山腰留一档平台，rn 0.69 再给一道 59° 的主崖。
    - 台地立面从 71° 放缓到 ~55°，步长 7.5 → 8.5 m。
    - 台地强度 0.42~1.00 → 0.30~0.85；冲沟放宽变浅，只切到 40 m 以下。
    - 不对称（西南陡 / 东北缓）作用带放宽到 12~48 m，幅度加大，
      剪影才有"一面崖、一面坡"的分量；主山脊加高。
    - 岸线收在 rn 1.0：陆地到此为止，水下是一圈 72° 竖壁直插 −9 m，
      岸线是一整圈干净的环，不再有"鱼鳍"。
* 颜色全部烘进顶点色 "Col"（线性空间），一个材质一次 draw call。
* 顶点色**按棱面（平面）上色，不按三角面上色**：同一平面的三角形必须同色，
  否则面内碎成脏斑（见 plane_groups()）。

山洞（山脚 / 山腰各一个）
--------------------------
* 洞口位置不是写死的：在高度场上沿径向采样，找出**连续的那段陡崖**，
  洞口取崖面正中，**洞半径按崖面高度反推**（崖面多高洞就能开多大）。
  早先的版本拿射线去"碰"崖壁，很容易落在台地的棱上 —— 台地立面只有 1~2 m 厚，
  3 m 半径的洞一刀下去就把台子啃穿了，洞口糊成一团看不出是洞的黑窟窿。
* 洞体用一根**正圆柱**直接布尔切出来，切口是平整的一圈圆（口沿不加任何石块），
  切进去是直筒，洞底再扩一间石室（石室半径按崖面上方净空算，净空不够就只留直筒）。
  想要石头就单独摆 `low_poly_rock.glb`。
* 切之前在切口周围局部加密，避免粗三角形把圆沿切成锯齿。

山顶的鸟巢只做了 **预览占位**（对象名 `NestPlaceholder`）：
    - 它会存进 .blend 方便看比例，但 **不导出到 .glb**（GLB 只有山）。
    - 游戏里真正的鸟巢建议单独做成资产，摆在预留坑里。
    - 加 --nonest 可以不生成它。
"""

import math
import os
import random
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
NAME = "low_poly_nest_mountain"

# ==================== 尺寸（米，1 Blender unit = 1 m）====================
SIZE_M = 100.0            # 山脚占地跨度（含浅浅的水下裙边）
N = 151                   # 高度场分辨率（先密后减面，低多边形的块面靠 decimate 出来）
PEAK_H_M = 51.5           # 主峰高度 = 山顶岩唇顶面
NEST_R_M = 5.75           # 山顶鸟巢坑口半径（Ø 11.5 m）
NEST_FLOOR_M = 44.0       # 鸟巢坑底高度
PLATEAU_R_M = 11.5        # 山顶平台半径（平台外缘开始下落）
CAVE_R_M = 2.3            # 洞口半径
CAVE_DEPTH_M = 6.5        # 洞深
SEA_BOT_M = -9.0          # 水下裙边底部
TARGET_TRIS = 4000        # 山体目标三角面数（低多边形，但台阶要够多面才立得起来）
SEED = 20240731

# 梯田参数：高度场和顶点色两处共用同一份（assets/AGENTS.md §6 的"单一常量源"）。
# WARP 把台地边界推来推去，让台阶是断断续续的舌状，而不是一圈圈规整的等高线；
# STEP 是台地之间的高差，顶点色里的"等高层理"也按这个步长对齐。
# 这一版把步长从 7.5 m 拉到 8.5 m：台地少一圈、每圈更宽，
# 读起来是"山体的台阶"而不是"一圈圈等高线"。
TERRACE_STEP_M = 8.5
TERRACE_WARP_M = 9.0

# 高度剖面：rn = 归一化半径（0 = 山轴，1 = 岸线），值是高度（米）
# 折点故意留成硬拐角 —— 这些拐角就是"多层次"的台地/崖壁分界。
#
# 这一版重排了折点，为的是让剪影**不再是一个圆滑的钟形**：
#   * 峰顶岩唇下面立刻跟上 57° 的崖（rn 0.19→0.25），峰是"削"出来的，
#     不是"圆"出来的 —— 上一版 0.15→0.235 只掉 1.6 m，峰顶是个面包。
#   * rn 0.56 附近留一档平台（坡度 37°），山腰因此有一个能站人的台。
#   * rn 0.69 再给一道 59° 的主崖，山被切成"上岩壁 / 中台地 / 下坡"三段。
#   * **岸线收在 rn 1.0**：陆地到此为止（z≈0.2），再往外是一道 72° 的
#     水下陡壁直插到 −9 m。上一版把 5 m 的落差摊在 rn 0.94~1.0 之间，
#     减面之后岸线处留下一排又长又薄的"鱼鳍"三角 —— 水上露头、水下也看得见，
#     是"形状刺眼"最扎眼的一处。现在水下落差集中在一圈竖壁上，
#     水面之下一片干净，岸线是一整圈干净的环。
# 层次自上而下：山顶平台 → 上层岩壁 → 山腰大台地 → 山腰陡坡 → 山脚缓台地 → 沙滩
PROF_RN = np.array([0.000, 0.070, 0.115, 0.150, 0.190, 0.250, 0.310, 0.360,
                    0.430, 0.490, 0.560, 0.610, 0.690, 0.780, 0.870, 0.975,
                    1.000, 1.020, 1.045, 1.060])
PROF_H = np.array([NEST_FLOOR_M, NEST_FLOOR_M + 2.2, PEAK_H_M - 1.2, PEAK_H_M,
                   PEAK_H_M - 1.6, PEAK_H_M - 6.0, PEAK_H_M - 10.0, PEAK_H_M - 13.5,
                   PEAK_H_M - 19.5, PEAK_H_M - 23.0, PEAK_H_M - 25.5, PEAK_H_M - 27.5,
                   PEAK_H_M - 34.0, PEAK_H_M - 40.0, PEAK_H_M - 44.5, 1.2,
                   0.2, -3.0, -7.0, SEA_BOT_M])

# 冲沟（山体上的 V 形雨沟）：方位角°, 宽度 rad, 深度 m。避开两个洞口方位。
# 宽度放大、深度收浅 —— 沟是"折痕"而不是"裂口"，不然上部锥体会被切成一圈尖牙。
GULLIES = [(28.0, 0.34, 6.0), (196.0, 0.30, 5.0), (250.0, 0.26, 4.2),
           (86.0, 0.24, 3.6), (310.0, 0.23, 4.6)]


def angdiff(a, b):
    d = a - b
    return (d + math.pi) % (2 * math.pi) - math.pi

# 山洞：靠高度场找"立得住的崖面"，洞口取崖面正中，洞径按崖面高度反推。
#
# 早先的版本是拿射线去"碰"崖壁，结果很容易落在台地的棱上。台地的立面只有
# 1~2 m 厚（台面和上一个台面之间的那一层），3 m 半径的洞一刀下去就把台子
# 啃穿了，洞口糊成一团看不出是洞的黑窟窿。所以改成：先在高度场上沿径向
# 采样、找出连续的那段陡崖，再用崖面高度决定洞口半径 —— 洞一定塞得进墙。
CAVES = [
    dict(name="base", az=118.0, az_span=40.0, r_lo=26.0, r_hi=44.0,
         z_lo=3.0, z_hi=11.0, radius=2.3, depth=6.0, tilt=8.0),
    dict(name="mid", az=338.0, az_span=40.0, r_lo=14.0, r_hi=30.0,
         z_lo=11.0, z_hi=23.0, radius=2.1, depth=5.0, tilt=12.0),
]


# ==================== 颜色工具 ====================
def srgb2lin(c):
    c = np.asarray(c, dtype=float)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def smoothstep(a, b, x):
    """a → b 之间平滑过渡（a > b 表示反向）。"""
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def mix(c1, c2, t):
    return c1 * (1.0 - t) + c2 * t


# 调色板 —— "阳光下的热带岛山"（低饱和版）
#
# 这一版推翻上一版重做。上一版的毛病不是"太艳"也不是"太灰"，而是**两族颜色
# 挤在同一个浑浊的暖灰带里**：植被是卡其黄绿（0.36,0.46,0.28，R 太高 → 发土），
# 岩石是水泥灰（0.28~0.47，冷中性）。两者明度接近、色相接近，远看就是
# "长了一层苔藓的水泥山"，既没有丛林的生气，也没有石头的质感。
#
# 上一版修完那一版之后又走到了另一个极端：**太干净、太亮、太"卡通"**——
# 奶油白的岩冠（0.74/0.68/0.57）压在饱和的草绿（chroma 0.16）上，两块颜色
# 各自都好看，撞在一起就是"刺眼"；而且山脚最暗（0.21）、峰顶最亮（0.74），
# 明度跨度 0.53，整座山的明度骨架读成"一根锥子"，不是一座山。
#
# 现在的三个支点：
#
# 1) **压饱和**。所有色的 chroma 收到 ≈0.10~0.12：林子是鼠尾草绿，
#    石头是被晒过的暖灰砂岩。两族颜色仍然分得开（绿 vs 暖褐），
#    但不再是两个方块撞在一起。
#
# 2) **收明度跨度**。最深 0.25、最亮 0.69，跨度 0.44（上一版 0.53）。
#    山脚不再黑成一块、峰顶不再白成一块，"下重上轻"保留但不再刺眼。
#
# 3) **加过渡带**。绿和石之间不再是硬切：中间插一段灌丛 / 干苔
#    （见 colourise() 里的三段混合 rock → scrub → veg），
#    台地边缘因此有"灌木从台面翻下来"的层次，而不是"绿色地毯拍在米色石头上"。
PAL = {
    "sea_deep": srgb2lin([0.11, 0.22, 0.30]),
    "sea_shal": srgb2lin([0.32, 0.47, 0.50]),
    # 沙滩：暖白 + 湿沙的深一档
    "sand_l": srgb2lin([0.87, 0.80, 0.63]),
    "sand_d": srgb2lin([0.70, 0.61, 0.45]),
    "soil_l": srgb2lin([0.45, 0.34, 0.22]),
    "soil_d": srgb2lin([0.28, 0.21, 0.14]),
    # 植被：R ≈ B << G，这是"绿"和"黄绿"的分界线。
    # 饱和度是"上一版太艳 / 这一版太灰"的中间值：chroma ≈ 0.13~0.15。
    # 再压就成"橄榄绿泥浆"了 —— 山会读成一块脏抹布，而不是一座岛山。
    "jungle_d": srgb2lin([0.23, 0.35, 0.24]),   # 山脚的深林（最暗的一档）
    "jungle": srgb2lin([0.28, 0.42, 0.27]),     # 主体林色
    "jungle_l": srgb2lin([0.35, 0.48, 0.32]),   # 阳面林冠
    "fern": srgb2lin([0.44, 0.53, 0.33]),       # 山腰草坡
    "dry": srgb2lin([0.55, 0.52, 0.35]),        # 干草：绿 → 石的过渡色
    # 岩石：暖砂岩，但**不再往奶油白走**。上一版 rock_peak 是 0.74/0.68/0.57，
    # 在蓝天前就是一块刺眼的浅色疙瘩；现在峰顶压到 0.68/0.62/0.53，
    # 亮度降一档、但保留"被太阳晒过的砂岩"的暖调 ——
    # 再往灰里压就会变成"水泥山"（上一轮试过，太冷）。
    "rock_d": srgb2lin([0.45, 0.40, 0.33]),
    "rock_m": srgb2lin([0.54, 0.48, 0.41]),
    "rock_l": srgb2lin([0.62, 0.55, 0.46]),
    "rock_peak": srgb2lin([0.68, 0.62, 0.53]),
    # 岩缝里的浅苔：偏灰的绿，专治"岩冠一整块死板的浅色"
    "moss": srgb2lin([0.45, 0.47, 0.37]),
    "cave_in": srgb2lin([0.28, 0.25, 0.21]),
    "twig_l": srgb2lin([0.67, 0.55, 0.37]),
    "twig_m": srgb2lin([0.50, 0.40, 0.25]),
    "twig_d": srgb2lin([0.32, 0.25, 0.15]),
}

# 石头 / 林子的"同族变体"：只偏移色相或明度，不换色族。
#
# 石头用两种**暖**岩：晒白的砂岩 / 赭红的氧化岩。之前试过掺"青灰石"，
# 结果整片崖面被推成了发紫的灰浆色，既不像石头也不像土 —— 暖岩之间的差别
# 才是"地质感"，冷暖对撞只会脏。
#
# 幅度比上一版收了一半：上一版 SAND 偏黄 0.84、IRON 偏红 0.60，叠上去之后
# 岩冠被推成"奶油 + 铁锈"的花斑，远看发花。这一版只留一点点色相偏移。
STONE_SAND = np.array([1.10, 1.05, 0.90])   # 晒白的砂岩（偏黄、偏亮）
STONE_IRON = np.array([1.05, 0.86, 0.72])   # 赭红的氧化岩（偏红、偏暗）
# 林子：阴面偏冷偏暗、阳面偏暖偏亮 —— 阴影里的叶子本来就偏青，
# 晒到的叶尖本来就偏黄。这一条比"随机调亮度"有效得多。
# 幅度同样收窄：LIT 里的 (1.20,1.10,0.76) 会把阳面染成荧光黄绿。
CANOPY_DARK = np.array([0.80, 0.86, 0.92])
CANOPY_LIT = np.array([1.12, 1.06, 0.86])

# 垂直色阶：(高度 m, 色键)。层内用 smoothstep 过渡，所以看不到"跳色"。
# 林线跟着 cover_alt 一起下移到 30~40 m，所以"干草"这一档用不上了，
# 山腰是"林冠 → 草坡"，草坡直接过渡到岩石的暖褐。
VEG_RAMP = [
    (0.0, "jungle_d"), (3.0, "jungle_d"), (9.0, "jungle"), (16.0, "jungle"),
    (22.0, "jungle_l"), (28.0, "fern"), (34.0, "dry"), (42.0, "dry"),
]
ROCK_RAMP = [
    (0.0, "rock_d"), (10.0, "rock_m"), (24.0, "rock_m"), (38.0, "rock_l"),
    (48.0, "rock_peak"), (56.0, "rock_peak"),
]


def ramp_col(ramp, z):
    """按高度在色阶里取色（线性空间）。"""
    if z <= ramp[0][0]:
        return PAL[ramp[0][1]]
    for i in range(len(ramp) - 1):
        z0, k0 = ramp[i]
        z1, k1 = ramp[i + 1]
        if z <= z1:
            return mix(PAL[k0], PAL[k1], smoothstep(z0, z1, z))
    return PAL[ramp[-1][1]]


# ==================== 噪声 ====================
def _hash2(ix, iy, seed):
    h = np.sin(ix * 127.1 + iy * 311.7 + seed * 74.7) * 43758.5453
    return h - np.floor(h)


def noise2(X, Y, freq, seed):
    x, y = X * freq, Y * freq
    ix, iy = np.floor(x), np.floor(y)
    fx, fy = x - ix, y - iy
    ux = fx * fx * (3 - 2 * fx)
    uy = fy * fy * (3 - 2 * fy)
    a, b = _hash2(ix, iy, seed), _hash2(ix + 1, iy, seed)
    c, d = _hash2(ix, iy + 1, seed), _hash2(ix + 1, iy + 1, seed)
    return (a * (1 - ux) + b * ux) * (1 - uy) + (c * (1 - ux) + d * ux) * uy


def fbm(X, Y, freq, seed, octaves=4, lac=2.07, gain=0.5):
    tot = np.zeros_like(X)
    amp, f, nrm = 1.0, freq, 0.0
    for i in range(octaves):
        tot += amp * noise2(X, Y, f, seed + i * 13.7)
        nrm += amp
        amp *= gain
        f *= lac
    return tot / nrm


def smooth_field(H, passes=1):
    """3x3 加权模糊（边缘复制）。

    低多边形要"面"，不要"毛刺"：先把高度场里的高频压掉，
    后面量化出来的台地才是干净的几何面，而不是细碎折线。
    """
    for _ in range(passes):
        P = np.pad(H, 1, mode='edge')
        H = (P[0:-2, 0:-2] + 2.0 * P[0:-2, 1:-1] + P[0:-2, 2:]
             + 2.0 * P[1:-1, 0:-2] + 4.0 * P[1:-1, 1:-1] + 2.0 * P[1:-1, 2:]
             + P[2:, 0:-2] + 2.0 * P[2:, 1:-1] + P[2:, 2:]) / 16.0
    return H


# ==================== 高度场 ====================
BASE_R = SIZE_M * 0.5 * 0.96      # rn = 1 时的世界半径


def build_heightfield():
    xs = np.linspace(-SIZE_M / 2, SIZE_M / 2, N)
    X, Y = np.meshgrid(xs, xs)

    U, V = X / BASE_R, Y / (BASE_R * 0.92)
    TH = np.arctan2(V, U)
    r = np.sqrt(U * U + V * V)

    # 不平整的轮廓：山脚海岬般的起伏
    rsh = (1.0 + 0.085 * np.sin(3 * TH + 0.7) + 0.05 * np.sin(5 * TH + 2.1)
           + 0.03 * np.sin(8 * TH + 0.4) + 0.07 * (fbm(X, Y, 0.030, 3.0, 3) - 0.5) * 2.0)
    rn = r / np.maximum(rsh, 1e-6)

    H = np.interp(rn, PROF_RN, PROF_H)

    def bump(cx, cy, amp, sx, sy, rot=0.0):
        dx, dy = X - cx, Y - cy
        if rot:
            ca, sa = math.cos(rot), math.sin(rot)
            dx, dy = ca * dx - sa * dy, sa * dx + ca * dy
        return amp * np.exp(-(dx * dx / (2 * sx * sx) + dy * dy / (2 * sy * sy)))

    # 山脚一圈次峰 / 岩肩：把圆锥打散成"多峰山体"，低多边形剪影更好看。
    # 这一版把每个岩肩**加宽**（s 8~9.5 → 10~11.5）：窄岩肩在剪影上读成
    # "凸出来的包"，宽岩肩才读成"山体自己的肩线"。
    for ang, dist, amp, s in [(18, 34, 9.5, 10.5), (74, 33, 8.0, 9.5),
                              (152, 35, 9.0, 11.0), (208, 33, 7.0, 9.5),
                              (262, 34, 8.5, 10.0), (312, 34, 7.5, 10.0)]:
        a = math.radians(ang)
        H += bump(math.cos(a) * dist, math.sin(a) * dist, amp, s, s * 0.85, a)
    # 山腰两条扶壁脊
    for ang, dist, amp, s in [(112, 22, 4.5, 7.0), (300, 21, 4.0, 6.5)]:
        a = math.radians(ang)
        H += bump(math.cos(a) * dist, math.sin(a) * dist, amp, s, s * 0.6, a)

    # 地表起伏（山顶保护区几乎不动，免得鸟巢坑被噪点啃掉）
    # 频率和幅度都比以前低：原来 0.085 频（≈12 m 波长）的噪声叠了 4 个倍频，
    # 高频尾巴只有 1~2 m，量化成梯田之后就成了台阶边缘的锯齿，
    # 远看像一圈圈碎掉的尖牙 —— 这是"形状刺眼"的主要来源。
    flat = np.clip((rn - 0.32) / 0.22, 0, 1)          # 山顶 → 0
    H += (0.90 * (fbm(X, Y, 0.055, 5.0, 3) - 0.5) * 2.0) * flat
    # 中频那一层再收一半：它落在台地宽度以内，量化之后是"台阶边缘的碎齿"
    H += (0.08 * (fbm(X, Y, 0.22, 9.0, 2) - 0.5) * 2.0) * flat

    # 山体不对称：西南面陡、东北面缓。只抬/压中段（20~46 m），山顶平台和
    # 山脚都不动 —— 平台高度、山脚占地都还是基准表里的数。
    # 作用带放宽到 12~48 m，幅度加大：上一版只影响 20~46 m，
    # 山的上半截左右一样宽，剪影是"对称的锥子"；现在不对称一直压到山腰，
    # 剪影才有"一面崖、一面坡"的分量。
    mid = np.clip((H - 12.0) / 14.0, 0, 1) * np.clip((48.0 - H) / 10.0, 0, 1)
    H += 4.6 * np.cos(TH - math.radians(215.0)) * mid
    # 一条主山脊：山体有"面"和"背脊"，而不是一个规整的回转体
    spine = np.exp(-(angdiff(TH, math.radians(38.0)) / 0.50) ** 2)
    H += 4.2 * spine * mid

    # 轻量平滑：把残留的高频毛刺压掉，后面的梯田量化才切得干净
    H = smooth_field(H, 2)

    # 梯田：山腰的招牌层次（山脚和山顶不加，免得台阶感压倒造型）。
    # 每一层的边界被噪声推来推去，所以台地是断断续续、宽窄不一的舌状台阶，
    # 而不是一圈圈规整的等高线。
    band = np.clip((H - 6.0) / 4.0, 0, 1) * np.clip((PEAK_H_M - 13.0 - H) / 9.0, 0, 1)
    band *= np.clip((rn - 0.22) / 0.12, 0, 1)          # 山顶平台不梯田化
    # 台地的强度随方位变化：有的方向是整齐的梯田，有的方向几乎是一面缓坡。
    # 整座山一圈圈等高的台阶会读成"婚庆蛋糕"，真实的山不会这样。
    # 整体幅度收窄（0.42~1.00 → 0.30~0.85）：上一版有一半的方向是"满强度梯田"，
    # 台阶的立面把崖壁切成一圈圈碎齿，从剪影看过去很扎眼。
    band = band * (0.30 + 0.55 * (0.5 + 0.5 * np.cos(2.0 * TH + 0.9)))
    warp = TERRACE_WARP_M * (fbm(X, Y, 0.030, 29.0, 3) - 0.5) * 2.0
    step = TERRACE_STEP_M * (1.0 + 0.22 * (fbm(X, Y, 0.055, 23.0, 3) - 0.5) * 2.0)
    lv = (H + warp) / step
    fl = np.floor(lv)
    fr = lv - fl
    # 台阶立面不再是一堵 ~71° 的墙：落差改成摊在 46%~100% 这段里，
    # 平均坡度约 55°。立面陡一点是好事，但陡到 70° 再配上减面，
    # 每条台地边缘就变成一圈锯齿状的碎面 —— 这是"形状很刺眼"的一大来源。
    # 60° 上下仍然读得出"梯田"，但棱线是干净的整条边。
    eased = np.clip((fr - 0.46) / 0.54, 0, 1)
    eased = eased * eased * (3 - 2 * eased)
    H = H * (1 - band) + ((fl + eased) * step - warp) * band

    # 峰顶岩冠的岩脊：低频、大尺度，给上部锥体几块大棱面，别是一个光溜溜的圆包。
    # 放在梯田量化**之后** —— 放在之前会被量化切碎，切出来的就是"尖牙"不是"岩脊"。
    # 高度门限让峰尖本身不动（主峰高度是基准表里的数），只刻锥体的两翼。
    # 低频那一层加重（2.4 → 3.0）、中频那一层收轻（1.2 → 0.9）：
    # 大棱面是"岩石感"，中频起伏是"碎面"，后者一多剪影就炸。
    crag = (np.clip((0.31 - rn) / 0.10, 0, 1) * np.clip((rn - 0.155) / 0.045, 0, 1)
            * np.clip((PEAK_H_M - 0.5 - H) / 6.0, 0, 1))
    H += 3.0 * (fbm(X, Y, 0.032, 37.0, 3) - 0.5) * 2.0 * crag
    H += 0.9 * (fbm(X, Y, 0.075, 43.0, 2) - 0.5) * 2.0 * crag

    # 冲沟：从上往下切出的雨水沟，把圆台剪影打碎。
    # 沟放宽、变浅，而且只切到 40 m 以下 —— 原来一直切到峰顶，
    # 几条沟就把上部锥体切成一圈尖牙。
    for ang, wid, dep in GULLIES:
        g = np.exp(-(angdiff(TH, math.radians(ang)) / (wid * 1.55)) ** 2)
        g *= np.clip((PEAK_H_M - 13.0 - H) / 8.0, 0, 1)
        g *= np.clip((H - 5.0) / 4.0, 0, 1)
        H -= dep * 0.66 * g * (0.75 + 0.5 * fbm(X, Y, 0.05, 61.0, 2))
    # 山脚一圈起伏，岸线不再是一个正圆
    H += 2.2 * (fbm(X, Y, 0.028, 71.0, 3) - 0.5) * 2.0 * np.clip((2.0 - rn) * 1.4, 0, 1)

    # 剪影：山腰被噪声顶出 / 削掉几处，免得从任何角度看都是个规整的圆台。
    # 频率压低 → 起伏更大但更整块，剪影是"一笔"而不是"一笔带锯齿"。
    H += 2.8 * (fbm(X, Y, 0.016, 83.0, 3) - 0.5) * 2.0 \
        * np.clip((rn - 0.20) * 4.0, 0, 1) * np.clip((0.95 - rn) * 5.0, 0, 1)

    return np.array(X), np.array(Y), H, np.array(rn), np.array(rsh)


# ==================== 建实体 ====================
def boundary_loops(bm):
    be = [e for e in bm.edges if len(e.link_faces) == 1]
    adj = {}
    for e in be:
        a, b = e.verts
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)
    loops, seen = [], set()
    for start in list(adj):
        if start in seen:
            continue
        loop, prev, cur = [start], None, start
        seen.add(start)
        while True:
            nxt = None
            for v in adj[cur]:
                if v is not prev and v not in seen:
                    nxt = v
                    break
            if nxt is None:
                break
            loop.append(nxt)
            seen.add(nxt)
            prev, cur = cur, nxt
        if len(loop) >= 3:
            loops.append(loop)
    return loops


def build_solid(X, Y, H, rn):
    verts = np.column_stack([X.ravel(), Y.ravel(), H.ravel()]).tolist()
    idx = np.arange(N * N).reshape(N, N)
    faces = np.column_stack([idx[:-1, :-1].ravel(), idx[:-1, 1:].ravel(),
                             idx[1:, 1:].ravel(), idx[1:, :-1].ravel()]).tolist()
    me = bpy.data.meshes.new("NestMountainMesh")
    me.from_pydata(verts, [], faces)
    me.update()
    ob = bpy.data.objects.new("NestMountain", me)
    bpy.context.scene.collection.objects.link(ob)

    rnf = rn.ravel().tolist()
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[v for i, v in enumerate(bm.verts) if rnf[i] > 1.045],
                     context='VERTS')
    bm.verts.ensure_lookup_table()

    for loop in boundary_loops(bm):
        cxx = sum(v.co.x for v in loop) / len(loop)
        cyy = sum(v.co.y for v in loop) / len(loop)
        for v in loop:
            v.co.z = SEA_BOT_M
        centre = bm.verts.new((cxx, cyy, SEA_BOT_M))
        bm.verts.ensure_lookup_table()
        n = len(loop)
        for i in range(n):
            bm.faces.new((loop[i], loop[(i + 1) % n], centre))

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    me.update()
    return ob


def activate(ob):
    for o in bpy.context.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob


def apply_mod(ob, mod):
    bpy.ops.object.modifier_apply(modifier=mod.name)


# ==================== 山洞 ====================
def height_at(Xs, Hs, x, y):
    """高度场双线性采样（世界坐标 -> 高度，米）。

    高度场是"每个 (x, y) 一个高度"，所以采样很直接；崖面/台面的关系
    也因此可以精确地量出来。Xs 是 x / y 共用的轴（方形网格）。
    """
    n = len(Xs)
    d = Xs[1] - Xs[0]
    fx = min(max((x - Xs[0]) / d, 0.0), n - 1.001)
    fy = min(max((y - Xs[0]) / d, 0.0), n - 1.001)
    i, j = int(fx), int(fy)
    tx, ty = fx - i, fy - j
    h00 = Hs[j][i]
    h10 = Hs[j][i + 1]
    h01 = Hs[j + 1][i]
    h11 = Hs[j + 1][i + 1]
    return (h00 * (1 - tx) + h10 * tx) * (1 - ty) + (h01 * (1 - tx) + h11 * tx) * ty


def cliff_segments(Xs, Hs, az_deg, r_lo, r_hi, ds=0.2, min_slope=1.2):
    """沿某个方位把高度场切一遍，找出连续陡崖段。

    返回 [(r_top, r_bot, z_top, z_bot), ...]：每段是一面立得住的崖。
    判据是"每米下降 > 1.2"（陡于 ~50°）。
    """
    a = math.radians(az_deg)
    ca, sa = math.cos(a), math.sin(a)
    rs = np.arange(r_lo, r_hi, ds)
    hs = np.array([height_at(Xs, Hs, ca * r, sa * r) for r in rs])
    out = []
    i = 0
    while i < len(hs) - 1:
        if (hs[i] - hs[i + 1]) / ds <= min_slope:
            i += 1
            continue
        j = i
        while j < len(hs) - 1 and (hs[j] - hs[j + 1]) / ds > min_slope:
            j += 1
        k = min(j + 1, len(hs) - 1)
        out.append((float(rs[i]), float(rs[k]), float(hs[i]), float(hs[k])))
        i = j + 1
    return out


def find_cave_site(ob, Xs, Hs, spec):
    """在高度场上找一段"立得住的崖面"，洞口定在崖面正中。

    返回 (方位角, 崖面中点的半径, 崖面中点的高度, 崖面高度, 可用洞半径)。
    洞半径按崖面高度反推：崖面多高，洞就能开多大 —— 这样洞一定塞得进墙里。
    """
    a0 = math.radians(spec["az"])
    # 崖面上方的净空：洞顶不能高过上一步台面
    min_wall = 2.0 * (spec["radius"] + 0.6)
    best = None
    for azd in np.arange(spec["az"] - spec["az_span"], spec["az"] + spec["az_span"] + 0.01, 2.0):
        for (r_top, r_bot, z_top, z_bot) in cliff_segments(Xs, Hs, azd, spec["r_lo"], spec["r_hi"]):
            wall_h = z_top - z_bot
            if wall_h < min_wall:
                continue
            z_mid = 0.5 * (z_top + z_bot)
            if not (spec["z_lo"] <= z_mid <= spec["z_hi"]):
                continue
            r_mid = 0.5 * (r_top + r_bot)
            radius = min(spec["radius"], wall_h * 0.5 - 0.6)
            # 贴着目标高度、而且崖面越高越"立得住"
            score = -abs(z_mid - (spec["z_lo"] + spec["z_hi"]) * 0.5) + 0.25 * wall_h
            if best is None or score > best[0]:
                best = (score, float(azd), r_mid, z_mid, wall_h, radius)
    if best is None:
        return None

    # 在崖面上打一条水平射线，拿到精确的洞口位置和法线
    score, azd, r_mid, z_mid, wall_h, radius = best
    a = math.radians(azd)
    outward = Vector((math.cos(a), math.sin(a), 0.0))
    start = outward * (SIZE_M * 0.6) + Vector((0, 0, z_mid))
    hit, loc, nrm, _idx = ob.ray_cast(start, -outward, distance=SIZE_M)
    if not hit:
        print("  ! no wall at az=%.0f z=%.1f" % (azd, z_mid))
        return None
    loc = Vector(loc)
    if abs(nrm.z) > 0.55 or abs(math.hypot(loc.x, loc.y) - r_mid) > 2.0:
        # 射线打到的不是预定那段崖面（高度场和减面后的网格有偏差）
        print("  ! wall mismatch az=%.0f: hit r=%.1f (want %.1f) nz=%.2f"
              % (azd, math.hypot(loc.x, loc.y), r_mid, nrm.z))
        return None
    print("  site az=%.0f  mouth (%.1f, %.1f, %.1f)  wall=%.1f m  r=%.2f"
          % (azd, loc.x, loc.y, loc.z, wall_h, radius))
    return azd, loc, wall_h, radius


def bore_cave(ob, azimuth_deg, loc, wall_h, radius, depth, tilt_deg):
    """用一根**正圆柱**切出洞口。

    洞口是**平整的圆形切口**（不加口沿石块）；要石头就在场景里单独摆
    `low_poly_rock.glb`，洞口的"平切"反而更好摆、更容易和地形对齐。
    """
    loc = Vector(loc)
    a = math.radians(azimuth_deg)
    outward = Vector((math.cos(a), math.sin(a), 0.0))
    direction = (-outward + Vector((0, 0, math.tan(math.radians(tilt_deg))))).normalized()

    # 切口周围加密：圆柱和粗三角形相交时，口沿才不会切出锯齿
    me = ob.data
    bm = bmesh.new()
    bm.from_mesh(me)
    sel = [f for f in bm.faces
           if (f.calc_center_median() - loc).length < radius + 2.2]
    if sel:
        edges = set()
        for f in sel:
            edges.update(f.edges)
        bmesh.ops.subdivide_edges(bm, edges=list(edges), cuts=2, use_grid_fill=True)
        bm.to_mesh(me)
    bm.free()
    me.update()

    # 正圆柱：口沿是一圈平整的圆，切进去是直筒
    axis_len = depth + 3.0
    centre = loc + direction * (axis_len * 0.5 - 1.5)
    bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=radius, depth=axis_len,
                                        location=centre)
    cutter = bpy.context.object
    cutter.rotation_euler = direction.to_track_quat('Z', 'Y').to_euler()
    activate(ob)
    mb = ob.modifiers.new("cave", 'BOOLEAN')
    mb.operation = 'DIFFERENCE'
    mb.solver = 'EXACT'
    mb.object = cutter
    apply_mod(ob, mb)

    # 洞底扩一间石室，别让洞里是个死胡同管子。
    # 石室半径按崖面上方的净空算 —— 净空不够就只留直筒，宁可小也不捅穿台面。
    headroom = wall_h * 0.5 - 0.5
    room_r = min(radius * 1.5, headroom - 0.4)
    made_room = False
    if room_r > radius * 1.05:
        room = loc + direction * (depth - radius * 0.55)
        bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8,
                                             radius=room_r, location=room)
        ball = bpy.context.object
        activate(ob)
        mb2 = ob.modifiers.new("room", 'BOOLEAN')
        mb2.operation = 'DIFFERENCE'
        mb2.solver = 'EXACT'
        mb2.object = ball
        apply_mod(ob, mb2)
        bpy.data.objects.remove(ball, do_unlink=True)
        made_room = True
    else:
        ball = None

    for o in (cutter,):
        bpy.data.objects.remove(o, do_unlink=True)

    print("  cave az=%.0f -> mouth (%.1f, %.1f, %.1f)  r=%.2f  depth=%.1f  room=%s"
          % (azimuth_deg, loc.x, loc.y, loc.z, radius, depth,
             "yes" if made_room else "no"))
    return loc, direction, radius, depth



# ==================== 顶点色 ====================
def plane_groups(me):
    """把共面的三角面归到一组，**组内同色**。

    低多边形不能按三角面上色：同一块平面的两个三角形一旦颜色不同，
    面内就碎成脏斑，棱线也糊成一团，远看就是一层噪点。
    组内统一取色才是干净的块面（assets/AGENTS.md §6 第 9 条）。
    """
    groups = {}
    for p in me.polygons:
        n = p.normal
        d = n.dot(p.center)
        key = (round(n.x, 3), round(n.y, 3), round(n.z, 3), round(d, 2))
        groups.setdefault(key, []).append(p)
    return groups


def colourise(me, caves):
    ca = me.color_attributes.new(name="Col", type='FLOAT_COLOR', domain='CORNER')
    P = PAL
    SUN = Vector((0.42, -0.34, 0.84)).normalized()    # 预览里的"假日照"方向
    TINT_LIT = np.array([1.04, 1.00, 0.94])           # 朝阳面偏暖
    TINT_SHADE = np.array([0.95, 0.98, 1.04])         # 背阴面偏冷

    for key, faces in plane_groups(me).items():
        rep = max(faces, key=lambda f: f.area)           # 用最大那个三角面当代表
        c = rep.center
        n = rep.normal
        nz = n.z
        slope = 1.0 - max(-1.0, min(1.0, nz))            # 0 = 平, 1 = 垂直
        rn = math.sqrt((c.x / BASE_R) ** 2 + (c.y / (BASE_R * 0.92)) ** 2)
        z = c.z

        # --- 低频块面噪声（只留低频：高频会把块面重新打回噪点）---
        patch = fbm(np.array([c.x]), np.array([c.y]), 0.045, 17.0, 3)[0]   # 大块
        patch2 = fbm(np.array([c.x]), np.array([c.y]), 0.13, 41.0, 2)[0]   # 中块
        outcrop = fbm(np.array([c.x]), np.array([c.y]), 0.05, 77.0, 2)[0]   # 露头分布
        # 超大尺度的"秃斑"（≈45 m 波长）：用来把植被从一圈圈等高的绿环
        # 切成不规则的块。没有这一层，台地边缘的绿色是完整的一圈，
        # 远看就是"蛋糕层" —— 颜色和形状都刺眼。
        bald = fbm(np.array([c.x]), np.array([c.y]), 0.022, 91.0, 2)[0]
        patch3 = fbm(np.array([c.x]), np.array([c.y]), 0.20, 53.0, 2)[0]   # 中频斑
        warp = TERRACE_WARP_M * (fbm(np.array([c.x]), np.array([c.y]), 0.030, 29.0, 3)[0]
                                 - 0.5) * 2.0

        # --- 垂直色阶：同一色系里靠明度分层 ---
        veg = ramp_col(VEG_RAMP, z)
        rock = ramp_col(ROCK_RAMP, z)
        alt = smoothstep(30.0, 44.0, z)      # 越高越接近峰顶（跟林线一起下移）

        # 石头的两种暖岩：只偏移色相，不动明度骨架。
        # 大尺度噪声决定这一片区是晒白的砂岩还是赭红的氧化岩。
        # 阈值要贴着 fbm 的真实分布：它的中位数在 0.45~0.51、p25≈0.36、
        # p75≈0.55，所以门限必须落在 0.30~0.60，阈值开太宽等于没有变化。
        #
        # **斑驳频率必须随高度切换**：低频斑（22 m 波长）在山腰是漂亮的大色块，
        # 但岩冠只有 ~12 m 大，整个岩冠会落在同一个低频色块里 → 一整片死板的
        # 浅色。所以越高越换中频斑（~8 m），岩冠内部才有斑驳。
        mottle = patch * (1.0 - alt) + patch2 * alt
        edge = 0.30 - 0.11 * alt
        # 混色强度全部收窄：上一版 0.55 / 0.50 把岩冠推成了"奶油 + 铁锈"的花斑，
        # 远看是一块发花的东西，而不是石头。
        rock = mix(rock, rock * STONE_SAND, 0.38 * smoothstep(edge, edge + 0.30, mottle))
        rock = mix(rock, rock * STONE_IRON, 0.34 * smoothstep(edge, edge + 0.30, 1.0 - mottle))
        # 林冠的明暗冷暖：阳面亮而暖、阴面暗而冷，森林因此有体积
        veg = mix(veg, veg * CANOPY_DARK, 0.40 * smoothstep(0.30, 0.60, 1.0 - mottle))
        veg = mix(veg, veg * CANOPY_LIT, 0.38 * smoothstep(0.30, 0.60, mottle))
        # 中频斑：崖面是模型上面积最大的部分，太平就闷成一块石板。
        # 幅度只有 ±3~4%：再大就成噪点了。
        rock = rock * (0.97 + 0.06 * patch3)
        veg = veg * (0.97 + 0.06 * patch3)
        # 朝上的岩面亮一些，陡面暗一些（自遮挡的廉价近似）
        rock = rock * (0.91 + 0.09 * max(0.0, nz))
        # 上部岩壁的大尺度明暗：山脊迎光、冲沟背阴。
        # 不加这一层，峰顶就是一块均匀的米色 —— 造型再好也是"一坨"。
        rock = rock * (1.0 + 0.13 * (patch - 0.5) * 2.0 * alt)
        # 峰顶还要加一层**中频**斑（≈5 m）：岩冠本身只有 ~15 m 大，
        # 上面的 22 m 低频斑在它内部几乎是常数 —— 不换频率就没有"石头的颗粒"。
        rock = rock * (1.0 + 0.11 * (patch3 - 0.5) * 2.0 * alt)

        # --- 峰顶风化：越高越多赭红氧化，岩缝里挂一点苔 ---
        rock = mix(rock, rock * STONE_IRON, 0.28 * alt)

        # --- 植被覆盖率 = 高度 × 坡度 − 秃斑 ---
        # **林线在 30~38 m**：再高就把山的上半截交给"干草色"，
        # 峰顶是一整块土黄的糊状色块（"冲山顶"）。
        # 38 m 以上基本是裸岩，植被只在台地和沟里挂着 ——
        # "上有岩壁、下有林"的两段式，读起来才像一座山。
        cover_alt = 1.0 - 0.95 * smoothstep(30.0, 38.0, z)
        # 坡度响应：台面（<30°）长满植被，越陡挂不住土。
        # 30° → 1.0 ；50° → 0.9 ；65° → 0.66 ；80° → 0.16
        # 换成幂曲线会太激进（上一版 60° 就只剩 0.22），
        # 山会变成"一层绿皮贴在石头上"，反而更像"长苔藓的石头"。
        cover_slope = smoothstep(0.95, 0.55, slope)
        cover_tongue = 0.22 * smoothstep(0.40, 0.64, patch2)          # 崖上挂的草舌
        base = min(1.0, cover_slope + cover_tongue)
        # 露头 / 秃斑：从 base 里**扣掉**，而不是再乘一层。
        # （上一版把三个独立噪声因子连乘，平均覆盖只剩 ~0.3，山变成一块米色石头。）
        # 门限刻意开得窄：fbm 的中位数在 0.5 附近，只有高于 0.5 的那部分才吃到秃斑，
        # 这样绿毯子还在，只是被撕开几块，而不是整座山被剃光。
        bald_amt = 0.45 * smoothstep(0.50, 0.68, bald)               # ≈45 m 波长的大秃斑
        outcrop_amt = 0.40 * smoothstep(0.46, 0.66, outcrop)         # ≈20 m 波长的露头
        cover = cover_alt * max(0.0, min(1.0, base - bald_amt - outcrop_amt))
        # 斑块噪声把覆盖边界再揉碎一点：植被的"海岸线"应该是不规则的
        cover = min(1.0, max(0.0, cover + 0.14 * (patch3 - 0.5)))

        # --- 三段混合：岩石 → 灌丛 → 植被 ---
        # 直接 mix(rock, veg, cover) 会让"绿色地毯"和"米色石头"直接贴在一起，
        # 中间那一步就是"突兀"。现在中间插一段**灌丛 / 干苔**：
        # 它由 rock 和 veg 各取一半再往干黄方向推一点得到，
        # 所以自动跟着高度色阶走，不用另配一套颜色表。
        scrub = mix(rock, veg, 0.5) * np.array([1.02, 0.99, 0.88])
        if cover <= 0.5:
            col = mix(rock, scrub, cover * 2.0)
        else:
            col = mix(scrub, veg, (cover - 0.5) * 2.0)

        # 岩缝里的苔痕：峰顶的阴面石头缝里会长绿，别让岩冠死板一块。
        # 用专用的浅苔色，不要用色阶里的 veg —— 高处 veg 已经是干草的土黄，
        # 拿它当苔痕涂在浅色岩上等于没涂。
        col = mix(col, P["moss"],
                  0.38 * alt * smoothstep(0.36, 0.60, 1.0 - mottle) * (1.0 - cover))

        # --- 等高层理：跟真正的台地同一套相位 ---
        # 相位峰 = 台面（晒得干、偏黄、提亮），相位谷 = 立面（背阴、压暗、偏冷）。
        # 这么一分，梯田的层次就从**颜色里**读得出来，不只靠几何和光。
        # 幅度收窄到 ±2.8%：上一版 ±5% 再叠上 22% 的干草 / 压暗，
        # 等于每条台地都镶了一道亮边 + 一道暗边，一圈圈"荧光描边"叠上去
        # 就是"颜色很突兀"的另一半来源。
        phase = math.cos((z + warp) / TERRACE_STEP_M * math.tau)
        shelf = max(0.0, phase)
        col = col * (1.0 + 0.028 * phase)
        # 台面上的草常被太阳晒：偏干偏黄
        col = mix(col, col * (1.08, 1.02, 0.82), 0.13 * shelf * cover)
        # 立面朝背光：压暗并偏冷
        col = mix(col, col * (0.93, 0.96, 1.03), 0.12 * max(0.0, -phase))

        # --- 潮线：常年被浪拍到的岩面颜色更深 ---
        col = col * (1.0 - 0.15 * smoothstep(2.4, -0.4, z))

        # --- 沙滩：环岛的一圈暖白 + 水线附近压深一档当"湿沙" ---
        # 坡度只用来挡真正立起来的地方（山脚的陡坡不长沙）。
        sand_t = smoothstep(4.0, 1.0, z) * smoothstep(0.75, 0.35, slope)
        if sand_t > 0.0:
            sand = P["sand_l"] * (0.93 + 0.12 * patch)
            sand = mix(sand, P["sand_d"], smoothstep(1.1, -0.2, z))
            col = mix(col, sand, sand_t)

        # --- 覆盖：水下裙边 / 鸟巢坑 ---
        if z < -0.4:                                           # 水下
            col = mix(P["sea_deep"], P["sea_shal"], smoothstep(-9.0, 0.0, z)) \
                * (0.95 + 0.08 * patch)
        elif rn < 0.145 and z < PEAK_H_M - 0.4:                # 山顶鸟巢预留坑
            col = mix(P["soil_l"], P["soil_d"], patch2) * (0.93 + 0.10 * patch)

        # 洞内：沿洞轴变暗。
        # 注意只看"进了洞"的面：面的法线必须大致背对洞口，否则洞外正上方的
        # 崖面会落进这根管的半径里，被涂黑成几根尖刺。
        for (loc, direction, radius, depth) in caves:
            d = c - loc
            along = d.dot(direction)
            if along <= 0.15 or along > depth + radius:
                continue
            if n.dot(direction) > -0.15:      # 面朝外 = 洞外的岩面
                continue
            if (d - direction * along).length < radius * 1.35:
                f = max(0.0, min(1.0, along / (depth * 0.80)))
                # 洞口一带保留岩色（洞壁厚度），越深越黑；地板比顶棚亮一点，
                # 像是天光漏进来，洞口才不会糊成一块剪影。
                k = 0.30 + 0.62 * f
                up = (d - direction * along).z / max(radius, 1e-3)
                lit = 0.35 + 0.65 * max(0.0, min(1.0, 0.5 - up * 0.5))
                cave_col = P["cave_in"] * (0.45 + 1.6 * lit)
                col = mix(col, cave_col, k)

        # --- 冷暖分离：朝阳面暖、背阴面冷。
        # 这一项是低多边形"块面感"的主要来源：相邻面因为法线不同而分出冷暖，
        # 棱线自然就清楚了，不需要靠随机噪声去"造"块。
        t = max(0.0, min(1.0, (n.dot(SUN) + 1.0) * 0.5))
        col = col * (TINT_SHADE + (TINT_LIT - TINT_SHADE) * t)

        col = np.clip(col, 0.0, 1.0)
        for p in faces:
            for li in p.loop_indices:
                ca.data[li].color = (col[0], col[1], col[2], 1.0)


# ==================== 预览：摆独立的石头资产 ====================
ROCK_GLB = os.path.join(os.path.dirname(OUT_DIR), "low-poly-rock", "low_poly_rock.glb")


def drop_to_ground(ob, x, y, z_hint):
    """从高处往下打一条射线，返回该 XY 处的地表高度（打不到就当 z=0）。"""
    hit, loc, _n, _i = ob.ray_cast(Vector((x, y, z_hint + 60.0)),
                                   Vector((0, 0, -1)), distance=140.0)
    return loc.z if hit else 0.0


def place_preview_rocks(ob, caves):
    """把 low_poly_rock.glb 摆到两个洞口旁边，交代洞口尺度。

    石头是**独立资产**（models/low-poly-rock，自己的脚本和 GLB），这里只是
    在预览场景里引用并复制几份，不进山体的 GLB。山脚洞在坡上、山腰洞在台地上，
    所以落地高度是用射线实测的，不是写死的 z。
    """
    if not os.path.exists(ROCK_GLB):
        print("  (preview rocks skipped: %s not found)" % ROCK_GLB)
        return
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=ROCK_GLB)
    src = [o for o in bpy.data.objects if o not in before and o.type == 'MESH']
    if not src:
        return
    proto = src[0]

    # 每个洞口：正前方 2~3 块，左右错开、朝向不同
    layout = [(3.2, 1.9, 25.0), (-3.6, 2.6, -40.0), (4.4, 5.2, 70.0)]
    for ci, (loc_v, direction, radius, depth) in enumerate(caves):
        # direction 是"往山里钻"的方向，朝洞外要取反
        n = Vector((-direction.x, -direction.y, 0.0)).normalized()
        u = Vector((-n.y, n.x, 0.0))                               # 洞口横向
        for k, (side, fwd, yaw) in enumerate(layout):
            x = loc_v.x + n.x * (radius + fwd) + u.x * side
            y = loc_v.y + n.y * (radius + fwd) + u.y * side
            z = drop_to_ground(ob, x, y, loc_v.z) - 0.06           # 稍微埋进去一点
            rocks = proto.copy()                                   # 共用 mesh 数据
            rocks.data = proto.data
            rocks.name = "Rock_preview_%d_%d" % (ci, k)
            rocks.location = (x, y, z)
            rocks.rotation_euler = (0.0, 0.0, math.radians(yaw))
            bpy.context.scene.collection.objects.link(rocks)
            print("    rock cave%d @ (%.1f, %.1f, %.1f)" % (ci, x, y, z))
    for o in src:
        bpy.data.objects.remove(o, do_unlink=True)                 # 原件不需要了
    print("  preview rocks placed near both cave mouths")


def make_material(me, name="NestMountainMat"):
    me.materials.clear()
    for d in list(bpy.data.materials):
        if d.users == 0:
            bpy.data.materials.remove(d)
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    bsdf.inputs['Roughness'].default_value = 0.92
    bsdf.inputs['Metallic'].default_value = 0.0
    attr = nt.nodes.new('ShaderNodeVertexColor')
    attr.layer_name = "Col"
    attr.location = (-320, 200)
    nt.links.new(attr.outputs['Color'], bsdf.inputs['Base Color'])
    me.materials.append(mat)


# ==================== 预览占位鸟巢 ====================
def twig_tube(pts, radius, sides=4, seed=0):
    """沿折线挤出一根方形截面的枝条，返回 (verts, faces)。"""
    rng = random.Random(seed)
    verts, faces = [], []
    rings = []
    up = Vector((0, 0, 1))
    for i, p in enumerate(pts):
        if i < len(pts) - 1:
            d = (Vector(pts[i + 1]) - Vector(p))
        else:
            d = (Vector(p) - Vector(pts[i - 1]))
        d.normalize()
        ref = up if abs(d.z) < 0.9 else Vector((1, 0, 0))
        u = d.cross(ref).normalized()
        w = d.cross(u).normalized()
        rr = radius * (0.85 + 0.3 * rng.random())
        ring = []
        for k in range(sides):
            ang = 2 * math.pi * k / sides + rng.random() * 0.4
            off = u * (math.cos(ang) * rr) + w * (math.sin(ang) * rr)
            ring.append(len(verts))
            verts.append((p[0] + off.x, p[1] + off.y, p[2] + off.z))
        rings.append(ring)
    for i in range(len(rings) - 1):
        a, b = rings[i], rings[i + 1]
        for k in range(sides):
            k2 = (k + 1) % sides
            faces.append((a[k], a[k2], b[k2], b[k]))
    return verts, faces


def build_nest_placeholder():
    """碗状柴枝堆：占住山顶的坑，方便看尺度（不进 GLB）。"""
    rng = random.Random(SEED + 7)
    verts, faces = [], []

    def add(pts, r, seed):
        v, f = twig_tube(pts, r, 4, seed)
        base = len(verts)
        verts.extend(v)
        faces.extend([tuple(i + base for i in fa) for fa in f])

    rim_z = PEAK_H_M - 0.9
    floor_z = NEST_FLOOR_M + 0.9

    # 1) 内壁：一圈圈斜着绕的枝条，从坑底绕到坑沿
    for i in range(34):
        a0 = rng.random() * math.tau
        turns = 0.55 + 0.5 * rng.random()
        h0 = floor_z + (rim_z - floor_z) * rng.random() * 0.75
        pts = []
        n = 6
        for k in range(n):
            t = k / (n - 1)
            ang = a0 + turns * math.tau * t
            rr = NEST_R_M * (1.02 - 0.30 * t) * (0.90 + 0.13 * rng.random())
            z = h0 + (rim_z - h0) * t + 0.55 * math.sin(t * math.pi) * rng.uniform(-1, 1)
            z = min(z, rim_z)
            pts.append((math.cos(ang) * rr, math.sin(ang) * rr, z))
        add(pts, 0.16 + 0.10 * rng.random(), 100 + i)

    # 2) 巢底：交叉的横枝，铺成浅碟
    for i in range(16):
        a0 = rng.random() * math.tau
        pts = []
        n = 5
        for k in range(n):
            t = k / (n - 1)
            rr = NEST_R_M * (0.10 + 0.85 * t)
            ang = a0 + 0.35 * math.sin(t * 3.0) + rng.uniform(-0.1, 0.1)
            z = floor_z + 1.5 * (1.0 - (1.0 - t) ** 2) + rng.uniform(-0.25, 0.25)
            pts.append((math.cos(ang) * rr, math.sin(ang) * rr, z))
        add(pts, 0.17, 200 + i)

    # 3) 巢沿：外翻的粗枝
    for i in range(18):
        a0 = rng.random() * math.tau
        pts = []
        for k in range(4):
            t = k / 3.0
            ang = a0 + (0.9 - 0.5 * t) * math.tau * (1 if i % 2 else -1)
            rr = NEST_R_M * (1.06 + 0.10 * t) * (0.95 + 0.09 * rng.random())
            z = rim_z + 0.35 * t + rng.uniform(-0.2, 0.2)
            pts.append((math.cos(ang) * rr, math.sin(ang) * rr, z))
        add(pts, 0.22, 300 + i)

    me = bpy.data.meshes.new("NestPlaceholderMesh")
    me.from_pydata(verts, [], faces)
    me.update()
    ob = bpy.data.objects.new("NestPlaceholder", me)
    bpy.context.scene.collection.objects.link(ob)

    # 枝条顶点色（三层棕 + 每根随机）
    ca = me.color_attributes.new(name="Col", type='FLOAT_COLOR', domain='CORNER')
    P = PAL
    for p in me.polygons:
        z = p.center.z
        t = min(1.0, max(0.0, (z - NEST_FLOOR_M) / max(0.1, PEAK_H_M - NEST_FLOOR_M)))
        v = (math.sin(p.center.x * 21.7 + p.center.y * 9.1) * 0.5 + 0.5)
        col = (P["twig_d"] * (1 - t) + P["twig_l"] * t) * (0.85 + 0.30 * v)
        col = np.clip(col, 0, 1)
        for li in p.loop_indices:
            ca.data[li].color = (col[0], col[1], col[2], 1.0)
    make_material(me, "NestPlaceholderMat")
    for p in me.polygons:
        p.use_smooth = False
    return ob


# ==================== 预览渲染 ====================
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
    bg.inputs[0].default_value = (0.74, 0.80, 0.86, 1.0)
    bg.inputs[1].default_value = 0.55

    # 曝光：太阳 3.6 会把向阳面直接顶到 1.0（Standard 变换下就是死白），
    # 颜色全被削平，越亮的绿越发荧光。压到 2.0 左右才是模型本来的颜色。
    # 这一版再把太阳抬到 2.8、辅光压到 0.5：低多边形的立体感来自
    # **受光面和背光面的差**，辅光一强，形体就平了，颜色也灰扑扑的。
    for name, energy, rot, angle in [
            ("Sun", 2.8, (math.radians(50), 0, math.radians(-125)), 3.0),
            ("Fill", 0.5, (math.radians(64), 0, math.radians(60)), 22.0),
            ("Front", 0.28, (math.radians(80), 0, math.radians(-95)), 30.0)]:
        ld = bpy.data.lights.new(name, 'SUN')
        ld.energy = energy
        ld.angle = math.radians(angle)
        ob = bpy.data.objects.new(name, ld)
        ob.rotation_euler = rot
        scene.collection.objects.link(ob)

    # 海面（只在预览里，用来交代 z=0 的水位线）
    me = bpy.data.meshes.new("SeaMesh")
    s = 900.0
    me.from_pydata([(-s, -s, 0), (s, -s, 0), (s, s, 0), (-s, s, 0)], [], [(0, 1, 2, 3)])
    me.update()
    sea = bpy.data.objects.new("SeaPreview", me)
    mat = bpy.data.materials.new("SeaPreviewMat")
    mat.use_nodes = True
    bsdf = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    bsdf.inputs['Base Color'].default_value = (0.09, 0.24, 0.34, 1.0)
    bsdf.inputs['Roughness'].default_value = 0.25
    me.materials.append(mat)
    scene.collection.objects.link(sea)

    cam_data = bpy.data.cameras.new("PreviewCam")
    cam_data.lens = 42.0
    cam = bpy.data.objects.new("PreviewCam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    return cam, sea


def render_shot(cam, path, loc, look_at, res=(900, 640)):
    scene = bpy.context.scene
    scene.render.resolution_x, scene.render.resolution_y = res
    cam.location = Vector(loc)
    cam.rotation_euler = (Vector(look_at) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


def stitch(paths, out_path, cols):
    imgs = [bpy.data.images.load(p) for p in paths]
    w, h = imgs[0].size
    rows = int(math.ceil(len(imgs) / cols))
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


# ==================== 主流程 ====================
def clear_scene():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.cameras, bpy.data.lights):
        for d in list(coll):
            if d.users == 0:
                coll.remove(d)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    do_render = "--nopreview" not in argv
    do_nest = "--nonest" not in argv

    random.seed(SEED)
    np.random.seed(SEED)
    clear_scene()
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1.0

    print("building heightfield ...")
    X, Y, H, rn, rsh = build_heightfield()
    ob = build_solid(X, Y, H, rn)
    me = ob.data
    activate(ob)
    print("  grid %d x %d -> %d faces" % (N, N, len(me.polygons)))

    sm = ob.modifiers.new("smooth", 'SMOOTH')
    sm.factor, sm.iterations = 0.40, 2
    apply_mod(ob, sm)

    # 山顶保护区：鸟巢坑 + 平台边缘不被减面吃掉
    vg = ob.vertex_groups.new(name="protect")
    for v in me.vertices:
        c = v.co
        rr = math.sqrt((c.x / BASE_R) ** 2 + (c.y / (BASE_R * 0.92)) ** 2)
        vg.add([v.index], 0.0 if rr < 0.185 else 1.0, 'REPLACE')

    d1 = ob.modifiers.new("dissolve", 'DECIMATE')
    d1.decimate_type = 'DISSOLVE'
    d1.angle_limit = math.radians(6.0)
    apply_mod(ob, d1)

    tr = ob.modifiers.new("tri", 'TRIANGULATE')
    apply_mod(ob, tr)

    f = len(me.polygons)
    d2 = ob.modifiers.new("collapse", 'DECIMATE')
    d2.decimate_type = 'COLLAPSE'
    d2.ratio = min(1.0, TARGET_TRIS / max(1, f))
    d2.vertex_group = "protect"
    d2.vertex_group_factor = 1.0
    apply_mod(ob, d2)
    ob.vertex_groups.remove(ob.vertex_groups["protect"])
    print("  after decimate: %d faces" % len(me.polygons))

    # 山洞（在最终体量上钻，位置由高度场里"立得住的崖面"决定）
    caves = []
    xs_axis = np.linspace(-SIZE_M / 2, SIZE_M / 2, N)
    for spec in CAVES:
        site = find_cave_site(ob, xs_axis, H, spec)
        if not site:
            print("  ! no cliff found for cave '%s'" % spec["name"])
            continue
        azd, loc, wall_h, radius = site
        res = bore_cave(ob, azd, loc, wall_h, radius, spec["depth"], spec["tilt"])
        if res:
            caves.append(res)

    # 收尾清理：焊接、去碎片、补洞、重算法线
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=3.0e-3)
    bmesh.ops.dissolve_degenerate(bm, dist=3.0e-3, edges=bm.edges)
    tiny = [f for f in bm.faces if f.calc_area() < 3.0e-3]
    if tiny:
        bmesh.ops.delete(bm, geom=tiny, context='FACES')
    doomed = []
    for e in bm.edges:
        if len(e.link_faces) > 2:
            keep = max(e.link_faces, key=lambda f: f.calc_area())
            doomed += [f for f in e.link_faces if f is not keep]
    if doomed:
        bmesh.ops.delete(bm, geom=list(set(doomed)), context='FACES')
    holes = [e for e in bm.edges if len(e.link_faces) == 1]
    if holes:
        bmesh.ops.holes_fill(bm, edges=holes, sides=0)
    bmesh.ops.triangulate(bm, faces=bm.faces)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    me.update()
    for p in me.polygons:
        p.use_smooth = False

    colourise(me, caves)
    make_material(me)

    # 烘变换 + 原点归零
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    activate(ob)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    ob.data.transform(ob.matrix_world)
    ob.matrix_world.identity()

    nest = build_nest_placeholder() if do_nest else None

    # 导出 GLB：只有山（占位鸟巢 / 灯光 / 相机 / 海面都不进）
    activate(ob)
    glb = os.path.join(OUT_DIR, NAME + ".glb")
    bpy.ops.export_scene.gltf(filepath=glb, export_format='GLB', use_selection=True,
                              export_apply=True, export_yup=True,
                              export_texcoords=False, export_normals=True,
                              export_vertex_color='MATERIAL')

    # 预览
    if do_render:
        cam, sea = setup_preview()
        place_preview_rocks(ob, caves)
        shots_dir = "/tmp/nest_mountain"
        os.makedirs(shots_dir, exist_ok=True)
        far = 150.0
        az = math.radians(118)
        cam_34 = (math.cos(az) * far, math.sin(az) * far, 58.0)
        target = (0.0, 0.0, 20.0)
        p1 = os.path.join(shots_dir, "a.png")
        render_shot(cam, p1, cam_34, target)
        if nest:
            nest.hide_render = True
        p2 = os.path.join(shots_dir, "b.png")
        render_shot(cam, p2, cam_34, target)
        if nest:
            nest.hide_render = False
        # 俯视山顶
        p3 = os.path.join(shots_dir, "c.png")
        render_shot(cam, p3, (0.0, 0.0, 86.0), (0.0, 0.0, PEAK_H_M - 2.0))
        # 山脚洞口特写（用真实洞口位置 / 洞轴）
        c0 = caves[0]
        n0 = Vector((c0[1].x, c0[1].y, 0.0)).normalized()
        p4 = os.path.join(shots_dir, "d.png")
        render_shot(cam, p4, Vector(c0[0]) - n0 * 30.0 + Vector((0, 0, 6.0)),
                    Vector(c0[0]))
        if nest:
            nest.hide_render = True
        stitch([p1, p2, p3, p4], os.path.join(OUT_DIR, NAME + "_preview.png"), 2)

        # 洞口：每个洞来一组"全身 + 特写"，方便核对洞口在山体上的位置
        shots = []
        for i, (loc_v, direction, r, d) in enumerate(caves):
            n = Vector((direction.x, direction.y, 0.0)).normalized()   # 洞轴的水平朝向
            far_eye = Vector(loc_v) - n * 118.0 + Vector((0, 0, 46.0))
            tgt = Vector((0, 0, 18.0))
            p = os.path.join(shots_dir, "wide%d.png" % i)
            render_shot(cam, p, far_eye, tgt, res=(760, 560))
            shots.append(p)
            eye = Vector(loc_v) - n * 34.0 + Vector((0, 0, 5.0))
            p = os.path.join(shots_dir, "cave%d.png" % i)
            render_shot(cam, p, eye, Vector(loc_v) + n * 2.0, res=(760, 560))
            shots.append(p)
        stitch(shots, os.path.join(OUT_DIR, NAME + "_cave.png"), 2)
        if nest:
            nest.hide_render = False
        p = os.path.join(shots_dir, "top.png")
        render_shot(cam, p, (0.0, -26.0, 80.0), (0.0, 0.0, PEAK_H_M - 3.0), res=(900, 700))
        stitch([p], os.path.join(OUT_DIR, NAME + "_top.png"), 1)
        sea.hide_render = True

    blend = os.path.join(OUT_DIR, NAME + ".blend")
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=blend)

    zs = [v.co.z for v in me.vertices]
    xs = [v.co.x for v in me.vertices]
    ys = [v.co.y for v in me.vertices]
    print("=" * 62)
    print("%s  tris=%d  verts=%d" % (NAME, len(me.polygons), len(me.vertices)))
    print("BBOX  X %.1f  Y %.1f  Z %.1f..%.1f  (山脚占地 %.0f m, 主峰 %.1f m)"
          % (max(xs) - min(xs), max(ys) - min(ys), min(zs), max(zs),
             max(max(xs) - min(xs), max(ys) - min(ys)), max(zs)))
    print("山顶平台 Ø %.1f m, 鸟巢坑 Ø %.1f m 深 %.1f m, 坑底 z=%.1f"
          % (PLATEAU_R_M * 2, NEST_R_M * 2, PEAK_H_M - NEST_FLOOR_M, NEST_FLOOR_M))
    print("山洞:", ["az=%.0f z=%.1f r=%.2f"
                    % (math.degrees(math.atan2(-c[1].y, -c[1].x)) % 360.0,
                       c[0].z, c[2]) for c in caves] if caves else "无")
    print("saved:", glb)
    print("saved:", blend)


if __name__ == "__main__":
    main()
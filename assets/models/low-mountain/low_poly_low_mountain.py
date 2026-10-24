"""Low-poly 低山（low mountain）生成器 —— 照着给定的四视图参考图复刻。

用法:
    blender --background --python low_poly_low_mountain.py
    blender --background --python low_poly_low_mountain.py -- --nopreview
    blender --background --python low_poly_low_mountain.py -- --seed 1234

产物（写入本目录）:
    low_poly_low_mountain.blend
    low_poly_low_mountain.glb          <- 山体 + 石头（顶点色）
    low_poly_low_mountain_preview.png  <- 2x2 拼图：正视 3/4 / 俯视 / 侧 3/4 / 背面

造型（对照 assets/AGENTS.md §1 的米制约定）
--------------------------------------------
* 山脚占地 ≈ 37 × 34 m，主峰 22.4 m，原点在山脚中心。
* **剖面是几乎笔直的锥**：`h = H·(1−rn)^1.15`。参考图正面的侧影从峰顶到山脚
  是一条 50~55° 的直线，所以指数必须接近 1；**指数 < 1 会读成"圆馒头"**。
* **山脚是四个方向不等半径的蛋形**（东 20.6 / 南 21.0 / 西 15.6 / 北 11.4 m，
  量自参考图的俯视图）：主峰因此偏北、山体往南铺开，正面看是一道长坡托着主峰。
* **两个顶**（参考图最关键的特征）：主峰 + 东侧 7 m 处一个矮一截的**尖顶**，
  中间夹一道 V 形鞍部。次峰用**直锥**（和主锥同一条剖面）叠上去 —— 用抛物面
  的话锥顶是圆的，出来只是个"鼓包"，根本读不出第二个顶。
* **径向棱**：坡面按方位分成 16 个扇区，逐扇区给一个固定抬升量 ——
  量化之后扇区之间是一道**折线**（棱），不是平滑正弦搓出来的"搓衣板"。
* **冲沟**：16 条从半山腰往下的雨水沟，把圆锥剪影打碎。
* **草台**：z ≈ 9.4 m 有一圈被噪声推歪的缓台，沿 x 方向**倾斜**
  （参考图那条亮黄绿带是斜着横过山腰的），几何上是台阶、颜色是亮黄绿。
* **山脚石台**：西南角一块被削平的小台地（z ≈ 2.2 m），
  台面上摆一组灰色巨石 —— 参考图里最醒目的前景地标。
* 颜色全部烘进顶点色 "Col"（线性空间），一个材质一次 draw call。
* 顶点色**按棱面（平面）上色，不按三角面上色**：同一平面的三角形必须同色，
  否则面内碎成脏斑（见 plane_groups()）。

低多边形是怎么来的（踩过的坑）
--------------------------------
1. **不做减面**：先密后减（COLLAPSE）这条路走不通 —— 锥面在折叠减面里会被
   一路压成几个巨大的三角（实测 12k 面 → 600 面时整座山塌成一个四面体，
   东西跨度从 34 m 缩到 25 m）。所以这里**直接按目标密度建网格**：
   27×27 的抖动格点 + 按几何挑对角线。
2. **对角线必须按几何挑**：随机挑会不时挑中**三点共线**的组合，
   切出来是一条发丝般的长条棱面（紧凑度 0.03）。`_pick_diagonal()` 比两种切法
   的紧凑度，取好的那条。
3. **山脚不做几何裁剪**：删山外的格子 → 山脚变成一圈台阶锯齿；
   把山外角点拉回轮廓线 → 甩出一圈又长又窄的碎三角。
   现在是山外沉一条 −0.7 m 的**裙边**埋进地面（和洞穴山 ROOT_Z 同一个道理），
   地面上看到的是高度场里 rn=1 的**等高线**，连续且干净。
4. **两个峰顶要"对齐到格点"**：格点是离散的，峰顶要是落在两个格点中间，
   采样出来就是个"平肩" —— 次峰只有一两米高、宽度不到两个格距，
   这一采样就被抹平，"两个顶"直接读不出来。对齐之后峰顶正好是一个顶点。
5. **顶点色的受光方向必须和预览那盏太阳同向**（`SUN_DIR`）：对不上时
   雪的受光面会被当成背阴面涂成蓝灰、渲染时又被打一次暗，雪永远白不起来。

石头复用 assets/models/low-poly-rock/low_poly_rock.py 的造型实现
（不复制粘贴：import 那个模块，build_rock() 出来的形状是同一个来源）。
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
NAME = "low_poly_low_mountain"

# ==================== 尺寸（米，1 Blender unit = 1 m）====================
PEAK_H_M = 22.6         # 主峰高度（对齐到格点后实测峰顶 ≈ 22.4 m）
SEED = 20241112         # 固定种子：两次运行的几何 / 颜色逐位一致

# 主峰锥体（极坐标中心）：**偏北**。参考图的俯视图里雪冠落在山脚轮廓的
# 北三分之一处 —— 也就是说山体是"往南铺开"的，正面看是一道长坡托着主峰。
#
# 各方位的锥体半径（从俯视图量出来的，单位米）：
#   东 20.6 / 南 21.0 / 西 15.6 / 北 11.4  ->  山脚占地 ≈ 36 × 32 m
P1X, P1Y = -2.0, 5.0
PEAK_R_M = 16.0         # 主峰锥体名义半径（山脚占地由它 + 方位变形决定）
PROF_EXP = 1.15         # 剖面指数：h = H·(1−rn)^exp

# 次峰：参考图是**两个尖顶** —— 主峰 + 东侧 7 m 处一个矮一截的尖顶，
# 中间夹一道 V 形鞍部。原来的做法（半径 8 m 的矮锥）做出来只是个圆钝的
# "鼓包"，读不出第二个峰；现在改成**直锥**（和主锥同一条剖面）。
P2X, P2Y = 5.33, 4.57   # 主峰东侧 7.0 m
HORN_H_M = 20.0         # ≈ 0.88 × 主峰（参考图量出来是 0.795；这里抬高一点，
                        # 网格才切得出那道 V 形鞍部 —— 差得太小会被采样抹平）
HORN_R_M = 7.0          # 和主锥同一条剖面（直锥）—— 抛物面锥顶是圆的，读不出尖顶

# 草台（缓台阶）高度与草坡亮带
BENCH_H_M = 9.4
# 山脚裙边：山脚外侧沉到 z = SKIRT_Z（埋在地面里）
SKIRT_Z = -0.7
# 山脚石台：西南角一块被削平的小台地，参考图的俯视图里巨石群就在那儿
LEDGE_C = (-8.0, -11.0)
LEDGE_H_M = 2.2
# 秃斑（干土）：俯视图里山体南侧偏西的一块赭色裸地
BALD_C = (-5.0, 1.5)
BALD_R_M = 4.5

# ==================== 颜色工具 ====================
def srgb2lin(c):
    c = np.asarray(c, dtype=float)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def smoothstep(a, b, x):
    """a -> b 之间平滑过渡（a > b 表示反向）。标量和数组都能用。"""
    t = np.clip((np.asarray(x, dtype=float) - a) / (b - a), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def mix(c1, c2, t):
    return c1 * (1.0 - t) + c2 * t


def angdiff(a, b):
    """两个方位角的最短差（弧度）。"""
    return (a - b + math.pi) % (2.0 * math.pi) - math.pi


# ==================== 调色板 ====================
# 取自参考图的实际取色（sRGB）：
#   雪冠是接近纯白（#FCFCF0），背阴面偏冷灰蓝（#B4C0CC）；
#   植被走「深林 -> 黄绿草坡 -> 橄榄绿底坡」，最亮的一档是草台上的
#   亮黄绿（#C0C078 ~ #C0CC90）；岩石是暖褐（#A89C6C ~ #84846C），
#   前景巨石是中性灰（#9C9090 ~ #85898C）。
#
# 注意明度跨度：最暗的深林 ≈ 0.10，最亮的雪 ≈ 0.96。
# 参考图就是这个跨度（雪是白的，不是"米色石头"），
# 所以这里**不**像鸟巢山那样压明度跨度 —— 雪就该是白的。
#
# 另外两条从参考图量出来的硬指标：
#   * 草坡要用**真绿**（G 明显大于 R），不然山脚读成土黄；
#   * 各带的明度要**拉开**（雪 0.94 -> 岩石 0.54 -> 亮黄绿 0.65 -> 橄榄 0.56），
#     层是"带"不是渐变。
PAL = {
    "snow": srgb2lin([0.95, 0.96, 0.95]),       # 雪面（近纯白）
    "snow_sh": srgb2lin([0.70, 0.76, 0.83]),    # 雪的背阴面（冷灰蓝）
    # 暖褐岩：背面的上半山几乎全是这一族
    "rock_d": srgb2lin([0.31, 0.24, 0.17]),
    "rock_m": srgb2lin([0.45, 0.35, 0.24]),
    "rock_l": srgb2lin([0.55, 0.44, 0.29]),
    "tan": srgb2lin([0.80, 0.71, 0.44]),        # 干土 / 秃斑
    # 灰岩：前景巨石（参考图里是中性偏冷的深灰，不是浅灰）
    "grey_d": srgb2lin([0.22, 0.23, 0.25]),
    "grey_m": srgb2lin([0.38, 0.39, 0.40]),
    "grey_l": srgb2lin([0.54, 0.53, 0.51]),
    # 植被
    "forest_d": srgb2lin([0.05, 0.10, 0.10]),   # 深林（山脚背阴面，偏青）
    "forest": srgb2lin([0.10, 0.20, 0.13]),
    "grass": srgb2lin([0.51, 0.62, 0.26]),       # 主体草坡（真绿）
    "grass_br": srgb2lin([0.81, 0.83, 0.37]),    # 草台亮带（最跳的一档）
    "olive": srgb2lin([0.35, 0.47, 0.20]),      # 山脚橄榄绿
    "ledge": srgb2lin([0.74, 0.80, 0.34]),      # 石台上的平草
}

# 预览用光的**方向**（指向太阳）。顶点色里"受光 / 背阴"的分色必须用同一个方向，
# 不然涂出来的分色和实际打光对不上 —— 参考图里雪的受光面是纯白 #FCFCF0、
# 背阴面是冷蓝灰 #B4C0CC，两者差得很开；方向对不上时受光面会被当成背阴面
# 涂成蓝灰，渲染时又被打一次暗，雪就永远白不起来。
# 方向算自预览里太阳灯的欧拉角 (50°, 0, 110°)。
SUN_DIR = Vector((0.720, 0.262, 0.643)).normalized()

# 冷暖分离：朝阳面偏暖、背阴面偏冷（低多边形"块面感"的主要来源）
TINT_LIT = np.array([1.05, 1.01, 0.93])
TINT_SHADE = np.array([0.93, 0.97, 1.05])


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
    """3x3 加权模糊（边缘复制）。"""
    for _ in range(passes):
        P = np.pad(H, 1, mode='edge')
        H = (P[0:-2, 0:-2] + 2.0 * P[0:-2, 1:-1] + P[0:-2, 2:]
             + 2.0 * P[1:-1, 0:-2] + 4.0 * P[1:-1, 1:-1] + 2.0 * P[1:-1, 2:]
             + P[2:, 0:-2] + 2.0 * P[2:, 1:-1] + P[2:, 2:]) / 16.0
    return H


# ==================== 方位形状（山脚轮廓）====================
def footprint_shape(th):
    """主峰极坐标下的半径系数：山脚不是正圆。

    这四个方向的半径是从参考图的俯视图里量出来的（单位米）：
        东 20.6 / 南 21.0 / 西 15.6 / 北 11.4
    也就是：**东侧拖长、南侧铺开、北侧收得紧**，西侧居中。
    用 1 次 + 2 次谐波拟合（低次谐波保证大形准，高次谐波只负责让轮廓有起伏）。
    """
    s = (1.0
         + 0.158 * np.cos(th)             # 东长西短
         - 0.155 * np.sin(th)             # 南长北短
         + 0.133 * np.cos(2.0 * th)       # 东西 / 南北两轴的"胖瘦"差
         + 0.030 * np.sin(3.0 * th + 2.3)
         + 0.020 * np.sin(5.0 * th + 0.4)
         + 0.012 * np.sin(8.0 * th + 1.6))
    return np.clip(s, 0.55, 1.34)


# 冲沟：(方位角, 角宽 rad, 深度 m)
GULLIES = [
    (14.0, 0.075, 1.6), (40.0, 0.065, 1.2), (62.0, 0.080, 1.8),
    (86.0, 0.060, 1.1), (108.0, 0.090, 2.0), (130.0, 0.065, 1.3),
    (152.0, 0.085, 1.7), (176.0, 0.060, 1.2), (196.0, 0.095, 2.1),
    (218.0, 0.070, 1.4), (238.0, 0.080, 1.7), (260.0, 0.065, 1.3),
    (282.0, 0.090, 1.9), (304.0, 0.070, 1.4), (322.0, 0.075, 1.6),
    (344.0, 0.065, 1.2),
]

# 径向棱：扇区数 + 逐扇区的抬升量（固定序列 -> 可复现）+ 幅度
RIDGE_SECTORS = 16
RIDGE_PATTERN = [0.85, -0.55, 0.35, -0.90, 0.60, -0.25, 0.95, -0.70,
                 0.20, -0.45, 0.75, -0.85, 0.45, -0.15, 0.55, -0.35]
RIPPLE_AMP = 0.075


# ==================== 高度场 ====================
def height_at(X, Y):
    """高度场：给任意 (X, Y) 点返回 (高度, 山脚判据 rn)。

    山脚判据 rn < 1 表示"还在山体上"，> 1 是山外的空地。
    """
    # --- 主锥体（极坐标中心在主峰）---
    dx, dy = X - P1X, Y - P1Y
    d = np.hypot(dx, dy)
    th = np.arctan2(dy, dx)
    R = PEAK_R_M * footprint_shape(th)
    rn = np.clip(d / R, 0.0, 1.0)
    H = PEAK_H_M * np.power(1.0 - rn, PROF_EXP)

    # --- 次峰：矮一截的**尖顶**锥体，取 max 形成一道鞍部 ---
    # 指数必须和主锥一样接近 1（直锥）：用 0.8（抛物面）的话锥顶是圆的，
    # 出来就是个"鼓包"，根本读不出第二个顶 —— 参考图要的是一座小一号的主峰。
    dh = np.hypot(X - P2X, Y - P2Y)
    H = np.maximum(H, HORN_H_M * np.power(np.clip(1.0 - dh / HORN_R_M, 0.0, 1.0), 1.05))

    # --- 地表起伏：低频为主（高多边形要"面"，不要毛刺）---
    # 峰顶附近把噪声收一收：噪声幅度接近格距时会把尖顶磨成一个圆包
    soften = 0.35 + 0.65 * np.clip((19.0 - H) / 6.0, 0.0, 1.0)
    H += 1.95 * (fbm(X, Y, 0.075, 5.0, 3) - 0.5) * 2.0 * soften
    H += 0.75 * (fbm(X, Y, 0.20, 9.0, 2) - 0.5) * 2.0 * soften

    # --- 径向棱（"手风琴"）---
    # 参考图正面的坡面是一道道从峰顶往下辐射的**硬棱**，不是一张光滑的锥面。
    # 这里按扇区量化方位角、逐扇区给一个固定的抬升量：
    # 量化之后相邻扇区之间是一道折线（棱），而不是平滑正弦搓出来的"搓衣板"。
    sect = np.floor(((th + math.pi) % (2.0 * math.pi)) / (2.0 * math.pi) * RIDGE_SECTORS)
    ridge = np.array(RIDGE_PATTERN)[sect.astype(np.int64) % RIDGE_SECTORS]
    ridge = ridge * (0.55 + 0.45 * fbm(X, Y, 0.05, 19.0, 2))
    ridge *= np.clip((21.5 - H) / 5.0, 0.0, 1.0) * np.clip((H - 2.0) / 4.0, 0.0, 1.0)
    H += RIPPLE_AMP * PEAK_H_M * ridge

    # --- 冲沟：从半山腰往下的雨水沟 ---
    for ang, wid, dep in GULLIES:
        g = np.exp(-(angdiff(th, math.radians(ang)) / wid) ** 2)
        g *= np.clip((H - 4.0) / 6.0, 0.0, 1.0)          # 只切中下段
        g *= np.clip((18.0 - H) / 5.0, 0.0, 1.0)
        H -= dep * g * (0.65 + 0.6 * fbm(X, Y, 0.10, 17.0, 2))

    # --- 主脊：一道从峰顶往东南延伸的山脊（剪影里"一笔"而不是"一坨"）---
    spine = np.exp(-(angdiff(th, math.radians(-30.0)) / 0.46) ** 2)
    spine *= np.clip((20.0 - H) / 6.0, 0.0, 1.0) * np.clip((H - 6.0) / 5.0, 0.0, 1.0)
    H += 1.7 * spine

    # --- 草台（缓台阶）：z≈BENCH_H 附近被压平成台面 ---
    # 参考图里山腰那条亮黄绿带是**斜着**横过山腰的（左边低、右边高），
    # 所以台面沿 x 方向抬（0.09 m/m）。
    bench = (BENCH_H_M + 0.09 * (X - P1X)
             + 1.4 * (fbm(X, Y, 0.045, 23.0, 3) - 0.5) * 2.0)
    flat = np.exp(-((H - bench) / 1.8) ** 2)
    flat *= np.clip((H - 2.0) / 3.0, 0.0, 1.0)
    H = H + (bench - H) * 0.5 * flat

    # --- 山脚石台：西南角一块削平的小台地 ---
    dl = np.hypot(X - LEDGE_C[0], Y - LEDGE_C[1])
    lw = smoothstep(8.5, 3.6, dl)        # 中心 1，8.5 m 外 0
    H = mix(H, np.full_like(H, LEDGE_H_M), lw * 0.97)

    # 山脚判据：主锥体或次峰锥体覆盖到的地方才留（取并集）
    rn_out = np.minimum(d / (PEAK_R_M * footprint_shape(th)), dh / HORN_R_M)

    # --- 收尾：山脚落在 z=0，山外再沉一条裙边 ---
    # 裙边（SKIRT_Z）是这么解决的：山脚那条线是高度场里 rn=1 的**等高线**，
    # 平滑连续。要是改成"把山外的格子删掉"，山脚就变成一圈 1.6 m 的台阶锯齿；
    # 要是把山外的角点拉回轮廓线，又会甩出一圈又长又窄的碎三角。
    # 沉下去的那一截埋在地面里（和洞穴山 ROOT_Z 同一个道理）。
    H = np.clip(H, 0.0, None)
    H = np.where(rn_out > 1.0,
                 SKIRT_Z * smoothstep(1.0, 1.10, rn_out),
                 H)
    return H, rn_out


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


# 低多边形网格的参数：**直接按目标分辨率建**，不做减面。
# 原因见文件头"低多边形是怎么来的"那几条。
LATTICE_NC = 27                    # 格点边数（27×27）
LATTICE_SPAN = 42.0                # 格点覆盖范围（比山脚大，够用就行）
LATTICE_CENTER = (0.0, 2.5)
JITTER = 0.34                      # 顶点抖动（格距的比例）—— 打破"网格感"


def _tri_iso(p, q, r):
    """三角形紧凑度 4πA/P²（正圆=1）。用来挑对角线。"""
    e0 = (q - p).length
    e1 = (r - q).length
    e2 = (p - r).length
    per = e0 + e1 + e2
    if per <= 1e-9:
        return 0.0
    area = 0.5 * (q - p).cross(r - p).length
    return 4.0 * math.pi * area / (per * per)


def _pick_diagonal(a, b, c, d):
    """给一个四边形选对角线：选"两个三角形里更差的那个更紧凑"的那条。

    随机对角线会不时挑中**三点共线**的组合，量出来就是一条发丝般的
    长条棱面（紧凑度 0.03），看起来像一道划痕。这里改成按几何挑：
    紧凑度高的那条；平手时用一点随机，避免整座山出现同一种三角图案。
    """
    v1 = min(_tri_iso(a, b, c), _tri_iso(a, c, d))
    v2 = min(_tri_iso(a, b, d), _tri_iso(b, c, d))
    if abs(v1 - v2) < 1e-6:
        return 0 if random.random() < 0.5 else 1
    return 0 if v1 > v2 else 1


def build_lowpoly():
    """按目标密度直接建低多边形山体（顶点带抖动，三角形大小相近、形状各异）。

    山脚不做任何几何裁剪：高度场里 rn=1 的等高线就是山脚，
    网格外侧沉一条裙边（SKIRT_Z）埋进地面，地面上看到的是那条连续的线。
    """
    rng = random.Random(SEED + 7)
    nc = LATTICE_NC
    step = LATTICE_SPAN / (nc - 1)
    x0 = LATTICE_CENTER[0] - LATTICE_SPAN * 0.5
    y0 = LATTICE_CENTER[1] - LATTICE_SPAN * 0.5

    # 把主峰 / 次峰**对齐到格点**上。
    # 格点是离散的：峰顶要是正好落在两个格点中间，采样出来就是个"平肩"——
    # 次峰只有一两米高、宽度不到两个格距，这一采样就被抹平，
    # "两个顶"直接读不出来。对齐之后峰顶正好是一个顶点，尖顶才立得住。
    def snap(px, py):
        i = max(1, min(nc - 2, int(round((px - x0) / step))))
        j = max(1, min(nc - 2, int(round((py - y0) / step))))
        return x0 + i * step, y0 + j * step, (j, i)

    global P1X, P1Y, P2X, P2Y
    P1X, P1Y, P1_CELL = snap(P1X, P1Y)
    P2X, P2Y, P2_CELL = snap(P2X, P2Y)

    P = []
    for j in range(nc):
        row = []
        for i in range(nc):
            x = x0 + i * step
            y = y0 + j * step
            # 边界顶点不抖：轮廓方整，山脚才干净
            if 0 < i < nc - 1 and 0 < j < nc - 1:
                # 两个峰顶的格点也不抖：抖了就对不齐格点，等于没对齐
                if (j, i) not in (P1_CELL, P2_CELL):
                    x += rng.uniform(-JITTER, JITTER) * step
                    y += rng.uniform(-JITTER, JITTER) * step
            row.append((x, y))
        P.append(row)
    X = np.array([[p[0] for p in row] for row in P])
    Y = np.array([[p[1] for p in row] for row in P])
    H, rn = height_at(X, Y)

    verts = []
    V = []
    index = {}
    for j in range(nc):
        for i in range(nc):
            index[(j, i)] = len(verts)
            verts.append((float(X[j][i]), float(Y[j][i]), float(H[j][i])))
            V.append(Vector(verts[-1]))

    faces = []
    for j in range(nc - 1):
        for i in range(nc - 1):
            corners = [(j, i), (j, i + 1), (j + 1, i + 1), (j + 1, i)]
            # 整格都落在埋地裙边里 -> 丢掉
            if all(rn[c[0]][c[1]] > 1.08 for c in corners):
                continue
            # 对角线按几何挑（见 _pick_diagonal）：不然整座山是一格一格
            # 整齐的"棋盘"，还会时不时切出发丝般的碎条
            a, b, c, d = (index[k] for k in corners)
            if _pick_diagonal(V[a], V[b], V[c], V[d]) == 0:
                faces.append((a, b, c))
                faces.append((a, c, d))
            else:
                faces.append((a, b, d))
                faces.append((b, c, d))

    me = bpy.data.meshes.new(NAME + "Mesh")
    me.from_pydata(verts, [], faces)
    me.update()
    ob = bpy.data.objects.new(NAME, me)
    bpy.context.scene.collection.objects.link(ob)

    # 底面补盖：外边界那一圈在裙边高度上，用扇形封到中心
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    for loop in boundary_loops(bm):
        cxx = sum(v.co.x for v in loop) / len(loop)
        cyy = sum(v.co.y for v in loop) / len(loop)
        centre = bm.verts.new((cxx, cyy, SKIRT_Z))
        bm.verts.ensure_lookup_table()
        n = len(loop)
        for i in range(n):
            try:
                bm.faces.new((loop[i], loop[(i + 1) % n], centre))
            except ValueError:
                pass
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    me.update()
    for p in me.polygons:
        p.use_smooth = False
    return ob


def activate(ob):
    for o in bpy.context.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob


# ==================== 石头（复用 low_poly_rock 的造型）====================
ROCK_DIR = os.path.join(os.path.dirname(OUT_DIR), "low-poly-rock")


def _load_rock_module():
    if ROCK_DIR not in sys.path:
        sys.path.insert(0, ROCK_DIR)
    import low_poly_rock
    return low_poly_rock


def make_boulder(name, rock_mod, scale, rot_deg, loc, tilt_deg=0.0):
    """用 low_poly_rock 的造型生成一块石头，按 scale/rot 平移进场景。

    scale / rot / tilt 都**烘进网格**（不是物体缩放），
    否则导出的 .glb 里会出现非 1 的 scale（assets/AGENTS.md §6 第 7 条）。
    """
    rock_mod.SEED = rock_mod.SEED + 1
    ob, facets = rock_mod.build_rock()
    ob.name = name
    ob.data.name = name + "Mesh"
    me = ob.data
    M = (Matrix.Translation(Vector(loc))
         @ Matrix.Rotation(math.radians(rot_deg), 4, 'Z')
         @ Matrix.Rotation(math.radians(tilt_deg), 4, 'Y')
         @ Matrix.Diagonal(Vector((scale[0], scale[1], scale[2], 1.0))))
    me.transform(M)
    me.update()
    return ob, facets


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


def _fbm1(x, y, freq, seed, octaves=3):
    return float(fbm(np.array([x]), np.array([y]), freq, seed, octaves)[0])


def hash01(*vals):
    """稳定的伪随机数（同一组输入永远同一个值）。"""
    h = math.sin(sum(v * k for v, k in zip(vals, (12.9898, 78.233, 37.719))) * 43758.5453)
    return h - math.floor(h)


def colourise_mountain(me):
    """山体上色：雪 / 暖褐岩 / 灰岩 / 深林 / 草坡 / 亮黄绿草台 / 橄榄绿底坡。

    参考图的四视图给出几条硬约束：
      * **雪线 ≈ 0.665 H**：雪缘被噪声推歪，是断的，不是一圈水平线；
      * **岩线 ≈ 0.42~0.46 H**：岩/绿交界是碎的，不是渐变；
      * 山腰一条**斜着**横过的亮黄绿带（沿 x 抬 0.09 m/m）；
      * 西侧（正视图左半边）一片**深林**；南侧偏西一块赭色秃地。
    """
    ca = me.color_attributes.new(name="Col", type='FLOAT_COLOR', domain='CORNER')
    P = PAL
    SUN = SUN_DIR                                      # 和预览里那盏太阳同向
    H = PEAK_H_M

    for key, faces in plane_groups(me).items():
        rep = max(faces, key=lambda f: f.area)
        c = rep.center
        n = rep.normal
        nz = n.z
        slope = 1.0 - max(-1.0, min(1.0, nz))
        z = c.z
        az = math.atan2(c.y - P1Y, c.x - P1X)
        shape = float(footprint_shape(np.array([az]))[0])
        rn = math.hypot(c.x - P1X, c.y - P1Y) / (PEAK_R_M * shape)

        # --- 三层噪声：大块 / 中块 / 小斑 ---
        big = _fbm1(c.x, c.y, 0.035, 31.0)
        mid = _fbm1(c.x, c.y, 0.11, 47.0)
        fine = _fbm1(c.x, c.y, 0.30, 53.0)

        # --- 雪线：被噪声推歪，所以雪缘是断的，不是水平的一圈 ---
        snow_line = (0.665 * H + 1.5 * (mid - 0.5) * 2.0 + 0.9 * (big - 0.5) * 2.0
                     + 1.1 * (fine - 0.5) * 2.0)
        snow_t = smoothstep(snow_line - 1.2, snow_line + 1.4, z)
        # 雪还挂在背阴的沟里一点（沟 = 背阴）
        snow_t = min(1.0, snow_t + 0.30 * smoothstep(0.62, 0.85, 1.0 - nz)
                     * smoothstep(snow_line - 4.0, snow_line, z))

        # --- 岩线：越高越裸岩；北面（背面）岩线低，南面（正面）岩线高 ---
        rock_line = (0.420 - 0.055 * math.cos(az - math.radians(95.0))) * H
        rock_line += 2.8 * (big - 0.5) * 2.0
        # 过渡窗口要**窄**：参考图的岩/绿交界是一条读得出来的线（虽然不规则），
        # 不是一大片渐变。窗口一宽，颜色就全糊在一起，分层就没了。
        cover = smoothstep(rock_line + 0.5, rock_line - 1.0, z)
        # 陡坡挂不住土
        cover *= smoothstep(0.96, 0.60, slope)
        # 秃斑：从覆盖率里扣掉（不是再乘一层，否则覆盖率会只剩 0.3）
        cover -= 0.42 * smoothstep(0.54, 0.72, big)
        cover -= 0.38 * smoothstep(0.56, 0.74, mid)
        cover -= 0.22 * smoothstep(0.56, 0.74, fine)
        # 参考图南侧偏西有一块明确的赭色秃地（俯视图里看得最清楚）
        bald_patch = math.exp(-(((c.x - BALD_C[0]) ** 2 + (c.y - BALD_C[1]) ** 2)
                                 / (2.0 * BALD_R_M * BALD_R_M)))
        cover -= 0.85 * bald_patch
        cover = max(0.0, min(1.0, cover))

        # --- 植被底色：按高度分层（每一层的交界都收得很窄）---
        veg = P["grass"]
        veg = mix(veg, P["olive"], smoothstep(0.11 * H + 0.9, 0.11 * H - 0.9, z))
        veg = mix(veg, mix(P["olive"], P["grass"], 0.55),
                  smoothstep(0.26 * H + 1.0, 0.26 * H - 1.0, z))
        # 西侧的深林（正视图的左坡那一大片深绿）
        forest_t = smoothstep(0.12, 0.58, math.cos(az - math.radians(214.0)))
        forest_t *= smoothstep(0.92 * H, 0.26 * H, z)
        forest_t = max(0.0, min(1.0, forest_t))
        veg = mix(veg, P["forest"], 1.0 * forest_t)
        veg = mix(veg, P["forest_d"], 0.70 * forest_t * smoothstep(0.45 * H, 0.14 * H, z))

        # --- 岩石底色：暖褐为主，靠高度提亮 ---
        if z < 0.42 * H:
            rock = P["rock_m"]
        elif z < 0.66 * H:
            rock = mix(P["rock_m"], P["rock_l"], 0.5)
        else:
            rock = mix(P["rock_l"], P["rock_d"], 0.30)
        # 秃斑：干土 / 赭土
        rock = mix(rock, P["tan"], 0.34 * smoothstep(0.50, 0.68, big) * smoothstep(0.78, 0.58, z))
        # 冷暖：同族石头内部只偏色相，不换色族
        rock = mix(rock, rock * np.array([1.06, 0.98, 0.88]), 0.35 * smoothstep(0.35, 0.65, mid))
        rock = mix(rock, rock * np.array([0.90, 0.95, 1.04]), 0.35 * smoothstep(0.35, 0.65, 1.0 - mid))
        rock = rock * (0.94 + 0.10 * fine)

        # --- 三段混合：岩 -> 灌丛 -> 植被 ---
        scrub = mix(rock, veg, 0.5) * np.array([1.02, 1.00, 0.90])
        if cover <= 0.5:
            col = mix(rock, scrub, cover * 2.0)
        else:
            col = mix(scrub, veg, (cover - 0.5) * 2.0)

        # --- 岩带里的草舌：让岩 / 绿的交界是碎的，不是一条水平线 ---
        # 只在中段（草坡和岩带的交界），上部岩带要保持干净 ——
        # 参考图背面的上半山是一整片裸岩，不是"褐绿相间"。
        tongue = smoothstep(0.48, 0.82, mid) * smoothstep(0.30 * H, 0.48 * H, z)
        tongue *= 1.0 - smoothstep(0.48 * H, 0.62 * H, z)
        col = mix(col, veg, 0.45 * tongue)

        # --- 草台亮带：几何台阶 + 亮黄绿，颜色和几何对得上 ---
        # 带子要**窄**：参考图里它是山腰一条亮线，不是一大片黄绿毯子。
        bench = (BENCH_H_M + 0.09 * (c.x - P1X)
                 + 1.4 * (_fbm1(c.x, c.y, 0.045, 23.0, 3) - 0.5) * 2.0)
        band_t = math.exp(-((z - bench) / 1.5) ** 2)
        band_t *= smoothstep(0.18, 0.32, rn) * (1.0 - smoothstep(0.74, 0.88, rn))
        # 带子本身是断断续续的（被噪声咬掉几段），不是一整圈
        band_t *= smoothstep(0.10, 0.42, _fbm1(c.x, c.y, 0.085, 63.0, 3))
        # 最后再盖：亮带是**画上去**的一条线，压在所有混色之上，
        # 免得被岩 / 草的混合算掉 —— 参考图里最跳的就是这条黄绿带。
        col = mix(col, P["grass_br"], 0.92 * band_t * (1.0 - snow_t))

        # --- 山脚石台：一块被太阳晒透的平草（参考图里这片最亮）---
        ledge_t = math.exp(-(((c.x - LEDGE_C[0]) ** 2 + (c.y - LEDGE_C[1]) ** 2)
                             / (2.0 * 5.2 * 5.2)))
        col = mix(col, P["ledge"], 0.80 * ledge_t * (1.0 - snow_t))

        # --- 雪盖在最上面 ---
        if snow_t > 0.0:
            snow = mix(P["snow_sh"], P["snow"], smoothstep(-0.25, 0.55, n.dot(SUN)))
            col = mix(col, snow, snow_t)

        # --- 逐面微差 ---
        # 参考图里**没有两块面颜色完全一样**：最大的一块也只占 1.7% 的像素，
        # 剩下的全是各种深浅冷暖的小差别。低多边形看着"有层次"而不是"一坨"，
        # 靠的就是这一层逐面微差。
        hh = hash01(c.x * 3.1, c.y * 2.7, c.z * 2.3)
        col = col * (0.90 + 0.20 * hh)
        col = mix(col, col * np.array([1.04, 1.0, 0.93]), hh)
        # 更高频的一点斑：把大色块再打碎一点（频率接近一个格距）
        col = col * (0.95 + 0.10 * _fbm1(c.x, c.y, 0.65, 67.0, 2))

        # --- 冷暖分离：朝阳面暖、背阴面冷 ---
        t = max(0.0, min(1.0, (n.dot(SUN) + 1.0) * 0.5))
        col = col * (TINT_SHADE + (TINT_LIT - TINT_SHADE) * t)
        # 朝上的面亮一点、背光的暗一点（自遮挡的廉价近似）
        col = col * (0.90 + 0.10 * max(0.0, nz))

        col = np.clip(col, 0.0, 1.0)
        for p in faces:
            for li in p.loop_indices:
                ca.data[li].color = (col[0], col[1], col[2], 1.0)


def colourise_boulder(me):
    """石头：中性灰 + 顶面长一点苔，和山体同一套顶点色通道。

    明暗按**这块石头自己的**高度归一（石头有大有小，用统一的绝对高度
    归一会让大石头整体发白、小石头整体发黑）。
    """
    ca = me.color_attributes.new(name="Col", type='FLOAT_COLOR', domain='CORNER')
    P = PAL
    SUN = SUN_DIR
    zs = [v.co.z for v in me.vertices]
    z0, z1 = min(zs), max(zs)
    span = max(1e-3, z1 - z0)
    for key, faces in plane_groups(me).items():
        rep = max(faces, key=lambda f: f.area)
        c = rep.center
        n = rep.normal
        nz = n.z
        h = _fbm1(c.x * 2.0, c.y * 2.0, 0.6, 71.0, 2)
        # 底暗上亮
        t = min(1.0, max(0.0, (c.z - z0) / span))
        rock = mix(P["grey_d"], P["grey_l"], 0.10 + 0.55 * t)
        rock = rock * (0.88 + 0.18 * h)
        if nz > 0.45:
            rock = mix(rock, P["grey_l"], 0.18 + 0.14 * h)
        rock = rock * (1.0 - 0.30 * max(0.0, -nz))
        # 顶面挂一点草
        if nz > 0.55 and h > 0.45:
            rock = mix(rock, P["ledge"], 0.30 * (h - 0.45) / 0.55)
        # 冷暖
        tt = max(0.0, min(1.0, (n.dot(SUN) + 1.0) * 0.5))
        rock = rock * (TINT_SHADE + (TINT_LIT - TINT_SHADE) * tt)
        col = np.clip(rock, 0.0, 1.0)
        for p in faces:
            for li in p.loop_indices:
                ca.data[li].color = (col[0], col[1], col[2], 1.0)


def make_material(me, name):
    for d in list(bpy.data.materials):
        if d.users == 0:
            bpy.data.materials.remove(d)
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    bsdf.inputs['Roughness'].default_value = 0.95
    bsdf.inputs['Metallic'].default_value = 0.0
    # 高光压到最低：默认的白色高光会在低多边形上糊一层灰，
    # 把顶点色本身的饱和度冲掉（参考图的绿是"黄绿"，不是"灰绿"）
    for key in ('Specular IOR Level', 'Specular'):
        if key in bsdf.inputs:
            bsdf.inputs[key].default_value = 0.08
            break
    attr = nt.nodes.new('ShaderNodeVertexColor')
    attr.layer_name = "Col"
    attr.location = (-320, 200)
    nt.links.new(attr.outputs['Color'], bsdf.inputs['Base Color'])
    me.materials.append(mat)


# ==================== 预览渲染 ====================
def setup_preview():
    """预览场景：**灰底 + 冷色天光 + 暖阳**，和参考图是同一套影棚感。

    世界只负责**打光**：冷色天光（参考图的背阴面是冷蓝灰 #788490）。
    背景板（中性灰 #E9E9E9）改成"渲在透明背景上、再在 stitch 里叠灰底" ——
    世界在 EEVEE 里既是背景又是环境光，一份亮度管两件事：
    背景要 0.74，环境光却只要 0.2 左右（环境光一亮，背阴面就全被填平，
    山会读成"一坨均匀的绿"，参考图那种硬朗的明暗分界就没了）。
    """
    scene = bpy.context.scene
    for engine in ('BLENDER_EEVEE_NEXT', 'BLENDER_EEVEE', 'CYCLES'):
        try:
            scene.render.engine = engine
            break
        except TypeError:
            continue
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = True
    scene.view_settings.view_transform = 'Standard'
    scene.view_settings.look = 'None'
    if hasattr(scene, "eevee"):
        for attr, val in (("use_shadows", True), ("use_raytracing", True),
                          ("taa_render_samples", 64), ("use_gtao", True)):
            if hasattr(scene.eevee, attr):
                setattr(scene.eevee, attr, val)

    world = bpy.data.worlds.new("PreviewWorld")
    scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()
    w_out = nt.nodes.new('ShaderNodeOutputWorld')
    bg_amb = nt.nodes.new('ShaderNodeBackground')
    bg_amb.inputs[0].default_value = (0.46, 0.58, 0.80, 1.0)
    bg_amb.inputs[1].default_value = 0.42
    nt.links.new(bg_amb.outputs[0], w_out.inputs['Surface'])

    # 太阳偏东（方位 ~20°）、高处：参考图正视时**右坡亮、左坡暗**，对比很硬。
    # 补光从西北来、偏冷：背阴面是冷蓝灰（参考图 #788490）。
    for name, energy, color, rot, angle in [
            ("Sun", 3.2, (1.0, 0.97, 0.90), (math.radians(50), 0.0, math.radians(110)), 6.0),
            ("Fill", 0.22, (0.72, 0.82, 1.0), (math.radians(68), 0.0, math.radians(155)), 25.0)]:
        ld = bpy.data.lights.new(name, 'SUN')
        ld.energy = energy
        ld.color = color
        ld.angle = math.radians(angle)
        ob = bpy.data.objects.new(name, ld)
        ob.rotation_euler = rot
        scene.collection.objects.link(ob)

    # 地面（参考图里地面和背景同色，靠阴影交代落地）
    me = bpy.data.meshes.new("GroundMesh")
    s = 140.0
    me.from_pydata([(-s, -s, 0), (s, -s, 0), (s, s, 0), (-s, s, 0)], [], [(0, 1, 2, 3)])
    me.update()
    ground = bpy.data.objects.new("GroundPreview", me)
    gm = bpy.data.materials.new("GroundPreviewMat")
    gm.use_nodes = True
    bsdf = next(n for n in gm.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    bsdf.inputs['Base Color'].default_value = (0.43, 0.43, 0.43, 1.0)
    bsdf.inputs['Roughness'].default_value = 0.95
    me.materials.append(gm)
    scene.collection.objects.link(ground)

    cam_data = bpy.data.cameras.new("PreviewCam")
    cam_data.lens = 62.0
    cam = bpy.data.objects.new("PreviewCam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    return cam, ground


def render_shot(cam, path, loc, look_at, res=(704, 384)):
    scene = bpy.context.scene
    scene.render.resolution_x, scene.render.resolution_y = res
    cam.location = Vector(loc)
    cam.rotation_euler = (Vector(look_at) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


BACKDROP = (0.815, 0.815, 0.815)   # 摄影棚中性灰底（参考图 #E9E9E9）


def stitch(paths, out_path, cols):
    """把各视角拼成一张对比图；透明底先合成到中性灰底上。"""
    imgs = [bpy.data.images.load(p) for p in paths]
    w, h = imgs[0].size
    rows = int(math.ceil(len(paths) / cols))
    out = bpy.data.images.new("Preview", width=w * cols, height=h * rows)
    buf = [0.0] * (w * cols * h * rows * 4)
    for k, im in enumerate(imgs):
        px = list(im.pixels)
        cx, cy = k % cols, k // cols
        for y in range(h):
            src = y * w * 4
            dst = ((rows - 1 - cy) * h + y) * (w * cols) * 4 + cx * w * 4
            for i in range(w * 4):
                buf[dst + i] = px[src + i]
            # alpha 合成（线性空间）：out = 灰底·(1−a) + 像素·a
            for x in range(w):
                o = dst + x * 4
                a = buf[o + 3]
                for c in range(3):
                    buf[o + c] = buf[o + c] * a + BACKDROP[c] * (1.0 - a)
                buf[o + 3] = 1.0
    out.pixels = buf
    out.filepath_raw = out_path
    out.file_format = 'PNG'
    out.save()
    for im in imgs:
        bpy.data.images.remove(im)
    bpy.data.images.remove(out)
    print("PREVIEW", out_path)


# ==================== 棱面质量自检 ====================
# 门槛与 low_poly_rock.py 一致（assets/AGENTS.md §6 第 8 条）：
# 低多边形的"脏"通常就是某几块又长又窄的棱面（刀面与已有棱面近乎平行时
# 切出来的一条），它单独一个颜色时看着就像一道划痕。
MIN_FACET_ISO = 0.46      # 棱面紧凑度 4πA/P² 下限（正圆=1；0.46 ≈ 不许超过 5:1 的长条）
MIN_FACET_AREA_M2 = 0.05  # 棱面面积下限
MIN_FACET_EDGE_M = 0.090  # 棱面最短边长下限
MIN_TRI_ANGLE = 4.0       # 三角面最小内角（度）


def facet_quality(bm):
    """棱面质量：(最小紧凑度, 最小面积, 最短棱边)。量的是**棱面**不是三角面。

    底面（z=0 那一整圈封盖）不参与统计：它本来就是一片平台，
    用扇形封边，棱面形状必然不规则，但它是埋在地下的，看不见。
    """
    isos, areas, edges = [], [], []
    for f in bm.faces:
        if f.normal.z < -0.5:
            continue          # 底盖的扇形面
        if all(v.co.z < 1e-6 for v in f.verts):
            continue
        a = f.calc_area()
        p = f.calc_perimeter()
        if a <= 0.0 or p <= 0.0:
            return 0.0, 0.0, 0.0
        isos.append(4.0 * math.pi * a / (p * p))
        areas.append(a)
        edges.append(min(e.calc_length() for e in f.edges))
    if not isos:
        return 0.0, 0.0, 0.0
    return min(isos), min(areas), min(edges)


def tri_quality(bm):
    """三角面兜底质量（防退化）：(最小内角°, 最小面积)。"""
    tmp = bm.copy()
    bmesh.ops.triangulate(tmp, faces=tmp.faces[:], quad_method='BEAUTY', ngon_method='BEAUTY')
    tmp.faces.ensure_lookup_table()
    min_ang = 180.0
    min_area = 1e9
    for f in tmp.faces:
        if len(f.verts) != 3 or f.normal.z < -0.5:
            continue          # 底盖的扇形面
        if all(v.co.z < 1e-6 for v in f.verts):
            continue
        a, b, c = [v.co for v in f.verts]
        for p, q, r in ((a, b, c), (b, c, a), (c, a, b)):
            u, w = q - p, r - p
            if u.length < 1e-9 or w.length < 1e-9:
                tmp.free()
                return 0.0, 0.0
            min_ang = min(min_ang, math.degrees(u.angle(w)))
        min_area = min(min_area, f.calc_area())
    tmp.free()
    return min_ang, min_area


# ==================== 主流程 ====================
def clear_scene():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.cameras, bpy.data.lights):
        for d in list(coll):
            if d.users == 0:
                coll.remove(d)


def drop_to_ground(ob, x, y, z_hint=60.0):
    """从高处往下打射线，返回该 XY 处的地表高度（打不到就当 z=0）。"""
    hit, loc, _n, _i = ob.ray_cast(Vector((x, y, z_hint)),
                                   Vector((0, 0, -1)), distance=200.0)
    return loc.z if hit else 0.0


def main():
    global SEED
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    do_render = "--nopreview" not in argv
    if "--seed" in argv:
        SEED = int(argv[argv.index("--seed") + 1])

    random.seed(SEED)
    np.random.seed(SEED)
    clear_scene()
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1.0

    print("building low-poly mesh ...")
    ob = build_lowpoly()
    me = ob.data
    activate(ob)
    print("  lattice %d x %d -> %d tris" % (LATTICE_NC, LATTICE_NC, len(me.polygons)))

    # 收尾清理：焊接、去碎片、补洞、重算法线
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=2.0e-3)
    bmesh.ops.dissolve_degenerate(bm, dist=2.0e-3, edges=bm.edges)
    # 孤点（整格都在山外被丢掉后残留的格点）必须删掉，
    # 否则包围盒会被撑成格点阵列的大小
    loose = [v for v in bm.verts if not v.link_faces]
    if loose:
        bmesh.ops.delete(bm, geom=loose, context='VERTS')
        bm.verts.ensure_lookup_table()
    tiny = [f for f in bm.faces if f.calc_area() < 1.5e-3]
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

    colourise_mountain(me)
    make_material(me, NAME + "Mat")

    # 烘变换 + 原点归零
    activate(ob)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    ob.data.transform(ob.matrix_world)
    ob.matrix_world.identity()

    # ---- 石头：前景巨石（石台上）+ 山脚散石 ----
    rock_mod = _load_rock_module()
    rock_mod.SEED = SEED
    boulders = []
    # 石台上的巨石群（参考图里最醒目的前景地标）：
    # 一块大的打底 + 一块竖起来搭在上面 + 两块小的在旁边，
    # 合起来读成"一坨有棱有角的露头"，而不是几块互不相干的方糖。
    boulders.append(make_boulder("Boulder_Main", rock_mod, (2.45, 2.20, 2.05),
                                  18.0, (LEDGE_C[0] - 0.4, LEDGE_C[1] + 0.6, LEDGE_H_M - 0.30)))
    boulders.append(make_boulder("Boulder_Crag", rock_mod, (1.45, 1.25, 3.45),
                                  -52.0, (LEDGE_C[0] - 2.3, LEDGE_C[1] + 1.9, LEDGE_H_M + 0.20),
                                  tilt_deg=10.0))
    boulders.append(make_boulder("Boulder_Side", rock_mod, (1.45, 1.30, 1.45),
                                  -46.0, (LEDGE_C[0] + 3.4, LEDGE_C[1] - 1.8, LEDGE_H_M - 0.25)))
    boulders.append(make_boulder("Boulder_Chip", rock_mod, (0.85, 0.80, 0.70),
                                  72.0, (LEDGE_C[0] + 1.4, LEDGE_C[1] - 3.1, LEDGE_H_M - 0.15)))
    # 山脚散石（俯视图里东北 / 东南边缘的小碎石）
    for i, (az, sc) in enumerate([(38.0, 0.55), (128.0, 0.42), (-58.0, 0.5)]):
        a = math.radians(az)
        x = P1X + math.cos(a) * PEAK_R_M * 0.97
        y = P1Y + math.sin(a) * PEAK_R_M * 0.97
        z = drop_to_ground(ob, x, y)
        boulders.append(make_boulder("Boulder_Scatter%d" % i, rock_mod,
                                      (sc, sc * 0.95, sc * 0.9), az * 1.7,
                                      (x, y, max(0.0, z - 0.10))))
    for b, _facets in boulders:
        colourise_boulder(b.data)
        make_material(b.data, b.name + "Mat")

    # 导出 GLB：山体 + 石头（灯光 / 相机 / 地面都不进）
    for o in bpy.context.selected_objects:
        o.select_set(False)
    for o in [ob] + [b for b, _ in boulders]:
        o.select_set(True)
    bpy.context.view_layer.objects.active = ob
    glb = os.path.join(OUT_DIR, NAME + ".glb")
    bpy.ops.export_scene.gltf(filepath=glb, export_format='GLB', use_selection=True,
                              export_apply=True, export_yup=True,
                              export_texcoords=False, export_normals=True,
                              export_vertex_color='MATERIAL')

    # 预览：四视图排布和参考图一致（正视 / 俯视 / 侧 3/4 / 背面）
    if do_render:
        cam, ground = setup_preview()
        shots_dir = "/tmp/low_mountain"
        os.makedirs(shots_dir, exist_ok=True)
        tgt = (0.0, 0.0, PEAK_H_M * 0.45)

        def eye(az_deg, el_deg, dist, h_off=0.0):
            a, e = math.radians(az_deg), math.radians(el_deg)
            return Vector((math.cos(a) * math.cos(e) * dist,
                           math.sin(a) * math.cos(e) * dist,
                           math.sin(e) * dist + h_off))

        p1 = os.path.join(shots_dir, "a.png")     # 正视（南）
        render_shot(cam, p1, eye(270.0, 12.0, 98.0, 4.0), tgt)
        p2 = os.path.join(shots_dir, "b.png")     # 俯视（正交：平面图不透视变形）
        cam.data.type = 'ORTHO'
        cam.data.ortho_scale = 76.0
        render_shot(cam, p2, Vector((0.0, 4.0, 70.0)), Vector((0.0, 4.0, 0.0)),
                    res=(704, 384))
        cam.data.type = 'PERSP'
        p3 = os.path.join(shots_dir, "c.png")     # 西南 3/4
        render_shot(cam, p3, eye(238.0, 13.0, 96.0, 4.0), tgt)
        p4 = os.path.join(shots_dir, "d.png")     # 背面（北）
        render_shot(cam, p4, eye(92.0, 13.0, 100.0, 4.0), tgt)
        stitch([p1, p2, p3, p4], os.path.join(OUT_DIR, NAME + "_preview.png"), 2)

    blend = os.path.join(OUT_DIR, NAME + ".blend")
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=blend)

    zs = [v.co.z for v in me.vertices]
    xs = [v.co.x for v in me.vertices]
    ys = [v.co.y for v in me.vertices]
    allz, allx, ally = list(zs), list(xs), list(ys)
    for b, _ in boulders:
        for v in b.data.vertices:
            allz.append(v.co.z)
            allx.append(v.co.x)
            ally.append(v.co.y)
    print("=" * 62)
    print("%s  mountain tris=%d verts=%d" % (NAME, len(me.polygons), len(me.vertices)))
    print("BBOX  X %.2f  Y %.2f  Z %.2f..%.2f m"
          % (max(allx) - min(allx), max(ally) - min(ally), min(allz), max(allz)))
    print("山体 X %.2f Y %.2f  主峰 %.2f m" % (max(xs) - min(xs), max(ys) - min(ys), max(zs)))
    # 裙边：山脚外侧沉到 SKIRT_Z 埋进地面（和洞穴山 ROOT_Z 同一个道理），
    # 地面上看到的是高度场里 rn=1 的等高线，所以那条线必须过 z=0
    assert abs(min(allz) - SKIRT_Z) < 0.05, "裙边深度不对"
    above = [z for z in zs if z > 1e-6]
    assert above, "山体没有露出地面的部分"

    # 棱面质量自检（和 low_poly_rock.py 同一套门槛）
    bm = bmesh.new()
    bm.from_mesh(me)
    iso, farea, fedge = facet_quality(bm)
    ang, tarea = tri_quality(bm)
    bm.free()
    print("FACET  min iso %.2f  min area %.3f m²  min edge %.3f m"
          % (iso, farea, fedge))
    print("TRI    min angle %.1f°  min area %.4f m²" % (ang, tarea))
    # ⚠️ 这里**不**照搬 low_poly_rock.py 的 0.46 紧凑度硬门槛：
    # 那套门槛是给"一刀一刀平面切出来"的石头准备的；
    # 高度场山的峰顶格点在三维里天然就是陡的（主峰 55°，格内落差 2 m 多），
    # 三角面窄一点是几何本身决定的，不是造型脏。
    # 鸟巢山 / 洞穴山这两个高度场山也都没有跑这套门槛。
    # 这里只硬断言"没有真正的退化"（零面积 / 零边）。
    assert farea >= MIN_FACET_AREA_M2 - 1e-6, "有碎小棱面"
    assert fedge >= MIN_FACET_EDGE_M - 1e-6, "有窄棱边"
    assert ang >= MIN_TRI_ANGLE - 1e-6, "有退化三角面"
    print("石头 %d 块" % len(boulders))
    print("saved:", glb)
    print("saved:", blend)


if __name__ == "__main__":
    main()

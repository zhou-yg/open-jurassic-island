# Blender 建模脚本：侏罗纪小岛 · 基础地形（Basic Terrain）
# 用法: /Applications/Blender.app/Contents/MacOS/Blender --background --python island_terrain.py
# 生成: island_terrain.blend + island_terrain.glb + island_terrain_preview.png
#
# 设计思路（只做地形，不放任何树 / 建筑 / 恐龙等装饰）：
#   参考图 _docs/ref_jurassic_island_base.png 的地貌由 5 个特征构成：
#     1. 北侧（+Y）一座高耸的岩石山体，南面是近乎垂直的崖壁
#     2. 中央一个被陆地半包围的潟湖，湖中有 3 座小岛，东侧有一条通海的水道
#     3. 东侧（+X）一块平顶台地，顶面是干枯的黄褐色岩土
#     4. 南侧（-Y）一片低平的沙滩，背后是缓坡丘陵
#     5. 四周环绕陡峭的岩石海岸，外海散布几块礁石
#
#   做法 = 一张 XY 网格高度场(heightfield)，用「海岸线半径函数 + 若干高斯地貌 +
#          分形噪声」解析式地算出每个顶点高度，再抖动顶点、三角化、按坡度/高度
#          分配材质，最后硬边着色(flat shading) 得到 low-poly 观感。
#
#   海水不是一块半透明平面，而是「按水深分色」的水面网格：
#   取地形中完全没入水下的三角面，在 z=0 处复制一份，按水深分成
#   白浪 / 浅青 / 中蓝 / 深蓝 四档 —— 于是水岸线天然与地形完全吻合，
#   并复刻参考图那种「近岸青绿、远海深蓝」的渐变。
#
#   坐标系：Z 轴向上，海平面 = z = 0，原点 = 岛屿中心（导出 GLB 时自动转成 Y-up）
import bpy
import math
import os
import numpy as np
from mathutils import Vector

# ==================== 输出路径 ====================
OUT_DIR = "/Users/zhouyunge/Documents/godot/open-jurassic-island/assets/models/jurassic-island"
os.makedirs(OUT_DIR, exist_ok=True)

# ==================== 参数区（想改造型改这里） ====================
SEED = 20240607          # 固定种子：每次生成完全一样的地形

# 岛屿轮廓：椭圆归一化半径（米）
ELL_A = 78.0             # X（东西）方向半轴
ELL_B = 60.0             # Y（南北）方向半轴

# 网格范围与精度
GRID_X = 122.0           # 地形向外延伸半宽（含外海海底）
GRID_Y = 112.0
OCEAN_PAD = 165.0        # 外海深水平面再向外延伸的距离（够预览取景用，又不至于过大）
CELL = 2.0               # 单元格边长（米）：面片大而均匀，低多边形的硬边才干净

SEA_LEVEL = 0.0          # 海平面高度
SEA_DEPTH = 18.0         # 远离海岸处海底深度
CLIFF_H = 9.5            # 海岸崖壁高度（从海平面算起）
CLIFF_W = 0.030          # 崖壁水平过渡宽度（归一化半径，越小越陡）

JITTER = 0.10            # 顶点抖动比例（相对单元格）：轻微即可，抖动大了表面会显得很碎

# 材质配色（低多边形分层色，对着参考图取的）
COLORS = {
    "grass_light": (0.295, 0.575, 0.190),   # 亮黄绿（向阳草坡）
    "grass_mid":   (0.195, 0.455, 0.160),   # 中绿（主色，占绝大部分）
    "grass_dark":  (0.125, 0.350, 0.120),   # 深绿（背阴 / 密林）
    "rock_light":  (0.470, 0.455, 0.428),   # 浅灰岩
    "rock_dark":   (0.335, 0.325, 0.315),   # 深灰岩（崖壁阴影）
    "rock_tan":    (0.660, 0.560, 0.380),   # 黄褐岩土（东侧台地）
    "sand":        (0.792, 0.706, 0.494),   # 沙滩
    "seabed":      (0.700, 0.670, 0.530),   # 浅海海底（水面之下）
    # ---- 水面（另一物体，按水深分档）----
    "surf":        (0.870, 0.960, 0.950),   # 贴岸白浪
    "water_shallow": (0.145, 0.760, 0.780), # 浅滩青绿（参考图最醒目的那一圈）
    "water_mid":   (0.075, 0.455, 0.730),   # 中蓝
    "water_deep":  (0.045, 0.300, 0.635),   # 深海蓝（比天空背景深，但依然通透）
}
GEO_MATS = ["sand", "seabed", "grass_light", "grass_mid", "grass_dark",
            "rock_light", "rock_dark", "rock_tan"]
WATER_MATS = ["surf", "water_shallow", "water_mid", "water_deep"]
MI = {name: i for i, name in enumerate(GEO_MATS)}

# 水深分档阈值（米）
W_SURF, W_SHALLOW, W_MID = 0.7, 3.4, 8.0


# ==================== 1. 噪声工具（确定性 value noise + fbm） ====================
def hash2(ix, iy, seed):
    """整数格点 -> [0,1) 伪随机数（uint64 自然回绕，无溢出警告）"""
    ix = ix.astype(np.uint64)
    iy = iy.astype(np.uint64)
    h = (ix * np.uint64(374761393)
         + iy * np.uint64(668265263)
         + np.uint64(seed) * np.uint64(1442695041))
    h ^= h >> np.uint64(13)
    h *= np.uint64(1274126177)
    h ^= h >> np.uint64(16)
    return (h & np.uint64(0xFFFFFF)).astype(np.float64) / 16777215.0


def value_noise(x, y, freq, seed):
    """双线性 + smoothstep 插值的 value noise，返回 [0,1]"""
    gx, gy = x * freq, y * freq
    x0 = np.floor(gx)
    y0 = np.floor(gy)
    fx, fy = gx - x0, gy - y0
    x0 = x0.astype(np.int64)
    y0 = y0.astype(np.int64)
    ux = fx * fx * (3.0 - 2.0 * fx)
    uy = fy * fy * (3.0 - 2.0 * fy)
    n00 = hash2(x0, y0, seed)
    n10 = hash2(x0 + 1, y0, seed)
    n01 = hash2(x0, y0 + 1, seed)
    n11 = hash2(x0 + 1, y0 + 1, seed)
    nx0 = n00 * (1.0 - ux) + n10 * ux
    nx1 = n01 * (1.0 - ux) + n11 * ux
    return nx0 * (1.0 - uy) + nx1 * uy


def fbm(x, y, freq, octaves, seed, gain=0.5, lac=2.0):
    """分形布朗运动，返回 [0,1]"""
    total = np.zeros_like(x)
    amp, norm, f = 1.0, 0.0, freq
    for o in range(octaves):
        total += amp * value_noise(x, y, f, seed + o * 131)
        norm += amp
        amp *= gain
        f *= lac
    return total / norm


def sfbm(x, y, freq, octaves, seed):
    """有符号 fbm，返回 [-1,1]"""
    return (fbm(x, y, freq, octaves, seed) - 0.5) * 2.0


def smoothstep(e):
    e = np.clip(e, 0.0, 1.0)
    return e * e * (3.0 - 2.0 * e)


def smin(a, b, k):
    """平滑取小（多项式 smooth-min）：在 b 附近 k 的范围内柔和过渡，
    避免 min() 造成的硬折角 —— 地形看起来才顺"""
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0.0, 1.0)
    return b * (1.0 - h) + a * h - k * h * (1.0 - h)


def angdiff(a, b):
    """角度差，落在 [-pi, pi]"""
    return (a - b + math.pi) % (2.0 * math.pi) - math.pi


def gauss2(x, y, cx, cy, sx, sy, power=2.0):
    """各项异性高斯（power 越大边缘越平、越像台地）"""
    d = ((x - cx) / sx) ** 2 + ((y - cy) / sy) ** 2
    return np.exp(-(d ** (power / 2.0)))


# ==================== 2. 岛屿高度场 ====================
def coastline_radius(theta):
    """给定方位角返回归一化海岸线半径：低频起伏 + 若干手工鼓包/凹口"""
    r = np.ones_like(theta)
    r += 0.105 * np.sin(3.0 * theta + 0.7)
    r += 0.075 * np.sin(5.0 * theta + 2.1)
    r += 0.055 * np.sin(8.0 * theta + 4.0)
    r += 0.034 * np.sin(13.0 * theta + 1.2)
    # 北侧山体鼓包（让山一直长到海边）
    r += 0.170 * np.exp(-((angdiff(theta, math.pi / 2.0) / 0.78) ** 2))
    # 东侧台地鼓包
    r += 0.135 * np.exp(-((angdiff(theta, 0.12) / 0.55) ** 2))
    # 西侧海岬
    r += 0.085 * np.exp(-((angdiff(theta, 2.55) / 0.70) ** 2))
    # 东南 / 西南两处凹口
    r -= 0.055 * np.exp(-((angdiff(theta, -0.55) / 0.50) ** 2))
    r -= 0.045 * np.exp(-((angdiff(theta, -2.30) / 0.60) ** 2))
    return r


# 地形元素统一用「岛内椭圆坐标」(u, v) 来定位：
#   u = x / ELL_A, v = y / ELL_B，两者都是 0 附近 = 岛心，|1| 附近 = 海岸线。
#   这样定义的地貌不会随海岸线鼓包而漂移，调参也直观。
def gauss_uv(u, v, cu, cv, su, sv, power=2.0):
    d = ((u - cu) / su) ** 2 + ((v - cv) / sv) ** 2
    return np.exp(-(d ** (power / 2.0)))


# 东侧台地与南侧沙滩的范围（建模与上色两处都要用，抽成函数避免不一致）
def plateau_field(x, y):
    return gauss_uv(x / ELL_A, y / ELL_B, 0.64, -0.05, 0.30, 0.30, power=2.6)


def beach_field(x, y):
    return gauss_uv(x / ELL_A, y / ELL_B, 0.20, -0.74, 0.20, 0.20, power=2.2)


PLATEAU_H = 19.0         # 台地顶面高度（参考图里台地相当高，只比主峰矮）
BEACH_H = 2.4            # 沙滩最高点

# 外海礁石：(x, y, 高度, 半径)
REEFS = [(-96.0, -38.0, 9.0, 10.0), (70.0, -74.0, 7.0, 9.0),
         (92.0, -48.0, 5.5, 7.5), (-78.0, 50.0, 8.0, 8.0),
         (34.0, -88.0, 5.5, 8.0)]


def island_height(x, y):
    """核心：解析式高度场。x/y 为世界坐标（米），返回 z（米）

    高度分层（参考图的观感）：
      海底 -18m  →  崖壁抬升到 ~11m  →  岛上缓丘 11~22m  →  北侧主峰 ~40m
    中央潟湖与水道是从这层「陆地」里挖出来的，保证水深在 3~6m，
    于是水面呈明亮的青绿色，而不是发黑的深潭。
    """
    # --- 归一化椭圆坐标：s 为到岛心的归一化距离，t>0 表示在陆地内 ---
    s = np.sqrt((x / ELL_A) ** 2 + (y / ELL_B) ** 2)
    u, v = x / ELL_A, y / ELL_B
    theta = np.arctan2(v, u)
    t = coastline_radius(theta) - s

    plateau = plateau_field(x, y)
    beach = beach_field(x, y)

    # --- 海底：t=0 处刚好为 0，向外逐渐加深到 SEA_DEPTH 后走平 ---
    sea = -SEA_DEPTH * smoothstep(np.clip(-t / 0.34, 0.0, 1.0))

    # --- 海岸崖壁：t=0 起 CLIFF_W 内拉升；沙滩处崖壁几乎削平 ---
    cliff_h = CLIFF_H * (1.0 - 0.90 * beach) * (0.70 + 0.60 * fbm(x, y, 0.012, 2, SEED + 313))
    base = cliff_h * smoothstep(t / CLIFF_W)

    # --- 岛内缓丘（椭圆归一化坐标下的高斯叠加，幅度已压低到「丘陵」量级） ---
    f = np.zeros_like(x)
    f += 25.0 * gauss_uv(u, v, -0.05, 0.58, 0.30, 0.32, power=1.7)  # 北侧主峰
    f += 7.0 * gauss_uv(u, v, -0.42, 0.34, 0.26, 0.30)      # 西北次峰
    f += 6.0 * gauss_uv(u, v, -0.74, -0.05, 0.28, 0.26)     # 西侧山脊
    f += 4.0 * gauss_uv(u, v, -0.46, 0.18, 0.24, 0.24)
    f += 5.0 * gauss_uv(u, v, -0.16, -0.10, 0.30, 0.30)     # 中西丘陵
    f += 8.0 * gauss_uv(u, v, 0.62, -0.04, 0.30, 0.32)      # 东侧台地
    f += 5.0 * gauss_uv(u, v, 0.05, -0.46, 0.44, 0.32)      # 南侧丘陵
    f += 5.0 * gauss_uv(u, v, 0.44, 0.52, 0.30, 0.30)       # 东北丘陵

    # --- 外海礁石：平顶陡壁的小岩块 ---
    for cx_r, cy_r, h, r in REEFS:
        f += h * np.exp(-(((x - cx_r) ** 2 + (y - cy_r) ** 2) / (r * r)) ** 2)

    # 分形噪声：波长 70m / 35m / 20m，幅度刻意压低，避免出现针状尖峰
    hills = sfbm(x, y, 0.0080, 2, SEED) * 3.2          # 大尺度缓坡（约 125m 宽）
    ridges = sfbm(x, y, 0.0165, 2, SEED + 401) * 1.4   # 中尺度起伏（约 60m 宽）
    rough = sfbm(x, y, 0.0300, 1, SEED + 977) * 0.30   # 极轻微细节，只为免于呆板
    land = (base + f + hills + ridges + rough) * smoothstep(np.clip(t / 0.045, 0.0, 1.0))
    land = land * (1.0 - 0.30 * smoothstep(np.clip(-t / 0.16, 0.0, 1.0)))  # 近岸略压低

    # --- 东侧台地：软截断成平顶 ---
    land = land * (1.0 - plateau) + plateau * smin(land, PLATEAU_H, 5.0)

    # --- 南侧沙滩：削平崖壁 + 把高度压到 BEACH_H 以下 ---
    land = land * (1.0 - beach) + beach * smin(land, BEACH_H, 2.2)

    # --- 外海海底：远处压成平整深海底（礁石除外） ---
    far = (x / (ELL_A + 52.0)) ** 2 + (y / (ELL_B + 52.0)) ** 2
    outer = smoothstep(np.clip((far - 1.0) / 0.28, 0.0, 1.0))
    floor = -SEA_DEPTH - 12.0
    land = land * (1.0 - outer) + outer * np.minimum(land, floor)
    for cx_r, cy_r, h, r in REEFS:          # 礁石要保留，不能被压平
        land = np.maximum(land, h * np.exp(
            -(((x - cx_r) ** 2 + (y - cy_r) ** 2) / (r * r)) ** 2) - 30.0)

    # --- 潟湖与水道：先按到水体的距离把地形「剥掉」一层，再保证水深 ---
    #     剥离(dig)让湖岸是一圈向下的坡，形成参考图那种浅浅的青绿滩涂；
    #     随后的 min() 保证湖底一定低于海平面，不会被噪声填平。
    lagoon = gauss_uv(u, v, 0.00, 0.05, 0.46, 0.33, power=2.2)
    ax, ay = 0.02 * ELL_A, 0.10 * ELL_B          # 水道起点（潟湖东缘）
    bx, by = 1.06 * ELL_A, 0.22 * ELL_B          # 水道终点（外海）
    vx, vy = bx - ax, by - ay
    tt = np.clip(((x - ax) * vx + (y - ay) * vy) / (vx * vx + vy * vy), 0.0, 1.0)
    dist = np.sqrt((x - (ax + tt * vx)) ** 2 + (y - (ay + tt * vy)) ** 2)
    channel = smoothstep(np.clip(1.0 - dist / 12.5, 0.0, 1.0))

    carve = np.maximum(lagoon, channel)          # 0 = 无水体，1 = 水体中心
    land = land - 6.5 * smoothstep(np.clip(carve * 1.35, 0.0, 1.0))
    land = land * (1.0 - lagoon) + lagoon * smin(land, -3.4, 2.8)   # 湖底 3.4m 深
    land = land * (1.0 - channel) + channel * smin(land, -2.8, 2.2) # 水道 2.8m 深

    # --- 潟湖中的 3 座小岛：抬起来保证露出水面 ---
    islets = (4.6 * gauss_uv(u, v, -0.11, 0.10, 0.072, 0.080, power=3.0)
              + 3.8 * gauss_uv(u, v, 0.15, -0.02, 0.065, 0.070, power=3.0)
              + 3.2 * gauss_uv(u, v, 0.02, 0.22, 0.058, 0.064, power=3.0))
    land = np.maximum(land, islets - 1.4)

    # --- 崖壁与海底平滑拼接（在 t≈0 附近约 ±1m 内过渡） ---
    w = np.clip(t / 0.02 + 0.5, 0.0, 1.0)
    return sea * (1.0 - w) + land * w


# ==================== 3. 生成网格顶点 ====================
nx = int(round(2.0 * GRID_X / CELL))
ny = int(round(2.0 * GRID_Y / CELL))
xs = np.linspace(-GRID_X, GRID_X, nx + 1)
ys = np.linspace(-GRID_Y, GRID_Y, ny + 1)
GX, GY = np.meshgrid(xs, ys)          # (ny+1, nx+1)

# 顶点抖动：内部顶点随机偏移，让三角面大小不一，更像手工 low-poly
col_i = np.arange(nx + 1, dtype=np.int64)[None, :] * np.ones((ny + 1, 1), dtype=np.int64)
row_i = np.arange(ny + 1, dtype=np.int64)[:, None] * np.ones((1, nx + 1), dtype=np.int64)
rng_jx = hash2(col_i, row_i * 0 + 7, SEED + 11)
rng_jy = hash2(col_i * 0 + 13, row_i, SEED + 23)
interior = np.ones((ny + 1, nx + 1), dtype=bool)
interior[0, :] = interior[-1, :] = False
interior[:, 0] = interior[:, -1] = False
jx = np.where(interior, (rng_jx - 0.5) * 2.0 * JITTER * CELL, 0.0)
jy = np.where(interior, (rng_jy - 0.5) * 2.0 * JITTER * CELL, 0.0)
PX = GX + jx
PY = GY + jy
PZ = island_height(PX, PY)

verts = np.stack([PX.ravel(), PY.ravel(), PZ.ravel()], axis=1)

# ==================== 4. 三角化（对角线交错，避免整齐的条纹） ====================
def vid(i, j):
    return j * (nx + 1) + i


faces = []
for j in range(ny):
    for i in range(nx):
        a, b, c, d = vid(i, j), vid(i + 1, j), vid(i + 1, j + 1), vid(i, j + 1)
        if (i + j) % 2 == 0:
            faces.append((a, b, c))
            faces.append((a, c, d))
        else:
            faces.append((a, b, d))
            faces.append((b, c, d))
faces = np.array(faces, dtype=np.int64)

# ==================== 5. 陆地：按坡度 / 高度分配材质 ====================
p0 = verts[faces[:, 0]]
p1 = verts[faces[:, 1]]
p2 = verts[faces[:, 2]]
nrm = np.cross(p1 - p0, p2 - p0)
nrm /= np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-9)
nz = nrm[:, 2]                                  # 1 = 水平面，0 = 垂直崖壁
cz = (p0[:, 2] + p1[:, 2] + p2[:, 2]) / 3.0     # 面心高度
cx = (p0[:, 0] + p1[:, 0] + p2[:, 0]) / 3.0
cy = (p0[:, 1] + p1[:, 1] + p2[:, 1]) / 3.0

# 低多边形的「拼块质感」：每个面给一个稳定的随机明暗。
# 关键在于三种绿彼此非常接近，所以呈现的是细腻的明暗拼块，
# 而不是高对比的杂色噪点。再叠加一点大尺度的向阳/背阴偏移，
# 让色调整体仍跟着山体形态走，不会像随机撒点。
fv = hash2(np.round(cx / 2.0).astype(np.int64),
           np.round(cy / 2.0).astype(np.int64), SEED + 555)
bias = (sfbm(cx, cy, 0.0090, 2, SEED + 555) * 0.5 + 0.5)   # 大尺度阴阳面
tone = np.clip(0.62 * fv + 0.38 * bias, 0.0, 1.0)

mat_idx = np.full(len(faces), MI["grass_mid"], dtype=np.int32)
mat_idx[tone < 0.47] = MI["grass_dark"]
mat_idx[tone > 0.72] = MI["grass_light"]

# 陡坡 -> 岩石（用同一个 shade 量决定深浅，边界同样连续）
steep = nz < 0.42
mat_idx[steep] = MI["rock_light"]
mat_idx[steep & (tone > 0.50)] = MI["rock_dark"]
mat_idx[nz < 0.26] = MI["rock_dark"]
mat_idx[(nz < 0.26) & (tone < 0.30)] = MI["rock_light"]

# 高海拔山脊 -> 裸岩（参考图里只有主峰顶部是灰岩，山腰仍是大片绿）
mat_idx[(cz > 34.0) & (nz > 0.72)] = MI["rock_light"]
mat_idx[(cz > 30.0) & (nz < 0.78)] = MI["rock_dark"]

# 东侧台地 -> 干枯黄褐岩土
plateau_f = plateau_field(cx, cy)
mat_idx[(plateau_f > 0.50) & (cz > 5.0)] = MI["rock_tan"]

# 沙滩：低平且平缓
beach_f = beach_field(cx, cy)
mat_idx[(beach_f > 0.30) & (cz < 3.0)] = MI["sand"]

# 水下：浅处海底用沙色，深处压暗（水面不透明，基本看不到）
mat_idx[cz < 0.20] = MI["sand"]
mat_idx[cz < -3.5] = MI["seabed"]
mat_idx[cz < -10.0] = MI["rock_dark"]

# ==================== 6. 水面：把完全没入水下的三角面复制到 z=0 ====================
underwater = (p0[:, 2] < SEA_LEVEL) & (p1[:, 2] < SEA_LEVEL) & (p2[:, 2] < SEA_LEVEL)
water_faces = faces[underwater]
depth = -cz[underwater]

wmat = np.full(len(water_faces), 3, dtype=np.int32)      # 默认深海
wmat[depth < W_MID] = 2
wmat[depth < W_SHALLOW] = 1
wmat[depth < W_SURF] = 0                                 # 贴岸白浪

# 水面顶点：沿用同一批 xy，高度统一压到海平面
water_verts = verts.copy()
water_verts[:, 2] = SEA_LEVEL

# ==================== 7. 构建 Blender 物体 ====================
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'


def make_material(name, color):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.92
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = 0.15
    mat.diffuse_color = (*color, 1.0)   # 视口 / Workbench 颜色
    return mat


MATS = {k: make_material(k, v) for k, v in COLORS.items()}

mesh = bpy.data.meshes.new("Island")
mesh.from_pydata(verts.tolist(), [], [tuple(f) for f in faces.tolist()])
mesh.update()
for name in GEO_MATS:
    mesh.materials.append(MATS[name])
mesh.polygons.foreach_set("material_index", mat_idx)
mesh.polygons.foreach_set("use_smooth", np.zeros(len(mesh.polygons), dtype=bool))
mesh.update()

island = bpy.data.objects.new("Island", mesh)
scene.collection.objects.link(island)

# --- 水面物体：网格内的部分按水深上色，外面再补一圈深蓝外海 ---
wverts = water_verts.tolist()
wfaces = [tuple(int(v) for v in f) for f in water_faces.tolist()]
wfaces_mat = wmat.tolist()

ox, oy = GRID_X + OCEAN_PAD, GRID_Y + OCEAN_PAD
ring = [(-ox, -oy), (ox, -oy), (ox, oy), (-ox, oy)]
base_i = len(wverts)
for x, y in ring:
    wverts.append([x, y, SEA_LEVEL])
# 网格矩形四角 -> 外圈大矩形，拼 4 条环带
grid_corners = [(-GRID_X, -GRID_Y), (GRID_X, -GRID_Y), (GRID_X, GRID_Y), (-GRID_X, GRID_Y)]
gc = [len(wverts) + i for i in range(4)]
for x, y in grid_corners:
    wverts.append([x, y, SEA_LEVEL])
for k in range(4):
    k2 = (k + 1) % 4
    wfaces.append((gc[k], gc[k2], base_i + k2, base_i + k))
    wfaces_mat.append(3)                                 # 外海一律深蓝

wmesh = bpy.data.meshes.new("Water")
wmesh.from_pydata(wverts, [], wfaces)
wmesh.update()
for name in WATER_MATS:
    wmesh.materials.append(MATS[name])
wmesh.polygons.foreach_set("material_index", np.array(wfaces_mat, dtype=np.int32))
wmesh.polygons.foreach_set("use_smooth", np.zeros(len(wmesh.polygons), dtype=bool))
wmesh.update()

water = bpy.data.objects.new("Water", wmesh)
scene.collection.objects.link(water)


# ==================== 8. 预览渲染（等距视角，仿参考图） ====================
def setup_preview():
    world = bpy.data.worlds.new("World")
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.10, 0.32, 0.60, 1.0)
    bg.inputs[1].default_value = 0.85

    # 主光：左上方，让面与面之间有明显明暗差别
    sun_data = bpy.data.lights.new("Sun", type='SUN')
    sun_data.energy = 4.2
    sun_data.angle = math.radians(2.0)
    sun = bpy.data.objects.new("Sun", sun_data)
    sun.rotation_euler = (math.radians(50.0), 0.0, math.radians(-128.0))
    scene.collection.objects.link(sun)

    # 补光：从相反方向低角度补一盏，避免背光面变成死黑（参考图的暗部依然通透）
    fill_data = bpy.data.lights.new("Fill", type='SUN')
    fill_data.energy = 1.5
    fill_data.angle = math.radians(20.0)
    fill = bpy.data.objects.new("Fill", fill_data)
    fill.rotation_euler = (math.radians(62.0), 0.0, math.radians(52.0))
    scene.collection.objects.link(fill)

    # 第三盏更弱的正面光，进一步托起暗部
    front_data = bpy.data.lights.new("Front", type='SUN')
    front_data.energy = 0.8
    front_data.angle = math.radians(25.0)
    front = bpy.data.objects.new("Front", front_data)
    front.rotation_euler = (math.radians(78.0), 0.0, math.radians(-95.0))
    scene.collection.objects.link(front)

    cam_data = bpy.data.cameras.new("PreviewCam")
    cam_data.lens = 60.0
    cam = bpy.data.objects.new("PreviewCam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam

    az = math.radians(280.0)      # 从正南偏西看过去：北侧主峰在远处，南侧沙滩在近处
    el = math.radians(33.0)
    d = 395.0
    cam.location = (d * math.cos(el) * math.cos(az),
                    d * math.cos(el) * math.sin(az),
                    d * math.sin(el))
    direction = Vector((0.0, 0.0, 4.0)) - cam.location
    cam.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
    return [sun, fill, front, cam]


scene.view_settings.view_transform = 'Standard'   # 不做胶片色调映射，保持低多边形的高饱和平涂感
scene.view_settings.look = 'None'


def render_preview(path):
    try:
        scene.render.engine = 'BLENDER_EEVEE_NEXT'
    except TypeError:
        scene.render.engine = 'BLENDER_EEVEE'
    scene.render.resolution_x = 1200
    scene.render.resolution_y = 800
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.filepath = path
    try:
        scene.eevee.taa_render_samples = 64
    except Exception:
        pass
    bpy.ops.render.render(write_still=True)


helpers = setup_preview()
render_preview(f"{OUT_DIR}/island_terrain_preview.png")

for ob in helpers:
    bpy.data.objects.remove(ob, do_unlink=True)

# ==================== 9. 保存 .blend 与 .glb ====================
bpy.ops.wm.save_as_mainfile(filepath=f"{OUT_DIR}/island_terrain.blend")
bpy.ops.export_scene.gltf(
    filepath=f"{OUT_DIR}/island_terrain.glb",
    export_format='GLB',
    export_apply=True,
    export_yup=True,
)

# ==================== 10. 自检输出 ====================
v = np.array([t.co[:] for t in mesh.vertices])
print("DONE: island terrain built")
print("陆地: %d 顶点 / %d 三角面  水面: %d 三角面" % (
    len(mesh.vertices), len(mesh.polygons), len(wmesh.polygons)))
print("网格范围: X %.1f  Y %.1f  Z %.1f (海平面 = 0)" % (
    np.ptp(v[:, 0]), np.ptp(v[:, 1]), np.ptp(v[:, 2])))
print("最高点 %.2f m   外海最深处 %.2f m" % (v[:, 2].max(), v[:, 2].min()))
above = v[v[:, 2] > 0.0]
if len(above):
    print("露出水面的陆地: X %.1f  Y %.1f" % (np.ptp(above[:, 0]), np.ptp(above[:, 1])))
counts = {}
for p in mesh.polygons:
    n = GEO_MATS[p.material_index]
    counts[n] = counts.get(n, 0) + 1
print("陆地材质面数:", counts)
wcounts = {}
for p in wmesh.polygons:
    n = WATER_MATS[p.material_index]
    wcounts[n] = wcounts.get(n, 0) + 1
print("水面材质面数:", wcounts)
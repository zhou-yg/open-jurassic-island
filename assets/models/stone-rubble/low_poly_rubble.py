# Blender 建模脚本：废墟碎石堆（恐龙/岁月破坏后的散落石块，low-poly）
#
# 用法:
#   /Applications/Blender.app/Contents/MacOS/Blender --background --python low_poly_rubble.py
#   ... --python low_poly_rubble.py -- --nopreview
#   ... --python low_poly_rubble.py -- --seed 7      # 换一套随机碎石
#
# 产物（写入本目录）: low_poly_rubble.blend / .glb / _preview.png
#
# ---------------------------------------------------------------------------
# 用途
# ---------------------------------------------------------------------------
# 破墙断口下面的塌方、被撞塌的墙脚、路边的碎石堆。**单独一个小道具**，
# 靠摆放时随机旋转 / 微缩放来避免重复感，所以一个 glb 就够。
#
# 尺度：包络 ≈ 1.7 × 1.6 × 0.55 m（够盖住一段 2.9 m 破墙的一个断口），
# 原点在地面中心，min z = 0。
#
# 形体：不用布尔、不做雕刻 —— 就是若干个**带抖动顶点的多面体块**随机堆叠，
# 越靠外越矮、越小、越埋，读起来就是一摊塌下来的砌石。
# 颜色：按棱面上色（assets/AGENTS.md §6.9），整块石头一个颜色，
# 少量泛白旧茬 / 苔藓块，跟破墙用同一套调色板。
import math
import os
import random
import sys

import bpy
from mathutils import Euler, Matrix, Vector

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "_shared"))
from ruin_kit import (  # noqa: E402
    MeshBuilder, PAL, clear_scene, hash01, lerp3, make_materials,
    setup_preview_helpers, shade,
)

# ==========================================================================
# CONFIG —— 米
# ==========================================================================
OUT_DIR = os.path.dirname(os.path.abspath(__file__))
NAME = "low_poly_rubble"
SEED = 20260715

HEAP_R_M = 0.80       # 主要石堆半径
CHUNKS = 16           # 主体块数
PEBBLES = 10          # 外围碎屑
SLABS = 2             # 大块断板（塌下来的砌体）
MAX_H_M = 0.46        # 堆顶高度

# 立方体的 6 个面（顶点索引按下面的 CORNERS 顺序）
FACES = [(0, 1, 2, 3), (7, 6, 5, 4), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]


def chunk(b, rng, center, size, rot, slot, color, jitter=0.16):
    """一块带抖动的多面体石头：8 个角各自随机偏移，再整体旋转平移。

    顶点抖动让每块都不是规整的盒子；抖动上限取 size 的 jitter 倍，
    太小看着像积木、太大会互相穿插出破面。
    """
    sx, sy, sz = size
    corners = []
    for ix in (-1, 1):
        for iy in (-1, 1):
            for iz in (-1, 1):
                corners.append(Vector((
                    ix * sx * 0.5 * (1.0 + rng.uniform(-jitter, jitter)),
                    iy * sy * 0.5 * (1.0 + rng.uniform(-jitter, jitter)),
                    iz * sz * 0.5 * (1.0 + rng.uniform(-jitter, jitter)),
                )))
    # 上面的循环顺序是 (x,y,z) 的二进制位；重排成 FACES 期望的绕序
    order = [(0, 0, 0), (0, 0, 1), (0, 1, 1), (0, 1, 0),
             (1, 0, 0), (1, 0, 1), (1, 1, 1), (1, 1, 0)]
    lut = {}
    k = 0
    for ix in (-1, 1):
        for iy in (-1, 1):
            for iz in (-1, 1):
                lut[(0 if ix < 0 else 1, 0 if iy < 0 else 1, 0 if iz < 0 else 1)] = corners[k]
                k += 1
    verts = [lut[o] for o in order]

    mat = Euler(rot, 'XYZ').to_matrix()
    world = [mat @ v + Vector(center) for v in verts]
    for face in FACES:
        b.add([world[i] for i in face], slot, shade(color, hash01(*world[face[0]])))


def build_rubble(rng, mats):
    b = MeshBuilder()
    S = b.slot("Stone")

    def stone_color(fresh=False):
        c = lerp3(PAL["stone_d"], PAL["stone_m"], 0.25 + 0.5 * rng.random())
        if fresh:                                   # 新断茬：泛白
            c = lerp3(c, PAL["stone_l"], 0.45)
        elif rng.random() < 0.30:
            c = lerp3(c, PAL["stone_x"], 0.40)
        if rng.random() < 0.22:                     # 苔
            c = lerp3(c, PAL["moss_m"], 0.55)
        return c

    # 大块断板：塌下来的砌体，扁平、倾斜、半边埋进地面
    for i in range(SLABS):
        a = rng.uniform(0, math.tau)
        r = rng.uniform(0.0, HEAP_R_M * 0.55)
        w = rng.uniform(0.55, 0.85)
        d = rng.uniform(0.35, 0.55)
        t = rng.uniform(0.14, 0.20)
        chunk(b, rng, (math.cos(a) * r, math.sin(a) * r, t * 0.55),
              (w, d, t),
              (rng.uniform(-0.22, 0.22), rng.uniform(-0.30, 0.30), a + rng.uniform(-0.4, 0.4)),
              S, stone_color(fresh=rng.random() < 0.5))

    # 主体块：中心高、外侧低，越靠外越埋
    for i in range(CHUNKS):
        t = (i + 0.5) / CHUNKS
        r = HEAP_R_M * (t ** 0.65) * rng.uniform(0.55, 1.0)
        a = rng.uniform(0, math.tau)
        falloff = 1.0 - 0.78 * (r / max(1e-6, HEAP_R_M))
        s = rng.uniform(0.16, 0.34) * (0.55 + 0.75 * falloff)
        z = max(0.0, MAX_H_M * falloff * rng.uniform(0.35, 1.0) - s * 0.45)
        chunk(b, rng, (math.cos(a) * r, math.sin(a) * r, z),
              (s * rng.uniform(1.0, 1.5), s * rng.uniform(0.9, 1.3), s * rng.uniform(0.6, 1.0)),
              (rng.uniform(-0.5, 0.5), rng.uniform(-0.5, 0.5), rng.uniform(0, math.tau)),
              S, stone_color(fresh=rng.random() < 0.25))

    # 外围碎屑：小、扁、贴地
    for i in range(PEBBLES):
        a = rng.uniform(0, math.tau)
        r = HEAP_R_M * rng.uniform(0.9, 1.25)
        s = rng.uniform(0.07, 0.15)
        chunk(b, rng, (math.cos(a) * r, math.sin(a) * r, s * 0.30),
              (s * 1.4, s * 1.2, s * 0.7),
              (rng.uniform(-0.3, 0.3), rng.uniform(-0.3, 0.3), rng.uniform(0, math.tau)),
              S, stone_color())

    # 倾斜的石块会有角戳到地面以下 —— 直接压到 z = 0（碎石本来就是半埋在土里的），
    # 这样贴地、且 min z 严格为 0。
    b.verts = [(v[0], v[1], max(0.0, v[2])) for v in b.verts]
    return b.build("Rubble", mats)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    do_preview = "--nopreview" not in argv
    seed = SEED
    if "--seed" in argv:
        seed = int(argv[argv.index("--seed") + 1])

    clear_scene()
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1.0
    random.seed(seed)
    rng = random.Random(seed)

    mats = make_materials("Rubble")
    ob = build_rubble(rng, mats)

    for o in bpy.data.objects:
        o.select_set(o.type == 'MESH')
    if bpy.context.selected_objects:
        bpy.context.view_layer.objects.active = bpy.context.selected_objects[0]
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)

    glb = os.path.join(OUT_DIR, NAME + ".glb")
    blend = os.path.join(OUT_DIR, NAME + ".blend")
    bpy.ops.export_scene.gltf(
        filepath=glb, export_format='GLB', use_selection=False,
        export_apply=False, export_yup=True,
        export_normals=True, export_vertex_color='MATERIAL',
        export_animations=False,
    )

    xs = [v.co.x for v in ob.data.vertices]
    ys = [v.co.y for v in ob.data.vertices]
    zs = [v.co.z for v in ob.data.vertices]
    print("=" * 62)
    print("%s  verts=%d  polys=%d" % (NAME, len(ob.data.vertices), len(ob.data.polygons)))
    print("BBOX  X %.3f  Y %.3f  Z %.3f..%.3f m  (min z 应≈0)" % (
        max(xs) - min(xs), max(ys) - min(ys), min(zs), max(zs)))

    if do_preview:
        rig = setup_preview_helpers()
        rig.contact_sheet(
            os.path.join(OUT_DIR, NAME + "_preview.png"),
            target=(0.0, 0.0, 0.22),
            shots=[("side", 90.0, 12.0, 2.6),
                   ("three_quarter", 40.0, 26.0, 2.7),
                   ("top", 90.0, 78.0, 2.4)],
        )

    bpy.ops.wm.save_as_mainfile(filepath=blend)
    print("saved:", glb)
    print("saved:", blend)

    assert all(abs(s - 1.0) < 1e-4 for s in ob.scale), "scale 必须为 1"
    assert abs(min(zs)) < 0.02, "地面必须在 z=0，实测 %.4f" % min(zs)
    print("SELF-CHECK OK")


if __name__ == "__main__":
    main()

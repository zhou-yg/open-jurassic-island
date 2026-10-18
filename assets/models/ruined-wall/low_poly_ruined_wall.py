# Blender 建模脚本：独立"破败矮墙"模块（可沿 X 任意拼接加长，low-poly）
#
# 用法:
#   /Applications/Blender.app/Contents/MacOS/Blender --background --python low_poly_ruined_wall.py
#   ... --python low_poly_ruined_wall.py -- --nopreview     # 只出 glb/blend，不渲染
#   ... --python low_poly_ruined_wall.py -- --seed 7        # 换一套破败随机
#   ... --python low_poly_ruined_wall.py -- --len 3.6       # 换单段长度（米）
#
# 产物（写入本目录）:
#   low_poly_ruined_wall.blend / .glb / _preview.png
#
# ---------------------------------------------------------------------------
# 这是什么 / 怎么用
# ---------------------------------------------------------------------------
# 一段**首尾都能对接**的破败石墙。把它沿着自己的 X 轴复制多份，就得到一堵任意
# 长度的废墟墙，而且接缝处过渡是连续的（理由见 _shared/ruin_kit.py 文件头
# 「拼接缝契约」）。在 Godot 里的用法：
#
#   墙体沿 +X 铺开，单段长 WALL_LEN_M（默认 2.90 m，与大门两翼同长），
#   第 i 段放到 x = i * WALL_LEN_M 即可；想往 −X 铺就传负的 i 或用 rotation.y = PI。
#   想增加变化：相邻段用 `scale.x = -1`（镜像）不会破坏接缝 —— 见契约第 3 条。
#
# 结构（全部按米建模，+Z 向上，地面 z = 0）
#   原点 = **墙体自身的中心**（X 居中、Y 居中、Z = 地面）。
#   之所以把原点放在中心而不是端头：拼接时"复制 + 平移一个段长"最不容易错，
#   而且旋转 180° 后依然是原地不动的一段墙。
#
# ---------------------------------------------------------------------------
# 为什么和大门两翼长得一模一样
# ---------------------------------------------------------------------------
# 因为**它们就是同一份代码**：build_wall_segment() 在 _shared/ruin_kit.py 里只有
# 一份实现，大门脚本和本脚本都 import 它。墙厚 / 墙高 / 基座 / 压顶 / 砖模数
# 全部同源，所以把本模型怼在大门两翼上继续加长，接缝天然对齐。
#
# 颜色（顶点色 COLOR_0，线性空间，1 个材质槽：石/木/苔共用 Stone 槽）
# 破败感靠三件事，都不靠贴图（同 assets/AGENTS.md §6.9）：
#   1) 形体：逐块砖决定存废 → 崩塌缺口、残缺压顶、塌口断面
#   2) 分色：整块棱面变色 —— 苔藓、泛白的旧补丁、深色断面
#   3) 分层：墙身下深上浅，压顶木色脊线
import os
import random
import sys

import bpy

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "_shared"))
from ruin_kit import (  # noqa: E402
    MeshBuilder, WALL_BAY_M, build_wall_segment, clear_scene,
    make_materials, setup_preview_helpers,
)

# ==========================================================================
# CONFIG —— 所有尺寸单位都是米
# ==========================================================================
OUT_DIR = os.path.dirname(os.path.abspath(__file__))
NAME = "low_poly_ruined_wall"
SEED = 20260715

# 单段长度：取大门两翼同长（WING_M = 2.90），这样两边可以直接对接。
# 必须是 WALL_BAY_M 的整数倍附近，build_wall_segment 会自己 round 到整数块砖。
WALL_LEN_M = 2.90


# ==========================================================================
# 建模
# ==========================================================================
def build_wall(rng, length, mats):
    """一段墙 = 一个网格对象 Wall，原点在中心、地面 z=0。

    残破的控制目标是"能当墙用"：大部分砖层还在（decay 低），
    只在 1~2 处塌口 + 局部矮一截，这样多段拼起来是一堵**长墙**，
    而不是一排孤零零的柱子 —— 后者没法用来加长。
    """
    b = MeshBuilder()
    # 以 0 为中心 → 两个端面都是接缝端
    build_wall_segment(
        b, rng, -length * 0.5, length * 0.5,
        tag=11, joint_ends=("start", "end"),
        decay=0.10, decay_slope=0.22, keep_rows=1.6, moss=0.24,
        gap_chance=0.90, gap_rows=2.2,
        decay_end="end",
    )
    ob = b.build("Wall", mats)
    ob.location = (0.0, 0.0, 0.0)
    return ob


# ==========================================================================
# 主流程
# ==========================================================================
def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    do_preview = "--nopreview" not in argv
    seed = SEED
    if "--seed" in argv:
        seed = int(argv[argv.index("--seed") + 1])
    length = WALL_LEN_M
    if "--len" in argv:
        length = float(argv[argv.index("--len") + 1])

    clear_scene()
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1.0
    random.seed(seed)
    rng = random.Random(seed)

    mats = make_materials("Ruin")
    wall = build_wall(rng, length, mats)

    # ---- 收尾：apply 变换 + 原点归零（assets/AGENTS.md §4）----
    for ob in bpy.data.objects:
        ob.select_set(ob.type == 'MESH')
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

    xs = [v.co.x for ob in bpy.data.objects if ob.type == 'MESH' for v in ob.data.vertices]
    ys = [v.co.y for ob in bpy.data.objects if ob.type == 'MESH' for v in ob.data.vertices]
    zs = [v.co.z for ob in bpy.data.objects if ob.type == 'MESH' for v in ob.data.vertices]
    print("=" * 62)
    print("%s  objects=%d  verts=%d  polys=%d" % (
        NAME, len([o for o in bpy.data.objects if o.type == 'MESH']),
        sum(len(o.data.vertices) for o in bpy.data.objects if o.type == 'MESH'),
        sum(len(o.data.polygons) for o in bpy.data.objects if o.type == 'MESH')))
    print("BBOX  X %.3f  Y %.3f  Z %.3f..%.3f m  (min z 应≈0)" % (
        max(xs) - min(xs), max(ys) - min(ys), min(zs), max(zs)))
    print("单段长 %.2f m / 可拼接长度 = 2.90 m 的整数倍" % (max(xs) - min(xs)))

    if do_preview:
        render_preview(wall)

    bpy.ops.wm.save_as_mainfile(filepath=blend)
    print("saved:", glb)
    print("saved:", blend)

    # ---- 自检（assets/AGENTS.md §6）----
    for ob in bpy.data.objects:
        if ob.type != 'MESH':
            continue
        assert all(abs(s - 1.0) < 1e-4 for s in ob.scale), "scale 必须为 1: %s" % ob.name
    assert abs(min(zs)) < 0.02, "地面必须在 z=0，实测 %.4f" % min(zs)

    verify_seams(wall, length)
    print("SELF-CHECK OK")


def verify_seams(wall, length):
    """数值验证"接缝自然"——不靠看图，靠两段墙的端面必须完全重合。

    做法：把同一段墙分别放在 x=0 与 x=+length 两处，
    取左段在接缝平面 x=+length/2 上的所有顶点，和右段在 x=+length/2 上
    （即右段本地 x=-length/2）的所有顶点，比较两者的 (y, z) 集合。
    只要两个端面的 (y,z) 顶点集完全一致，接缝处就不可能露出台阶、缝隙或穿插。

    顺带验证基座 / 压顶在 X 方向没有出挑：
      min(x) 必须 == -length/2，max(x) 必须 == +length/2（误差 1e-6）。
    一旦有人给基座加了 X 向外的偏移，两段拼起来就会互相插进去，这里立刻报错。
    """
    me = wall.data
    half = length * 0.5
    eps = 1e-5

    xs = [v.co.x for v in me.vertices]
    assert abs(min(xs) + half) < eps, "基座/压顶 在 -X 端出挑了：min x = %.6f，应为 %.6f" % (min(xs), -half)
    assert abs(max(xs) - half) < eps, "基座/压顶 在 +X 端出挑了：max x = %.6f，应为 %.6f" % (max(xs), half)

    # 接缝平面上的顶点剖面（两段共有同一个平面，剖面必须一致）
    def profile_at(px):
        return sorted((round(v.co.y, 5), round(v.co.z, 5))
                      for v in me.vertices if abs(v.co.x - px) < eps)

    right_end = profile_at(half)      # 本段 +X 端面 = 下一段的接入面
    left_end = profile_at(-half)      # 本段 -X 端面 = 上一段的接入面
    assert right_end == left_end, (
        "接缝端面不对称，拼接会露出台阶：-X 端 %d 个剖面点 / +X 端 %d 个点" %
        (len(left_end), len(right_end)))

    # 端面必须顶到满高（否则接缝处会掉一块）
    top_end = max(z for _, z in right_end)
    top_all = max(v.co.z for v in me.vertices)
    assert abs(top_end - (top_all - 0.20)) < 0.03 or top_end >= top_all - 0.21, (
        "接缝端没有顶到墙顶：端面最高 %.3f / 整体最高 %.3f" % (top_end, top_all))

    print("SEAM  OK 端面剖面 %d 点，接缝最高 %.3f m，X 严格切在 ±%.4f m" %
          (len(right_end), top_end, half))


# ==========================================================================
# 预览：正面 / 3-4 视角 / 两段拼接特写
# ==========================================================================
def render_preview(wall):
    """预览图要能证明"接缝自然"：单段 + 三段拼接（正面 / 3-4 视角）。

    单段看形体，三段看接缝 —— 接缝若有一丝台阶或色差，三段图上一眼就能看出来。
    """
    rig = setup_preview_helpers()

    # 额外复制两段到 ±段长，做出"三连"的实景（不改动原 mesh，只是临时对象）
    copies = []
    for sgn in (-1, 1):
        cp = wall.copy()
        cp.data = wall.data.copy()
        cp.location = (sgn * WALL_LEN_M, 0.0, 0.0)
        bpy.context.scene.collection.objects.link(cp)
        copies.append(cp)

    # 墙体沿 X 铺开 → 相机方位角要落在 ±Y 方向（az=90 是正侧面），
    # az=0 会顺着墙轴看过去，只能看到端头一个柱子。
    # 最后一格 zoom 到 x=+1.45 的接缝上：这是"过渡自然"的直接证据。
    rig.contact_sheet(
        os.path.join(OUT_DIR, NAME + "_preview.png"),
        target=(0.0, 0.0, 1.10),
        shots=[("single_side", 90.0, 6.0, 6.3),
               ("single_3q", 128.0, 20.0, 6.8),
               ("joined_side", 90.0, 7.0, 13.2),
               ("joined_3q", 124.0, 18.0, 13.8),
               ("seam_zoom", 74.0, 9.0, 5.0, (WALL_LEN_M * 0.5, 0.0, 1.20))],
    )

    for cp in copies:
        bpy.data.objects.remove(cp, do_unlink=True)


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""诊断：头两侧脸颊"折线感 vs 多面感"的成因对照。

跑法（Blender headless，不用 Godot）：
    /Applications/Blender.app/Contents/MacOS/Blender -b -P cheek_compare.py

产出：同目录的 cheek_compare.png —— 三行对照
    A 现状 31x31 环 + 交替对角线 + FACE_LIFT 硬归零
    B 31x31 + FACE_LIFT 改 smoothstep（去掉几何折痕）
    C 21x21 + smoothstep（面块够大，多面感回来）

结论（2026-11 实测）：
    * 颅骨 31 环 x 31 列 = 1922 三角面，占整只猴 5338 面的 35%
    * 相邻面法线夹角中位数只有 1.49°，每个面在预览图上仅 3~4 像素
      → 平面着色下 1.5° 的法线差 ≈ 2% 明暗差，**面块根本读不出来**
    * 于是唯一能读出来的是四边形按 (i+j) 奇偶**交替对角线**产生的
      **人字纹**——它读起来是"折线 / 噪点"，不是"面块"
    * FACE_LIFT 在 |az|=60.2° 硬归零的 C1 折痕（脸盘颜色边界在 61.3°，
      只差 1.1°）确实存在，但视觉影响远小于人字纹（B 图几乎没变）
"""
import bpy, bmesh, math, os, sys
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.dirname(HERE)
MODELS = os.path.dirname(MODEL_DIR)

sys.path.insert(0, os.path.join(MODELS, "ds-monkey-trunk"))
import ds_monkey_trunk as TR            # 会清场 + 建好预览灯 / 相机
sys.path.insert(0, os.path.join(MODELS, "_shared"))
sys.modules.pop("monkey_head", None)
import monkey_head as MH

scene = bpy.context.scene
TR.scene.render.film_transparent = False
TR.scene.render.image_settings.color_mode = 'RGBA'
TR.scene.view_settings.view_transform = 'Standard'


def lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def densify_rows(anchors, n):
    """把 (仰角°, 权重) 的锚点细分成 n 行（同 m3f 脚本里的那个）。"""
    out = []
    deg0, deg1 = anchors[0][0], anchors[-1][0]
    for i in range(n):
        deg = deg0 + (deg1 - deg0) * i / float(n - 1)
        w = anchors[-1][1]
        for k in range(len(anchors) - 1):
            d0, w0 = anchors[k]; d1, w1 = anchors[k + 1]
            if d1 <= deg <= d0:
                t = (d0 - deg) / (d0 - d1); w = w0 + (w1 - w0) * t; break
        out.append((round(deg, 3), round(w, 4)))
    return out


ORIG_SIDE = list(MH.SIDE_LIMIT)


def patched_skull(smooth_lift):
    """把 FACE_LIFT 的收尾方式换掉，其余与共用头一致。"""
    def sp(az, el):
        zn = max(-0.999, min(0.999, math.sin(el)))
        hw = MH.lerp_table(MH.PROFILE, zn); fb = MH.lerp_table(MH.FRONT, zn)
        mz = MH.lerp_table(MH.MUZZLE, zn); bk = MH.lerp_table(MH.BACK, zn)
        ca, sa = math.cos(az), math.sin(az); x = hw * sa
        if ca >= 0.0:
            y = fb * (abs(ca) ** MH.FACE_ROUND_P)
            la = abs(az)
            if la < MH.FACE_LIFT_AZ:
                if smooth_lift:
                    t = max(0.0, min(1.0, 1.0 - la / MH.FACE_LIFT_AZ))
                    y += MH.FACE_LIFT * (t * t * (3 - 2 * t))     # C1 连续
                else:
                    y += MH.FACE_LIFT * (1.0 - (la / MH.FACE_LIFT_AZ) ** 2)
            y += MH.MUZZLE_SCALE * mz * math.exp(-(az / MH.MUZZLE_AZ) ** 2)
        else:
            y = bk * ca
        return Vector((x, y, MH.RZ * zn))
    return sp


def build(nrow, nf, nface, smooth_lift):
    MH.ROWS[:] = [(76.0, 0.10), (66.0, 0.25), (48.0, 0.55), (33.0, 0.95), None] + \
        densify_rows([(8.0, 0.75), (-8.0, 0.45), (-17.0, 0.32), (-26.0, 0.20),
                      (-46.0, 0.0), (-64.0, 0.0), (-79.0, 0.0)], nrow - 5)
    MH.NCOL_FACE, MH.NCOL_FUR = nface, nf
    MH.NCOL = 2 * nf + nface + 1

    def col_az_dense(i, A):
        nfu, nfc = MH.NCOL_FUR, MH.NCOL_FACE
        if i < nfu:
            return -math.pi + (math.pi - A) * ((i + 0.5) / nfu)
        if i <= nfu + nfc:
            return -A + 2.0 * A * ((i - nfu) / float(nfc))
        j = i - nfu - nfc - 1
        return A + (math.pi - A) * ((j + 0.5) / nfu)

    MH.col_az = col_az_dense
    MH.SIDE_LIMIT[:] = [(el, az * 0.86) for (el, az) in ORIG_SIDE]
    MH.skull_point = patched_skull(smooth_lift)
    return MH.build_skull()


def shade_edge(head):
    """复刻 m3f 的 shade_face_edge()：脸盘边缘一圈染过渡色。"""
    me = head.data
    ncols, nrows = MH.NCOL, len(MH.ROWS)
    i_last = MH.NCOL_FUR + MH.NCOL_FACE
    pairs = set()
    for j in range(nrows):
        a = 1 + j * ncols + i_last;       pairs.add((a, a + 1))
        b = 1 + j * ncols + (MH.NCOL_FUR - 1); pairs.add((b, b + 1))
    mat = bpy.data.materials.new("shadow")
    mat.use_nodes = True
    bsdf = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    bsdf.inputs["Base Color"].default_value = \
        tuple(lin(c) for c in (0.690, 0.478, 0.286)) + (1.0,)
    me.materials.append(mat)
    si = len(me.materials) - 1
    for poly in me.polygons:
        vs = list(poly.vertices)
        for a, b in pairs:
            if a in vs and b in vs:
                poly.material_index = si
                break


VARIANTS = [
    (31, 9, 12, False, "A 现状 31x31 硬归零"),
    (31, 9, 12, True,  "B 31x31 + smoothstep"),
    (21, 7,  7, True,  "C 21x21 + smoothstep"),
]
W = H = 560
TR.scene.render.resolution_x = W
TR.scene.render.resolution_y = H
buf = None
for i, (nrow, nf, nface, sl, label) in enumerate(VARIANTS):
    bpy.ops.object.select_all(action='DESELECT')
    for ob in list(bpy.data.objects):
        if ob.type == 'MESH':
            bpy.data.objects.remove(ob, do_unlink=True)
    head = build(nrow, nf, nface, sl)
    shade_edge(head)
    ntri = sum(len(p.vertices) - 2 for p in head.data.polygons)
    TR.aim_camera(TR.CAM, Vector((0.0, 0.0, -0.01)), 3.0, 0.26, 14.0)
    p = os.path.join(TR.RENDER_DIR, "cheekcmp_%d.png" % i)
    TR.render_to(p)
    a = TR.load_rgba(p, W, H)
    if buf is None:
        import numpy as np
        buf = np.ones((H * len(VARIANTS), W, 4), dtype=np.float32)
    buf[i * H:(i + 1) * H, 0:W] = a
    print("rendered %-26s 颅骨 %d 三角面" % (label, ntri))

import numpy as np
OUT = os.path.join(HERE, "cheek_compare.png")
TR.save_rgba(buf, OUT, "cheek_compare")
print("->", OUT)

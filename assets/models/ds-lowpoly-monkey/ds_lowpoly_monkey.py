# -*- coding: utf-8 -*-
"""
ds_lowpoly_monkey.py
====================
Procedural generator for ``ds-lowpoly-monkey`` - a chibi low-poly monkey
rebuilt 1:1 from ``reference.jpg`` (the 2x2 four-view sheet in this folder:
front / right side / three-quarter walk / back).

The reference is a *rendered* sheet on a checkerboard transparent background.
Only the four character silhouettes are used; the checkerboard and the faint
stray colour blocks are ignored.

Design notes
------------
* metric, 1 Blender unit = 1 m, ground at z = 0, character faces +Y
  (Godot: -Z forward), origin at the ground point between the feet
* standing height ≈ 0.96 m (to the tip of the head tuft)
* big chibi skull, huge tan face shield, protruding muzzle, small round ears
* flat-shaded, quad-built low-poly surfaces; every joint is a ball with the
  limb tube growing *out of* it, so the silhouette stays continuous when the
  limb rotates (no "bamboo joint" creases)
* rig = node hierarchy (one mesh object per limb, origin on the joint),
  NOT an armature with weights.  glTF -> Godot AnimationPlayer, no skinning
  artifacts, and every object keeps scale = 1
* **the head is the shared asset** ``models/_shared/monkey_head.py`` (the head
  of ``ds-monkey-head``), scaled 1.20x and mounted on the neck joint.  Its
  two expression clips (Laugh / Fear) are **adapted into the body clips**
  instead of being exported as separate clips (see ``EXPRESSION``).
* 8 baked animation clips (30 fps):
    DSMonkey_Run / Startle / Tremble / ThrowOne / ThrowTwo / Clap / Snatch
    + DSMonkey_SitIdle (the reference sitting pose, as a usable loop)

Outputs
-------
ds_lowpoly_monkey.glb            Godot asset (8 clips)
ds_lowpoly_monkey.blend          Blender source
ds_lowpoly_monkey_preview.png    2x2 sheet in the reference layout (sitting)
ds_lowpoly_monkey_anim.png       animation contact sheet

Run with::

    blender --background --python ds_lowpoly_monkey.py
"""

import math
import os
import random
import subprocess
import sys
import tempfile

import bpy
import bmesh
from mathutils import Euler, Matrix, Vector
from mathutils.bvhtree import BVHTree

# --------------------------------------------------------------------------
# paths / constants
# --------------------------------------------------------------------------
HERE = os.path.dirname(os.path.abspath(__file__))
BLEND_PATH = os.path.join(HERE, "ds_lowpoly_monkey.blend")
GLB_PATH = os.path.join(HERE, "ds_lowpoly_monkey.glb")
PREVIEW_PATH = os.path.join(HERE, "ds_lowpoly_monkey_preview.png")
ANIM_PATH = os.path.join(HERE, "ds_lowpoly_monkey_anim.png")

FPS = 30
PREFIX = "DSMonkey"

random.seed(20251028)

# --------------------------------------------------------------------------
# palette - shared with the head (models/_shared/monkey_head.py), so the painted
# body panels and the separate head mesh read as one monkey.
# --------------------------------------------------------------------------
PALETTE = {
    "Fur":       (0.478, 0.271, 0.153),   # #7A4527 == monkey_head PAL["fur"]
    "FurDark":   (0.306, 0.173, 0.114),   # #4E2C1D == monkey_head PAL["fur_dark"]
    "Tan":       (0.859, 0.659, 0.431),   # #DBA86E == monkey_head PAL["face"]
    "TanDeep":   (0.788, 0.561, 0.341),   # #C98F57 belly / hands / feet (a touch deeper)
}
MAT_ORDER = ["Fur", "FurDark", "Tan", "TanDeep"]
MAT_INDEX = {n: i for i, n in enumerate(MAT_ORDER)}

# --------------------------------------------------------------------------
# the shared head (models/_shared/monkey_head.py)
# --------------------------------------------------------------------------
# The shared head is modelled around a 0.300 m skull.  The body it replaces had
# a 0.360 m skull, and the chibi proportions live on that ratio, so the whole
# head is scaled by 1.20 in the mesh data (never by an object scale).
HEAD_SCALE = 1.05
HEAD_SKULL_C = Vector((0.0, 0.0, 0.175))   # skull centre in the head object

# shared-head object name -> body node name (Godot reads these)
HEAD_PART_RENAME = {
    "DSMonkeyHead": PREFIX + "_Head",
    "DSMonkeyTuft": PREFIX + "_Tuft",
    "DSMonkeyEar_L": PREFIX + "_Ear_L",
    "DSMonkeyEar_R": PREFIX + "_Ear_R",
    "DSMonkeyEye_L": PREFIX + "_Eye_L",
    "DSMonkeyEye_R": PREFIX + "_Eye_R",
    "DSMonkeyPupil_L": PREFIX + "_Pupil_L",
    "DSMonkeyPupil_R": PREFIX + "_Pupil_R",
    "DSMonkeyEyeShut_L": PREFIX + "_EyeShut_L",
    "DSMonkeyEyeShut_R": PREFIX + "_EyeShut_R",
    "DSMonkeyBrow_L": PREFIX + "_Brow_L",
    "DSMonkeyBrow_R": PREFIX + "_Brow_R",
    "DSMonkeyNostrils": PREFIX + "_Nostrils",
    "DSMonkeyMouthSmile": PREFIX + "_MouthSmile",
    "DSMonkeyMouthLaugh": PREFIX + "_MouthLaugh",
    "DSMonkeyMouthFear": PREFIX + "_MouthFear",
}
HEAD_STATIC_PARTS = [PREFIX + "_Tuft", PREFIX + "_Nostrils"]
HEAD_ANIM_PARTS = [PREFIX + "_Eye_L", PREFIX + "_Eye_R",
                   PREFIX + "_Pupil_L", PREFIX + "_Pupil_R",
                   PREFIX + "_EyeShut_L", PREFIX + "_EyeShut_R",
                   PREFIX + "_Brow_L", PREFIX + "_Brow_R",
                   PREFIX + "_MouthSmile", PREFIX + "_MouthLaugh",
                   PREFIX + "_MouthFear"]
HEAD_REST_LOC = {}
HEAD_REST_ROT = {}
MH = None

def srgb2lin(c):
    out = []
    for v in c:
        out.append(v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4)
    return tuple(out)


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def smoothstep(t):
    t = clamp(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def ease_out(t):
    t = clamp(t, 0.0, 1.0)
    return 1.0 - (1.0 - t) ** 3


def ease_in(t):
    t = clamp(t, 0.0, 1.0)
    return t ** 3


def lerp(a, b, t):
    return a + (b - a) * t


def dir_az_el(az, el):
    return Vector((math.sin(az) * math.cos(el),
                   math.cos(az) * math.cos(el),
                   math.sin(el))).normalized()


# --------------------------------------------------------------------------
# mesh builder
# --------------------------------------------------------------------------
class MeshBuilder:
    def __init__(self):
        self.verts = []
        self.faces = []
        self.mats = []

    def v(self, p):
        self.verts.append(tuple(p))
        return len(self.verts) - 1

    def face(self, idx, mat):
        self.faces.append(tuple(idx))
        self.mats.append(MAT_INDEX[mat])

    def tri(self, a, b, c, mat):
        self.face((a, b, c), mat)

    def quad(self, a, b, c, d, mat):
        self.face((a, b, c, d), mat)


def _mat_fn(mat):
    if isinstance(mat, str):
        return lambda d, c, n: mat
    return mat


def sphere(b, center, radii, segs, rings, mat, mat_fn=None, basis=None,
           deform=None, phase=0.0):
    """Flat-shaded quad UV sphere with per-face material callback.

    ``rings`` is the number of latitude bands between the two poles.
    ``deform(direction, point) -> point`` edits the point in local space.
    ``mat_fn(direction, face_center, face_normal) -> palette name``.
    """
    if mat_fn is None:
        mat_fn = _mat_fn(mat)
    center = Vector(center)
    basis = basis if basis is not None else Matrix.Identity(3)

    def make_point(d):
        p = Vector((d.x * radii[0], d.y * radii[1], d.z * radii[2]))
        if deform is not None:
            p = deform(d, p)
        p = basis @ p
        return center + p

    ring_dirs = []
    ring_idx = []
    for j in range(1, rings):
        phi = math.pi * j / rings
        row_d = []
        row_i = []
        for i in range(segs):
            theta = 2.0 * math.pi * i / segs + phase
            d = Vector((math.sin(phi) * math.cos(theta),
                        math.sin(phi) * math.sin(theta),
                        math.cos(phi)))
            row_d.append(d)
            row_i.append(b.v(make_point(d)))
        ring_dirs.append(row_d)
        ring_idx.append(row_i)

    north_d = Vector((0.0, 0.0, 1.0))
    south_d = Vector((0.0, 0.0, -1.0))
    north_i = b.v(make_point(north_d))
    south_i = b.v(make_point(south_d))

    def face_mat(ds):
        d = sum(ds, Vector((0, 0, 0)))
        d.normalize()
        pts = [make_point(x) for x in ds]
        c = sum(pts, Vector((0, 0, 0))) / len(pts)
        # approximate normal from the poly (works for quads and tris)
        n = (pts[1] - pts[0]).cross(pts[2] - pts[0])
        if n.length < 1e-9:
            n = d
        n.normalize()
        return mat_fn(d, c, n)

    # north cap
    for i in range(segs):
        j = (i + 1) % segs
        mat_name = face_mat([north_d, ring_dirs[0][i], ring_dirs[0][j]])
        b.tri(north_i, ring_idx[0][i], ring_idx[0][j], mat_name)

    # bands
    for j in range(len(ring_idx) - 1):
        for i in range(segs):
            k = (i + 1) % segs
            ds = [ring_dirs[j][i], ring_dirs[j][k],
                  ring_dirs[j + 1][k], ring_dirs[j + 1][i]]
            mat_name = face_mat(ds)
            b.quad(ring_idx[j][i], ring_idx[j][k],
                   ring_idx[j + 1][k], ring_idx[j + 1][i], mat_name)

    # south cap
    last = len(ring_idx) - 1
    for i in range(segs):
        j = (i + 1) % segs
        mat_name = face_mat([south_d, ring_dirs[last][j], ring_dirs[last][i]])
        b.tri(south_i, ring_idx[last][j], ring_idx[last][i], mat_name)


def ball(b, center, radius, segs, rings, mat, mat_fn=None, deform=None):
    r = (radius, radius, radius) if isinstance(radius, (int, float)) else radius
    sphere(b, center, r, segs, rings, mat, mat_fn=mat_fn, deform=deform)


def _frame(axis):
    ref = Vector((0.0, 1.0, 0.0))
    if abs(axis.dot(ref)) > 0.92:
        ref = Vector((1.0, 0.0, 0.0))
    u = axis.cross(ref).normalized()
    v = axis.cross(u).normalized()
    return u, v


def tube(b, p0, p1, r0, r1, segs, mat, cap0=True, cap1=True, phase=0.0):
    p0, p1 = Vector(p0), Vector(p1)
    axis = p1 - p0
    if axis.length < 1e-8:
        return
    axis.normalize()
    u, v = _frame(axis)
    ring0 = []
    ring1 = []
    for i in range(segs):
        th = 2.0 * math.pi * i / segs + phase
        off = u * math.cos(th) + v * math.sin(th)
        ring0.append(b.v(p0 + off * r0))
        ring1.append(b.v(p1 + off * r1))
    for i in range(segs):
        k = (i + 1) % segs
        b.quad(ring0[i], ring0[k], ring1[k], ring1[i], mat)
    if cap0:
        c0 = b.v(p0)
        for i in range(segs):
            k = (i + 1) % segs
            b.tri(c0, ring0[k], ring0[i], mat)
    if cap1:
        c1 = b.v(p1)
        for i in range(segs):
            k = (i + 1) % segs
            b.tri(c1, ring1[i], ring1[k], mat)


def tube_path(b, points, radii, segs, mat, cap0=True, cap1=True):
    pts = [Vector(p) for p in points]
    if len(pts) < 2:
        return
    tangents = []
    for i in range(len(pts)):
        if i == 0:
            t = pts[1] - pts[0]
        elif i == len(pts) - 1:
            t = pts[-1] - pts[-2]
        else:
            t = pts[i + 1] - pts[i - 1]
        tangents.append(t.normalized())

    u, v = _frame(tangents[0])
    rings = []
    for i, p in enumerate(pts):
        if i > 0:
            # parallel transport the frame
            u = (u - tangents[i] * u.dot(tangents[i]))
            if u.length < 1e-7:
                u, v = _frame(tangents[i])
            else:
                u.normalize()
        v = tangents[i].cross(u).normalized()
        r = radii[i]
        ring = []
        for s in range(segs):
            th = 2.0 * math.pi * s / segs
            ring.append(b.v(p + (u * math.cos(th) + v * math.sin(th)) * r))
        rings.append(ring)

    for i in range(len(rings) - 1):
        for s in range(segs):
            k = (s + 1) % segs
            b.quad(rings[i][s], rings[i][k], rings[i + 1][k], rings[i + 1][s], mat)
    if cap0:
        c = b.v(pts[0])
        for s in range(segs):
            k = (s + 1) % segs
            b.tri(c, rings[0][k], rings[0][s], mat)
    if cap1:
        c = b.v(pts[-1])
        for s in range(segs):
            k = (s + 1) % segs
            b.tri(c, rings[-1][s], rings[-1][k], mat)


def shell_patch(b, surface, outline, rings, lift, mat, radial_center, center_dir=None):
    """Curved polygon patch lying on a (deformed) ellipsoid surface.

    ``surface(direction, lift)`` returns the local mesh point.  The outline is
    a closed loop of unit directions; the patch is built as concentric rings
    so the facets stay chunky.  Winding is decided from the geometry, so the
    patch always faces outward.
    """
    dirs = [Vector(d).normalized() for d in outline]
    if center_dir is None:
        c = sum(dirs, Vector((0.0, 0.0, 0.0)))
        if c.length < 1e-8:
            c = Vector((0.0, 1.0, 0.0))
    else:
        c = Vector(center_dir)
    c.normalize()
    n = len(dirs)
    ring_dirs = []
    for r in range(1, rings + 1):
        t = r / float(rings)
        ring = []
        for d in dirs:
            v = c.lerp(d, t)
            if v.length < 1e-8:
                v = d
            ring.append(v.normalized())
        ring_dirs.append(ring)

    center_p = surface(c, lift)
    center_i = b.v(center_p)
    ring_i = []
    for ring in ring_dirs:
        ring_i.append([b.v(surface(d, lift)) for d in ring])

    p1 = surface(ring_dirs[0][0], lift)
    p2 = surface(ring_dirs[0][1], lift)
    flip = (p1 - center_p).cross(p2 - center_p).dot(center_p - radial_center) < 0.0

    def tri(a, bb, cc):
        b.face((a, cc, bb) if flip else (a, bb, cc), mat)

    def quad(a, bb, cc, dd):
        b.face((a, dd, cc, bb) if flip else (a, bb, cc, dd), mat)

    for i in range(n):
        k = (i + 1) % n
        tri(center_i, ring_i[0][i], ring_i[0][k])
    for r in range(len(ring_i) - 1):
        for i in range(n):
            k = (i + 1) % n
            quad(ring_i[r][i], ring_i[r][k], ring_i[r + 1][k], ring_i[r + 1][i])


def oval_outline(center_dir, tangent_u, tangent_v, a, b, segs=12):
    """Ellipse in direction space around ``center_dir``."""
    dc = Vector(center_dir).normalized()
    tu = Vector(tangent_u)
    tv = Vector(tangent_v)
    tu = (tu - dc * tu.dot(dc)).normalized()
    tv = dc.cross(tu).normalized()
    out = []
    for i in range(segs):
        th = 2.0 * math.pi * i / segs
        d = dc + tu * (math.sin(a) * math.cos(th)) + tv * (math.sin(b) * math.sin(th))
        out.append(d.normalized())
    return out


def catmull_rom(points, samples_per_seg=8):
    pts = [Vector(p) for p in points]
    ext = [pts[0]] + pts + [pts[-1]]
    out = []
    for i in range(len(pts) - 1):
        p0, p1, p2, p3 = ext[i], ext[i + 1], ext[i + 2], ext[i + 3]
        for s in range(samples_per_seg):
            t = s / float(samples_per_seg)
            t2, t3 = t * t, t * t * t
            p = 0.5 * ((2.0 * p1) +
                       (-p0 + p2) * t +
                       (2.0 * p0 - 5.0 * p1 + 4.0 * p2 - p3) * t2 +
                       (-p0 + 3.0 * p1 - 3.0 * p2 + p3) * t3)
            out.append(p)
    out.append(pts[-1])
    return out


# --------------------------------------------------------------------------
# shared head (built by models/_shared/monkey_head.py after the scene is cleared)
# --------------------------------------------------------------------------
def _basis_from_normal(n):
    """3x3 basis whose local +Z is ``n`` and local +X is horizontal."""
    n = Vector(n).normalized()
    right = Vector((1.0, 0.0, 0.0))
    if abs(n.dot(right)) > 0.94:
        right = Vector((0.0, 1.0, 0.0))
    right = (right - n * right.dot(n)).normalized()
    up = n.cross(right).normalized()
    return Matrix((right, up, n)).transposed()




# --------------------------------------------------------------------------
# rig description
# --------------------------------------------------------------------------
# name -> (parent, local rest location, rest rotation (deg))
RIG_SPEC = {}


def add_joint(name, parent, loc, rot=(0.0, 0.0, 0.0)):
    RIG_SPEC[name] = (parent, Vector(loc), Vector(rot))


add_joint(PREFIX + "_Root", None, (0, 0, 0))
add_joint(PREFIX + "_Hips", PREFIX + "_Root", (0, 0, 0.315))
add_joint(PREFIX + "_Torso", PREFIX + "_Hips", (0, 0, 0))
# The head itself lives at HEAD_SKULL_C inside this node; the node stays on the
# neck so nodding rotates the skull about the neck, not about its own centre.
add_joint(PREFIX + "_Head", PREFIX + "_Torso", (0, 0, 0.245))
# Ear joints are overwritten by import_shared_head() with the shared head's ear
# centres once the head exists; the old values belonged to the hand-built head.
add_joint(PREFIX + "_Ear_R", PREFIX + "_Head", (0.206, -0.010, 0.145), (0, -6, 40))
add_joint(PREFIX + "_Ear_L", PREFIX + "_Head", (-0.206, -0.010, 0.145), (0, 6, -40))

for side, sx in (("R", 1.0), ("L", -1.0)):
    # The shoulder pivot sits right on the torso surface (the shoulder ball
    # bites ~3 mm into it, so the arm still reads as attached) and high enough
    # that the arm can swing clear of the belly.  At 0.094 m / z 0.175 the
    # upper arm was ~75% inside the torso at chest height and read as a fold of
    # the body (see base_stand()).
    add_joint(PREFIX + "_Arm_%s_Upper" % side, PREFIX + "_Torso",
              (0.122 * sx, 0, 0.185), (0, 0, 0))
    add_joint(PREFIX + "_Arm_%s_Fore" % side, PREFIX + "_Arm_%s_Upper" % side,
              (0, 0, -0.145), (0, 0, 0))
    add_joint(PREFIX + "_Arm_%s_Hand" % side, PREFIX + "_Arm_%s_Fore" % side,
              (0, 0, -0.135))
    add_joint(PREFIX + "_Leg_%s_Thigh" % side, PREFIX + "_Hips",
              (0.070 * sx, 0, -0.010), (0, 0, 0))
    add_joint(PREFIX + "_Leg_%s_Shin" % side, PREFIX + "_Leg_%s_Thigh" % side,
              (0, 0, -0.150), (0, 0, 0))
    add_joint(PREFIX + "_Leg_%s_Foot" % side, PREFIX + "_Leg_%s_Shin" % side,
              (0, 0, -0.115), (0, 0, 0))

TAIL_WORLD = [
    (0.015, -0.095, 0.305),
    (0.050, -0.170, 0.330),
    (0.110, -0.225, 0.375),
    (0.180, -0.240, 0.430),
    (0.250, -0.215, 0.480),
    (0.300, -0.155, 0.500),
    (0.315, -0.090, 0.485),
    (0.300, -0.040, 0.450),
    (0.265, -0.030, 0.420),
    (0.235, -0.060, 0.412),
]
TAIL_SAMPLES = 27
TAIL_CURVE = catmull_rom(TAIL_WORLD, samples_per_seg=3)
TAIL_SPLIT = [0, 7, 14, 21, 27]
TAIL_RADII = [0.018 * (1.0 - 0.72 * (i / 27.0)) for i in range(28)]
TAIL_SEG_NAMES = [PREFIX + "_Tail_%d" % i for i in range(1, 5)]
for i, nm in enumerate(TAIL_SEG_NAMES):
    start = TAIL_CURVE[TAIL_SPLIT[i]]
    if i == 0:
        parent = PREFIX + "_Hips"
        local = start - Vector((0.0, 0.0, 0.315))
    else:
        parent = TAIL_SEG_NAMES[i - 1]
        local = start - TAIL_CURVE[TAIL_SPLIT[i - 1]]
    add_joint(nm, parent, local)

# names that can be animated (everything but the root)
ANIMATED = [n for n in RIG_SPEC if n != PREFIX + "_Root"]


def rest_location(name):
    return RIG_SPEC[name][1].copy()


def rest_rotation(name):
    return Vector([math.radians(v) for v in RIG_SPEC[name][2]])


# --------------------------------------------------------------------------
# materials / object creation
# --------------------------------------------------------------------------
MATS = {}


def build_materials():
    for name in MAT_ORDER:
        srgb = PALETTE[name]
        lin = srgb2lin(srgb)
        mat = bpy.data.materials.new("DSMonkey_" + name)
        mat.use_nodes = True
        bsdf = None
        for node in mat.node_tree.nodes:
            if node.type == "BSDF_PRINCIPLED":
                bsdf = node
                break
        if bsdf is None:
            continue
        bsdf.inputs["Base Color"].default_value = (*lin, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.86
        if "Specular IOR Level" in bsdf.inputs:
            bsdf.inputs["Specular IOR Level"].default_value = 0.18
        mat.diffuse_color = (*lin, 1.0)
        MATS[name] = mat


def make_object(name, builder, collection=None, recalc=True, smooth=False):
    me = bpy.data.meshes.new(name + "_mesh")
    me.from_pydata(builder.verts, [], builder.faces)
    me.update()
    for n in MAT_ORDER:
        me.materials.append(MATS[n])
    for i, poly in enumerate(me.polygons):
        poly.material_index = builder.mats[i]
        poly.use_smooth = smooth
    if recalc:
        bm = bmesh.new()
        bm.from_mesh(me)
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
        bm.to_mesh(me)
        bm.free()
        me.update()
    ob = bpy.data.objects.new(name, me)
    (collection or bpy.context.scene.collection).objects.link(ob)
    ob.scale = (1.0, 1.0, 1.0)
    return ob


# --------------------------------------------------------------------------
# body parts
# --------------------------------------------------------------------------
OBJ = {}


def import_shared_head():
    """Build the head from ``models/_shared/monkey_head.py`` and mount it.

    Must run **after** ``clear_scene()``: the shared module builds its meshes
    into the current scene on import, and a later scene wipe would delete them
    (importing before the wipe also makes Blender rename duplicates with a
    ``.001`` suffix, which breaks every lookup by name).
    """
    global MH
    shared = os.path.join(os.path.dirname(HERE), "_shared")
    if shared not in sys.path:
        sys.path.insert(0, shared)
    sys.modules.pop("monkey_head", None)      # re-runs inside one Blender session
    import monkey_head as mh
    MH = mh

    # the body palette above is copied from the head palette - keep them in sync
    for body_key, head_key in (("Fur", "fur"), ("FurDark", "fur_dark"),
                               ("Tan", "face")):
        assert PALETTE[body_key] == mh.PAL[head_key], \
            "body palette drifted from monkey_head PAL[%r]" % head_key

    K = HEAD_SCALE
    off = HEAD_SKULL_C

    # 1) rename every part to the body's node convention
    for old, new in HEAD_PART_RENAME.items():
        mh.OBJ[old].name = new
        OBJ[new] = mh.OBJ[old]

    # 2) scale + translate the whole head so the skull centre sits at
    #    HEAD_SKULL_C in the head node (which stays on the neck pivot).
    #    Mesh data is scaled, never the object's ``scale`` (§6.7).
    #    world(head-local) = off + K * old_world, split as
    #    location = off + K * old_location, vertices = K * old_vertex.
    for old in HEAD_PART_RENAME:
        ob = mh.OBJ[old]
        ob.location = off + Vector(ob.location) * K
        for v in ob.data.vertices:
            v.co = v.co * K
    # the skull mesh itself carries the skull-centre offset, because the head
    # node's pivot has to stay on the neck (that is what the nods rotate about)
    head_ob = OBJ[PREFIX + "_Head"]
    for v in head_ob.data.vertices:
        v.co += off
    head_ob.location = Vector((0.0, 0.0, 0.0))

    # 3) the ears are built in skull space; re-pivot them on their own centre so
    #    the ear joints rotate the bowl instead of orbiting the skull centre
    for side, sign in (("L", -1.0), ("R", 1.0)):
        ob = OBJ[PREFIX + "_Ear_" + side]
        c = Vector((mh.EAR_X * sign, mh.EAR_Y, mh.EAR_Z)) * K
        pivot = off + c
        for v in ob.data.vertices:
            v.co -= c
        ob.location = pivot
        RIG_SPEC[PREFIX + "_Ear_" + side] = (PREFIX + "_Head", pivot,
                                            Vector((0.0, 0.0, 0.0)))

    # 4) rest transforms the expression baker keys against.  The three mouths
    #    that hide inside the skull already carry the shared module's PARK
    #    offset, so "rest" for them means "parked".
    for old, new in HEAD_PART_RENAME.items():
        ob = OBJ[new]
        HEAD_REST_LOC[new] = Vector(ob.location)
        HEAD_REST_ROT[new] = Vector(ob.rotation_euler)

    # every expression part must exist before the baker looks it up
    assert set(HEAD_ANIM_PARTS) <= set(OBJ)
    print("shared head: %d parts, scale %.2f" % (len(HEAD_PART_RENAME), K))


TORSO_C = Vector((0.0, 0.0, 0.105))
# Slimmer than the old barrel: with the big shared head the reference body is
# clearly narrower than the skull, and a 0.23 m torso swallowed the upper arm.
TORSO_R = (0.113, 0.101, 0.140)


def torso_deform(d, p):
    k = d.z
    if k > 0.0:
        p.x *= 1.0 - 0.10 * k
        p.y *= 1.0 - 0.08 * k
    else:
        p.x *= 1.0 + 0.050 * (-k)
    if d.y > 0.0:
        p.y += 0.008 * max(0.0, -k)
    return p


def torso_surface(d, lift=0.0):
    p = Vector((d.x * TORSO_R[0], d.y * TORSO_R[1], d.z * TORSO_R[2]))
    p = torso_deform(d, p)
    n = Vector((p.x / (TORSO_R[0] ** 2),
                p.y / (TORSO_R[1] ** 2),
                p.z / (TORSO_R[2] ** 2))).normalized()
    return TORSO_C + p + n * lift


def build_torso(collection):
    b = MeshBuilder()
    sphere(b, TORSO_C, TORSO_R, 12, 9, "Fur", deform=torso_deform)
    # short neck, so the chin sits above the chest like the reference
    tube(b, (0.0, 0.0, 0.222), (0.0, 0.0, 0.262), 0.048, 0.052, 10, "Fur")
    ball(b, (0.0, 0.0, 0.256), 0.052, 10, 6, "Fur")
    ob = make_object(PREFIX + "_Torso", b, collection)
    OBJ[PREFIX + "_Torso"] = ob
    return ob


HIPS_R = (0.110, 0.094, 0.088)


def hips_surface(d, lift=0.0):
    p = Vector((d.x * HIPS_R[0], d.y * HIPS_R[1], d.z * HIPS_R[2]))
    n = Vector((p.x / (HIPS_R[0] ** 2),
                p.y / (HIPS_R[1] ** 2),
                p.z / (HIPS_R[2] ** 2))).normalized()
    return p + n * lift


def build_hips(collection):
    b = MeshBuilder()
    sphere(b, (0, 0, 0), HIPS_R, 10, 7, "Fur")
    ob = make_object(PREFIX + "_Hips", b, collection)
    OBJ[PREFIX + "_Hips"] = ob
    return ob


def build_arm(side, sx, collection):
    up_name = PREFIX + "_Arm_%s_Upper" % side
    fore_name = PREFIX + "_Arm_%s_Fore" % side
    hand_name = PREFIX + "_Arm_%s_Hand" % side

    # Slimmer than the torso surface is thick: the arm has to clear the widest
    # part of the torso at the elbow, not just at the shoulder.
    b = MeshBuilder()
    ball(b, (0, 0, 0.002), 0.0395, 10, 6, "Fur")
    tube(b, (0, 0, 0.004), (0, 0, -0.145), 0.0360, 0.0300, 10, "Fur")
    OBJ[up_name] = make_object(up_name, b, collection)

    b = MeshBuilder()
    ball(b, (0, 0, 0), 0.0335, 10, 6, "Fur")
    tube(b, (0, 0, -0.004), (0, 0, -0.135), 0.0295, 0.0255, 10, "Fur")
    OBJ[fore_name] = make_object(fore_name, b, collection)

    b = MeshBuilder()
    ball(b, (0, 0, 0), 0.026, 10, 6, "TanDeep")
    # small palm
    sphere(b, (0.0, 0.005, -0.030), (0.034, 0.027, 0.040), 10, 6, "TanDeep")
    # three short curled fingers
    for fx in (-0.017, 0.0, 0.017):
        p0 = Vector((fx, 0.013, -0.050))
        p1 = Vector((fx, 0.028, -0.068))
        tube(b, p0, p1, 0.0100, 0.0086, 6, "TanDeep")
        ball(b, p1, 0.0088, 6, 4, "TanDeep")
    # thumb on the body side
    p0 = Vector((-sx * 0.024, 0.008, -0.020))
    p1 = Vector((-sx * 0.035, 0.021, -0.040))
    tube(b, p0, p1, 0.0095, 0.0078, 6, "TanDeep")
    ball(b, p1, 0.0080, 6, 4, "TanDeep")
    OBJ[hand_name] = make_object(hand_name, b, collection)


def build_leg(side, sx, collection):
    thigh_name = PREFIX + "_Leg_%s_Thigh" % side
    shin_name = PREFIX + "_Leg_%s_Shin" % side
    foot_name = PREFIX + "_Leg_%s_Foot" % side

    b = MeshBuilder()
    ball(b, (0, 0, 0.004), 0.048, 10, 6, "Fur")
    tube(b, (0, 0, 0.008), (0, 0, -0.150), 0.047, 0.036, 10, "Fur")
    OBJ[thigh_name] = make_object(thigh_name, b, collection)

    b = MeshBuilder()
    ball(b, (0, 0, 0), 0.039, 10, 6, "Fur")
    tube(b, (0, 0, -0.004), (0, 0, -0.115), 0.035, 0.028, 10, "Fur")
    OBJ[shin_name] = make_object(shin_name, b, collection)

    b = MeshBuilder()
    ball(b, (0, 0, 0), 0.026, 10, 6, "TanDeep")
    # rounded, flat-soled foot
    sole_z = -0.040
    cy = 0.036
    rings = [
        (sole_z, 0.036, 0.064),
        (sole_z + 0.017, 0.042, 0.074),
        (sole_z + 0.038, 0.037, 0.060),
    ]
    ring_idx = []
    n = 12
    for z, rx, ry in rings:
        row = []
        for i in range(n):
            th = 2.0 * math.pi * i / n
            row.append(b.v((rx * math.cos(th), cy + ry * math.sin(th), z)))
        ring_idx.append(row)
    for j in range(len(ring_idx) - 1):
        for i in range(n):
            k = (i + 1) % n
            b.quad(ring_idx[j][i], ring_idx[j][k],
                   ring_idx[j + 1][k], ring_idx[j + 1][i], "TanDeep")
    # sole
    csole = b.v((0.0, cy, sole_z))
    for i in range(n):
        k = (i + 1) % n
        b.tri(csole, ring_idx[0][k], ring_idx[0][i], "TanDeep")
    # ankle cap
    ctop = b.v((0.0, cy - 0.006, sole_z + 0.042))
    for i in range(n):
        k = (i + 1) % n
        b.tri(ctop, ring_idx[-1][i], ring_idx[-1][k], "TanDeep")
    # toes
    for tx in (-0.024, 0.0, 0.024):
        ball(b, (tx, cy + 0.066, sole_z + 0.011),
             (0.0155, 0.0200, 0.0115), 8, 4, "TanDeep")
    OBJ[foot_name] = make_object(foot_name, b, collection)


def build_tail(collection):
    for i, nm in enumerate(TAIL_SEG_NAMES):
        a = TAIL_SPLIT[i]
        e = TAIL_SPLIT[i + 1]
        pts = TAIL_CURVE[a:e + 1]
        origin = pts[0]
        local_pts = [p - origin for p in pts]
        radii = TAIL_RADII[a:e + 1]
        b = MeshBuilder()
        ball(b, (0, 0, 0), max(0.0055, radii[0] * 1.05), 8, 5, "Fur")
        tube_path(b, local_pts, radii, 8, "Fur", cap0=False, cap1=(i == 3))
        if i == 3:
            tip = local_pts[-1] + (local_pts[-1] - local_pts[-2]).normalized() * 0.012
            tube(b, local_pts[-1], tip, radii[-1], 0.0015, 6, "FurDark")
        ob = make_object(nm, b, collection)
        OBJ[nm] = ob


# 肚皮椭圆：参考图（simple-lowpoly-monkey）里橘色肚皮几乎盖住整个肚子，
# 这里把方位角上限从 0.51 放到 0.78（≈45°），肚皮才够大。
BELLY_OUTLINE_HALF = [
    (0.000, 0.700), (0.290, 0.660), (0.545, 0.545), (0.730, 0.380),
    (0.800, 0.155), (0.795, -0.110), (0.700, -0.330), (0.540, -0.520),
    (0.320, -0.640), (0.000, -0.690),
]


def build_belly(collection):
    b = MeshBuilder()
    right = [dir_az_el(az, el) for (az, el) in BELLY_OUTLINE_HALF]
    left = [dir_az_el(-az, el) for (az, el) in reversed(BELLY_OUTLINE_HALF[1:-1])]
    shell_patch(b, torso_surface, right + left, 4, 0.0036, "Tan", TORSO_C)
    ob = make_object(PREFIX + "_Belly", b, collection, recalc=False)
    OBJ[PREFIX + "_Belly"] = ob
    return ob


def build_butt(collection):
    b = MeshBuilder()
    for sx in (-1.0, 1.0):
        dc = Vector((0.42 * sx, -0.76, -0.50)).normalized()
        basis = _basis_from_normal(dc)
        right = Vector(basis.col[0])
        outline = oval_outline(dc, right, dc.cross(right), 0.46, 0.42, 12)
        shell_patch(b, hips_surface, outline, 4, 0.0034, "TanDeep",
                    Vector((0.0, 0.0, 0.0)))
    ob = make_object(PREFIX + "_Butt", b, collection, recalc=False)
    OBJ[PREFIX + "_Butt"] = ob
    return ob


def build_character():
    # the head already exists (import_shared_head ran right after clear_scene)
    assert MH is not None, "import_shared_head() must run before build_character()"
    collection = bpy.context.scene.collection
    build_torso(collection)
    build_belly(collection)
    build_hips(collection)
    build_butt(collection)
    build_arm("R", 1.0, collection)
    build_arm("L", -1.0, collection)
    build_leg("R", 1.0, collection)
    build_leg("L", -1.0, collection)
    build_tail(collection)

    root = bpy.data.objects.new(PREFIX + "_Root", None)
    root.empty_display_type = "PLAIN_AXES"
    root.empty_display_size = 0.08
    bpy.context.scene.collection.objects.link(root)
    OBJ[PREFIX + "_Root"] = root

    # parent everything exactly as the spec says (head + ears included)
    for name, (parent, loc, rot) in RIG_SPEC.items():
        if parent is None:
            continue
        ob = OBJ[name]
        ob.parent = OBJ[parent]
        ob.location = loc
        ob.rotation_euler = Euler([math.radians(v) for v in rot], "XYZ")
        ob.scale = (1.0, 1.0, 1.0)

    # the rest of the shared head (tuft / eyes / pupils / brows / mouths ...)
    # keeps the transform import_shared_head() gave it
    for name in HEAD_STATIC_PARTS + HEAD_ANIM_PARTS:
        ob = OBJ[name]
        ob.parent = OBJ[PREFIX + "_Head"]
        ob.scale = (1.0, 1.0, 1.0)

    for name, parent in ((PREFIX + "_Belly", PREFIX + "_Torso"),
                         (PREFIX + "_Butt", PREFIX + "_Hips")):
        ob = OBJ[name]
        ob.parent = OBJ[parent]
        ob.location = (0.0, 0.0, 0.0)
        ob.rotation_euler = (0.0, 0.0, 0.0)
        ob.scale = (1.0, 1.0, 1.0)
    # preview only: no harsh self-shadows across the painted face
    for name in (PREFIX + "_Head", PREFIX + "_Eye_L", PREFIX + "_Eye_R"):
        if hasattr(OBJ[name], "visible_shadow"):
            OBJ[name].visible_shadow = False
    return root


# --------------------------------------------------------------------------
# pose helpers
# --------------------------------------------------------------------------
def new_pose():
    return {}


def add(p, name, rx=0.0, ry=0.0, rz=0.0, lx=0.0, ly=0.0, lz=0.0):
    v = p.setdefault(name, [0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
    v[0] += rx
    v[1] += ry
    v[2] += rz
    v[3] += lx
    v[4] += ly
    v[5] += lz


def merge_pose(a, b, w):
    """a + b * w (b is blended in)."""
    out = {k: list(v) for k, v in a.items()}
    for k, v in b.items():
        if k in out:
            for i in range(6):
                out[k][i] += v[i] * w
        else:
            out[k] = [x * w for x in v]
    return out


def blend_pose(a, b, w):
    w = clamp(w, 0.0, 1.0)
    out = {}
    for k in set(a) | set(b):
        va = a.get(k, [0.0] * 6)
        vb = b.get(k, [0.0] * 6)
        out[k] = [lerp(va[i], vb[i], w) for i in range(6)]
    return out


def pose_add(p, q, w=1.0):
    return merge_pose(p, q, w)


def base_stand():
    p = new_pose()
    # 20 deg outward: the torso's widest point (0.185 m) is at the elbow level,
    # so the arm has to swing out a bit to leave the body silhouette.  The
    # shoulder ball still touches the torso (that is the armpit), the tube
    # below it does not.
    add(p, PREFIX + "_Arm_R_Upper", rx=4, ry=-20)
    add(p, PREFIX + "_Arm_L_Upper", rx=4, ry=20)
    add(p, PREFIX + "_Arm_R_Fore", rx=9)
    add(p, PREFIX + "_Arm_L_Fore", rx=9)
    add(p, PREFIX + "_Leg_R_Thigh", ry=-2)
    add(p, PREFIX + "_Leg_L_Thigh", ry=2)
    add(p, PREFIX + "_Leg_R_Shin", rx=-3)
    add(p, PREFIX + "_Leg_L_Shin", rx=-3)
    add(p, PREFIX + "_Leg_R_Foot", rx=2)
    add(p, PREFIX + "_Leg_L_Foot", rx=2)
    return p


def crouch(p, k):
    """Bend the knees and lower the body while keeping the feet planted."""
    add(p, PREFIX + "_Hips", rx=-4 * k, lz=-0.010 * k)
    add(p, PREFIX + "_Torso", rx=-10 * k)
    add(p, PREFIX + "_Head", rx=7 * k)
    for side in ("R", "L"):
        add(p, PREFIX + "_Leg_%s_Thigh" % side, rx=34 * k)
        add(p, PREFIX + "_Leg_%s_Shin" % side, rx=-62 * k)
        add(p, PREFIX + "_Leg_%s_Foot" % side, rx=26 * k)
    return p


def sit_pose():
    """The reference's sitting pose (also used for the preview sheet)."""
    p = new_pose()
    add(p, PREFIX + "_Hips", lz=-0.205, rx=3)
    add(p, PREFIX + "_Torso", rx=-7)
    add(p, PREFIX + "_Head", rx=4)
    for side, sx in (("R", 1.0), ("L", -1.0)):
        add(p, PREFIX + "_Leg_%s_Thigh" % side, rx=92, rz=-30 * sx)
        add(p, PREFIX + "_Leg_%s_Shin" % side, rx=-72, rz=-16 * sx)
        add(p, PREFIX + "_Leg_%s_Foot" % side, rx=-18, rz=16 * sx)
        add(p, PREFIX + "_Arm_%s_Upper" % side, rx=7, ry=-22 * sx)
        add(p, PREFIX + "_Arm_%s_Fore" % side, rx=0)
        add(p, PREFIX + "_Arm_%s_Hand" % side, rx=50)
    add(p, PREFIX + "_Tail_1", rz=-8, rx=-6)
    add(p, PREFIX + "_Tail_2", rz=-6)
    add(p, PREFIX + "_Tail_3", rz=4)
    add(p, PREFIX + "_Head", rz=-3)
    return p


# --------------------------------------------------------------------------
# animation helpers
# --------------------------------------------------------------------------
TAU = 2.0 * math.pi


def arm(p, side, ux=0.0, uy=0.0, uz=0.0, fx=0.0, fy=0.0, fz=0.0,
        hx=0.0, hy=0.0, hz=0.0):
    """Pose an arm.  +ux = swing forward, +uy = swing inward, +fx = elbow flex."""
    sx = 1.0 if side == "R" else -1.0
    add(p, PREFIX + "_Arm_%s_Upper" % side, rx=ux, ry=uy * sx, rz=uz * sx)
    add(p, PREFIX + "_Arm_%s_Fore" % side, rx=fx, ry=fy * sx, rz=fz * sx)
    add(p, PREFIX + "_Arm_%s_Hand" % side, rx=hx, ry=hy * sx, rz=hz * sx)


def leg(p, side, tx=0.0, ty=0.0, tz=0.0, sx=0.0, sy=0.0, sz=0.0,
        fx=0.0, fy=0.0, fz=0.0):
    """Pose a leg.  +tx = thigh forward, -sx = knee bend, +fx = toes up."""
    sgn = 1.0 if side == "R" else -1.0
    add(p, PREFIX + "_Leg_%s_Thigh" % side, rx=tx, ry=ty * sgn, rz=tz * sgn)
    add(p, PREFIX + "_Leg_%s_Shin" % side, rx=sx, ry=sy * sgn, rz=sz * sgn)
    add(p, PREFIX + "_Leg_%s_Foot" % side, rx=fx, ry=fy * sgn, rz=fz * sgn)


def keyed(keys, t):
    """Interpolate a list of (time, pose) with smoothstep easing."""
    if t <= keys[0][0]:
        return {k: list(v) for k, v in keys[0][1].items()}
    if t >= keys[-1][0]:
        return {k: list(v) for k, v in keys[-1][1].items()}
    for i in range(len(keys) - 1):
        t0, p0 = keys[i]
        t1, p1 = keys[i + 1]
        if t0 <= t <= t1:
            u = smoothstep((t - t0) / max(1e-6, t1 - t0))
            return blend_pose(p0, p1, u)
    return {k: list(v) for k, v in keys[-1][1].items()}


def table_interp(table, x):
    if x <= table[0][0]:
        return table[0][1]
    if x >= table[-1][0]:
        return table[-1][1]
    for i in range(len(table) - 1):
        x0, y0 = table[i]
        x1, y1 = table[i + 1]
        if x0 <= x <= x1:
            u = smoothstep((x - x0) / max(1e-6, x1 - x0))
            return y0 + (y1 - y0) * u
    return table[-1][1]


def tail_wave(p, amp=10.0, phase=0.0, freq=1.0, t=0.0, lift=0.0):
    for i, nm in enumerate(TAIL_SEG_NAMES):
        ph = TAU * freq * t - 0.55 * i + phase
        add(p, nm, rz=amp * (1.0 + 0.18 * i) * math.sin(ph),
            rx=lift * (1.0 - 0.15 * i) + 2.5 * math.sin(ph * 1.7 - 0.8))


# --------------------------------------------------------------------------
# clips
# --------------------------------------------------------------------------
KNEE_RUN = [(0.00, 12), (0.10, 24), (0.28, 20), (0.48, 34),
            (0.60, 78), (0.74, 98), (0.88, 50), (1.00, 12)]
FOOT_RUN = [(0.00, 14), (0.10, -3), (0.30, 0), (0.48, -26),
            (0.62, 6), (0.80, 16), (1.00, 14)]


def clip_run(t):
    p = base_stand()
    for side, off in (("L", 0.0), ("R", 0.5)):
        q = (t + off) % 1.0
        th = 33.0 * math.cos(TAU * q)
        kn = table_interp(KNEE_RUN, q)
        ft = table_interp(FOOT_RUN, q)
        sway = 4.0 * math.sin(TAU * q)
        leg(p, side, tx=th, ty=-sway, sx=-kn, fx=ft)
    add(p, PREFIX + "_Hips", lz=0.010 + 0.010 * math.cos(2 * TAU * t),
        rz=4.0 * math.sin(TAU * t))
    add(p, PREFIX + "_Torso", rx=-10, rz=7.0 * math.sin(TAU * t),
        ry=2.0 * math.sin(2 * TAU * t))
    add(p, PREFIX + "_Head", rx=8, rz=-6.0 * math.sin(TAU * t),
        ry=-2.0 * math.sin(TAU * t))
    arm(p, "L", ux=-30.0 * math.cos(TAU * t), uy=-3,
        fx=30 + 14 * math.cos(TAU * t))
    arm(p, "R", ux=30.0 * math.cos(TAU * t), uy=-3,
        fx=30 - 14 * math.cos(TAU * t))
    add(p, PREFIX + "_Ear_R", ry=4.0 * math.sin(2 * TAU * t + 0.4))
    add(p, PREFIX + "_Ear_L", ry=-4.0 * math.sin(2 * TAU * t + 0.4))
    tail_wave(p, amp=11.0, t=t, freq=1.0, lift=-4.0)
    return p


def _startle_crouch(k, back=0.0, forward=0.0):
    p = base_stand()
    add(p, PREFIX + "_Hips", rx=-2.0 * k, lz=-0.004 * k)
    add(p, PREFIX + "_Torso", rx=-16.0 * k)
    add(p, PREFIX + "_Head", rx=10.0 * k)
    for side in ("R", "L"):
        leg(p, side, tx=46.0 * k, sx=-88.0 * k, fx=42.0 * k)
        arm(p, side, ux=(-38.0 * back) + (26.0 * forward),
            uy=-10.0 * k, fx=28.0 + 22.0 * k)
    return p


def clip_startle(t):
    stand = settle(base_stand())
    c1 = settle(_startle_crouch(0.30))
    c2 = settle(_startle_crouch(1.0, back=1.0))
    launch = base_stand()
    add(launch, PREFIX + "_Hips", lz=0.10, rx=2)
    add(launch, PREFIX + "_Torso", rx=2)
    add(launch, PREFIX + "_Head", rx=-4)
    for side in ("R", "L"):
        leg(launch, side, tx=-12, sx=0, fx=-12)
        arm(launch, side, ux=-125, uy=-18, fx=26)
    apex = base_stand()
    add(apex, PREFIX + "_Hips", lz=0.235, rx=6)
    add(apex, PREFIX + "_Torso", rx=-4)
    add(apex, PREFIX + "_Head", rx=-2, rz=5)
    for side in ("R", "L"):
        leg(apex, side, tx=52, sx=-88, fx=18)
        arm(apex, side, ux=-108, uy=-36, fx=40)
    fall = base_stand()
    add(fall, PREFIX + "_Hips", lz=0.105)
    add(fall, PREFIX + "_Torso", rx=-8)
    add(fall, PREFIX + "_Head", rx=6)
    for side in ("R", "L"):
        leg(fall, side, tx=18, sx=-24, fx=22)
        arm(fall, side, ux=34, uy=-6, fx=44)
    land = _startle_crouch(1.20, forward=1.0)
    add(land, PREFIX + "_Torso", rx=-8)
    add(land, PREFIX + "_Head", rx=8)
    for side in ("R", "L"):
        arm(land, side, ux=44, uy=-14, fx=54)
    land = settle(land)
    recover = settle(_startle_crouch(0.35))
    keys = [(0.00, stand), (0.08, c1), (0.20, c2), (0.30, launch),
            (0.44, apex), (0.58, fall), (0.70, land), (0.82, recover),
            (1.00, settle(base_stand()))]
    p = keyed(keys, t)
    tail_wave(p, amp=6.0, t=t, freq=1.0, lift=-12.0)
    add(p, PREFIX + "_Ear_R", rx=-6)
    add(p, PREFIX + "_Ear_L", rx=-6)
    return p


def clip_tremble(t):
    p = base_stand()
    crouch(p, 0.55)
    add(p, PREFIX + "_Torso", rx=-8)
    add(p, PREFIX + "_Head", rx=7)
    for side in ("R", "L"):
        arm(p, side, ux=52, uy=27, fx=96, hx=14)
        add(p, PREFIX + "_Ear_%s" % side, rx=-8)
    sh = math.sin(TAU * 8.0 * t)
    sh2 = math.sin(TAU * 8.0 * t + 1.2)
    add(p, PREFIX + "_Hips", lx=0.006 * sh, lz=0.0015 * math.sin(2 * TAU * 8 * t))
    add(p, PREFIX + "_Torso", rz=2.6 * sh, rx=1.3 * sh2)
    add(p, PREFIX + "_Head", rz=-4.0 * sh, rx=2.2 * sh2)
    for side in ("R", "L"):
        arm(p, side, ux=2.6 * sh, uy=1.8 * sh2, fx=4.0 * sh)
    tail_wave(p, amp=4.0, t=t, freq=8.0, lift=-10.0)
    add(p, PREFIX + "_Tail_1", rx=8)
    return p


def clip_throw_one(t):
    stand = base_stand()

    wind = base_stand()
    add(wind, PREFIX + "_Hips", rz=-12, rx=2)
    add(wind, PREFIX + "_Torso", rz=-24, rx=5)
    add(wind, PREFIX + "_Head", rz=18, rx=2)
    for side in ("R", "L"):
        leg(wind, side, tx=8, sx=-17, fx=9)
    arm(wind, "R", ux=-108, uy=-30, fx=76)
    arm(wind, "L", ux=38, uy=16, fx=52)

    release = base_stand()
    add(release, PREFIX + "_Hips", rz=10, rx=-2)
    add(release, PREFIX + "_Torso", rz=20, rx=-16)
    add(release, PREFIX + "_Head", rz=-12, rx=-6)
    for side in ("R", "L"):
        leg(release, side, tx=6, sx=-14, fx=8)
    arm(release, "R", ux=74, uy=4, fx=8)
    arm(release, "L", ux=-22, uy=-6, fx=58)

    follow = base_stand()
    add(follow, PREFIX + "_Hips", rz=14, rx=-2)
    add(follow, PREFIX + "_Torso", rz=28, rx=-20, ry=3)
    add(follow, PREFIX + "_Head", rz=-22, rx=-8)
    for side in ("R", "L"):
        leg(follow, side, tx=5, sx=-13, fx=8)
    arm(follow, "R", ux=56, uy=34, fx=24)
    arm(follow, "L", ux=-30, uy=-10, fx=48)

    settle = base_stand()
    add(settle, PREFIX + "_Torso", rz=8, rx=-4)
    add(settle, PREFIX + "_Head", rz=-6)
    arm(settle, "R", ux=16, uy=6, fx=24)
    keys = [(0.00, stand), (0.18, wind), (0.32, wind), (0.46, release),
            (0.58, follow), (0.74, settle), (1.00, stand)]
    p = keyed(keys, t)
    tail_wave(p, amp=9.0, t=t, freq=1.0, lift=-3.0)
    return p


def clip_throw_two(t):
    stand = base_stand()

    wind = base_stand()
    add(wind, PREFIX + "_Hips", rx=3, lz=-0.005)
    add(wind, PREFIX + "_Torso", rx=10)
    add(wind, PREFIX + "_Head", rx=-10)
    for side in ("R", "L"):
        leg(wind, side, tx=12, sx=-24, fx=12)
        arm(wind, side, ux=-145, uy=-32, fx=42)

    release = base_stand()
    add(release, PREFIX + "_Hips", rx=-2, lz=-0.004)
    add(release, PREFIX + "_Torso", rx=-22)
    add(release, PREFIX + "_Head", rx=-10)
    for side in ("R", "L"):
        leg(release, side, tx=10, sx=-20, fx=10)
        arm(release, side, ux=82, uy=4, fx=6)

    follow = base_stand()
    add(follow, PREFIX + "_Torso", rx=-26)
    add(follow, PREFIX + "_Head", rx=-8)
    for side in ("R", "L"):
        leg(follow, side, tx=8, sx=-16, fx=9)
        arm(follow, side, ux=52, uy=2, fx=22)

    settle = base_stand()
    add(settle, PREFIX + "_Torso", rx=-6)
    for side in ("R", "L"):
        arm(settle, side, ux=16, fx=24)
    keys = [(0.00, stand), (0.20, wind), (0.34, wind), (0.46, release),
            (0.58, follow), (0.74, settle), (1.00, stand)]
    p = keyed(keys, t)
    tail_wave(p, amp=8.0, t=t, freq=1.0, lift=-8.0)
    return p


def clip_clap(t):
    p = base_stand()
    add(p, PREFIX + "_Torso", rx=-3)
    add(p, PREFIX + "_Head", rx=2)
    phase = (t * 4.0) % 1.0
    # op = 1 -> hands apart, op = 0 -> palms together (clap at phase 0.5)
    op = 0.5 + 0.5 * math.cos(TAU * phase)
    close = 1.0 - op
    # Close with a *yaw* (rz) instead of a Y-axis inward swing: with the arms
    # swung forward, uy drags the elbow through the chest (36 overlapping
    # triangles); yawing keeps the elbows in front and still meets the palms.
    for side in ("R", "L"):
        arm(p, side, ux=40, uy=2, uz=20 * close, fx=36 + 2 * close,
            hx=16 + 2 * close)
    add(p, PREFIX + "_Head", rx=2.8 * close, rz=1.8 * math.sin(TAU * phase))
    add(p, PREFIX + "_Torso", rx=1.8 * close)
    add(p, PREFIX + "_Ear_R", ry=3.0 * close)
    add(p, PREFIX + "_Ear_L", ry=-3.0 * close)
    tail_wave(p, amp=10.0, t=t, freq=4.0, lift=-2.0)
    return p


def clip_snatch(t):
    stand = base_stand()

    reach = base_stand()
    add(reach, PREFIX + "_Hips", rx=-2, rz=-5)
    add(reach, PREFIX + "_Torso", rx=-18, rz=-8)
    add(reach, PREFIX + "_Head", rx=-8, rz=6)
    for side in ("R", "L"):
        leg(reach, side, tx=7, sx=-15, fx=8)
    arm(reach, "R", ux=88, uy=-4, fx=10, hx=-8)
    arm(reach, "L", ux=-24, uy=-10, fx=42)

    grab = base_stand()
    add(grab, PREFIX + "_Hips", rx=-2, rz=-6)
    add(grab, PREFIX + "_Torso", rx=-22, rz=-10)
    add(grab, PREFIX + "_Head", rx=-12, rz=8)
    for side in ("R", "L"):
        leg(grab, side, tx=9, sx=-18, fx=9)
    arm(grab, "R", ux=84, uy=2, fx=26, hx=10)
    arm(grab, "L", ux=-28, uy=-12, fx=46)

    pull = base_stand()
    add(pull, PREFIX + "_Hips", rx=1, rz=-10)
    add(pull, PREFIX + "_Torso", rx=-2, rz=-18, ry=-3)
    add(pull, PREFIX + "_Head", rx=4, rz=10)
    for side in ("R", "L"):
        leg(pull, side, tx=4, sx=-10, fx=6)
    arm(pull, "R", ux=40, uy=20, fx=108, hx=16)
    arm(pull, "L", ux=-18, uy=-8, fx=52)

    clutch = base_stand()
    add(clutch, PREFIX + "_Hips", rx=2, rz=-6, lz=-0.008)
    add(clutch, PREFIX + "_Torso", rx=-8, rz=-14)
    add(clutch, PREFIX + "_Head", rx=6, rz=8)
    for side in ("R", "L"):
        leg(clutch, side, tx=14, sx=-28, fx=14)
    arm(clutch, "R", ux=34, uy=26, fx=112, hx=18)
    arm(clutch, "L", ux=10, uy=6, fx=60)

    keys = [(0.00, stand), (0.16, reach), (0.30, grab), (0.46, pull),
            (0.62, clutch), (0.82, clutch), (1.00, stand)]
    p = keyed(keys, t)
    tail_wave(p, amp=10.0, t=t, freq=1.0, lift=-4.0)
    return p


def clip_sit_idle(t):
    p = sit_pose()
    breath = math.sin(TAU * t)
    add(p, PREFIX + "_Torso", rx=1.4 * breath, ry=0.8 * math.sin(TAU * t + 0.8))
    add(p, PREFIX + "_Head", rx=-1.2 * breath + 0.8 * math.sin(TAU * t + 1.8),
        rz=3.0 * math.sin(TAU * t + 2.2))
    add(p, PREFIX + "_Ear_R", ry=4.0 * max(0.0, math.sin(TAU * 2 * t - 0.4)))
    add(p, PREFIX + "_Ear_L", ry=-4.0 * max(0.0, math.sin(TAU * 2 * t - 0.4)))
    for side, sgn in (("R", 1.0), ("L", -1.0)):
        arm(p, side, ux=1.2 * breath, uy=-1.0 * breath, fx=1.5 * breath)
    tail_wave(p, amp=6.0, t=t, freq=1.0, lift=1.5 * breath)
    # tiny idle weight shift keeps it from looking frozen
    add(p, PREFIX + "_Hips", lx=0.002 * math.sin(TAU * t + 0.3))
    return p


CLIPS = [
    (PREFIX + "_Run", clip_run, 24, 1),
    (PREFIX + "_Startle", clip_startle, 30, 1),
    (PREFIX + "_Tremble", clip_tremble, 48, 1),
    (PREFIX + "_ThrowOne", clip_throw_one, 30, 1),
    (PREFIX + "_ThrowTwo", clip_throw_two, 30, 1),
    (PREFIX + "_Clap", clip_clap, 42, 1),
    (PREFIX + "_Snatch", clip_snatch, 30, 1),
    (PREFIX + "_SitIdle", clip_sit_idle, 60, 1),
]


# --------------------------------------------------------------------------
# facial expressions (shared head -> body clips)
# --------------------------------------------------------------------------
# The shared head ships three mouths (smile / open laugh / fear O) plus two
# squint arcs that live *inside* the skull by default.  The standalone head
# asset exports that as two extra clips; on the body we adapt the same parts to
# the clips that have a matching beat instead of adding standalone animations:
#
#   Run                 neutral
#   Startle             fear   (pops on the crouch, back to neutral on landing)
#   Tremble             fear   (the whole clip)
#   ThrowOne / ThrowTwo shout  (open mouth through the release)
#   Clap                laugh  (laughing at its own clapping)
#   Snatch              fear -> shout (surprise at the grab, effort on the pull)
#   SitIdle             neutral
#
# The swap is **discrete**: a mouth is either on the face or parked inside the
# skull.  A half-faded swap leaves two mouths on screen at once, which is the
# bug the head asset documents (§2.6).
NEUTRAL, LAUGH, FEAR, SHOUT = "neutral", "laugh", "fear", "shout"

EXPRESSION = {
    PREFIX + "_Run": [(0.00, NEUTRAL)],
    PREFIX + "_Startle": [(0.00, NEUTRAL), (0.07, FEAR), (0.80, FEAR),
                          (0.86, NEUTRAL)],
    PREFIX + "_Tremble": [(0.00, NEUTRAL), (0.04, FEAR), (0.94, FEAR),
                          (1.00, NEUTRAL)],
    PREFIX + "_ThrowOne": [(0.00, NEUTRAL), (0.20, SHOUT), (0.56, SHOUT),
                           (0.72, NEUTRAL)],
    PREFIX + "_ThrowTwo": [(0.00, NEUTRAL), (0.20, SHOUT), (0.56, SHOUT),
                           (0.72, NEUTRAL)],
    PREFIX + "_Clap": [(0.00, NEUTRAL), (0.08, LAUGH), (0.86, NEUTRAL)],
    PREFIX + "_Snatch": [(0.00, NEUTRAL), (0.14, FEAR), (0.34, FEAR),
                         (0.42, SHOUT), (0.82, SHOUT), (0.92, NEUTRAL)],
    PREFIX + "_SitIdle": [(0.00, NEUTRAL)],
}

FACE_HIDE = Vector((0.0, -0.060 * HEAD_SCALE, 0.0))   # park inside the skull
FACE_SHOW = -FACE_HIDE


def _expr_states():
    """{state: (joint deltas in degrees, face-part deltas in metres/radians)}"""
    n, S = PREFIX, HEAD_SCALE
    states = {NEUTRAL: ({}, {})}

    states[LAUGH] = (
        {n + "_Ear_L": (0.0, 9.2, 0.0), n + "_Ear_R": (0.0, -9.2, 0.0)},
        {n + "_MouthSmile": {"loc": FACE_HIDE},
         n + "_MouthLaugh": {"loc": FACE_SHOW},
         n + "_Eye_L": {"loc": FACE_HIDE}, n + "_Eye_R": {"loc": FACE_HIDE},
         n + "_Pupil_L": {"loc": FACE_HIDE}, n + "_Pupil_R": {"loc": FACE_HIDE},
         n + "_EyeShut_L": {"loc": FACE_SHOW},
         n + "_EyeShut_R": {"loc": FACE_SHOW},
         n + "_Brow_L": {"loc": (0.0, 0.0, 0.011 * S), "rot": (0.0, 0.14, 0.0)},
         n + "_Brow_R": {"loc": (0.0, 0.0, 0.011 * S), "rot": (0.0, -0.14, 0.0)}})

    states[FEAR] = (
        {n + "_Ear_L": (0.0, -19.5, 14.3), n + "_Ear_R": (0.0, 19.5, -14.3)},
        {n + "_MouthSmile": {"loc": FACE_HIDE},
         n + "_MouthFear": {"loc": FACE_SHOW},
         n + "_Brow_L": {"loc": (0.0, 0.0, 0.019 * S), "rot": (0.0, 0.42, 0.0)},
         n + "_Brow_R": {"loc": (0.0, 0.0, 0.019 * S), "rot": (0.0, -0.42, 0.0)},
         n + "_Pupil_L": {"loc": (0.004 * S, 0.0, 0.002 * S)},
         n + "_Pupil_R": {"loc": (-0.004 * S, 0.0, 0.002 * S)}})

    # effort: open mouth, eyes stay open (the Laugh state swaps in squint arcs)
    states[SHOUT] = (
        {n + "_Ear_L": (0.0, 5.0, 0.0), n + "_Ear_R": (0.0, -5.0, 0.0)},
        {n + "_MouthSmile": {"loc": FACE_HIDE},
         n + "_MouthLaugh": {"loc": FACE_SHOW},
         n + "_Brow_L": {"loc": (0.0, 0.0, 0.006 * S), "rot": (0.0, 0.08, 0.0)},
         n + "_Brow_R": {"loc": (0.0, 0.0, 0.006 * S), "rot": (0.0, -0.08, 0.0)}})
    return states


EXPR_STATES = _expr_states()


def expression_at(clip_name, t):
    """Discrete face state at normalised time ``t`` of ``clip_name``."""
    state = NEUTRAL
    for when, who in EXPRESSION.get(clip_name, ()):
        if t + 1e-9 >= when:
            state = who
    return EXPR_STATES[state]


def expression_pose(joints):
    """Joint (ear) deltas -> a pose dict the body baker can merge."""
    p = new_pose()
    for nm, (rx, ry, rz) in joints.items():
        add(p, nm, rx=rx, ry=ry, rz=rz)
    return p


# --------------------------------------------------------------------------
# forward kinematics + ground handling
# --------------------------------------------------------------------------
def fk_matrices(pose):
    world = {}
    for name in RIG_SPEC:
        parent, loc, rot = RIG_SPEC[name]
        anim = pose.get(name, [0.0] * 6)
        local = Matrix.Translation(Vector(loc) + Vector(anim[3:6]))
        e = Euler([math.radians(rot[i]) + math.radians(anim[i])
                   for i in range(3)], "XYZ")
        m = local @ e.to_matrix().to_4x4()
        if parent is None:
            world[name] = m
        else:
            world[name] = world[parent] @ m
    return world


def mesh_world_min_z(name, world):
    ob = OBJ[name]
    m = world[name]
    zs = [(m @ v.co).z for v in ob.data.vertices]
    return min(zs) if zs else 1e9


def foot_min_z(pose, side=None):
    world = fk_matrices(pose)
    sides = (side,) if side else ("R", "L")
    return min(mesh_world_min_z(PREFIX + "_Leg_%s_Foot" % s, world) for s in sides)


def fix_ground(pose, target=0.0015):
    """Raise the hips when a foot would sink through the floor (jumps)."""
    z = foot_min_z(pose)
    if z < target:
        add(pose, PREFIX + "_Hips", lz=(target - z))
    return pose


def settle(pose, target=0.0015):
    """Put the lowest foot exactly on the floor (raise *or* lower)."""
    z = foot_min_z(pose)
    add(pose, PREFIX + "_Hips", lz=(target - z))
    return pose


def ground_pose(clip_name, t, fn):
    """Per-clip ground policy: jumps/run may leave the floor, the rest plant."""
    p = fn(t)
    if clip_name in (PREFIX + "_Run", PREFIX + "_Startle"):
        return fix_ground(p)
    return settle(p)


def apply_pose(pose):
    for name in RIG_SPEC:
        ob = OBJ[name]
        if name == PREFIX + "_Root":
            continue
        parent, loc, rot = RIG_SPEC[name]
        anim = pose.get(name, [0.0] * 6)
        ob.location = Vector(loc) + Vector(anim[3:6])
        ob.rotation_euler = Euler(
            [math.radians(rot[i]) + math.radians(anim[i]) for i in range(3)],
            "XYZ")


def reset_pose():
    apply_pose({})


def apply_face(face):
    """Put the shared head's expression parts in a state (for previews)."""
    for nm in HEAD_ANIM_PARTS:
        ob = OBJ[nm]
        d = face.get(nm, {})
        ob.location = HEAD_REST_LOC[nm] + Vector(d.get("loc", (0.0, 0.0, 0.0)))
        ob.rotation_euler = (HEAD_REST_ROT[nm]
                             + Vector(d.get("rot", (0.0, 0.0, 0.0))))


def reset_face():
    apply_face({})


# --------------------------------------------------------------------------
# animation authoring / export
# --------------------------------------------------------------------------
def build_animations():
    scene = bpy.context.scene
    scene.render.fps = FPS
    for act in list(bpy.data.actions):
        bpy.data.actions.remove(act)

    for clip_name, fn, frames, step in CLIPS:
        # evaluate every frame's pose once (including the ground fix and the
        # facial expression that belongs to this clip)
        poses = []
        for f in range(0, frames + 1, step):
            t = f / float(frames)
            pose = ground_pose(clip_name, t, fn)
            joints, face = expression_at(clip_name, t)
            if joints:
                pose = merge_pose(pose, expression_pose(joints), 1.0)
            poses.append((f, pose, face))

        act = bpy.data.actions.new(clip_name)
        act.use_fake_user = True
        layer = act.layers.new("Layer")
        strip = layer.strips.new(type="KEYFRAME")
        slots = {}
        for nm in ANIMATED:
            slot = act.slots.new(id_type="OBJECT", name=nm)
            slots[nm] = slot
            cb = strip.channelbag(slot, ensure=True)
            fcu_rot = [cb.fcurves.new("rotation_euler", index=i) for i in range(3)]
            fcu_loc = [cb.fcurves.new("location", index=i) for i in range(3)]
            parent, loc, rest_rot = RIG_SPEC[nm]
            for f, pose, _face in poses:
                anim = pose.get(nm, [0.0] * 6)
                for i in range(3):
                    fcu_rot[i].keyframe_points.insert(
                        float(f), math.radians(rest_rot[i]) + math.radians(anim[i]))
                    fcu_loc[i].keyframe_points.insert(
                        float(f), loc[i] + anim[3 + i])
            for fcu in fcu_rot + fcu_loc:
                for kp in fcu.keyframe_points:
                    kp.interpolation = "LINEAR"

        # face parts are keyed per frame too; the swap states change in one
        # frame, and a one-frame LINEAR slide reads as a pop (no double mouth)
        for nm in HEAD_ANIM_PARTS:
            slot = act.slots.new(id_type="OBJECT", name=nm)
            slots[nm] = slot
            cb = strip.channelbag(slot, ensure=True)
            fcu_rot = [cb.fcurves.new("rotation_euler", index=i) for i in range(3)]
            fcu_loc = [cb.fcurves.new("location", index=i) for i in range(3)]
            rest_l = HEAD_REST_LOC[nm]
            rest_r = HEAD_REST_ROT[nm]
            for f, _pose, face in poses:
                d = face.get(nm, {})
                dl = d.get("loc", (0.0, 0.0, 0.0))
                dr = d.get("rot", (0.0, 0.0, 0.0))
                for i in range(3):
                    fcu_rot[i].keyframe_points.insert(float(f), rest_r[i] + dr[i])
                    fcu_loc[i].keyframe_points.insert(float(f), rest_l[i] + dl[i])
            for fcu in fcu_rot + fcu_loc:
                for kp in fcu.keyframe_points:
                    kp.interpolation = "LINEAR"

        for nm in ANIMATED + HEAD_ANIM_PARTS:
            ob = OBJ[nm]
            if ob.animation_data is None:
                ob.animation_data_create()
            tr = ob.animation_data.nla_tracks.new()
            tr.name = clip_name
            st = tr.strips.new(clip_name, 0, act)
            st.action_slot = slots[nm]
            st.mute = False
            tr.mute = True

    scene.frame_start = 0
    scene.frame_end = max(frames for _n, _f, frames, _s in CLIPS)


def export_glb():
    bpy.ops.object.select_all(action="DESELECT")
    for ob in OBJ.values():
        ob.select_set(True)
    bpy.context.view_layer.objects.active = OBJ[PREFIX + "_Root"]
    bpy.ops.export_scene.gltf(
        filepath=GLB_PATH,
        export_format="GLB",
        use_selection=True,
        export_apply=False,
        export_yup=True,
        export_animations=True,
        export_animation_mode="ACTIONS",
        export_merge_animation="NLA_TRACK",
        export_frame_range=True,
        export_force_sampling=True,
        export_optimize_animation_size=False,
        export_cameras=False,
        export_lights=False,
        export_materials="EXPORT",
        export_normals=True,
    )
    print("WROTE", GLB_PATH)


def audit_animations():
    print("=" * 68)
    print("DS-LOWPOLY-MONKEY  animation audit")
    for clip_name, fn, frames, _step in CLIPS:
        worst_foot = 1e9
        worst_any = 1e9
        for f in range(0, frames + 1):
            pose = ground_pose(clip_name, f / float(frames), fn)
            world = fk_matrices(pose)
            worst_foot = min(worst_foot, mesh_world_min_z(
                PREFIX + "_Leg_R_Foot", world),
                mesh_world_min_z(PREFIX + "_Leg_L_Foot", world))
            for nm in (PREFIX + "_Leg_R_Foot", PREFIX + "_Leg_L_Foot",
                       PREFIX + "_Arm_R_Hand", PREFIX + "_Arm_L_Hand",
                       PREFIX + "_Tail_4", PREFIX + "_Hips"):
                worst_any = min(worst_any, mesh_world_min_z(nm, world))
        print("%-22s %2d frames  foot min z %+.4f  body min z %+.4f  %s" % (
            clip_name, frames, worst_foot, worst_any,
            "OK" if worst_any > -0.012 else "CLIPS GROUND"))

    # clap hand spacing (distance between hand surfaces)
    clap_fn = dict((n, f) for n, f, _fr, _st in CLIPS)[PREFIX + "_Clap"]
    dmin, dmax = 1e9, -1e9
    for f in range(0, 42):
        pose = fix_ground(clap_fn(f / 42.0))
        world = fk_matrices(pose)
        pts = []
        for side in ("R", "L"):
            ob = OBJ[PREFIX + "_Arm_%s_Hand" % side]
            m = world[PREFIX + "_Arm_%s_Hand" % side]
            pts.append([m @ v.co for v in ob.data.vertices])
        best = min((a - b).length for a in pts[0] for b in pts[1])
        dmin = min(dmin, best)
        dmax = max(dmax, best)
    print("CLAP hand surface distance: min %.4f m  max %.4f m" % (dmin, dmax))
    print("=" * 68)


# --------------------------------------------------------------------------
# scene / preview
# --------------------------------------------------------------------------
def clear_scene():
    bpy.ops.wm.read_homefile(use_empty=True, use_factory_startup=True)
    for coll in (bpy.data.actions, bpy.data.meshes, bpy.data.materials,
                 bpy.data.objects, bpy.data.images, bpy.data.worlds,
                 bpy.data.cameras, bpy.data.lights):
        for item in list(coll):
            try:
                coll.remove(item)
            except Exception:
                pass
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0
    scene.render.fps = FPS
    scene.frame_start = 1
    scene.frame_end = 60


def pick_engine():
    engines = [e.identifier for e in
               bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items]
    for eng in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        if eng in engines:
            return eng
    return "CYCLES"


def setup_render(w, h):
    scene = bpy.context.scene
    scene.render.resolution_x = w
    scene.render.resolution_y = h
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = "PNG"
    try:
        scene.view_settings.view_transform = "Standard"
    except Exception:
        pass
    scene.view_settings.look = "None"
    scene.render.engine = pick_engine()
    if hasattr(scene, "eevee"):
        for attr, val in (("taa_render_samples", 64),
                          ("use_gtao", False),
                          ("use_raytracing", False)):
            if hasattr(scene.eevee, attr):
                try:
                    setattr(scene.eevee, attr, val)
                except Exception:
                    pass


def make_world_and_lights():
    scene = bpy.context.scene
    world = bpy.data.worlds.new("DSMonkey_World")
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.93, 0.90, 0.86, 1.0)
        bg.inputs[1].default_value = 0.78

    sun_data = bpy.data.lights.new("DSMonkey_Sun", type="SUN")
    sun_data.energy = 3.0
    sun_data.angle = math.radians(38.0)
    sun_data.color = (1.0, 0.95, 0.88)
    sun = bpy.data.objects.new("DSMonkey_Sun", sun_data)
    scene.collection.objects.link(sun)
    sun.location = (-1.0, 4.4, 5.4)
    sun.rotation_euler = (Vector((0.0, 0.0, 0.45)) - sun.location).to_track_quat("-Z", "Y").to_euler()

    fill_data = bpy.data.lights.new("DSMonkey_Fill", type="AREA")
    fill_data.energy = 190.0
    fill_data.size = 4.0
    fill_data.color = (0.85, 0.90, 1.0)
    fill = bpy.data.objects.new("DSMonkey_Fill", fill_data)
    scene.collection.objects.link(fill)
    fill.location = (3.6, 1.8, 2.4)
    fill.rotation_euler = (Vector((0.0, 0.0, 0.4)) - fill.location).to_track_quat("-Z", "Y").to_euler()

    # floor
    bpy.ops.mesh.primitive_plane_add(size=12.0, location=(0, 0, -0.002))
    floor = bpy.context.active_object
    floor.name = "PreviewFloor"
    m = bpy.data.materials.new("PreviewFloor")
    m.use_nodes = True
    bsdf = None
    for n in m.node_tree.nodes:
        if n.type == "BSDF_PRINCIPLED":
            bsdf = n
            break
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (0.80, 0.77, 0.72, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.92
    floor.data.materials.append(m)
    return sun, fill, floor


def make_camera():
    cam_data = bpy.data.cameras.new("PreviewCam")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = 1.02
    cam = bpy.data.objects.new("PreviewCam", cam_data)
    bpy.context.scene.collection.objects.link(cam)
    bpy.context.scene.camera = cam
    return cam


def place_camera(cam, position, target, ortho=1.02):
    cam.location = Vector(position)
    direction = Vector(target) - Vector(position)
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    cam.data.ortho_scale = ortho


def render_to(path):
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


def tile_images(paths, cols, rows, out_path):
    """Tile PNGs with ffmpeg; preserves exact rendered pixels."""
    n = len(paths)
    if n == 1:
        subprocess.check_call(["cp", paths[0], out_path])
        return
    if n == 4 and cols == 2 and rows == 2:
        cmd = ["ffmpeg", "-y", "-loglevel", "error",
               "-i", paths[0], "-i", paths[1], "-i", paths[2], "-i", paths[3],
               "-filter_complex",
               "[0][1]hstack=inputs=2[top];[2][3]hstack=inputs=2[bot];"
               "[top][bot]vstack=inputs=2[out]",
               "-map", "[out]", out_path]
        subprocess.check_call(cmd)
        return
    # generic: use an ffmpeg tile from a numbered sequence
    tmpdir = tempfile.mkdtemp(prefix="dstitch_")
    for i, p in enumerate(paths):
        subprocess.check_call(["cp", p, os.path.join(tmpdir, "f_%03d.png" % i)])
    subprocess.check_call([
        "ffmpeg", "-y", "-loglevel", "error", "-framerate", "1",
        "-i", os.path.join(tmpdir, "f_%03d.png"),
        "-vf", "tile=%dx%d:padding=4:margin=4:color=white" % (cols, rows),
        "-frames:v", "1", out_path])
    for f in os.listdir(tmpdir):
        os.remove(os.path.join(tmpdir, f))
    os.rmdir(tmpdir)


def render_preview_sheet(cam):
    """2x2 sheet: front / side / three-quarter / back, sitting like the ref."""
    apply_pose(fix_ground(sit_pose()))
    bpy.context.view_layer.update()
    tmpdir = tempfile.mkdtemp(prefix="dsprev_")
    target = Vector((0.0, 0.0, 0.36))
    views = [
        ("front", (0.0, 4.5, 0.36)),
        ("side", (-4.5, 0.0, 0.36)),
        ("three", (3.05, 3.30, 0.44)),
        ("back", (0.0, -4.5, 0.36)),
    ]
    paths = []
    for name, pos in views:
        place_camera(cam, pos, target, ortho=1.00)
        path = os.path.join(tmpdir, name + ".png")
        render_to(path)
        paths.append(path)
    tile_images(paths, 2, 2, PREVIEW_PATH)
    print("WROTE", PREVIEW_PATH)
    for p in paths:
        os.remove(p)
    os.rmdir(tmpdir)


def label_anim_sheet():
    """Add a clip-name header strip to the contact sheet (ffmpeg)."""
    labels = ["Run", "Startle", "Tremble", "ThrowOne",
              "ThrowTwo", "Clap", "Snatch", "SitIdle"]
    font = "/System/Library/Fonts/Helvetica.ttc"
    if os.path.exists(font):
        font_arg = "fontfile=" + font
    else:
        font_arg = "font=Sans"
    filters = ["pad=iw:ih+36:0:36:color=0xF0ECE6"]
    for i, label in enumerate(labels):
        filters.append(
            "drawtext=%s:text='%s':x=%d:y=9:fontsize=20:fontcolor=0x3A2418" %
            (font_arg, label, 12 + i * 324))
    tmp = ANIM_PATH + ".tmp.png"
    subprocess.check_call(["ffmpeg", "-y", "-loglevel", "error",
                           "-i", ANIM_PATH, "-vf", ",".join(filters), tmp])
    os.replace(tmp, ANIM_PATH)


def render_anim_sheet(cam):
    """3 sample frames for each clip, tiled 8 x 3."""
    tmpdir = tempfile.mkdtemp(prefix="dsanim_")
    target = Vector((0.0, 0.0, 0.50))
    place_camera(cam, (3.55, 3.85, 0.70), Vector((0.0, 0.0, 0.60)), ortho=1.35)
    setup_render(320, 320)
    samples = {
        PREFIX + "_Run": (0.00, 0.25, 0.50),
        PREFIX + "_Startle": (0.20, 0.44, 0.70),
        PREFIX + "_Tremble": (0.08, 0.21, 0.34),
        PREFIX + "_ThrowOne": (0.18, 0.46, 0.58),
        PREFIX + "_ThrowTwo": (0.20, 0.46, 0.58),
        PREFIX + "_Clap": (0.00, 0.125, 0.25),
        PREFIX + "_Snatch": (0.16, 0.46, 0.62),
        PREFIX + "_SitIdle": (0.10, 0.45, 0.80),
    }
    paths = []
    idx = 0
    # row-major: row 0 = first sample of every clip, row 1 = second, ...
    for row in range(3):
        for clip_name, fn, frames, _step in CLIPS:
            t = samples[clip_name][row]
            pose = ground_pose(clip_name, t, fn)
            joints, face = expression_at(clip_name, t)
            if joints:
                pose = merge_pose(pose, expression_pose(joints), 1.0)
            apply_pose(pose)
            apply_face(face)
            bpy.context.view_layer.update()
            path = os.path.join(tmpdir, "a_%02d.png" % idx)
            render_to(path)
            paths.append(path)
            idx += 1
    tile_images(paths, 8, 3, ANIM_PATH)
    label_anim_sheet()
    print("WROTE", ANIM_PATH)
    reset_pose()
    reset_face()
    for p in paths:
        os.remove(p)
    os.rmdir(tmpdir)


# --------------------------------------------------------------------------
# audit
# --------------------------------------------------------------------------
def _pose_bvh(name, world):
    bm = bmesh.new()
    bm.from_mesh(OBJ[name].data)
    bm.transform(world[name])
    tree = BVHTree.FromBMesh(bm)
    bm.free()
    return tree


def audit_arm_clearance(pose):
    """Count arm/torso triangle pairs that interpenetrate.

    The shoulder ball is *meant* to be half buried in the torso, so the upper
    arm is allowed a few overlapping triangles right at the pivot.  Anything
    below the shoulder (forearm, hand) must be zero - that is what "the arms
    are glued to the body" looks like.  Also reported for the resting stand,
    which is what the preview sheet and most clips start from.
    """
    world = fk_matrices(pose)
    torso = _pose_bvh(PREFIX + "_Torso", world)
    report = []
    for side in ("R", "L"):
        for part in ("Upper", "Fore", "Hand"):
            nm = PREFIX + "_Arm_%s_%s" % (side, part)
            pairs = torso.overlap(_pose_bvh(nm, world))
            report.append((nm, len(pairs)))
    worst = max(count for nm, count in report if not nm.endswith("_Upper"))
    print("ARM clearance (rest pose): " +
          "  ".join("%s %d" % (nm.split("_")[-2], c) for nm, c in report))
    return worst


def audit_static():
    print("=" * 68)
    print("DS-LOWPOLY-MONKEY  static audit")
    all_v = []
    for name, ob in OBJ.items():
        if ob.type != "MESH":
            continue
        for v in ob.data.vertices:
            all_v.append(ob.matrix_world @ v.co)
    xs = [p.x for p in all_v]
    ys = [p.y for p in all_v]
    zs = [p.z for p in all_v]
    print("bbox X %.3f..%.3f  Y %.3f..%.3f  Z %.3f..%.3f" %
          (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)))
    print("HEIGHT %.3f m  SPAN %.3f x %.3f m" %
          (max(zs) - min(zs), max(xs) - min(xs), max(ys) - min(ys)))
    head = OBJ[PREFIX + "_Head"]
    hx = [(head.matrix_world @ v.co).x for v in head.data.vertices]
    ear = OBJ[PREFIX + "_Ear_R"]
    ex = [(ear.matrix_world @ v.co).x for v in ear.data.vertices]
    print("HEAD  skull width %.3f m   with ears %.3f m" %
          (max(hx) - min(hx), 2.0 * max(ex)))
    tris = 0
    for ob in OBJ.values():
        if ob.type == "MESH":
            ob.data.calc_loop_triangles()
            tris += len(ob.data.loop_triangles)
    print("VERTS %d  TRIS %d  OBJECTS %d" % (
        sum(len(ob.data.vertices) for ob in OBJ.values() if ob.type == "MESH"),
        tris, len(OBJ)))
    bad = [(n, tuple(o.scale)) for n, o in OBJ.items()
           if any(abs(s - 1.0) > 1e-6 for s in o.scale)]
    print("SCALE audit:", "OK" if not bad else bad)
    assert abs(min(zs)) < 0.02, "feet must touch z=0"


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def main():
    clear_scene()
    # the shared head has to be imported *after* the scene wipe (it builds its
    # meshes into the current scene on import)
    import_shared_head()
    build_materials()
    build_character()
    reset_pose()
    bpy.context.view_layer.update()
    audit_static()
    audit_arm_clearance(base_stand())

    sp = settle(sit_pose())
    apply_pose(sp)
    bpy.context.view_layer.update()
    all_sit = []
    for name, ob in OBJ.items():
        if ob.type != "MESH":
            continue
        for v in ob.data.vertices:
            all_sit.append((ob.matrix_world @ v.co).z)
    print("SIT audit: feet min z %.4f  hands min z %.4f  whole min z %.4f  top %.3f" % (
        foot_min_z(sp),
        min(mesh_world_min_z(PREFIX + "_Arm_%s_Hand" % s, fk_matrices(sp)) for s in ("R", "L")),
        min(all_sit), max(all_sit)))
    reset_pose()
    bpy.context.view_layer.update()

    if "--static" not in sys.argv:
        build_animations()
        reset_pose()
        bpy.context.view_layer.update()
        audit_animations()

    cam = make_camera()
    make_world_and_lights()
    setup_render(560, 640)
    bpy.context.scene.frame_set(1)
    bpy.context.view_layer.update()
    bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH)
    print("WROTE", BLEND_PATH)

    if "--static" not in sys.argv:
        export_glb()

    if "--no-preview" not in sys.argv:
        render_preview_sheet(cam)
        if "--static" not in sys.argv:
            render_anim_sheet(cam)
    print("DONE")


if __name__ == "__main__":
    main()

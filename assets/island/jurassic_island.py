"""Build the low-poly Jurassic island terrain in Blender from baked shape data.

Usage:
    /Applications/Blender.app/Contents/MacOS/Blender --background \
        --python assets/island/jurassic_island.py

Inputs
    assets/island/jurassic_island_shapes.py
        plan-space masks extracted from _docs/ref_jurassic_island_base.png
        (`landmarks`/`analysis` scripts under .mcp/analysis show how they were
        recovered: the reference is a standard 2:1 isometric render).
        `LANDMARKS` heights are in plan-pixel units, converted with the same
        SCALE used horizontally.

Outputs
    assets/island/jurassic_island.blend
    assets/island/jurassic_island.glb
    assets/island/jurassic_island_preview.png      (reference-like 3/4 view)
    assets/island/jurassic_island_top.png          (plan view)

Tuning is done through the CONFIG block: geometry knobs are grouped by what
they control (shape, relief, coastline, materials, render).
"""

import base64
import importlib.util
import math
import os
import sys
import zlib

import bmesh
import bpy
import numpy as np
from mathutils import Vector

# ==========================================================================
# CONFIG
# ==========================================================================
ASSET_DIR = "/Users/zhouyunge/Documents/godot/open-jurassic-island/assets/island"
SHAPES_PATH = os.path.join(ASSET_DIR, "jurassic_island_shapes.py")

# --- scale -----------------------------------------------------------------
SCALE = 0.30            # metres per plan pixel -> island is ~226 x 304 m
SEA_LEVEL = 0.0

# --- mesh ------------------------------------------------------------------
GRID = 148              # height-field samples per side (~1.5 m cells)
DECIMATE_RATIO = 0.38   # collapse ratio; low-poly faceting comes from here
MASK_BLUR = 5           # plan-px box blur applied to the baked masks
COAST_SMOOTH = 1        # passes of 3x3 smoothing on the height field

# --- relief (metres) -------------------------------------------------------
SHELF_H = 4.5           # rise from the water line to the coastal shelf
SHELF_IN, SHELF_OUT = 2.0, 26.0
BODY_H = 12.0           # broad interior elevation
BODY_IN, BODY_OUT = 14.0, 110.0
RIDGE_GAIN = 1.32       # multiplier on RIDGES heights
MACRO_AMP, MACRO_SCALE = 7.0, 62.0    # broad undulation, amps in metres
MICRO_AMP, MICRO_SCALE = 3.6, 21.0    # small lumps that read as low-poly hills
SEED = 20240611

FLAT_DRY = 0.45         # how strongly the eastern plateau is flattened
DRY_H = 9.5
BEACH_PULL = 0.60       # how strongly the sand band is pulled to BEACH_H
BEACH_H = 2.4
LAGOON_H = -4.2         # lagoon basin floor, below the water line
LAGOON_GROW = 5         # plan-px dilation of the lagoon mask

# --- coast -----------------------------------------------------------------
CLIFF_OUT = 11.0        # plan px over which the coast drops to SEA_FLOOR
SEA_FLOOR = -13.0
CLIP_Z = -10.0          # faces below this are removed (they are under water)

# --- ridge skeleton: (x1, y1, h1, x2, y2, h2, width_px) ---------------------
RIDGES = [
    (4.4, -259.3, 172, 43.7, -145.8, 108, 86),     # main north massif
    (4.4, -259.3, 172, 49.7, -284.7, 122, 66),     # north-west shoulder
    (49.7, -284.7, 122, 138.9, -266.3, 60, 56),    # west ridge
    (138.9, -266.3, 60, 60.0, -320.0, 80, 52),     # far north-west shoulder
    (43.7, -145.8, 108, 69.8, -172.7, 74, 62),     # shoulder into the hills
    (69.8, -172.7, 74, 113.4, -37.2, 48, 64),      # central hills
    (113.4, -37.2, 48, 60.0, 90.0, 34, 64),        # south hills
    (-246.0, 56.0, 20, -164.7, 80.7, 22, 78),      # eastern dry plateau
    (-164.7, 80.7, 22, -60.0, 130.0, 17, 80),
]

# --- palette: sRGB hex sampled from the reference render -------------------
# Values are the reference's on-screen colours; they are converted to Blender's
# linear base colours at material build time (see srgb_to_linear).
PALETTE_HEX = {
    "grass_a": "#6D973A", "grass_b": "#4F7D39", "grass_c": "#2D5D3E",
    "grass_d": "#79A63C",
    "rock_a": "#4B5359", "rock_b": "#60605E", "rock_c": "#786F66",
    "sand_a": "#C4A777", "sand_b": "#EDCF91",
    "dry_a": "#B1AE5A", "dry_b": "#88A73E",
    "sea": "#1273B0",
}
MAT_ORDER = ["grass_a", "grass_b", "grass_c", "grass_d",
             "rock_a", "rock_b", "rock_c", "sand_a", "sand_b",
             "dry_a", "dry_b"]
SLOPE_ROCK = 0.42       # face slope above which rock takes over
SAND_MAX_Z = 9.0

# --- vegetation (low-poly conifer blobs, as in the reference) --------------
TREE_SPACING = 9.5      # plan px between candidate positions
TREE_DENSITY = 0.42     # fraction of candidates that become a tree
TREE_HEIGHT = 6.5       # metres, before per-tree jitter (ref: ~3-7 m)
TREE_CLUMP = 0.42       # noise threshold: trees grow in patches
TREE_MIN_Z = 1.4        # no trees at or below this elevation
TREE_MAX_SLOPE = 1.75   # reject trees on steeper ground
TREE_COLOR_A = "#2C6B3A"
TREE_COLOR_B = "#3C8040"

# --- waterfall: a ribbon from the ridge ledge down the cliff --------------
WATERFALL_TOP = (10.0, -215.0)
WATERFALL_BASE = (-52.0, -150.0)
WATERFALL_W = 9.0       # plan px

# --- render ----------------------------------------------------------------
RES_X, RES_Y = 1536, 1024
SUN_ENERGY = 3.2
SUN_ANGLE = math.radians(58)     # elevation
SUN_AZIMUTH = math.radians(-118)  # from +X toward +Y


# ==========================================================================
# helpers
# ==========================================================================
def load_shapes(path):
    spec = importlib.util.spec_from_file_location("jurassic_island_shapes", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["jurassic_island_shapes"] = mod
    spec.loader.exec_module(mod)
    return mod


def unpack(s, res):
    bits = np.frombuffer(zlib.decompress(base64.b64decode(s)), np.uint8)
    return np.unpackbits(bits)[: res * res].reshape(res, res).astype(bool)


def smoothstep(a, b, x):
    """Smoothstep, also valid when a > b (reversed ramp)."""
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def box_blur(a, r):
    """Separable box blur (edge clamped); preserves array shape."""
    if r <= 0:
        return a.astype(np.float64)
    k = 2 * r + 1
    out = a.astype(np.float64)
    for axis in (0, 1):
        pad = [(0, 0), (0, 0)]
        pad[axis] = (r, r)
        p = np.pad(out, pad, mode="edge")
        c = np.cumsum(p, axis=axis)
        prepend = np.zeros_like(np.take(c, [0], axis=axis))
        c = np.concatenate([prepend, c], axis=axis)
        n = a.shape[axis]
        hi = np.take(c, np.arange(k, k + n), axis=axis)
        lo = np.take(c, np.arange(0, n), axis=axis)
        out = (hi - lo) / k
    return out


def bilinear(grid, gx, gy, X, Y):
    """Bilinear sample of `grid` (indexed [ix, iy]) at plan coords (X, Y)."""
    fx = np.clip((X - gx[0]) / (gx[-1] - gx[0]) * (len(gx) - 1), 0, len(gx) - 1)
    fy = np.clip((Y - gy[0]) / (gy[-1] - gy[0]) * (len(gy) - 1), 0, len(gy) - 1)
    x0 = np.clip(np.floor(fx).astype(int), 0, len(gx) - 2)
    y0 = np.clip(np.floor(fy).astype(int), 0, len(gy) - 2)
    tx = np.clip(fx - x0, 0, 1)
    ty = np.clip(fy - y0, 0, 1)
    g = grid.astype(np.float64)
    return ((g[x0, y0] * (1 - tx) + g[x0 + 1, y0] * tx) * (1 - ty)
            + (g[x0, y0 + 1] * (1 - tx) + g[x0 + 1, y0 + 1] * tx) * ty)


def distance_inside(mask, max_d):
    """Distance from the mask boundary in samples, positive inside."""
    dist = np.where(mask, float(max_d), 0.0)
    cur = mask.copy()
    for step in range(1, int(max_d) + 1):
        grown = cur.copy()
        grown[1:, :] |= cur[:-1, :]
        grown[:-1, :] |= cur[1:, :]
        grown[:, 1:] |= cur[:, :-1]
        grown[:, :-1] |= cur[:, 1:]
        grown &= mask
        newly = grown & ~cur
        if not newly.any():
            break
        dist[newly] = step
        cur = grown
    return dist


def value_noise(shape, seed, octaves, freq):
    """Fractal value noise on a `shape` grid; returns roughly [-1, 1]."""
    rng = np.random.default_rng(seed)
    total = np.zeros(shape, np.float64)
    amp, norm = 1.0, 0.0
    for _ in range(octaves):
        n = int(max(2, round(freq)))
        lat = rng.random((n + 2, n + 2))
        FX, FY = np.meshgrid(np.linspace(0, n, shape[0]),
                             np.linspace(0, n, shape[1]), indexing="ij")
        ix = np.clip(np.floor(FX).astype(int), 0, n - 1)
        iy = np.clip(np.floor(FY).astype(int), 0, n - 1)
        tx, ty = FX - ix, FY - iy
        tx = tx * tx * (3 - 2 * tx)
        ty = ty * ty * (3 - 2 * ty)
        total += amp * 2.0 * (
            (lat[ix, iy] * (1 - tx) + lat[ix + 1, iy] * tx) * (1 - ty)
            + (lat[ix, iy + 1] * (1 - tx) + lat[ix + 1, iy + 1] * tx) * ty - 0.5)
        norm += amp
        amp *= 0.5
        freq *= 2.0
    return total / max(norm, 1e-9)


def ridge_field(X, Y, ridges):
    """Union of elongated ridges; height interpolates along each segment.

    RIDGES heights come from the reference landmarks and are in plan-pixel
    units, so they are converted to metres with SCALE.
    """
    h = np.zeros(X.shape, np.float64)
    for x1, y1, h1, x2, y2, h2, width in ridges:
        vx, vy = x2 - x1, y2 - y1
        L2 = max(vx * vx + vy * vy, 1e-9)
        t = np.clip(((X - x1) * vx + (Y - y1) * vy) / L2, 0.0, 1.0)
        d = np.hypot(X - (x1 + t * vx), Y - (y1 + t * vy))
        h = np.maximum(h, (h1 + t * (h2 - h1)) * np.exp(-0.5 * (d / width) ** 2))
    return h * RIDGE_GAIN * SCALE


def smooth3(a, passes):
    """3x3 box smoothing, edge clamped."""
    out = a
    for _ in range(passes):
        p = np.pad(out, 1, mode="edge")
        out = (p[:-2, :-2] + p[:-2, 1:-1] + p[:-2, 2:]
               + p[1:-1, :-2] + p[1:-1, 1:-1] + p[1:-1, 2:]
               + p[2:, :-2] + p[2:, 1:-1] + p[2:, 2:]) / 9.0
    return out


# ==========================================================================
# scene / materials
# ==========================================================================
def reset_scene():
    # `read_factory_settings` is blocked by the MCP sandbox; homefile is fine.
    bpy.ops.wm.read_homefile(use_empty=True, use_factory_startup=True)
    for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.objects,
                 bpy.data.images, bpy.data.cameras, bpy.data.lights,
                 bpy.data.worlds, bpy.data.collections):
        for item in list(coll):
            coll.remove(item)


def srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hex_to_linear(h):
    h = h.lstrip("#")
    return tuple(srgb_to_linear(int(h[i:i + 2], 16) / 255.0) for i in (0, 2, 4))


def make_material(name, rgb, roughness=0.9):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*rgb, 1.0)
    bsdf.inputs["Roughness"].default_value = roughness
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = 0.12
    mat.diffuse_color = (*rgb, 1.0)
    return mat


# ==========================================================================
# terrain
# ==========================================================================
def build_height_field(shapes):
    """Sample the baked masks onto a regular grid and derive elevations."""
    src = shapes.RES
    gxs = np.linspace(shapes.GX0, shapes.GX1, src)
    gys = np.linspace(shapes.GY0, shapes.GY1, src)

    masks = {k: unpack(getattr(shapes, k), src).astype(np.float64)
             for k in ("FOOTPRINT", "LAGOON", "SAND", "DRY")}
    for k in masks:
        masks[k] = box_blur(masks[k], MASK_BLUR)
    grow = int(round(LAGOON_GROW))
    if grow:
        lg = masks["LAGOON"] > 0.35
        for _ in range(grow):
            o = lg.copy()
            o[1:, :] |= lg[:-1, :]; o[:-1, :] |= lg[1:, :]
            o[:, 1:] |= lg[:, :-1]; o[:, :-1] |= lg[:, 1:]
            lg = o
        masks["LAGOON"] = np.maximum(masks["LAGOON"], lg.astype(np.float64))
    footprint_f = np.clip(masks["FOOTPRINT"], 0, 1)

    gx = np.linspace(shapes.GX0, shapes.GX1, GRID)
    gy = np.linspace(shapes.GY0, shapes.GY1, GRID)
    GX, GY = np.meshgrid(gx, gy, indexing="ij")

    sw = (gx[-1] - gx[0]) / (GRID - 1)     # cell size in plan px
    foot = bilinear(footprint_f, gxs, gys, GX, GY)
    # signed distance to the coastline, in plan px (positive inland)
    d = distance_inside(foot > 0.5, 140).astype(np.float64) * sw
    d_out = distance_inside(foot <= 0.5, 30).astype(np.float64) * sw
    d_signed = d - d_out

    # land profile
    shell = smoothstep(SHELF_IN, SHELF_OUT, d) * SHELF_H
    body = smoothstep(BODY_IN, BODY_OUT, d) * BODY_H
    ridge = ridge_field(GX, GY, RIDGES) * np.clip(smoothstep(0, 22, d), 0, 1)
    macro = value_noise((GRID, GRID), SEED, 4, GRID * sw / MACRO_SCALE) * MACRO_AMP
    micro = value_noise((GRID, GRID), SEED + 11, 3, GRID * sw / MICRO_SCALE) * MICRO_AMP
    grain = np.clip(smoothstep(0, 14, d), 0, 1)
    h = shell + body + ridge + (macro + micro) * grain

    # beaches and the dry eastern plateau
    beach = np.clip(bilinear(masks["SAND"], gxs, gys, GX, GY), 0, 1)
    beach *= np.clip(smoothstep(-6, 8, d), 0, 1)
    h = h * (1 - BEACH_PULL * beach) + BEACH_H * BEACH_PULL * beach

    dry = np.clip(bilinear(masks["DRY"], gxs, gys, GX, GY), 0, 1)
    dry *= np.clip(smoothstep(-2, 18, d), 0, 1)
    h = h * (1 - FLAT_DRY * dry) + DRY_H * FLAT_DRY * dry

    # lagoon basin
    lagoon = np.clip(bilinear(masks["LAGOON"], gxs, gys, GX, GY) * 2.4, 0, 1)
    h = h * (1 - lagoon) + LAGOON_H * lagoon

    # coast: drop to the sea floor outside the footprint, quickly at first
    coast = smoothstep(0.0, -CLIFF_OUT, d_signed)
    h = (1 - coast) * np.maximum(h, 0.0) + coast * SEA_FLOOR
    h = smooth3(h, COAST_SMOOTH)
    h = np.maximum(h, SEA_FLOOR)

    return gx, gy, h, masks


def grid_to_object(name, gx, gy, h):
    nx, ny = len(gx), len(gy)
    verts = [(gx[i] * SCALE, gy[j] * SCALE, float(h[i, j]))
             for i in range(nx) for j in range(ny)]
    faces = []
    for i in range(nx - 1):
        for j in range(ny - 1):
            a = i * ny + j
            faces.append((a, a + ny, a + ny + 1, a + 1))
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def assign_materials(obj, masks, gxs, gys):
    mats = {k: make_material(k, hex_to_linear(v)) for k, v in PALETTE_HEX.items()}
    for name in MAT_ORDER:
        obj.data.materials.append(mats[name])

    mesh = obj.data
    n = len(mesh.polygons)
    nrm = np.zeros(n * 3)
    mesh.polygons.foreach_get("normal", nrm)
    ctr = np.zeros(n * 3)
    mesh.polygons.foreach_get("center", ctr)
    nrm = nrm.reshape(n, 3)
    ctr = ctr.reshape(n, 3)

    slope = 1.0 - np.clip(nrm[:, 2], 0, 1)
    cx, cy, cz = ctr[:, 0] / SCALE, ctr[:, 1] / SCALE, ctr[:, 2]
    sand = bilinear(masks["SAND"], gxs, gys, cx, cy)
    dry = bilinear(masks["DRY"], gxs, gys, cx, cy)

    rng = np.random.default_rng(SEED + 7)
    j = rng.random(n)
    idx = np.select([j < 0.30, j < 0.52, j < 0.76], [1, 2, 0], default=3)
    rocky = slope > SLOPE_ROCK
    idx[rocky] = 4 + np.clip((j[rocky] * 3).astype(int), 0, 2)
    dryish = (dry > 0.45) & ~rocky
    idx[dryish] = np.where(j[dryish] < 0.5, 9, 10)
    sandy = (sand > 0.4) & (cz < SAND_MAX_Z) & (slope < SLOPE_ROCK)
    idx[sandy] = np.where(j[sandy] < 0.6, 7, 8)

    mesh.polygons.foreach_set("material_index", idx.astype(np.int32))
    mesh.update()


# ==========================================================================
# scatter: forests and the waterfall
# ==========================================================================
def height_at(gx, gy, h, X, Y):
    i = int(np.clip(np.searchsorted(gx, X), 0, len(gx) - 1))
    j = int(np.clip(np.searchsorted(gy, Y), 0, len(gy) - 1))
    return float(h[i, j])


def build_forests(gx, gy, h, masks, gxs, gys):
    """Low-poly conifer blobs scattered on the grass, denser on the ridges.

    Each tree is a 5-sided cone plus a short trunk; all trees of one group are
    joined into a single mesh so the export stays tidy.
    """
    sx = gx[-1] - gx[0]
    sy = gy[-1] - gy[0]
    rng = np.random.default_rng(SEED + 31)
    verts, faces, mats = [], [], []
    step = TREE_SPACING
    n = 0
    ii = 0
    for X in np.arange(gx[0], gx[-1], step):
        ii += 1
        for Y in np.arange(gy[0], gy[-1], step):
            if rng.random() > TREE_DENSITY:
                continue
            # jitter so the grid does not read as rows
            px = X + (rng.random() - 0.5) * step * 0.9
            py = Y + (rng.random() - 0.5) * step * 0.9
            gi, gj = int((px - gx[0]) / sx * (GRID - 1)), int((py - gy[0]) / sy * (GRID - 1))
            if not (0 <= gi < GRID and 0 <= gj < GRID):
                continue
            z = h[gi, gj]
            if z < TREE_MIN_Z:
                continue
            # no trees on cliffs, beaches, the lagoon or the dry plateau
            if bilinear(masks["SAND"], gxs, gys, np.array([px]), np.array([py]))[0] > 0.35:
                continue
            if bilinear(masks["LAGOON"], gxs, gys, np.array([px]), np.array([py]))[0] > 0.2:
                continue
            if bilinear(masks["DRY"], gxs, gys, np.array([px]), np.array([py]))[0] > 0.45:
                continue
            gxx = [h[min(max(gi + a, 0), GRID - 1), min(max(gj + b, 0), GRID - 1)]
                   for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1))]
            slope = (max(gxx) - min(gxx)) / (step * SCALE)
            if slope > TREE_MAX_SLOPE:
                continue

            scale = TREE_HEIGHT * (0.72 + 0.55 * rng.random())
            wx, wy = px * SCALE, py * SCALE
            base = len(verts)
            seg = 5
            verts.append((wx, wy, z + scale))          # tip
            for s in range(seg):
                a = 2 * math.pi * s / seg + rng.random() * 0.4
                r = scale * 0.38
                verts.append((wx + math.cos(a) * r, wy + math.sin(a) * r,
                              z + scale * 0.30))
            for s in range(seg):
                a = 2 * math.pi * s / seg + 0.3
                r = scale * 0.26
                verts.append((wx + math.cos(a) * r, wy + math.sin(a) * r, z))
            for s in range(seg):
                faces.append((base, base + 1 + s, base + 1 + (s + 1) % seg))
            for s in range(seg):
                faces.append((base + 1 + s, base + 1 + seg + s,
                              base + 1 + seg + (s + 1) % seg))
                faces.append((base + 1 + s, base + 1 + seg + (s + 1) % seg,
                              base + 1 + (s + 1) % seg))
            mats.extend([TREE_MAT] * (2 * seg))
            n += 1
    print("trees: %d" % n)
    if not n:
        return []
    mesh = bpy.data.meshes.new("Forest")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new("Forest", mesh)
    bpy.context.scene.collection.objects.link(obj)
    # one material for the whole forest, with two tone slots per face
    for name, col in (("tree_a", TREE_COLOR_A), ("tree_b", TREE_COLOR_B)):
        obj.data.materials.append(make_material(name, hex_to_linear(col)))
    rng2 = np.random.default_rng(SEED + 99)
    idx = (rng2.random(len(mesh.polygons)) < 0.5).astype(np.int32)
    mesh.polygons.foreach_set("material_index", idx)
    mesh.update()
    for p in mesh.polygons:
        p.use_smooth = False
    return [obj]


def build_waterfall(h, gx, gy):
    """A flat ribbon of water from the ridge ledge down the cliff face."""
    X0, Y0 = WATERFALL_TOP
    X1, Y1 = WATERFALL_BASE
    steps = 26
    verts, faces = [], []
    width = WATERFALL_W
    for i in range(steps + 1):
        t = i / steps
        X = X0 + (X1 - X0) * t
        Y = Y0 + (Y1 - Y0) * t
        # hug the terrain, but never rise above the ridge line
        z = height_at(gx, gy, h, X, Y) + 0.5
        # the ribbon hangs slightly off the slope so it reads as water
        nx, ny = -(Y1 - Y0), (X1 - X0)
        ln = math.hypot(nx, ny) or 1.0
        nx, ny = nx / ln, ny / ln
        a = (X + nx * width / 2, Y + ny * width / 2, z)
        b = (X - nx * width / 2, Y - ny * width / 2, z)
        verts.append((a[0] * SCALE, a[1] * SCALE, a[2]))
        verts.append((b[0] * SCALE, b[1] * SCALE, b[2]))
    for i in range(steps):
        faces.append((2 * i, 2 * i + 2, 2 * i + 3, 2 * i + 1))
    mesh = bpy.data.meshes.new("Waterfall")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new("Waterfall", mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.data.materials.append(make_material("waterfall", hex_to_linear("#DCEFF5"), 0.25))
    for p in obj.data.polygons:
        p.use_smooth = False
    return obj


def build_islets(shapes, footprint_mask, gxs, gys):
    """Low-poly cones for lagoon islets and offshore rocks."""
    objs = []
    for k, (X, Y, r, kind) in enumerate(shapes.DISCS):
        in_lagoon = bool(bilinear(footprint_mask, gxs, gys,
                                  np.array([X]), np.array([Y]))[0] > 0.5)
        top = 4.0 if in_lagoon else 2.6
        z0 = -3.0 if in_lagoon else SEA_FLOOR * 0.5
        br = r * SCALE * 1.35
        seg = 7
        verts = [(X * SCALE, Y * SCALE, top)]
        for s in range(seg):
            a = 2 * math.pi * s / seg
            rr = br * (0.70 + 0.30 * ((s * 37) % 5) / 4.0)
            verts.append((X * SCALE + math.cos(a) * rr,
                          Y * SCALE + math.sin(a) * rr, z0))
        verts.append((X * SCALE, Y * SCALE, z0 - 4.0))
        faces = [(1 + (i + 1) % seg, 1 + i, 0) for i in range(seg)]
        faces += [(1 + i, 1 + (i + 1) % seg, seg + 1) for i in range(seg)]
        mesh = bpy.data.meshes.new("Islet_%02d" % k)
        mesh.from_pydata(verts, [], faces)
        mesh.update()
        obj = bpy.data.objects.new("Islet_%02d" % k, mesh)
        bpy.context.scene.collection.objects.link(obj)
        rock = make_material("islet_rock", (0.36, 0.37, 0.38))
        grass = make_material("islet_grass", hex_to_linear(PALETTE_HEX["grass_b"]))
        obj.data.materials.append(grass if in_lagoon else rock)
        for p in obj.data.polygons:
            p.use_smooth = False
        objs.append(obj)
    return objs


# ==========================================================================
# render
# ==========================================================================
def iso_basis():
    """Screen-right / screen-up for the reference isometric (az 45, el 30)."""
    e = math.radians(30.0)
    right = Vector((-1 / math.sqrt(2), 1 / math.sqrt(2), 0.0))
    up = Vector((-math.sin(e) / math.sqrt(2), -math.sin(e) / math.sqrt(2),
                 math.cos(e)))
    return right, up


def setup_render(objs, framing_objs=None):
    """`objs` are rendered; `framing_objs` (default: objs) define the view."""
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x, scene.render.resolution_y = RES_X, RES_Y
    scene.render.film_transparent = False
    scene.eevee.taa_render_samples = 32
    # the reference is a flat cartoon render: keep colours unfiltered
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    scene.view_settings.exposure = 0.0
    scene.view_settings.gamma = 1.0
    frame_src = framing_objs if framing_objs is not None else objs

    world = bpy.data.worlds.new("World")
    scene.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.16, 0.44, 0.68, 1)
    world.node_tree.nodes["Background"].inputs[1].default_value = 1.0

    # sun matching the reference: light from the upper-left/front
    sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN"))
    scene.collection.objects.link(sun)
    sun.data.energy = SUN_ENERGY
    sun.data.angle = math.radians(4.0)
    d = Vector((-math.cos(SUN_ANGLE) * math.cos(SUN_AZIMUTH),
                -math.cos(SUN_ANGLE) * math.sin(SUN_AZIMUTH),
                -math.sin(SUN_ANGLE)))
    sun.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()

    right, up = iso_basis()
    pts = [Vector(o.matrix_world @ v.co) for o in frame_src for v in o.data.vertices]
    us = [p.dot(right) for p in pts]
    vs = [p.dot(up) for p in pts]
    cu, cv = 0.5 * (min(us) + max(us)), 0.5 * (min(vs) + max(vs))
    span_u = max(us) - min(us)
    span_v = max(vs) - min(vs)
    ortho = max(span_u, span_v * RES_X / RES_Y) * 1.12

    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    center = (lo + hi) * 0.5
    # shift the bbox centre so the projected silhouette is centred on screen
    target = center + right * (cu - center.dot(right)) + up * (cv - center.dot(up))

    cam_data = bpy.data.cameras.new("Camera")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = ortho
    cam = bpy.data.objects.new("Camera", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    to_cam = (right.cross(up)).normalized()        # from scene towards camera
    cam.location = target + to_cam * (ortho * 2.0)
    cam.rotation_euler = (-to_cam).to_track_quat("-Z", "Y").to_euler()
    cam.data.clip_end = ortho * 8.0
    return cam


def add_sea():
    mesh = bpy.data.meshes.new("Sea")
    s = 2600.0
    mesh.from_pydata([(-s, -s, SEA_LEVEL), (s, -s, SEA_LEVEL),
                      (s, s, SEA_LEVEL), (-s, s, SEA_LEVEL)], [],
                     [(0, 1, 2, 3)])
    mesh.update()
    obj = bpy.data.objects.new("Sea", mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.data.materials.append(make_material("sea", hex_to_linear(PALETTE_HEX["sea"]), 0.45))
    return obj


def render_to(path, cam, top=False, objs=()):
    scene = bpy.context.scene
    if top:
        cam.data.type = "ORTHO"
        pts = [Vector(o.matrix_world @ v.co) for o in objs for v in o.data.vertices]
        xs = [p.x for p in pts]
        ys = [p.y for p in pts]
        cam.data.ortho_scale = max(max(xs) - min(xs),
                                   (max(ys) - min(ys)) * RES_X / RES_Y) * 1.12
        cam.location = (0.5 * (min(xs) + max(xs)), 0.5 * (min(ys) + max(ys)), 900)
        cam.rotation_euler = (0, 0, 0)
    scene.render.filepath = path
    scene.render.image_settings.file_format = "PNG"
    bpy.ops.render.render(write_still=True)


# ==========================================================================
# main
# ==========================================================================
def main():
    shapes = load_shapes(SHAPES_PATH)
    reset_scene()

    gx, gy, h, masks = build_height_field(shapes)
    gxs = np.linspace(shapes.GX0, shapes.GX1, shapes.RES)
    gys = np.linspace(shapes.GY0, shapes.GY1, shapes.RES)
    print("height field %s  z %.2f .. %.2f" % (h.shape, h.min(), h.max()))

    obj = grid_to_object("IslandTerrain", gx, gy, h)

    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.delete(bm, geom=[f for f in bm.faces
                               if f.calc_center_median().z < CLIP_Z],
                     context="FACES")
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    print("faces after clip: %d" % len(obj.data.polygons))

    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    mod = obj.modifiers.new("Decimate", "DECIMATE")
    mod.decimate_type = "COLLAPSE"
    mod.ratio = DECIMATE_RATIO
    mod.use_collapse_triangulate = True
    with bpy.context.temp_override(object=obj, active_object=obj,
                                   selected_objects=[obj],
                                   selected_editable_objects=[obj]):
        bpy.ops.object.modifier_apply(modifier=mod.name)
    for p in obj.data.polygons:
        p.use_smooth = False
    print("faces after decimate: %d" % len(obj.data.polygons))

    assign_materials(obj, masks, gxs, gys)
    islets = build_islets(shapes, masks["FOOTPRINT"], gxs, gys)
    forests = build_forests(gx, gy, h, masks, gxs, gys)
    fall = build_waterfall(h, gx, gy)
    sea = add_sea()

    xs = [v.co.x for v in obj.data.vertices]
    ys = [v.co.y for v in obj.data.vertices]
    zs = [v.co.z for v in obj.data.vertices]
    print("bounds x %.1f..%.1f  y %.1f..%.1f  z %.1f..%.1f" % (
        min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)))
    tris = sum(len(p.vertices) - 2 for p in obj.data.polygons)
    print("triangles: %d" % tris)

    land = [obj] + islets + forests + [fall]
    cam = setup_render(land + [sea], framing_objs=[obj] + islets)
    render = os.path.join(ASSET_DIR, "jurassic_island_preview.png")
    render_to(render, cam, objs=land + [sea])
    top = os.path.join(ASSET_DIR, "jurassic_island_top.png")
    render_to(top, cam, top=True, objs=[obj] + islets)

    blend = os.path.join(ASSET_DIR, "jurassic_island.blend")
    bpy.ops.wm.save_as_mainfile(filepath=blend)
    print("saved", blend)


if __name__ == "__main__":
    main()
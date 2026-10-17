"""Low-poly mountain-cave island generator.

    blender --background --python low_poly_mountain_cave_island.py

Produces one object "Island": a closed watertight mesh, flat-faceted, with a
cave bored into the mountain's front face and per-face vertex colours ("Col")
driving a Principled BSDF ("IslandMat").

Shape (matching the reference art)
----------------------------------
* Broad rounded island, wider than deep, with a short shallow skirt.
* The mountain occupies only the BACK-RIGHT; the rest is low shelf/headland
  well under half the peak height.
* A deep coastal notch at the front lets the sea cut into the island, forming
  the signature bay with sandy inner shores.
* Small rocky islets sit in the shallow water off the coast.

Cave placement
--------------
The cave is NOT placed by hand. `find_cave_site` walks the front of the
mountain, and for each candidate (x, z) finds the front-most y where the
surface reaches that height, then scores the local wall steepness. The best
site is bored into the hill along +Y while the mesh is still dense, so the
mouth stays circular; a vertex group protects that rim from decimation.

Outputs (next to this file):
    low_poly_mountain_cave_island.blend
    low_poly_mountain_cave_island.glb
"""

import math
import os

import bmesh
import bpy
import numpy as np

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
NAME = "low_poly_mountain_cave_island"

# ---- tunables -------------------------------------------------------------- #
SIZE, N = 24.0, 241          # heightfield extent / resolution (roomy: no clipped coast)
BOT, TMAX = -1.35, 1.05      # flat bottom Z, trim radius. TMAX is close to 1 on
                             # purpose: in the reference the sea around the
                             # island is water, so the mesh keeps only a thin
                             # surf ledge rather than a broad underwater skirt.
TARGET_TRIS = 1700
CAVE_R = 0.72                # cave mouth radius
CAVE_DEPTH = 3.4
CAVE_FRONT = 1.0             # how far the cutter sticks out of the wall
PROTECT_PAD = 1.05
PEAK = (3.0, 3.0)            # mountain centre: back-right only
PEAK_H = 4.90


# --------------------------------------------------------------------------- #
def _hash2(ix, iy, seed):
    h = np.sin(ix * 127.1 + iy * 311.7 + seed * 74.7) * 43758.5453
    return h - np.floor(h)


def noise2(X, Y, freq, seed):
    x, y = X * freq, Y * freq
    ix, iy = np.floor(x), np.floor(y)
    fx, fy = x - ix, y - iy
    ux = fx * fx * (3 - 2 * fx)
    uy = fy * fy * (3 - 2 * fy)
    a = _hash2(ix, iy, seed)
    b = _hash2(ix + 1, iy, seed)
    c = _hash2(ix, iy + 1, seed)
    d = _hash2(ix + 1, iy + 1, seed)
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


def srgb2lin(c):
    c = np.asarray(c, dtype=float)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def angdiff(a, b):
    d = a - b
    return (d + math.pi) % (2 * math.pi) - math.pi


# --------------------------------------------------------------------------- #
AX, AY = 1.00, 0.84


def build_heightfield():
    xs = np.linspace(-SIZE / 2, SIZE / 2, N)
    X, Y = np.meshgrid(xs, xs)

    theta = np.arctan2(Y / AY, X / AX)
    r = np.sqrt((X / AX) ** 2 + (Y / AY) ** 2)

    edge = 7.0 * (1.0 + 0.15 * np.sin(3 * theta + 0.9)
                  + 0.08 * np.sin(5 * theta + 1.7)
                  + 0.05 * np.sin(8 * theta + 0.4))
    # deep notch at the front -> the sea cuts into the island
    notch = 1.0 - 0.42 * np.exp(-(angdiff(theta, -math.pi / 2) / 0.50) ** 2)
    notch *= 1.0 - 0.16 * np.exp(-(angdiff(theta, math.pi) / 0.70) ** 2)
    edge = edge * notch * (0.88 + 0.24 * fbm(X, Y, 0.28, 11, 3))

    t = r / np.maximum(edge, 1e-6)
    land = np.clip(1.0 - t, 0.0, 1.0)

    # --- base shelf: low and gently rolling, with a WIDE sandy fringe ---
    # The reference shows a broad pale beach ring, so the near-shore band is
    # deliberately flat: it stays under BEACH_Z and gets sand-coloured.
    Z = np.where(t < 1.0, 0.06 + 0.72 * np.power(land, 0.34),
                 BOT * np.power(np.clip((t - 1.0) / (TMAX - 1.0), 0, 1), 0.75))

    def bump(cx, cy, amp, sx, sy, rot=0.0):
        dx, dy = X - cx, Y - cy
        if rot:
            ca, sa = math.cos(rot), math.sin(rot)
            dx, dy = ca * dx - sa * dy, sa * dx + ca * dy
        return amp * np.exp(-(dx * dx / (2 * sx * sx) + dy * dy / (2 * sy * sy)))

    # the mountain: back-right only. Wide enough to read as a massif with a
    # real wall to hold the cave, not a thin spike.
    Z += bump(PEAK[0], PEAK[1], PEAK_H, 2.30, 2.00, 0.40)
    Z += bump(2.2, 5.0, 1.20, 2.00, 1.60, 0.30)
    # low ground everywhere else (all well under half the peak)
    Z += bump(-3.6, 1.2, 0.95, 3.40, 2.70, -0.30)
    Z += bump(-5.8, -1.8, 0.90, 1.90, 1.70, 0.20)
    Z += bump(-2.0, -4.2, 0.80, 2.40, 1.70, 0.60)
    Z += bump(4.2, -4.8, 1.05, 2.00, 1.55, -0.50)
    Z += bump(5.8, 1.2, 0.70, 1.60, 1.35, 0.10)
    # rocky islets in the shallows
    for ix, iy, amp, sx, sy in [(-7.6, -5.0, 1.10, 0.68, 0.60),
                                (-4.8, -7.6, 0.95, 0.60, 0.55),
                                (0.8, -9.4, 1.00, 0.66, 0.57),
                                (6.2, -7.4, 1.05, 0.64, 0.57),
                                (8.8, -2.8, 0.90, 0.57, 0.53),
                                (-9.0, 0.8, 0.95, 0.60, 0.55),
                                (7.8, 4.6, 0.88, 0.55, 0.50),
                                (-2.4, -9.8, 0.85, 0.53, 0.50),
                                (10.2, 2.0, 0.80, 0.50, 0.46),
                                (-8.2, -6.4, 0.85, 0.52, 0.48)]:
        Z += bump(ix, iy, amp, sx, sy)
    # lagoon hollow on the left shelf
    Z -= 2.10 * np.exp(-(((X + 4.0) / 1.45) ** 2 + ((Y - 0.6) / 1.10) ** 2))

    # --- TERRACES: the reference's signature look is grass on flat shelves with
    # bare rock walls stepping between them. Kept to the LOW ground -- the
    # mountain itself stays a smooth rocky cone -- and the step height wobbles
    # with noise so the shelves don't read as a wedding cake.
    def terraces(z, base_step, weight):
        # The wobble must be gentle, otherwise the mountain wall itself gets
        # chopped up and the cave ends up sitting on a stair edge.
        wobble = 1.0 + 0.30 * (fbm(X, Y, 0.30, 23.0, 3) - 0.5) * 2.0
        lev = z / (base_step * wobble)
        fl = np.floor(lev)
        fr = lev - fl
        eased = np.clip((fr - 0.58) / 0.42, 0, 1)
        eased = eased * eased * (3 - 2 * eased)
        stepped = (fl + eased) * base_step * wobble
        # fade out on the mountain and at the waterline
        w = weight * np.clip((2.5 - z) / 1.5, 0, 1) * np.clip((z - 0.10) / 0.5, 0, 1)
        return stepped * w + z * (1 - w)

    Z = terraces(Z, 0.55, 0.48)

    mask = np.clip(land * 2.8, 0, 1)
    Z += 0.36 * fbm(X, Y, 0.50, 5.0, 4) * mask
    Z += 0.12 * fbm(X, Y, 1.50, 9.0, 3) * mask
    return np.array(X), np.array(Y), np.maximum(Z, BOT), np.array(t)


def build_solid(X, Y, Z, t):
    verts = np.column_stack([X.ravel(), Y.ravel(), Z.ravel()]).tolist()
    idx = np.arange(N * N).reshape(N, N)
    faces = np.column_stack([idx[:-1, :-1].ravel(), idx[:-1, 1:].ravel(),
                             idx[1:, 1:].ravel(), idx[1:, :-1].ravel()]).tolist()
    me = bpy.data.meshes.new("IslandMesh")
    me.from_pydata(verts, [], faces)
    me.update()
    ob = bpy.data.objects.new("Island", me)
    bpy.context.scene.collection.objects.link(ob)

    tflat = t.ravel().tolist()
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[v for i, v in enumerate(bm.verts) if tflat[i] > TMAX],
                     context='VERTS')
    bm.verts.ensure_lookup_table()
    # Cap the underside by walking the real boundary loops. Sorting the rim by
    # polar angle only works for star-shaped outlines; this island is concave,
    # so angle-sorting scrambles the loop and leaves the shell full of holes --
    # which in turn makes the later boolean shatter the cave mouth.
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

    for loop in boundary_loops(bm):
        cxx = sum(v.co.x for v in loop) / len(loop)
        cyy = sum(v.co.y for v in loop) / len(loop)
        for v in loop:
            v.co.z = BOT
        centre = bm.verts.new((cxx, cyy, BOT))
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


def find_cave_site(Z):
    """Front-most, steepest reachable spot on the mountain's front wall.

    For each (x, z) the front-most y whose terrain height reaches z is the
    wall surface; its dy/dz gives the steepness. Returns (x, y, z) on that
    wall, with y being the surface itself.
    """
    xs = np.linspace(-SIZE / 2, SIZE / 2, N)
    best = None
    for px in np.arange(1.6, 4.4, 0.05):
        j = int(round((px + SIZE / 2) / SIZE * (N - 1)))
        col = Z[:, j]
        for pz in np.arange(1.4, 3.2, 0.05):
            hit = np.where(col >= pz)[0]
            if not len(hit):
                continue
            iy = int(hit.min())
            ysurf = xs[iy]
            if not (-2.4 < ysurf < 3.0):        # keep it on the front face
                continue
            i0, i1 = max(0, iy - 3), min(N - 1, iy + 3)
            if i1 <= i0:
                continue
            dzdy = (Z[i1, j] - Z[i0, j]) / (xs[i1] - xs[i0])
            steep = dzdy / math.sqrt(1.0 + dzdy * dzdy)      # sin(wall angle)
            score = steep - 0.06 * abs(pz - 2.2)             # prefer mid height
            if best is None or score > best[0]:
                best = (score, float(px), float(ysurf), float(pz), float(steep))
    if best is None:
        return 2.2, 0.0, 2.2, 0.5
    return best[1], best[2], best[3], best[4]


def activate(ob):
    for o in bpy.context.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob


def apply_mod(ob, mod):
    bpy.ops.object.modifier_apply(modifier=mod.name)


def colourise(me, cave):
    SAND_L = srgb2lin([0.90, 0.82, 0.60])
    SAND_D = srgb2lin([0.77, 0.68, 0.48])
    GRASS_L = srgb2lin([0.58, 0.76, 0.30])
    GRASS_M = srgb2lin([0.41, 0.63, 0.21])
    GRASS_D = srgb2lin([0.25, 0.45, 0.14])
    ROCK_L = srgb2lin([0.70, 0.63, 0.53])
    ROCK_M = srgb2lin([0.52, 0.45, 0.37])
    ROCK_D = srgb2lin([0.34, 0.29, 0.24])
    SEABED = srgb2lin([0.31, 0.39, 0.40])
    CAVE_IN = srgb2lin([0.07, 0.065, 0.06])
    cx, cy, cz = cave[0], cave[1], cave[2]

    ROCK_LINE = 2.55              # above this the peak is bare rock, as in the ref
    ROCK_SLOPE = 0.30             # terrace risers count as rock; decimation
                                  # softens normals, so this is lower than it
                                  # looks (a face at 0.30 is still fairly steep)

    ca = me.color_attributes.new(name="Col", type='FLOAT_COLOR', domain='CORNER')
    for p in me.polygons:
        nz, z, c = p.normal.z, p.center.z, p.center
        v = math.sin(c.x * 3.1) * math.cos(c.y * 2.7) * 0.5 + 0.5
        band = math.sin(z * 2.1) * 0.5 + 0.5
        slope = 1.0 - nz
        # bare-rock share rises with altitude: the reference's summit is rock,
        # its shelves are grass. Slope alone under-reports rock once the
        # terracing has flattened things out.
        bare = np.clip((z - ROCK_LINE) / 1.5, 0, 1)
        if z < -0.05:
            col = SEABED * (0.78 + 0.42 * band)
        elif z < 1.05 and nz > 0.78:                          # beach fringe
            col = SAND_L * (1 - v) + SAND_D * v
        elif z < 0.62 and nz > 0.55:                          # inner sandy shore
            col = SAND_L * (0.86 + 0.22 * v)
        elif slope > ROCK_SLOPE or bare > 0.0:
            rock_t = np.clip(max((slope - ROCK_SLOPE) / 0.18, bare), 0, 1)
            grass_here = GRASS_M * (1 - v) + GRASS_D * v
            col = (ROCK_M * (1 - band) + ROCK_D * band) * rock_t \
                + grass_here * (1 - rock_t)
        elif slope > 0.22:
            t2 = np.clip((slope - 0.22) / 0.18, 0, 1)
            col = (ROCK_L * (1 - band) + ROCK_M * band) * t2 \
                + (GRASS_M * (1 - v) + GRASS_D * v) * (1 - t2)
        else:
            if z > 3.4:
                col = GRASS_L * (0.86 + 0.28 * v)
            elif z > 1.6:
                col = GRASS_L * (1 - v) + GRASS_M * v
            else:
                col = GRASS_M * (1 - v) + GRASS_D * v
        col = np.clip(col, 0, 1)
        for li in p.loop_indices:
            ca.data[li].color = (col[0], col[1], col[2], 1.0)

    # cave interior: dark, fading toward the back of the bore
    y_back = cy + CAVE_DEPTH
    for p in me.polygons:
        c = p.center
        if ((c.x - cx) ** 2 + (c.z - cz) ** 2) < (CAVE_R + 0.30) ** 2 \
                and (cy - CAVE_FRONT) < c.y < y_back:
            for li in p.loop_indices:
                f = 0.25 + 0.75 * min(1.0, max(0.0, (c.y - cy + CAVE_FRONT) / (CAVE_DEPTH + CAVE_FRONT)))
                col = CAVE_IN * f
                ca.data[li].color = (col[0], col[1], col[2], 1.0)


def make_material(me):
    me.materials.clear()
    for d in list(bpy.data.materials):
        if d.users == 0:
            bpy.data.materials.remove(d)
    mat = bpy.data.materials.new("IslandMat")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    bsdf.inputs['Roughness'].default_value = 0.9
    bsdf.inputs['Metallic'].default_value = 0.0
    attr = nt.nodes.new('ShaderNodeVertexColor')
    attr.layer_name = "Col"
    attr.location = (-320, 200)
    nt.links.new(attr.outputs['Color'], bsdf.inputs['Base Color'])
    me.materials.append(mat)


def main():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for coll in (bpy.data.meshes, bpy.data.materials):
        for d in list(coll):
            if d.users == 0:
                coll.remove(d)

    X, Y, Z, t = build_heightfield()
    ob = build_solid(X, Y, Z, t)
    me = ob.data
    activate(ob)

    sm = ob.modifiers.new("smooth", 'SMOOTH')
    sm.factor, sm.iterations = 0.45, 2
    apply_mod(ob, sm)

    px, py, pz, steep = find_cave_site(Z)
    print("cave wall: x=%.2f  surface y=%.2f  z=%.2f  steepness=%.2f" % (px, py, pz, steep))

    # --- decimate FIRST: dissolve -> triangulate -> collapse to budget ---
    d1 = ob.modifiers.new("dissolve", 'DECIMATE')
    d1.decimate_type = 'DISSOLVE'
    d1.angle_limit = math.radians(5.0)
    apply_mod(ob, d1)

    tr = ob.modifiers.new("tri", 'TRIANGULATE')
    apply_mod(ob, tr)

    f = len(me.polygons)
    pre_cave = max(1, TARGET_TRIS - 60)          # leave room for the cave faces
    d2 = ob.modifiers.new("collapse", 'DECIMATE')
    d2.decimate_type = 'COLLAPSE'
    d2.ratio = min(1.0, pre_cave / f)
    apply_mod(ob, d2)

    # --- locally refine the wall around the mouth, then bore the cave ---
    # The mesh has just been collapsed to chunky triangles; a boolean straight
    # into them would leave a jagged star-shaped hole. Subdividing only the
    # faces around the mouth keeps the overall low-poly look while giving the
    # cutter a fine enough boundary to produce a clean circular opening.
    def refine_near(radius, cuts):
        bm = bmesh.new()
        bm.from_mesh(me)
        sel = []
        for f in bm.faces:
            c = f.calc_center_median()
            if ((c.x - px) ** 2 + (c.z - pz) ** 2) < radius * radius \
                    and (py - CAVE_FRONT - 0.6) < c.y < (py + CAVE_DEPTH + 0.4):
                sel.append(f)
        if not sel:
            bm.free()
            return 0
        edges = set()
        for f in sel:
            edges.update(f.edges)
        bmesh.ops.subdivide_edges(bm, edges=list(edges), cuts=cuts,
                                  use_grid_fill=True)
        bm.to_mesh(me)
        bm.free()
        me.update()
        return len(sel)

    added = refine_near(CAVE_R + 1.20, 2)
    print("refined faces around mouth:", added, "-> tris now", len(me.polygons))

    depth = CAVE_FRONT + CAVE_DEPTH
    centre_y = py + (CAVE_DEPTH - CAVE_FRONT) / 2.0
    bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=CAVE_R, depth=depth,
                                        location=(px, centre_y, pz),
                                        rotation=(math.radians(90), 0, 0))
    cutter = bpy.context.object
    activate(ob)
    mb = ob.modifiers.new("cave", 'BOOLEAN')
    mb.operation = 'DIFFERENCE'
    mb.object = cutter
    mb.solver = 'EXACT'
    apply_mod(ob, mb)
    bpy.data.objects.remove(cutter, do_unlink=True)

    tr2 = ob.modifiers.new("tri2", 'TRIANGULATE')
    apply_mod(ob, tr2)

    # The local refinement pushed the count above budget. Collapse the rest of
    # the island back down while a vertex group pins the cave rim in place --
    # safe now that the shell is a closed manifold.
    vg = ob.vertex_groups.new(name="protect")
    for v in me.vertices:
        c = v.co
        near = ((c.x - px) ** 2 + (c.z - pz) ** 2) < (CAVE_R + 1.15) ** 2 \
            and (py - CAVE_FRONT) < c.y < (py + CAVE_DEPTH)
        vg.add([v.index], 0.0 if near else 1.0, 'REPLACE')

    f = len(me.polygons)
    if f > TARGET_TRIS:
        d3 = ob.modifiers.new("budget", 'DECIMATE')
        d3.decimate_type = 'COLLAPSE'
        d3.ratio = TARGET_TRIS / f
        d3.vertex_group = "protect"
        d3.vertex_group_factor = 1.0
        apply_mod(ob, d3)
        # a second, unweighted pass would eat the rim; instead accept the
        # small overshoot rather than tear the mouth open again.
    ob.vertex_groups.remove(ob.vertex_groups["protect"])

    # --- final cleanup -----------------------------------------------------
    # Boolean + collapse leave slivers (tiny degenerate triangles) and a few
    # doubled edges that show up as non-manifold. Weld, drop the slivers, close
    # whatever that opens, and re-triangulate so the export stays watertight.
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=2e-3)
    bmesh.ops.dissolve_degenerate(bm, dist=2e-3, edges=bm.edges)

    tiny = [f for f in bm.faces if f.calc_area() < 4e-4]
    if tiny:
        bmesh.ops.delete(bm, geom=tiny, context='FACES')

    # a doubled edge (3+ faces) means two coincident faces: drop the extras.
    # Collect first, delete once -- deleting inside the loop invalidates the
    # other edges still being iterated.
    doomed = []
    for e in bm.edges:
        if len(e.link_faces) > 2:
            keep = max(e.link_faces, key=lambda f: f.calc_area())
            for f in e.link_faces:
                if f is not keep:
                    doomed.append(f)
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

    colourise(me, (px, py, pz))
    make_material(me)

    bpy.context.preferences.filepaths.save_version = 0
    blend = os.path.join(OUT_DIR, NAME + ".blend")
    glb = os.path.join(OUT_DIR, NAME + ".glb")
    activate(ob)
    bpy.ops.wm.save_as_mainfile(filepath=blend)
    bpy.ops.export_scene.gltf(filepath=glb, export_format='GLB', use_selection=True,
                              export_apply=True, export_vertex_color='MATERIAL')
    zs = [v.co.z for v in me.vertices]
    print("faces: %d  verts: %d  z %.2f..%.2f" % (len(me.polygons), len(me.vertices),
                                                  min(zs), max(zs)))
    print("saved:", blend)
    print("saved:", glb)


if __name__ == "__main__":
    main()
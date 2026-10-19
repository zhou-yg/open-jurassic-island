"""把 .tscn 里的草/石实例抽成 {分组路径: {资产类型: [Transform3D 12 浮点]}}。

两个容易踩的坑（都踩过了，写在这里防止再犯）：

1. **必须合成祖先变换**。`local_scatter.tscn` 里真正带变换的是容器
   `Grass_000` / `Rock_000`，里面的 `GrassMesh` / `RockMesh` 才是 glb 实例
   且变换是单位阵。只看实例节点自己的 transform，会把 900 个草石全堆到原点。

2. **保留分组层级**。`Scatter/Grass/IslandGrass` 这种分组本身只有几个 Node3D，
   合并成 MultiMesh 只该解决"上千个节点"，不该把结构信息一起丢掉。
   每株道具自己的容器（`Rock_000` 这种带数字后缀的）会被折叠掉。

用 Python 文本解析而不是在 Godot 里 instantiate：island.gd 一 `_ready()` 就给
116 块地形 + 山体建三角面碰撞，转换脚本没必要付这个代价。
"""
import json
import re
import sys

PROPS = {
    "grass_tuft.glb": "grass_tuft",
    "grass_clump.glb": "grass_clump",
    "low_poly_rock.glb": "low_poly_rock",
}
NUM = r"[-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?"
IDENT = [1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0]
PER_PROP = re.compile(r"_\d+$")   # Rock_000 / Grass_179 → 每株道具自己的容器


def parse_scene(path):
    text = open(path, encoding="utf-8").read()

    ext_kind = {}
    for m in re.finditer(r'\[ext_resource[^\]]*?path="([^"]+)"[^\]]*?id="([^"]+)"\]', text):
        asset, rid = m.group(1), m.group(2)
        for key, kind in PROPS.items():
            if asset.endswith(key):
                ext_kind[rid] = kind

    nodes = {}   # path -> {"parent": path|None, "t": 12 floats, "kind": str|None}
    for blk in re.split(r"\n(?=\[node )", text):
        head = blk.split("\n", 1)[0]
        nm = re.search(r'name="([^"]+)"', head)
        if not nm:
            continue
        name = nm.group(1)
        pm = re.search(r'parent="([^"]*)"', head)
        parent = pm.group(1) if pm else None
        path_ = name if parent in (None, ".") else parent + "/" + name
        tm = re.search(r"^transform = Transform3D\(([^)]*)\)", blk, re.M)
        t = [float(x) for x in re.findall(NUM, tm.group(1))] if tm else list(IDENT)
        assert len(t) == 12, (path_, len(t))
        im = re.search(r'instance=ExtResource\("([^"]+)"\)', head)
        nodes[path_] = {"parent": None if parent == "." else parent,
                        "t": t, "kind": ext_kind.get(im.group(1)) if im else None}

    memo = {}

    def composed(path_):
        if path_ in memo:
            return memo[path_]
        n = nodes[path_]
        p = n["parent"]
        base = composed(p) if p else list(IDENT)
        out = compose(base, n["t"])
        memo[path_] = out
        return out

    def compose(a, b):
        """12 浮点表示的 3x4 矩阵相乘：返回 a·b（都按 Godot 的列优先 3 基向量 + 原点存）。"""
        def unpack(v):
            bx, by, bz, o = v[0:3], v[3:6], v[6:9], v[9:12]
            return bx, by, bz, o
        ax, ay, az, ao = unpack(a)
        bx, by, bz, bo = unpack(b)
        def tr(vec):  # 用 a 的基变换 vec
            return [ax[i] * vec[0] + ay[i] * vec[1] + az[i] * vec[2] for i in range(3)]
        ox = [ao[i] + tr(bo)[i] for i in range(3)]
        return tr(bx) + tr(by) + tr(bz) + ox

    out = {}
    for path_, n in nodes.items():
        if n["kind"] is None:
            continue
        # 跳过"道具内部的实例"（例如容器本身已经是实例的情况）
        p = n["parent"]
        nested = False
        while p:
            if nodes.get(p, {}).get("kind") is not None:
                nested = True
                break
            p = nodes[p]["parent"]
        if nested:
            continue
        parent_path = n["parent"] or ""
        segs = [s for s in parent_path.split("/") if s and not PER_PROP.search(s)]
        grp = "/".join(segs) if segs else "."
        out.setdefault(grp, {}).setdefault(n["kind"], []).append(
            [round(f, 4) for f in composed(path_)])
    return out


if __name__ == "__main__":
    src, dst = sys.argv[1], sys.argv[2]
    data = parse_scene(src)
    total = 0
    for grp, types in data.items():
        for t, v in types.items():
            total += len(v)
        print("  %-28s %s" % (grp, {k: len(v) for k, v in types.items()}))
    print("  total:", total)
    json.dump(data, open(dst, "w"), indent=0)
    print("wrote", dst)

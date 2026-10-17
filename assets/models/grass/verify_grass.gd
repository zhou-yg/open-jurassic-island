extends SceneTree
# 校验两款草资产的导入结果：顶点色是否接到材质、面数 / 高度 / 落地情况。
# 用法: Godot --headless --script res://assets/models/grass/verify_grass.gd

const ASSETS := [
	"res://assets/models/grass/grass_tuft.glb",
	"res://assets/models/grass/grass_clump.glb",
]


func _init() -> void:
	var failures := 0
	for path in ASSETS:
		var packed: PackedScene = load(path)
		if packed == null:
			push_error("[FAIL] 无法加载 %s" % path)
			failures += 1
			continue
		var root: Node = packed.instantiate()
		var mesh_instances: Array[MeshInstance3D] = []
		_collect(root, mesh_instances)
		print("=== %s ===" % path)
		if mesh_instances.is_empty():
			push_error("[FAIL] 没有 MeshInstance3D")
			failures += 1
		for mi in mesh_instances:
			var mesh := mi.mesh
			var aabb := mesh.get_aabb()
			var verts := 0
			var has_color := false
			for s in range(mesh.get_surface_count()):
				var arrays := mesh.surface_get_arrays(s)
				verts += (arrays[Mesh.ARRAY_VERTEX] as PackedVector3Array).size()
				if arrays[Mesh.ARRAY_COLOR] != null:
					var cols: PackedColorArray = arrays[Mesh.ARRAY_COLOR]
					if cols.size() > 0:
						has_color = true
						var lo := 1.0
						var hi := 0.0
						for c in cols:
							lo = minf(lo, minf(c.r, minf(c.g, c.b)))
							hi = maxf(hi, maxf(c.r, maxf(c.g, c.b)))
						print("  顶点色范围 %.4f ~ %.4f (%d 个)" % [lo, hi, cols.size()])
			var mat := mi.get_active_material(0)
			var vcol_ok := false
			if mat is BaseMaterial3D:
				vcol_ok = (mat as BaseMaterial3D).vertex_color_use_as_albedo
			print("  %s: 三角面=%d 顶点=%d 高度=%.3f 落地=%.3f 顶点色接材质=%s"
					% [mi.name, mesh.get_faces().size() / 3, verts, aabb.size.y, aabb.position.y, vcol_ok])
			if not has_color:
				push_error("[FAIL] %s 没有顶点色" % mi.name)
				failures += 1
			if not vcol_ok:
				push_error("[FAIL] %s 材质没启用 vertex_color_use_as_albedo" % mi.name)
				failures += 1
			if absf(aabb.position.y) > 0.01:
				push_error("[FAIL] %s 没有落在 y=0 平面上" % mi.name)
				failures += 1
		root.free()
	print("")
	if failures == 0:
		print("GRASS VERIFY: 全部通过")
	else:
		print("GRASS VERIFY: %d 项失败" % failures)
	quit(1 if failures > 0 else 0)


func _collect(node: Node, out: Array[MeshInstance3D]) -> void:
	if node is MeshInstance3D:
		out.append(node)
	for child in node.get_children():
		_collect(child, out)
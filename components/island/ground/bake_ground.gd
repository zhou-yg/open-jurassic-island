extends SceneTree
## 把 Ground 下成百上千个 plain_terrain 实例烘成**一个** MultiMesh。
##
## 为什么：`Ground` 原来是 116 个 `plain_terrain.glb` 实例 —— 每个实例都是一整棵
## 场景（MeshInstance3D + 导入材质 + 节点 + `_ready()`），4 个表面就是 4 个
## draw call，116 个实例 = 464 个 draw call；`island.gd` 还要给每个实例单独补一个
## StaticBody3D + 一份三角面碰撞（116 份形状数据）。
##
## 这些地块用的是**同一份网格**（只是变换不同），正是 MultiMesh 的场景：
##   - 节点数：116 → 1（`Ground/Terrain`）
##   - draw call：464 → 4（每个表面 1 个）
##   - 网格内存：116 份 → 1 份；碰撞形状也从 116 份变成 1 份共享
##
## 摆放数据存在 `island_ground.json`（可读、可手改），烘出来的是
## `island_ground.res`（二进制 MultiMesh）。要挪地块：改 JSON → 重烘。
##
## 用法（**必须带真实渲染器，不要加 `--headless`**）：
## [codeblock]
## # 从旧场景提取（第一次迁移用；场景里得还有逐块的 MeshInstance3D）
## godot --path . --script res://components/island/ground/bake_ground.gd -- \
##       res://components/island/island.tscn \
##       res://components/island/ground/island_ground.json \
##       res://components/island/ground/island_ground.res
##
## # 日常：改完 JSON 重烘（只给两个参数）
## godot --path . --script res://components/island/ground/bake_ground.gd -- \
##       res://components/island/ground/island_ground.json \
##       res://components/island/ground/island_ground.res
## [/codeblock]
##
## ⚠️ 为什么不能 headless：MultiMesh 的实例变换建立在 RenderingServer 上，headless 的
## dummy 渲染器会把 `set_instance_transform` 全丢掉，存出来是一堆零矩阵（det = 0，
## 加载时物理会直接报错）。和 `ground_scatter/bake_scatter.gd` 是同一个坑。

## 地块用的网格。JSON 里没有 glb 字段时用这里的默认值。
const TERRAIN_GLB := "res://assets/models/plain-terrain/plain_terrain.glb"
## 从场景提取时只认这个节点下的 MeshInstance3D。
const GROUND_NODE := "Ground"


func _initialize() -> void:
	var args := OS.get_cmdline_user_args()
	if args.is_empty():
		push_error("用法: -- <scene.tscn> <out.json> <out.res>  |  -- <json> <out.res>")
		quit(1)
		return
	var src: String = args[0]
	var from_json := src.get_extension() == "json"

	var data: Dictionary
	var out_res: String
	var out_json := ""
	if from_json:
		if args.size() < 2:
			push_error("用法: -- <json> <out.res>")
			quit(1)
			return
		data = _load_json(src)
		out_res = args[1]
	else:
		if args.size() < 3:
			push_error("用法: -- <scene.tscn> <out.json> <out.res>")
			quit(1)
			return
		out_json = args[1]
		out_res = args[2]
		data = _extract_from_scene(src)

	if data.is_empty() or not data.has("patches"):
		quit(1)
		return

	var mesh := _mesh_of(String(data.get("glb", TERRAIN_GLB)))
	if mesh == null:
		push_error("取不到网格: " + String(data.get("glb", TERRAIN_GLB)))
		quit(1)
		return

	var transforms: Array = data["patches"]
	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	mm.instance_count = transforms.size()
	for i in transforms.size():
		mm.set_instance_transform(i, _to_transform(transforms[i]))
	mm.mesh = mesh

	# JSON 里记下烘出来的实例数，方便和 .res 对账。
	if out_json != "":
		data["instances"] = mm.instance_count
		data["surfaces"] = mesh.get_surface_count()
		_write_json(out_json, data)
		print("EXTRACTED ", out_json)

	var err := ResourceSaver.save(mm, out_res)
	if err != OK:
		push_error("保存 MultiMesh 失败 %s -> %d" % [out_res, err])
		quit(1)
		return
	print("BAKED ", out_res)
	print("  实例 %d / 表面 %d / 顶点 %d" % [
		mm.instance_count, mesh.get_surface_count(), _vertex_count(mesh)])
	quit()


## ---------------- 提取 / 读写 ----------------

## 把场景里 Ground 下的每个 MeshInstance3D 的位置烘成 JSON。
func _extract_from_scene(path: String) -> Dictionary:
	var packed := load(path) as PackedScene
	if packed == null:
		push_error("场景读不出来: " + path)
		quit(1)
		return {}
	var root := packed.instantiate()
	var ground := root.get_node_or_null(GROUND_NODE)
	if ground == null:
		push_error("场景里没有 %s 节点: %s" % [GROUND_NODE, path])
		root.free()
		quit(1)
		return {}

	var patches: Array = []
	var glb := TERRAIN_GLB
	var first_mesh: Mesh = null
	var mixed := false
	for node in ground.find_children("*", "MeshInstance3D", true, false):
		var mi := node as MeshInstance3D
		if mi.mesh == null:
			continue
		if first_mesh == null:
			first_mesh = mi.mesh
		elif mi.mesh != first_mesh:
			# MultiMesh 只能有一个网格；混了别的资产就不是"同一块地形换变换"了
			mixed = true
			break
		patches.append(_to_array(_relative_transform(mi, ground)))
	root.free()

	if mixed:
		push_error("Ground 下的网格不是同一份，不能合批: " + path)
		quit(1)
		return {}
	if patches.is_empty():
		push_error("Ground 下没有 MeshInstance3D: " + path)
		quit(1)
		return {}
	return {"glb": glb, "patches": patches}


func _load_json(path: String) -> Dictionary:
	var data = JSON.parse_string(FileAccess.get_file_as_string(path))
	if data == null or not data.has("patches"):
		push_error("JSON 读不出来或缺少 patches: " + path)
		quit(1)
		return {}
	return data


func _write_json(path: String, data: Dictionary) -> void:
	var f := FileAccess.open(path, FileAccess.WRITE)
	if f == null:
		push_error("JSON 写不进去: " + path)
		quit(1)
		return
	f.store_string(JSON.stringify(data, "  ", false, true) + "\n")
	f.close()


## ---------------- 变换 / 网格 ----------------

## node 相对 ancestor 的变换。逐级乘本地变换，不依赖节点在树里
## （提取阶段场景只是 instantiate 过，没有进树，global_transform 全是单位矩阵）。
func _relative_transform(node: Node3D, ancestor: Node3D) -> Transform3D:
	var t := Transform3D()
	var n: Node = node
	while n != null and n != ancestor:
		t = (n as Node3D).transform * t
		n = n.get_parent()
	return t


## 一行 12 个 float：basis.x, basis.y, basis.z, origin（与散布的 JSON 一致）。
func _to_array(t: Transform3D) -> Array:
	return [t.basis.x.x, t.basis.x.y, t.basis.x.z,
		t.basis.y.x, t.basis.y.y, t.basis.y.z,
		t.basis.z.x, t.basis.z.y, t.basis.z.z,
		t.origin.x, t.origin.y, t.origin.z]


func _to_transform(v: Array) -> Transform3D:
	return Transform3D(
		Vector3(v[0], v[1], v[2]),
		Vector3(v[3], v[4], v[5]),
		Vector3(v[6], v[7], v[8]),
		Vector3(v[9], v[10], v[11]))


## glb 里取第一个 MeshInstance3D 的网格（与 bake_scatter.gd 同一套办法）。
func _mesh_of(glb_path: String) -> Mesh:
	var inst := (load(glb_path) as PackedScene).instantiate()
	var found: Mesh = null
	var stack: Array[Node] = [inst]
	while not stack.is_empty():
		var n: Node = stack.pop_back()
		if n is MeshInstance3D and (n as MeshInstance3D).mesh != null:
			found = (n as MeshInstance3D).mesh
			break
		for c in n.get_children():
			stack.append(c)
	inst.free()
	return found


func _vertex_count(mesh: Mesh) -> int:
	var total := 0
	for s in mesh.get_surface_count():
		total += mesh.surface_get_arrays(s)[Mesh.ARRAY_VERTEX].size()
	return total

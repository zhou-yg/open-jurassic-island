extends SceneTree
## 把散点 JSON 烘成 MultiMesh 场景：每个"分组 × 资产"只有 1 个 MultiMeshInstance3D。
##
## 输入：extract 脚本产出的 JSON，形如
##   { "Scatter/Grass/IslandGrass": {"grass_tuft": [[12 floats], ...], ...}, ... }
## 输出：一个场景（根上挂 ground_scatter.gd）+ 每个资产一份二进制 .res（MultiMesh）。
##
## 用法：
##   godot --headless --path . --script res://components/island/ground_scatter/bake_scatter.gd \
##         -- <json> <out_tscn> <res_dir> <res_prefix>
##
## 为什么不把 MultiMesh 内联进 .tscn：上千个 3×4 矩阵写成文本非常臃肿，
## 二进制 .res 更小、加载也更快；.tscn 里只留几个节点和引用。

const SCRIPT_PATH := "res://components/island/ground_scatter/ground_scatter.gd"

const TYPES := {
	"grass_tuft": {
		"glb": "res://assets/models/grass/grass_tuft.glb",
		"node": "GrassTuft",
		"shadow": false,     # 草不投影：上千棵草的阴影纯属浪费
	},
	"grass_clump": {
		"glb": "res://assets/models/grass/grass_clump.glb",
		"node": "GrassClump",
		"shadow": false,
	},
	"low_poly_rock": {
		"glb": "res://assets/models/low-poly-rock/low_poly_rock.glb",
		"node": "Rock",
		"shadow": true,
	},
}


func _mesh_of(glb_path: String) -> Mesh:
	var inst: Node = load(glb_path).instantiate()
	var found: Mesh = null
	var stack: Array[Node] = [inst]
	while not stack.is_empty():
		var n: Node = stack.pop_back()
		if n is MeshInstance3D and n.mesh != null:
			found = n.mesh
			break
		for c in n.get_children():
			stack.append(c)
	inst.free()
	return found


## 按 "A/B/C" 逐级建 Node3D 容器（保留原来的分组路径语义）。
func _ensure_container(root: Node3D, cache: Dictionary, rel: String) -> Node3D:
	if rel == "" or rel == ".":
		return root
	if cache.has(rel):
		return cache[rel]
	var parent_rel := rel.get_base_dir()
	if parent_rel == ".":
		parent_rel = ""
	var parent := _ensure_container(root, cache, parent_rel)
	var holder := Node3D.new()
	holder.name = rel.get_file()
	parent.add_child(holder)
	holder.owner = root
	cache[rel] = holder
	return holder


func _process(_dt: float) -> bool:
	var args := OS.get_cmdline_user_args()
	if args.size() < 4:
		push_error("用法: -- <json> <out_tscn> <res_dir> <res_prefix>")
		quit(1)
		return true
	var json_path: String = args[0]
	var out_tscn: String = args[1]
	var res_dir: String = args[2]
	var prefix: String = args[3]

	var data: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(json_path))
	if data == null:
		push_error("JSON 读不出来: " + json_path)
		quit(1)
		return true

	# 所有分组共有的第一段（island 的 "Scatter"）就是场景根，不该再套一层
	var strip := ""
	if not data.has("."):
		var firsts := {}
		for g in data.keys():
			firsts[(g as String).split("/")[0]] = true
		if firsts.size() == 1:
			strip = String(firsts.keys()[0]) + "/"

	var root := Node3D.new()
	root.name = "GroundScatter"
	root.set_script(load(SCRIPT_PATH))
	var containers := {}
	var summary: Array = []

	for group_path in data.keys():
		var types: Dictionary = data[group_path]
		var rel := String(group_path)
		if strip != "" and rel.begins_with(strip):
			rel = rel.substr(strip.length())
		var holder := _ensure_container(root, containers, rel)

		for kind in types.keys():
			if not TYPES.has(kind):
				push_warning("未知资产类型: " + String(kind))
				continue
			var spec: Dictionary = TYPES[kind]
			var transforms: Array = types[kind]
			var mesh := _mesh_of(String(spec["glb"]))
			if mesh == null:
				push_error("取不到网格: " + String(spec["glb"]))
				continue

			var mm := MultiMesh.new()
			mm.transform_format = MultiMesh.TRANSFORM_3D
			mm.instance_count = transforms.size()
			for i in transforms.size():
				var v: Array = transforms[i]
				mm.set_instance_transform(i, Transform3D(
						Vector3(v[0], v[1], v[2]),
						Vector3(v[3], v[4], v[5]),
						Vector3(v[6], v[7], v[8]),
						Vector3(v[9], v[10], v[11])))
			mm.mesh = mesh

			var tag := "flat" if rel == "" or rel == "." else rel.replace("/", "_")
			var res_path := "%s/%s_%s_%s.res" % [res_dir, prefix, tag, kind]
			var err: int = ResourceSaver.save(mm, res_path)
			if err != OK:
				push_error("保存 MultiMesh 失败 %s -> %d" % [res_path, err])
				continue

			var mmi := MultiMeshInstance3D.new()
			mmi.name = String(spec["node"])
			mmi.multimesh = load(res_path)
			mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON if spec["shadow"] \
					else GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
			mmi.gi_mode = GeometryInstance3D.GI_MODE_DISABLED
			holder.add_child(mmi)
			mmi.owner = root
			summary.append("%s / %s = %d" % [rel if rel != "" else ".", spec["node"], transforms.size()])

	var ps := PackedScene.new()
	var perr: int = ps.pack(root)
	if perr != OK:
		push_error("pack 失败 %d" % perr)
		quit(1)
		return true
	var serr: int = ResourceSaver.save(ps, out_tscn)
	if serr != OK:
		push_error("保存场景失败 %s -> %d" % [out_tscn, serr])
		quit(1)
		return true
	print("BUILT ", out_tscn)
	for line in summary:
		print("  ", line)
	quit()
	return true

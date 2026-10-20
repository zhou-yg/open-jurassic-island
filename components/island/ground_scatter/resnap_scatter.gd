extends SceneTree
## 把散点 JSON 里指定分组的道具重新贴到"它正下方的那个面"上。
##
## 什么时候需要：挪动山体 / 地形之后。散点是烘死的坐标，山一挪，
## 原本站在山脚地形上的石头石头就悬空或陷进去了。这个工具对每个道具
## 从其上方 6 m 往下打一条射线，命中山体就贴山体、命中地面就贴地面。
##
## 用法（**带真实渲染器**，要物理）：
##   godot --path . --script res://components/island/ground_scatter/resnap_scatter.gd -- \
##         <json> <分组名包含的子串>

var _scene: Node
var _frames := 0
var _done := false


func _initialize() -> void:
	var a := OS.get_cmdline_user_args()
	if a.size() < 2:
		push_error("用法: -- <json> <分组子串>")
		quit(1)
		return
	_scene = load("res://components/island/island.tscn").instantiate()
	root.add_child(_scene)


var _exclude: Array[RID] = []


func _surface_below(x: float, y: float, z: float) -> float:
	var q := PhysicsRayQueryParameters3D.create(Vector3(x, y + 6.0, z), Vector3(x, y - 6.0, z))
	# 石头也有碰撞体：不排除的话，草会被"贴"到旁边石头的顶上，越修越错
	q.exclude = _exclude
	var hit := root.world_3d.direct_space_state.intersect_ray(q)
	if hit.is_empty():
		return -INF
	return (hit["position"] as Vector3).y


func _process(_dt: float) -> bool:
	if _done:
		return true
	_frames += 1
	if _frames < 10:
		return false
	_done = true

	# 排除散布石头的碰撞体，只让射线打地形和山体
	var sc := _scene.get_node_or_null("Scatter")
	if sc != null:
		for b in sc.find_children("*", "StaticBody3D", true, false):
			_exclude.append((b as StaticBody3D).get_rid())

	var a := OS.get_cmdline_user_args()
	var json_path: String = a[0]
	var needle: String = a[1]
	var data: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(json_path))
	var moved := 0
	var missed := 0
	var culled := 0
	for grp in data.keys():
		if needle != "*" and not String(grp).contains(needle):
			continue
		for kind in data[grp]:
			var kept: Array = []
			for row in data[grp][kind]:
				var x: float = row[9]
				var y: float = row[10]
				var z: float = row[11]
				var h := _surface_below(x, y, z)
				if h == -INF:
					missed += 1
					kept.append(row)
					continue
				if h - y > 0.5:
					# 头顶的地面比它还高 → 被山体/地形埋住了，直接剔除
					culled += 1
					continue
				if absf(h - y) > 0.02:
					row[10] = snappedf(h, 0.0001)
					moved += 1
				kept.append(row)
			data[grp][kind] = kept
	json_dump(json_path, data)
	print("RESNAP  贴地 %d 个，剔除埋没 %d 个，未命中 %d 个（分组含 '%s'）" % [moved, culled, missed, needle])
	quit()
	return true


func json_dump(path: String, data: Dictionary) -> void:
	var f := FileAccess.open(path, FileAccess.WRITE)
	f.store_string(JSON.stringify(data, "", false))
	f.close()

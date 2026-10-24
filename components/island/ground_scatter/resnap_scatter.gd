extends SceneTree
## 把散点 JSON 里指定分组的道具重新贴到"它正下方的那个面"上。
##
## 什么时候需要：挪动山体 / 地形之后。散点是烘死的坐标，山一挪，
## 原本站在山脚地形上的石头石头就悬空或陷进去了。这个工具对每个道具
## 从其上方 6 m 往下打一条射线，命中山体就贴山体、命中地面就贴地面。
##
## 用法：
##   godot --path . --script res://components/island/ground_scatter/resnap_scatter.gd -- \
##         <json> <分组名包含的子串> [场景] [模式] [上窗口] [下窗口]
##
##   场景      默认 res://components/island/island.tscn
##   模式      drop（默认）/ project / slide
##             drop    往下贴：高了就落下来，埋进面里（高了 0.5 m 以上）的直接剔除
##             project 双向贴：不管高了低了都放到正下方那个面上，一个不删
##             slide   沿坡滑：保住道具原来的高度，沿坡面找到该高度所在的位置
##                     （换山用 —— 新山更陡，同一个高度对应的半径不一样）
##   上/下窗口  射线窗口（米），默认 6
##
## 改完 JSON 记得重新烘 MultiMesh（bake_scatter.gd，**不能**加 --headless）。

const DEFAULT_SCENE := "res://components/island/island.tscn"

var _scene: Node
var _frames := 0
var _done := false
var _mode := "drop"
var _up := 6.0
var _down := 6.0
var _peak := Vector3.ZERO
var _has_peak := false


func _initialize() -> void:
	var a := OS.get_cmdline_user_args()
	if a.size() < 2:
		push_error("用法: -- <json> <分组子串> [场景] [模式] [上窗口] [下窗口]")
		quit(1)
		return
	var scene_path: String = a[2] if a.size() > 2 else DEFAULT_SCENE
	_mode = a[3] if a.size() > 3 else "drop"
	if a.size() > 4:
		_up = float(a[4])
	if a.size() > 5:
		_down = float(a[5])
	_scene = load(scene_path).instantiate()
	root.add_child(_scene)


var _exclude: Array[RID] = []


## 从 (x, y, z) 上方 up、下方 down 打一条射线，返回命中面的高度（没有命中返回 -INF）。
func _surface_below(x: float, y: float, z: float, up: float, down: float) -> float:
	var q := PhysicsRayQueryParameters3D.create(Vector3(x, y + up, z), Vector3(x, y - down, z))
	# 石头也有碰撞体：不排除的话，草会被"贴"到旁边石头的顶上，越修越错
	q.exclude = _exclude
	var hit := root.world_3d.direct_space_state.intersect_ray(q)
	if hit.is_empty():
		return -INF
	return (hit["position"] as Vector3).y


## 山体最高点（世界坐标）。slide 模式拿它当坡面的"顶"。
func _find_peak() -> void:
	var best := Vector3.ZERO
	var best_y := -INF
	for node in _scene.find_children("*", "MeshInstance3D", true, false):
		var mi := node as MeshInstance3D
		if mi.mesh == null:
			continue
		if not str(mi.get_path()).contains("Mountain"):
			continue
		for v in mi.mesh.surface_get_arrays(0)[Mesh.ARRAY_VERTEX]:
			var w: Vector3 = mi.global_transform * v
			if w.y > best_y:
				best_y = w.y
				best = w
	_peak = best
	_has_peak = best_y > -INF


## 沿"从峰顶往外"的方向找：地表高度第一次低于 target 的那个位置。
## 返回 [位置, 命中高度]；走到底还没降到 target 就返回最后扫到的位置。
func _slide_to(target: float, dir: Vector2) -> Array:
	var found := Vector3.ZERO
	var found_h := 0.0
	var last := Vector3.ZERO
	var last_h := 0.0
	var got := false
	var step := 0.5
	for i in range(1, 61):
		var r := i * step
		var p := Vector3(_peak.x + dir.x * r, 0.0, _peak.z + dir.y * r)
		var h := _surface_below(p.x, _peak.y, p.z, 10.0, 60.0)
		if h == -INF:
			break
		last = p
		last_h = h
		got = true
		if h <= target:
			found = p
			found_h = h
			return [found, found_h]
	found = last
	found_h = last_h
	return [found, found_h] if got else [Vector3.ZERO, -INF]


func _process(_dt: float) -> bool:
	if _done:
		return true
	_frames += 1
	if _frames < 10:
		return false
	_done = true

	# 排除散布石头的碰撞体，只让射线打地形和山体
	for sc in _scene.find_children("*", "Node3D", true, false):
		if not String(sc.name).contains("Scatter"):
			continue
		for b in sc.find_children("*", "StaticBody3D", true, false):
			_exclude.append((b as StaticBody3D).get_rid())

	if _mode == "slide":
		_find_peak()
		if not _has_peak:
			push_error("slide 模式找不到山体（场景里没有名字含 Mountain 的网格）")
			quit(1)
			return true

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
				var h := _surface_below(x, y, z, _up, _down)
				if h == -INF:
					missed += 1
					kept.append(row)
					continue
				if _mode == "slide":
					# 保住原来的高度，沿坡面挪到该高度所在的位置
					var dir := Vector2(x - _peak.x, z - _peak.z)
					if dir.length() < 0.001:
						dir = Vector2(1.0, 0.0)
					dir = dir.normalized()
					var res := _slide_to(y, dir)
					var p: Vector3 = res[0]
					var ph: float = res[1]
					if ph == -INF:
						missed += 1
						kept.append(row)
						continue
					if absf(p.x - x) > 0.001 or absf(p.z - z) > 0.001 or absf(ph - y) > 0.001:
						row[9] = snappedf(p.x, 0.0001)
						row[10] = snappedf(ph, 0.0001)
						row[11] = snappedf(p.z, 0.0001)
						moved += 1
					kept.append(row)
					continue
				if _mode == "project":
					# 不删，只放到正下方的面上（差 0.35 m 以内算已经贴地，不动它）
					if absf(h - y) > 0.35:
						row[10] = snappedf(h, 0.0001)
						moved += 1
					kept.append(row)
					continue
				# drop
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
	print("RESNAP  贴地 %d 个，剔除埋没 %d 个，未命中 %d 个（分组含 '%s'，模式 %s）" % [
		moved, culled, missed, needle, _mode])
	quit()
	return true


func json_dump(path: String, data: Dictionary) -> void:
	var f := FileAccess.open(path, FileAccess.WRITE)
	f.store_string(JSON.stringify(data, "", false))
	f.close()

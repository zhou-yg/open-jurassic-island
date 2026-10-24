extends SceneTree
## 烘"主场景用的局部入口"：大门 + 向两侧延伸的断续残墙 + 断口碎石 + 倒伏墙。
##
## 和 `park_perimeter.tscn`（展示岛用的环岛围墙）不是同一个东西：
##   主场景的岛是 2000 m 量级、`Island` 节点还带 32 倍非等比缩放，
##   一个 60 m 的环形围墙放进去只会是地图上一个小点。所以这里只做**入口本身**：
##   10.41 m 宽的大门 + 两侧各 ~22 m 的残墙，按 1:1 米制摆在出生点正前方。
##
## 位置锚定在出生点：`jurassic-island.tscn` 的 Player 在 (0, 34, 77.85)，
## 地面在 y≈32。门放在 z = 66（出生点前方 12 m），面朝 +Z 冲着玩家。
## 玩家位置改了要同步改 `GATE_Z` 并重烘。
##
## 用法（**必须带真实渲染器**）：
##   godot --path . --script res://components/island/park_perimeter/bake_entrance_local.gd -- <out_tscn> [seed]

const SCENE := "res://scenes-3d/jurassic-island/jurassic-island.tscn"
const GATE_SCENE := "res://components/island/park_gate/park_gate.tscn"
const WALL_SCENE := "res://assets/models/ruined-wall/low_poly_ruined_wall.glb"
const RUBBLE_SCENE := "res://assets/models/stone-rubble/low_poly_rubble.glb"

const GATE_X := 0.0
const GATE_Z := 66.0          # 出生点 (0, 77.85) 前方 12 m
const SEG_LEN := 2.90
const GATE_HALF_W := 5.05
const EXTEND_M := 24.0        # 每侧墙延伸多长
const STEP_BREAK := 0.50
const SINK := 0.06
const RUN_MIN := 1
const RUN_MAX := 4
const GAP_MIN := 1.3
const GAP_MAX := 3.8
const TURN_DEG := 5.0         # 每个塌口允许微转，避免一条死直线
const FALLEN_CHANCE := 0.35

var _scene: Node
var _frames := 0
var _done := false
var _rng := RandomNumberGenerator.new()


func _initialize() -> void:
	var args := OS.get_cmdline_user_args()
	if args.is_empty():
		push_error("用法: -- <out_tscn> [seed]")
		quit(1)
		return
	_rng.seed = int(args[1]) if args.size() > 1 else 20260715
	_scene = load(SCENE).instantiate()
	root.add_child(_scene)
	# 静态草石 + 玩家 + **上一版入口**都带碰撞，射线会打在它们身上，先清掉。
	# 入口自己尤其要清：不然射线打在大门身上，重烘出来还是原地不动。
	for nm in ["LocalScatter", "Player", "ParkEntrance"]:
		var x := _scene.get_node_or_null(nm)
		if x != null:
			x.free()


func _ground(x: float, z: float) -> float:
	var q := PhysicsRayQueryParameters3D.create(Vector3(x, 900.0, z), Vector3(x, -400.0, z))
	var hit := root.world_3d.direct_space_state.intersect_ray(q)
	if hit.is_empty():
		return -INF
	return (hit["position"] as Vector3).y


func _yaw_of(h: Vector2) -> float:
	return atan2(-h.y, h.x)


func _process(_dt: float) -> bool:
	if _done:
		return true
	_frames += 1
	if _frames < 10:
		return false
	_done = true

	var out_path: String = OS.get_cmdline_user_args()[0]
	var root_node := Node3D.new()
	root_node.name = "ParkEntrance"
	var walls_root := Node3D.new()
	walls_root.name = "Walls"
	root_node.add_child(walls_root)
	walls_root.owner = root_node
	var debris_root := Node3D.new()
	debris_root.name = "Debris"
	root_node.add_child(debris_root)
	debris_root.owner = root_node

	var gate_pos := Vector2(GATE_X, GATE_Z)
	var gate_y := _ground(gate_pos.x, gate_pos.y)
	var gate_dir := Vector2(0, 1)      # 朝 +Z（冲着出生点）
	var tangent := Vector2(1, 0)

	var gate: Node3D = load(GATE_SCENE).instantiate()
	gate.name = "Gate"
	gate.position = Vector3(gate_pos.x, gate_y - SINK, gate_pos.y)
	gate.rotation.y = 0.0
	root_node.add_child(gate)
	gate.owner = root_node

	var wall_n := 0
	var rubble_n := 0
	var fallen_n := 0

	for side: float in [1.0, -1.0] as Array[float]:
		var pos: Vector2 = gate_pos + tangent * (GATE_HALF_W * side)
		var heading: Vector2 = tangent * side
		var walked := 0.0
		var last_y := gate_y
		var guard := 0
		while walked < EXTEND_M and guard < 60:
			guard += 1
			var k := _rng.randi_range(RUN_MIN, RUN_MAX)
			var placed := 0
			for i in k:
				var c: Vector2 = pos + heading * (SEG_LEN * 0.5)
				var y := _ground(c.x, c.y)
				if y == -INF:
					break
				if placed > 0 and absf(y - last_y) > STEP_BREAK:
					break
				var w: Node3D = load(WALL_SCENE).instantiate()
				w.name = "Wall_%s_%02d" % ["E" if side > 0 else "W", wall_n]
				var extra := 0.0 if _rng.randf() > 0.3 else _rng.randf_range(0.1, 0.5)
				w.position = Vector3(c.x, y - SINK - extra, c.y)
				w.rotation.y = _yaw_of(heading)
				walls_root.add_child(w)
				w.owner = root_node
				wall_n += 1
				placed += 1
				last_y = y
				pos += heading * SEG_LEN
				walked += SEG_LEN
			if placed == 0:
				pos += heading * (k * SEG_LEN)
				walked += k * SEG_LEN

			var gap := _rng.randf_range(GAP_MIN, GAP_MAX)
			var gc: Vector2 = pos + heading * (gap * 0.5)
			var gy := _ground(gc.x, gc.y)
			if gy != -INF:
				var r: Node3D = load(RUBBLE_SCENE).instantiate()
				r.name = "Rubble_%02d" % rubble_n
				r.position = Vector3(gc.x, gy - SINK, gc.y)
				r.rotation.y = _rng.randf_range(0.0, TAU)
				var sc := _rng.randf_range(1.0, 1.6)
				r.scale = Vector3(sc, _rng.randf_range(0.85, 1.2), sc)
				debris_root.add_child(r)
				r.owner = root_node
				rubble_n += 1
				if _rng.randf() < FALLEN_CHANCE:
					var f: Node3D = load(WALL_SCENE).instantiate()
					f.name = "Fallen_%02d" % fallen_n
					var lean := _rng.randf_range(1.50, 1.62) * (-1.0 if _rng.randf() < 0.5 else 1.0)
					f.basis = Basis(Vector3.UP, _yaw_of(heading)) * Basis(Vector3.RIGHT, lean)
					f.position = Vector3(gc.x - heading.x * 0.6, gy - 0.30, gc.y - heading.y * 0.6)
					debris_root.add_child(f)
					f.owner = root_node
					fallen_n += 1
			pos += heading * gap
			walked += gap
			# 每个塌口微转一点，墙体不是一条死直线
			heading = heading.rotated(_rng.randf_range(-1.0, 1.0) * deg_to_rad(TURN_DEG))

	# 门口撞击堆
	for sgn: float in [1.0, -1.0] as Array[float]:
		var bp: Vector2 = gate_pos + tangent * (GATE_HALF_W * sgn) + gate_dir * 0.7
		var by := _ground(bp.x, bp.y)
		if by == -INF:
			continue
		var rb: Node3D = load(RUBBLE_SCENE).instantiate()
		rb.name = "GateHit_%s" % ("E" if sgn > 0 else "W")
		rb.position = Vector3(bp.x, by - SINK, bp.y)
		rb.rotation.y = _rng.randf_range(0.0, TAU)
		var sb := _rng.randf_range(0.9, 1.2)
		rb.scale = Vector3(sb, _rng.randf_range(0.7, 1.0), sb)
		debris_root.add_child(rb)
		rb.owner = root_node

	var ps := PackedScene.new()
	if ps.pack(root_node) != OK:
		push_error("pack 失败")
		quit(1)
		return true
	if ResourceSaver.save(ps, out_path) != OK:
		push_error("保存失败: " + out_path)
		quit(1)
		return true

	print("BAKED ", out_path)
	print("  gate (%.2f, %.2f, %.2f)  walls=%d  rubble=%d  fallen=%d" % [
		gate.position.x, gate.position.y, gate.position.z, wall_n, rubble_n, fallen_n])
	quit()
	return true

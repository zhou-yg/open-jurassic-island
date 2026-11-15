extends Node
## 烘"主场景用的局部入口"：大门 + 向两侧延伸的断续残墙 + 断口碎石 + 倒伏墙。
##
## 和 `park_perimeter.tscn`（展示岛用的环岛围墙）不是同一个东西：
##   主场景的岛是 2000 m 量级、`Island` 节点还带 32 倍非等比缩放，
##   一个 60 m 的环形围墙放进去只会是地图上一个小点。所以这里只做**入口本身**：
##   10.41 m 宽的大门 + 两侧各 ~22 m 的残墙，按 1:1 米制摆在出生点正前方。
##
## 位置锚定在出生点：`jurassic-island.tscn` 的 Player 在 (0, 9.2, 55)，
## 地面在 y≈8.3。门放在 z = 43（出生点前方 12 m），面朝 +Z 冲着玩家。
## 玩家位置改了要同步改 `GATE_Z` 并重烘。
##
## 用法（**必须带真实渲染器**）：
##   godot --path . --script res://components/island/park_perimeter/bake_entrance_local.gd -- <out_tscn> [seed]

const SCENE := "res://scenes-3d/jurassic-island/jurassic-island.tscn"
const GATE_SCENE := "res://components/island/park_gate/park_gate.tscn"
const WALL_SCENE := "res://assets/models/ruined-wall/low_poly_ruined_wall.glb"
const RUBBLE_SCENE := "res://assets/models/stone-rubble/low_poly_rubble.glb"

## 默认输出路径（挂进场景跑时用；命令行可以覆盖）。
const DEFAULT_OUT := "res://components/island/park_perimeter/park_entrance_local.tscn"
const GATE_X := 0.0
const GATE_Z := 43.0          # 出生点 (0, 55) 前方 12 m（岛缩小一半后同步）
const SEG_LEN := 2.90
const GATE_HALF_W := 5.05
## 大门的缩放（1 = 原模型尺寸 10.56 × 6.24 m）。
const GATE_SCALE := 0.6
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
## 物理服务器收敛了没有。
var _settled := false


func _ready() -> void:
	var args := OS.get_cmdline_user_args()
	if args.is_empty():
		# 挂进场景跑（后台模式）时没有命令行参数 —— 用默认输出路径。
		print("没有命令行参数，输出到默认路径: ", DEFAULT_OUT)
	_rng.seed = int(args[1]) if args.size() > 1 else 20260715
	_scene = load(SCENE).instantiate()
	get_tree().root.add_child.call_deferred(_scene)
	# 静态草石 + 玩家 + **上一版入口**都带碰撞，射线会打在它们身上，先清掉。
	# 入口自己尤其要清：不然射线打在大门身上，重烘出来还是原地不动。
	for nm in ["LocalScatter", "Player", "ParkEntrance"]:
		var x := _scene.get_node_or_null(nm)
		if x != null:
			x.free()


func _ground(x: float, z: float) -> float:
	var q := PhysicsRayQueryParameters3D.create(Vector3(x, 900.0, z), Vector3(x, -400.0, z))
	var hit := get_tree().root.world_3d.direct_space_state.intersect_ray(q)
	if hit.is_empty():
		return -INF
	return (hit["position"] as Vector3).y


## 物理服务器是不是**收敛**了：同一批探针连续两轮量出来的地面高度完全一样，
## 而且每一轮都得打得到地面（打不到 = 地形碰撞还没进物理服务器）。
func _physics_settled() -> bool:
	var points := PackedVector2Array()
	for i in 64:
		var a := TAU * i / 64.0
		for r in [20.0, 60.0, 120.0, 200.0, 300.0]:
			points.append(Vector2(cos(a) * r, 66.0 + sin(a) * r * 0.5))
	var prev := PackedFloat32Array()
	for p in 12:
		var cur := PackedFloat32Array()
		var miss := 0
		for pt in points:
			var y := _ground(pt.x, pt.y)
			if y == -INF:
				miss += 1
			cur.append(y)
		if float(miss) / float(points.size()) > 0.05:
			prev = cur
			continue
		if p > 0 and cur == prev:
			return true
		prev = cur
	return false


func _yaw_of(h: Vector2) -> float:
	return atan2(-h.y, h.x)


func _process(_dt: float) -> void:
	if _done:
		return
	if _scene == null or not _scene.is_inside_tree():
		return
	_frames += 1
	# 等物理服务器**收敛**：地形碰撞是 116 块共享三角面的碰撞体，
	# 物理服务器第一次查询时才建 BVH —— 早到的射线会漏掉一部分地形，
	# 量出来的地面高度偏低（实测能差 10 m，��口直接埋进地里）。
	if _frames < 10 or Engine.get_physics_frames() < 240:
		return
	if not _settled:
		if not _physics_settled():
			return
		_settled = true
	_done = true

	var cli_args := OS.get_cmdline_user_args()
	# 命令行可以指定输出路径；挂进场景跑（后台模式）时用默认路径。
	var out_path: String = cli_args[0] if cli_args.size() > 0 else DEFAULT_OUT
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
	# 大门缩小到 60%：原模型 10.56 × 6.24 m，对 1.5 m 的玩家来说是四层楼高
	# 的门框。缩完 6.3 × 3.7 m —— 两层楼高，才像给人（和小型恐龙）进出的门。
	gate.scale = Vector3(GATE_SCALE, GATE_SCALE, GATE_SCALE)
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
		get_tree().quit(1)
		return
	if ResourceSaver.save(ps, out_path) != OK:
		push_error("保存失败: " + out_path)
		get_tree().quit(1)
		return

	print("BAKED ", out_path)
	print("  gate (%.2f, %.2f, %.2f)  walls=%d  rubble=%d  fallen=%d" % [
		gate.position.x, gate.position.y, gate.position.z, wall_n, rubble_n, fallen_n])
	get_tree().quit()
	return

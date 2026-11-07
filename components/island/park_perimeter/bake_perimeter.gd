extends SceneTree
## 烘一个环岛入口场景：门 + 沿岛缘内缩的断续围墙 + 断口碎石 + 倒伏墙。
##
## 为什么围墙是"沿岛缘"而不是"绕山画圆"：
##   山体半径就有 14.5 m，岛面最窄处半径 30 m。如果围一个以山为心的圆，
##   半径一旦超过 ~20 m 就会穿出岛外；而要围住全岛 50% 以上（1750 m²）的圆
##   半径得 23 m 以上 —— 两者不可兼得。沿岛缘内缩一圈则同时满足：
##   面积够大，山还能偏心摆。山偏心之后"进门 → 穿过空地 → 山在远处"的纵深也更自然。
##
## 布局规则：
##   1. **沿岛缘内缩**：每个角度用射线量出岛缘半径，墙落在 edge − INSET 处；
##      于是墙离崖边始终有 INSET 的距离，不会挂在崖上。
##   2. **断续 + 长短不一**：一段 1–5 段（2.9–14.5 m）之后必有一个塌口；
##      地面高差超过 STEP_BREAK 的地方强制断开（沉降把墙扯断）。
##   3. **被踩过的痕迹**：塌口碎石、倒伏整段墙、围内散落碎石、门墩撞击堆。
##
## 用法（**必须带真实渲染器**，headless 的渲染/物理都是 dummy）：
##   godot --path . --script res://components/island/park_perimeter/bake_perimeter.gd -- <out_tscn> [seed]

const TERRAIN_SCENE := "res://components/island/island.tscn"
const GATE_SCENE := "res://components/island/park_gate/park_gate.tscn"
const WALL_SCENE := "res://assets/models/ruined-wall/low_poly_ruined_wall.glb"
const RUBBLE_SCENE := "res://assets/models/stone-rubble/low_poly_rubble.glb"

# 岛面实测面积（1 m 网格射线采样，见 README）；用来核对"围住 50% 以上"
const ISLAND_AREA := 3504.0

# --- 布局参数 ---------------------------------------------------------------
const INSET := 10.5            # 墙离岛缘多远（外圈巡逻路走墙和崖之间那条带子）
## 恐龙巡逻的辐条**穿过围墙**的角度（度）。这几个角度上必须留出大门洞，
## 恐龙才能从外圈走进内圈 —— 跟
## `components/island/vegetation/bake_vegetation.gd` 的 SPOKE_ANGLES 一致。
const OPENING_ANGLES := [30.0, 150.0, 210.0, 330.0]
## 门洞宽度（米，沿墙量）。
const OPENING_WIDTH := 7.0
const SPAN_DEG := 140.0       # 大门两侧各绕多少度 → 背后留 80° 豁口
const GATE_ANGLE_DEG := 90.0  # 大门朝向（90° = +Z，默认预览相机那一侧）
const EDGE_SAMPLES := 144     # 岛缘采样的角度份数
const MIN_RING_R := 16.0      # 环半径下限，别让墙钻进山里
const SEG_LEN := 2.90
const GATE_HALF_W := 5.05
const STEP_BREAK := 0.42
const SINK := 0.05
const RUN_MIN := 1
const RUN_MAX := 5
const GAP_MIN := 1.2
const GAP_MAX := 3.6
const FALLEN_CHANCE := 0.40
const GATE_RUBBLE := 6
const SINK_VARIANCE := 0.28
const SINK_EXTRA := 0.55
const RUBBLE_EXTRA := 0.5

var _terrain: Node
var _frames := 0
var _done := false
var _rng := RandomNumberGenerator.new()
var _edge: PackedFloat32Array = PackedFloat32Array()


func _initialize() -> void:
	var args := OS.get_cmdline_user_args()
	if args.is_empty():
		push_error("用法: -- <out_tscn> [seed]")
		quit(1)
		return
	_rng.seed = int(args[1]) if args.size() > 1 else 20260715
	_terrain = load(TERRAIN_SCENE).instantiate()
	# 只借地形：展示节点（环境 / 灯光 / 预览相机）、草石和现有的围墙全关掉。
	# 否则量岛缘的射线会打在旧围墙 / 大门上（它们的碰撞也是按 62 m 尺度补的）。
	_terrain.set("show_presentation", false)
	_terrain.set("show_scatter", false)
	_terrain.set("show_perimeter", false)
	_terrain.collision_groups = [NodePath("Ground")] as Array[NodePath]
	root.add_child(_terrain)


func _ground(x: float, z: float) -> float:
	var q := PhysicsRayQueryParameters3D.create(Vector3(x, 60.0, z), Vector3(x, -40.0, z))
	var hit := root.world_3d.direct_space_state.intersect_ray(q)
	if hit.is_empty():
		return -INF
	return (hit["position"] as Vector3).y


## 量每个角度的岛缘半径并平滑。岛缘是许多块地形拼出来的，不平滑的话墙会抖成锯齿。
func _build_edge_profile() -> void:
	_edge.resize(EDGE_SAMPLES)
	for i in EDGE_SAMPLES:
		var a := TAU * i / EDGE_SAMPLES
		var last := 0.0
		var rr := 12.0
		while rr < 44.0:
			if _ground(cos(a) * rr, sin(a) * rr) != -INF:
				last = rr
			rr += 0.5
		_edge[i] = last
	# 环形 3 点滑动平均，抹掉单块地形的凸起
	var smooth := _edge.duplicate()
	for i in EDGE_SAMPLES:
		var s := 0.0
		for k in [-1, 0, 1]:
			s += _edge[(i + k + EDGE_SAMPLES) % EDGE_SAMPLES]
		smooth[i] = s / 3.0
	_edge = smooth


func _edge_at(angle: float) -> float:
	var t := fposmod(angle, TAU) / TAU * EDGE_SAMPLES
	var i := int(t) % EDGE_SAMPLES
	var j := (i + 1) % EDGE_SAMPLES
	return lerpf(_edge[i], _edge[j], t - floor(t))


func _ring_point(angle: float) -> Vector2:
	var r := maxf(MIN_RING_R, _edge_at(angle) - INSET)
	return Vector2(cos(angle), sin(angle)) * r


## 墙心处地面比"再往外 2.5 m"高多少 —— 大就说明站在崖边陡坡上，墙不该摆那儿。
func _outward_drop(c: Vector2) -> float:
	var out := c.normalized() * 2.5
	var h0 := _ground(c.x, c.y)
	var h1 := _ground(c.x + out.x, c.y + out.y)
	if h0 == -INF or h1 == -INF:
		return 0.0
	return h0 - h1


## 这个角度是不是落在某扇门洞里（辐条要从这儿穿过去）。
##
## 用**墙自己的半径**换算弧长 —— 用岛缘半径会算宽，门洞边上会漏一段墙。
func _in_opening(angle: float, radius: float) -> bool:
	for deg in OPENING_ANGLES:
		var d := absf(fposmod(angle - deg_to_rad(float(deg)) + PI, TAU) - PI)
		if d * radius < OPENING_WIDTH * 0.5:
			return true
	return false


func _yaw_of(heading: Vector2) -> float:
	return atan2(-heading.y, heading.x)


func _polygon_area(pts: Array) -> float:
	var a := 0.0
	var n := pts.size()
	for i in n:
		var p: Vector2 = pts[i]
		var q: Vector2 = pts[(i + 1) % n]
		a += p.x * q.y - q.x * p.y
	return absf(a) * 0.5


func _process(_dt: float) -> bool:
	if _done:
		return true
	_frames += 1
	if _frames < 8:
		return false
	_done = true

	var out_path: String = OS.get_cmdline_user_args()[0]
	_build_edge_profile()

	var root_node := Node3D.new()
	root_node.name = "ParkPerimeter"
	var walls_root := Node3D.new()
	walls_root.name = "Walls"
	root_node.add_child(walls_root)
	walls_root.owner = root_node
	var debris_root := Node3D.new()
	debris_root.name = "Debris"
	root_node.add_child(debris_root)
	debris_root.owner = root_node

	var gate_ang := deg_to_rad(GATE_ANGLE_DEG)
	var gate_dir: Vector2 = Vector2(cos(gate_ang), sin(gate_ang))
	var gate_pos: Vector2 = _ring_point(gate_ang)
	var gate_y := _ground(gate_pos.x, gate_pos.y)
	var tangent: Vector2 = gate_dir.orthogonal()

	var gate: Node3D = load(GATE_SCENE).instantiate()
	gate.name = "Gate"
	gate.position = Vector3(gate_pos.x, gate_y - SINK, gate_pos.y)
	gate.rotation.y = _yaw_of(tangent)
	root_node.add_child(gate)
	gate.owner = root_node

	var wall_n := 0
	var rubble_n := 0
	var fallen_n := 0
	var span_rad := deg_to_rad(SPAN_DEG)
	var branch_pos: Array = []
	var branch_neg: Array = []

	for side: float in [1.0, -1.0] as Array[float]:
		var pos: Vector2 = gate_pos + tangent * (GATE_HALF_W * side)
		var theta := 0.0
		var guard := 0
		var side_pts: Array = []
		while absf(theta) < span_rad and guard < 120:
			guard += 1
			var k := _rng.randi_range(RUN_MIN, RUN_MAX)
			var run_len := k * SEG_LEN
			var r_here := maxf(MIN_RING_R, _edge_at(gate_ang + theta) - INSET)
			var theta_end := theta + side * (run_len / r_here)   # 用平均半径换算角度步长
			var target: Vector2 = _ring_point(gate_ang + theta_end)
			var dir: Vector2 = (target - pos).normalized()
			var placed := 0
			var last_y := _ground(pos.x, pos.y)
			if last_y == -INF:
				last_y = gate_y
			for i in k:
				var c: Vector2 = pos + dir * (SEG_LEN * 0.5)
				# 门洞里不放墙：辐条要从这儿穿过去
				if _in_opening(atan2(c.y, c.x), maxf(MIN_RING_R, _edge_at(atan2(c.y, c.x)) - INSET)):
					pos += dir * SEG_LEN
					continue
				var y := _ground(c.x, c.y)
				if y == -INF:
					break
				if placed > 0 and absf(y - last_y) > STEP_BREAK:
					break
				if _outward_drop(c) > 1.2:
					break       # 脚下就是崖坡 → 墙在这儿塌下去了
				var w: Node3D = load(WALL_SCENE).instantiate()
				w.name = "Wall_%s_%02d" % ["E" if side > 0 else "W", wall_n]
				var extra := 0.0
				if _rng.randf() < SINK_VARIANCE:
					extra = _rng.randf_range(0.10, SINK_EXTRA)
				w.position = Vector3(c.x, y - SINK - extra, c.y)
				w.rotation.y = _yaw_of(dir)
				walls_root.add_child(w)
				w.owner = root_node
				wall_n += 1
				placed += 1
				last_y = y
				pos += dir * SEG_LEN
				side_pts.append(c)
			theta += side * (maxi(1, placed) * SEG_LEN / r_here)
			if placed == 0:
				theta += side * (run_len / r_here)

			var gap := _rng.randf_range(GAP_MIN, GAP_MAX)
			var gap_center: Vector2 = pos + dir * (gap * 0.5)
			var gy := _ground(gap_center.x, gap_center.y)
			if gy != -INF and not _in_opening(atan2(gap_center.y, gap_center.x),
					maxf(MIN_RING_R, _edge_at(atan2(gap_center.y, gap_center.x)) - INSET)):
				var r: Node3D = load(RUBBLE_SCENE).instantiate()
				r.name = "Rubble_%02d" % rubble_n
				r.position = Vector3(gap_center.x, gy - SINK, gap_center.y)
				r.rotation.y = _rng.randf_range(0.0, TAU)
				var sc := _rng.randf_range(1.0, 1.7)
				r.scale = Vector3(sc, _rng.randf_range(0.85, 1.25), sc)
				debris_root.add_child(r)
				r.owner = root_node
				rubble_n += 1
				if _rng.randf() < RUBBLE_EXTRA:
					var o: Vector2 = dir.orthogonal() * _rng.randf_range(-1.2, 1.2)
					var bp: Vector2 = gap_center + dir * _rng.randf_range(-1.4, 1.4) + o
					var by := _ground(bp.x, bp.y)
					if by != -INF:
						var r1b: Node3D = load(RUBBLE_SCENE).instantiate()
						r1b.name = "Rubble_%02d" % rubble_n
						r1b.position = Vector3(bp.x, by - SINK, bp.y)
						r1b.rotation.y = _rng.randf_range(0.0, TAU)
						var sc1 := _rng.randf_range(0.6, 1.1)
						r1b.scale = Vector3(sc1, _rng.randf_range(0.5, 0.9), sc1)
						debris_root.add_child(r1b)
						r1b.owner = root_node
						rubble_n += 1
				if _rng.randf() < FALLEN_CHANCE:
					var f: Node3D = load(WALL_SCENE).instantiate()
					f.name = "Fallen_%02d" % fallen_n
					var lean := _rng.randf_range(1.50, 1.62) * (-1.0 if _rng.randf() < 0.5 else 1.0)
					f.basis = Basis(Vector3.UP, _yaw_of(dir)) * Basis(Vector3.RIGHT, lean)
					var outward: Vector2 = gap_center.normalized()
					var fp: Vector2 = gap_center + outward * 0.8
					f.position = Vector3(fp.x, gy - 0.30, fp.y)
					debris_root.add_child(f)
					f.owner = root_node
					fallen_n += 1
			pos += dir * gap
			theta += side * (gap / r_here)
			side_pts.append(gap_center)
		# 两翼分别存；最后 [门] + 正向 + 反向倒序 = 一个不自交的闭合环
		if side > 0:
			branch_pos = side_pts.duplicate()
		else:
			branch_neg = side_pts.duplicate()

	# ---- 围内散落碎石 ----
	var interior := 0
	for i in 14:
		var a := _rng.randf_range(0.0, TAU)
		var rr := _rng.randf_range(8.0, 20.0)
		var ip: Vector2 = Vector2(cos(a), sin(a)) * rr
		var iy := _ground(ip.x, ip.y)
		if iy == -INF:
			continue
		var ri: Node3D = load(RUBBLE_SCENE).instantiate()
		ri.name = "InnerDebris_%02d" % i
		ri.position = Vector3(ip.x, iy - SINK, ip.y)
		ri.rotation.y = _rng.randf_range(0.0, TAU)
		var si := _rng.randf_range(0.45, 0.95)
		ri.scale = Vector3(si, _rng.randf_range(0.4, 0.8), si)
		debris_root.add_child(ri)
		ri.owner = root_node
		interior += 1

	# ---- 门墩两侧撞击堆 ----
	for sgn2: float in [1.0, -1.0] as Array[float]:
		var bp2: Vector2 = gate_pos + tangent * (GATE_HALF_W * sgn2) + gate_dir * 0.6
		var by2 := _ground(bp2.x, bp2.y)
		if by2 == -INF:
			continue
		var rb: Node3D = load(RUBBLE_SCENE).instantiate()
		rb.name = "GateHit_%s" % ("E" if sgn2 > 0 else "W")
		rb.position = Vector3(bp2.x, by2 - SINK, bp2.y)
		rb.rotation.y = _rng.randf_range(0.0, TAU)
		var sb := _rng.randf_range(0.9, 1.25)
		rb.scale = Vector3(sb, _rng.randf_range(0.7, 1.0), sb)
		debris_root.add_child(rb)
		rb.owner = root_node
		interior += 1

	# 反向那一支要倒序，环才闭合得对
	var loop: Array = [gate_pos] + branch_pos
	var rev: Array = branch_neg.duplicate()
	rev.reverse()
	loop += rev
	var area := _polygon_area(loop)
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
	print("  walls=%d rubble=%d fallen=%d inner=%d" % [wall_n, rubble_n, fallen_n, interior])
	print("  围住面积 %.0f m² = 岛面 %.0f m² 的 %.0f%%" % [area, ISLAND_AREA, area / ISLAND_AREA * 100.0])
	quit()
	return true

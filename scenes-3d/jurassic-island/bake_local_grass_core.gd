extends Node
## 烘**主场景的本地草石**：出生点附近的草丛 + 全岛的碎石。
##
## ## 为什么单独烘
##
## 大世界（2000 m）的岛面上没有草 —— 组件里那份草石是 62 m 尺度、
## 又是 32 倍缩放，早就关掉了（`show_scatter = false`）。
## 岛的地形本身是绿色的（plain_terrain），但没有一丛草，
## 玩家站在上面会觉得"这是个塑料球"。
##
## 所以这里在**出生点周围**重新铺一片草丛（1:1 米制，1.1 m 高），
## 碎石沿用原来那份（它们本来就撒在全岛）。
##
## ## 用法
##
## [codeblock]
## godot --path . --script res://scenes-3d/jurassic-island/bake_local_grass_cli.gd
## [/codeblock]
##
## 产物：`local_scatter.json`（源）+ `local_scatter.tscn` + `local_scatter_flat_*.res`。

const SCENE: String = "res://scenes-3d/jurassic-island/jurassic-island.tscn"
const SCRIPT_PATH: String = "res://components/island/ground_scatter/ground_scatter.gd"
const OUT_JSON: String = "res://scenes-3d/jurassic-island/local_scatter.json"
const OUT_TSCN: String = "res://scenes-3d/jurassic-island/local_scatter.tscn"
const RES_DIR: String = "res://scenes-3d/jurassic-island"
const RES_PREFIX: String = "local_scatter_flat"

## 草的铺法。
##
## 2026-11：岛整体缩小一半（面积减半 → 线性 ×0.7071），出生点和铺草半径
## 都跟着缩；石头原来撒在 r=1129 m（旧岛缘），现在全跑到岛外了 ——
## 改成在**新岛面**上重新撒。
const ISLAND_SHRINK := 0.70710678
const GRASS_CENTER := Vector2(0.0, 78.0 * ISLAND_SHRINK)   # 出生点
## 铺草的范围：全岛（不是只在出生点周围）。
##
## 2026-11：岛面改成绿色地表层之后，光靠那层绿还是"塑料板" ——
## 草丛是**贴地的细节**，1:1 米制（0.4–0.8 m），撒满全岛才像草。
## 数量是性能换来的：1 丛 ≈ 260 面，1.2 万丛 ≈ 3.2 M 面。
const GRASS_RADIUS := 700.0                 # 半径（米，够到岛缘）
const GRASS_COUNT := 12000                   # 草丛数量
const CLUMP_COUNT := 6000                    # 草簇数量
const GRASS_MIN_GAP := 1.1                   # 两丛草之间至少隔多远
## 全岛撒的石头数量（1:1 米制）。
const ROCK_COUNT := 180
## 撒石头用的半径（米）：比岛缘小一圈，保证都在岛上。
const ISLAND_R := 700.0
const GRASS_SCALE_MIN := 0.85
const GRASS_SCALE_MAX := 1.55
const SLOPE_LIMIT := 0.9                    # 太陡的地方不长草
const SNOW_LINE := 89.0
## 等物理服务器收敛用的探针半径（跟着岛缩）。
const PROBE_RADII := [28.0, 85.0, 185.0, 320.0, 460.0, 600.0]

## 资产类型 → 网格 / 节点名 / 是否投影。
const TYPES := {
	"grass_tuft": {
		"glb": "res://assets/models/grass/grass_tuft.glb",
		"node": "GrassTuft",
		"shadow": false,
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

var _scene: Node
var _frames := 0
var _done := false
var _settled := false
var _rng := RandomNumberGenerator.new()
## 各种拒绝原因的计数（诊断用）。
var _rej := {"noground": 0, "high": 0, "slope": 0, "close": 0}


func _ready() -> void:
	_rng.seed = 20261107
	_scene = load(SCENE).instantiate()
	get_tree().root.add_child.call_deferred(_scene)


func _process(_dt: float) -> void:
	if _done:
		return
	if _scene == null or not _scene.is_inside_tree():
		return
	_frames += 1
	# 等物理服务器**收敛**：地形碰撞是运行时补的，早到的射线会漏掉一部分地形，
	# 量出来的地面高度偏低，草就长在半空中。
	if _frames < 10 or Engine.get_physics_frames() < 240:
		return
	if not _settled:
		if not _physics_settled():
			return
		_settled = true
	_done = true
	_build()
	get_tree().quit()


## 物理服务器是不是收敛了：同一批探针连续两轮量出来的地面高度完全一样。
func _physics_settled() -> bool:
	var points := PackedVector2Array()
	for i in 64:
		var a := TAU * i / 64.0
		for r in PROBE_RADII:
			points.append(Vector2(cos(a) * float(r), sin(a) * float(r)))
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


func _ground(x: float, z: float) -> float:
	var q := PhysicsRayQueryParameters3D.create(Vector3(x, 900.0, z), Vector3(x, -200.0, z))
	q.collision_mask = 1
	var hit := get_tree().root.world_3d.direct_space_state.intersect_ray(q)
	if hit.is_empty():
		return -INF
	return (hit["position"] as Vector3).y


## 坡度（**米/米**，12 m 基线）。
##
## 高度差要除以基线才是坡度 —— 不除的话"上限 0.9"其实只有 0.075 m/m，
## 出生点周围整片地都被当成陡坡，一根草都长不出来。
const SLOPE_BASELINE := 12.0

func _slope(x: float, z: float) -> float:
	var h0 := _ground(x, z)
	if h0 == -INF:
		return 99.0
	var s := 0.0
	for off in [Vector2(SLOPE_BASELINE, 0), Vector2(-SLOPE_BASELINE, 0),
			Vector2(0, SLOPE_BASELINE), Vector2(0, -SLOPE_BASELINE)]:
		var h := _ground(x + off.x, z + off.y)
		if h != -INF:
			s = maxf(s, absf(h - h0) / SLOPE_BASELINE)
	return s


## 铺草：位置随机、贴地、坡太陡的不长。
##
## 铺全岛 → 上万丛，所以"离别的草够不够远"用**空间哈希**查（只看邻格），
## 逐个比对是 O(n²)：1.2 万丛要算 1.4 亿次，跑到天亮。
func _place_grass(count: int, seed_offset: int) -> Array:
	var out: Array = []
	var cells := {}          # Vector2i -> Array[Vector2]
	var tries := 0
	var cell := Vector2i(int(GRASS_MIN_GAP), int(GRASS_MIN_GAP))
	while out.size() < count and tries < count * 60:
		tries += 1
		var a := _rng.randf_range(0.0, TAU)
		# 半径按 sqrt 分布 —— 面积均匀，不会全挤在中心
		var r := GRASS_RADIUS * sqrt(_rng.randf())
		var p := GRASS_CENTER + Vector2(cos(a), sin(a)) * r
		var y := _ground(p.x, p.y)
		if y == -INF:
			_rej["noground"] += 1
			continue
		if y > SNOW_LINE:
			_rej["high"] += 1
			continue
		if _slope(p.x, p.y) > SLOPE_LIMIT:
			_rej["slope"] += 1
			continue
		# 空间哈希：只查自己这一格和周围 8 格
		var key := Vector2i(int(floor(p.x / cell.x)), int(floor(p.y / cell.y)))
		var too_close := false
		for dx in range(-1, 2):
			for dy in range(-1, 2):
				var bucket: Array = cells.get(Vector2i(key.x + dx, key.y + dy), [])
				for q in bucket:
					if p.distance_squared_to(q) < GRASS_MIN_GAP * GRASS_MIN_GAP:
						too_close = true
						break
				if too_close:
					break
			if too_close:
				break
		if too_close:
			_rej["close"] += 1
			continue
		cells[key] = (cells.get(key, []) as Array).duplicate()
		(cells[key] as Array).append(p)
		var yaw := _rng.randf_range(0.0, TAU)
		var sc := _rng.randf_range(GRASS_SCALE_MIN, GRASS_SCALE_MAX)
		out.append(_matrix(yaw, sc, Vector3(p.x, y, p.y)))
	return out


## 绕 Y 转 yaw、统一缩放 sc、平移到 pos 的 3×4 矩阵（12 个数，跟散点 JSON 一个格式）。
func _matrix(yaw: float, sc: float, pos: Vector3) -> Array:
	var c := cos(yaw) * sc
	var s := sin(yaw) * sc
	return [c, 0.0, -s, 0.0, sc, 0.0, s, 0.0, c, pos.x, pos.y, pos.z]


## 石头沿用原来那份（本来就撒在全岛），草是新铺的。
func _build() -> void:
	var old: Dictionary = {}
	if FileAccess.file_exists(OUT_JSON):
		var parsed = JSON.parse_string(FileAccess.get_file_as_string(OUT_JSON))
		if parsed is Dictionary:
			old = parsed
	# 石头**重新撒**（2026-11）：岛缩小一半之后，原来那份坐标撒在 r=1129 m，
	# 早就跑到岛外了；缩放它们又会和新的岛缘对不上。直接在岛面上重新撒，
	# 每块都贴地（y 按射线量）。
	var rocks: Array = []
	var dropped := 0
	var tries := 0
	while rocks.size() < ROCK_COUNT and tries < ROCK_COUNT * 40:
		tries += 1
		var a := _rng.randf_range(0.0, TAU)
		var r := ISLAND_R * sqrt(_rng.randf())
		var p := GRASS_CENTER + Vector2(cos(a), sin(a)) * r
		var y := _ground(p.x, p.y)
		if y == -INF:
			continue
		if y > SNOW_LINE:
			continue
		if _slope(p.x, p.y) > SLOPE_LIMIT:
			continue
		var yaw := _rng.randf_range(0.0, TAU)
		var sc := _rng.randf_range(0.55, 1.6)
		rocks.append(_matrix(yaw, sc, Vector3(p.x, y, p.y)))
	if rocks.size() < ROCK_COUNT:
		dropped = ROCK_COUNT - rocks.size()
	var data := {
		".": {
			"grass_tuft": _place_grass(GRASS_COUNT, 1),
			"grass_clump": _place_grass(CLUMP_COUNT, 2),
			"low_poly_rock": rocks,
		},
	}
	var f := FileAccess.open(OUT_JSON, FileAccess.WRITE)
	f.store_string(JSON.stringify(data, "  ", false, true) + "\n")
	f.close()
	print("  拒绝统计: %s" % str(_rej))
	print("WROTE ", OUT_JSON)
	print("  草丛 %d / 草簇 %d / 碎石 %d（收回岛外 %d 块）" % [
		(data["."] as Dictionary)["grass_tuft"].size(),
		(data["."] as Dictionary)["grass_clump"].size(),
		(data["."] as Dictionary)["low_poly_rock"].size(), dropped])
	_bake_multimeshes(data)


## JSON → MultiMesh 场景（跟 components/island/ground_scatter/bake_scatter.gd 一个做法）。
func _bake_multimeshes(data: Dictionary) -> void:
	var root := Node3D.new()
	root.name = "GroundScatter"
	root.set_script(load(SCRIPT_PATH))
	for group_path in data.keys():
		var types: Dictionary = data[group_path]
		for kind in types.keys():
			if not TYPES.has(kind):
				continue
			var spec: Dictionary = TYPES[kind]
			var transforms: Array = types[kind]
			var mesh := _mesh_of(String(spec["glb"]))
			if mesh == null:
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
			var res_path := "%s/%s_%s.res" % [RES_DIR, RES_PREFIX, String(kind)]
			ResourceSaver.save(mm, res_path)
			var mmi := MultiMeshInstance3D.new()
			mmi.name = String(spec["node"])
			mmi.multimesh = load(res_path)
			mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON \
				if spec["shadow"] else GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
			mmi.gi_mode = GeometryInstance3D.GI_MODE_DISABLED
			root.add_child(mmi)
			mmi.owner = root
	var ps := PackedScene.new()
	if ps.pack(root) != OK:
		push_error("pack 失败")
		return
	ResourceSaver.save(ps, OUT_TSCN)
	print("BUILT ", OUT_TSCN)


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

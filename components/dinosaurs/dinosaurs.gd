class_name DinosaurHerd
extends Node3D
##
## 池子里的两种数据类型用 **preload** 引（不用 class_name 直接引用）：
## `class_name` 要靠编辑器的全局类缓存才认得，命令行跑游戏时缓存可能是旧的，
## 那样脚本会直接解析失败。preload 永远认得。
##
const SpeciesScript := preload("res://components/dinosaurs/dinosaur_species.gd")
const GroupScript := preload("res://components/dinosaurs/dinosaur_spawn_group.gd")
const PatrolScript := preload("res://components/dinosaurs/dinosaur_patrol.gd")
## **恐龙群组件**：按数量把恐龙放进场景里，每只自己算巡逻路线。
##
## ## 为什么要这个组件
##
## 原来恐龙是**烘**进场景的：`world_dinosaurs.tscn` 里每只恐龙的巡逻路线
## 都是烘焙时算好的固定坐标。换个地形、换个岛大小都得重烘，而且路线跟场景
## 焊死了 —— 场景一挪，恐龙就沿着空气走。
##
## 现在：**恐龙是运行时放进去的**，路线按"碰撞"（射线打地面）和
## "恐龙偏好"（体型 → 领地大小）现场算（见 [DinosaurPatrol]）。
## 场景怎么变都不用重烘。
##
## ## 入参
##
## | 参数 | 是什么 |
## | --- | --- |
## | [member initial_count] | 一开始放多少只 |
## | [member pool] | **内置池**：备选的几种恐龙 + 各自的权重 |
## | [member spawn_groups] | **出生点组**（多个）：每组一处聚居地 |
## | [member territory_radius_min/max] | 领地半径范围（按体型插值） |
##
## ## 加恐龙
##
## [method add_dinosaur] 手动加一只：
## 不传出生点 → 按配置的聚居地自己找地方；传了就用给的坐标。
## 放进去之后它就开始巡逻。

## 没配出生点组时，自动摊出几处聚居地。
const AUTO_GROUP_COUNT := 6

@export_group("数量")
## 一开始放多少只恐龙。
@export var initial_count: int = 100
## 最多能有多少只（[method add_dinosaur] 的上限）。
@export var max_count: int = 400
@export_group("恐龙池")
## 备选的恐龙种类 + 权重（权重 = 随机抽到它的相对概率）。
## 每一项是一个 [DinosaurSpecies] 资源（场景 + 权重）。
@export var pool: Array[Resource] = []

@export_group("出生点")
## 出生点组：每组一处聚居地，恐龙按权重分配到各组。
##
## **留空 = 自动摊开**：组件会量出岛的大小，在离岛心 0.62 倍半径的环上
## 自动摊出 [constant AUTO_GROUP_COUNT] 块地（岛心留给玩家和山体）。
## 每一项是一个 [DinosaurSpawnGroup] 资源（中心 + 半径 + 权重）。
@export var spawn_groups: Array[Resource] = []

@export_group("巡逻")
## 领地半径范围（米）：按恐龙体型在两者之间插值（见 [method PatrolScript.territory_radius]）。
@export var territory_radius_min: float = 57.0
@export var territory_radius_max: float = 106.0
## 巡逻路线有几个路点。
@export var patrol_route_points: int = 24
## 恐龙之间至少隔多远（米）。
@export var min_spacing: float = 55.0
## 领地里能站人的地面坡度上限（米/米）。
@export var max_slope: float = 0.35
## 量坡度用的基线（米）。
@export var slope_baseline: float = 12.0
## 恐龙离岛缘至少多远（米）。浮空岛的边缘是悬崖，恐龙掉下去就没了。
@export var edge_margin: float = 45.0
## 恐龙脚底埋进地里的深度（米）。
@export var sink: float = 0.5
## 恐龙能爬多高（米，**相对岛面**）。默认 25 m —— 山腰以上留给"风景"。
##
## 不给上限的话，全岛找点的兜底逻辑会把恐龙放到几百米高的山腰上：
## 那里坡缓、站得住，但离玩家太远，一辈子遇不到。
@export var max_altitude: float = 25.0
## 恐龙身边要留多少净空才不会被树干顶住（米）。0 = 按体型自动算。
##
## 以前树是**绕着恐龙的巡逻路线**种的（烘焙时留出走廊），现在恐龙是运行时
## 放进去的、树已经种好了 —— 所以路线和出生点都要自己躲开树干。
@export var tree_clearance: float = 0.0

@export_group("边界")
## 是否给恐龙围一圈**隐形围栏**（边界层，只挡恐龙）。
##
## 浮空岛的边缘就是悬崖，恐龙在崖边走很容易掉下去（掉下去会被送回原地，
## 但看起来是"瞬移"）。
@export var build_boundary_fence: bool = true
## 围栏离岛缘多远（米）。
@export var boundary_inset: float = 40.0

## 已经放进来的恐龙。
var dinosaurs: Array[Node3D] = []
## 已经占住的位置（世界坐标 XZ），算间距用。
var _taken: Array[Vector2] = []
## 节点名里用的序号（**只增不减**）。
##
## 不能拿 [member dinosaurs] 的长度当序号：删掉一只再加一只，
## 新名字会跟还活着的那只重名，Godot 会把新节点自动改名成
## `@CharacterBody3D@12` —— 调试面板 / 测试场按名字认种类就全乱了。
var _spawn_serial: int = 0
## 每种恐龙放了多少只（统计用）。
var _species_count: Dictionary = {}
var _rng := RandomNumberGenerator.new()
var _ready_done := false
## 这一轮正在放的恐龙的体型（算净空用）。
var _current_body_size: float = 4.0
## 岛面高度（世界坐标）：量一次，用来算"恐龙能爬多高"。
var _base_y: float = 0.0
var _base_y_ready := false
## 岛缘的**最小**半径（米）：恐龙的活动范围上限（保守取圆，别放到悬崖边）。
var _min_edge: float = 0.0


func _ready() -> void:
	_rng.seed = 20261107
	# 射线要打得到地面，而碰撞是运行时补的 / 物理服务器要同步一次：
	# 所以等几帧再放恐龙。
	await get_tree().process_frame
	await get_tree().process_frame
	await get_tree().process_frame
	_measure_base_height()
	if build_boundary_fence:
		_build_boundary_fence()
	_spawn_initial()
	_ready_done = true


## 现在放了多少只。
func count() -> int:
	return dinosaurs.size()


## 开局那批恐龙放完了吗。
##
## [method _ready] 里要等物理服务器收敛（几帧）才放恐龙，所以场景刚加载完
## 的那一刻 [member dinosaurs] 可能还是空的。测试 / 自动化要等开局批次
## 放完再操作（尤其是"清空重建"）时，等这个返回 true。
func is_spawned() -> bool:
	return _ready_done


## 手动放一只恐龙进来。
##
## [param species_index] 池子里的第几种（-1 = 按权重随机）。
## [param spawn_point] 出生点（默认 = 按配置的聚居地自己找）。
##
## 放进去之后它**立刻开始巡逻**（路线按当前地形现算）。
func add_dinosaur(species_index: int = -1, spawn_point: Vector3 = Vector3.INF) -> Node3D:
	if dinosaurs.size() >= max_count:
		push_warning("恐龙数量到上限了（%d），不再放新的" % max_count)
		return null
	var species := _pick_species(species_index)
	if species == null or species.scene == null:
		push_warning("恐龙池子里没有可用的恐龙")
		return null
	var world := get_world_3d()
	if world == null:
		return null

	# 出生点：给的就用给的；没给就按配置的聚居地找
	_current_body_size = species.body_size()
	var pos := spawn_point
	if pos == Vector3.INF:
		pos = _find_spawn_in_groups()
		if pos == Vector3.INF or is_nan(pos.x):
			push_warning("所有聚居地都站不下恐龙了")
			return null
	# 贴到地面上（给的是"大概位置"）
	var y := PatrolScript.ground_height(world, pos.x, pos.z)
	if is_nan(y):
		return null
	pos.y = y

	var inst: Node3D = species.scene.instantiate()
	inst.name = "%s_%02d" % [_species_label(species), _spawn_serial]
	_spawn_serial += 1
	# **先摆好位置再进树**：`add_child` 会立刻跑 `_ready`，恐龙的 AI 在
	# `_ready` 里读自己的身体位置（当家 / 逃跑的参照点）。先 add 再挪的话，
	# 这几帧它停在组件原点：
	# 1. AI 把"家"记成原点（恐龙的逃跑方向会莫名其妙地朝岛外）；
	# 2. 玩家如果正好站在组件原点，会跟这只刚进树的恐龙重叠 ——
	#    实测会被物理弹到几万米外（`dinosaurs_test.tscn` 踩过这个坑）。
	# 所以先在树外把 position 摆好（`to_local` 换算到组件局部坐标）。
	var spawn_pos := Vector3(pos.x, y - sink, pos.z)
	inst.position = to_local(spawn_pos)
	add_child(inst)
	inst.global_position = spawn_pos
	# 朝向：面朝路线上的第一个路点，别一出生就侧着身子
	var route := _build_route(world, pos, species)
	_set_route(inst, route)
	if route.size() >= 2:
		var dir := route[1] - route[0]
		dir.y = 0.0
		if dir.length_squared() > 0.0001:
			# Godot 的前方是 -Z，而 atan2(x, z) 算的是 +Z —— 要转 180°。
			inst.rotation.y = atan2(dir.x, dir.z) + PI
	dinosaurs.append(inst)
	_taken.append(Vector2(pos.x, pos.z))
	_species_count[_species_label(species)] = \
			int(_species_count.get(_species_label(species), 0)) + 1
	return inst


## 把一只恐龙从场景里拿走（死掉了 / 被删了）。
func remove_dinosaur(dino: Node3D) -> void:
	if dino == null:
		return
	var i := dinosaurs.find(dino)
	if i >= 0:
		dinosaurs.remove_at(i)
		_taken.remove_at(i)
	dino.queue_free()


## 按权重从池子里抽一种恐龙。
func _pick_species(index: int) -> SpeciesScript:
	if index >= 0 and index < pool.size():
		return pool[index]
	var total := 0.0
	for s in pool:
		total += maxf(0.0, s.weight())
	if total <= 0.0:
		return null
	var pick := _rng.randf() * total
	for s in pool:
		pick -= maxf(0.0, s.weight())
		if pick <= 0.0:
			return s
	return pool[pool.size() - 1]


func _species_label(species: SpeciesScript) -> String:
	if not species.display_name.is_empty():
		return species.display_name
	if species.scene == null:
		return "Dino"
	var path := species.scene.resource_path.get_file().get_basename()
	return path.to_pascal_case()


## 领地 + 路线：按体型定领地大小，按地形算路点高度。
func _build_route(world: World3D, home: Vector3, species: SpeciesScript) -> PackedVector3Array:
	var body := species.body_size()
	var radius := PatrolScript.territory_radius(
			body, territory_radius_min, territory_radius_max)
	radius *= species.territory_scale
	# 路线的海拔上限：岛面 + max_altitude，或者"自己的家 + max_altitude"——
	# 手动指定的出生点如果本来就在高处（比如山顶），也得能在附近转圈。
	var route_max_y := maxf(_max_y(), home.y + max_altitude)
	return PatrolScript.build_route(world, home, radius, patrol_route_points,
			sink, 0.24, 0.002, max_slope, slope_baseline, _clearance_for(body), route_max_y)


## 路线写在**身体**上：Godot 的场景实例化只允许覆写实例根节点的属性，
## AI 每帧从身体那儿读路线。
func _set_route(dino: Node3D, route: PackedVector3Array) -> void:
	if "route" in dino:
		dino.set("route", route)
	if "respawn_position" in dino:
		dino.set("respawn_position", dino.global_position)


## 开局放 initial_count 只：按聚居地的权重分配，组内再按间距摊开。
func _spawn_initial() -> void:
	var groups := _weighted_groups()
	if groups.is_empty():
		push_warning("没有配置出生点组，恐龙没地方出生")
		return
	# 按权重把 initial_count 拆到各组
	var slots: Array[Resource] = []
	var total := 0.0
	for g in groups:
		total += maxf(0.0, g.weight)
	if total <= 0.0:
		return
	var per_group := {}
	for g in groups:
		per_group[g] = int(round(float(initial_count) * maxf(0.0, g.weight) / total))
	for g in groups:
		var n := int(per_group.get(g, 0))
		for _i in n:
			if dinosaurs.size() >= initial_count:
				break
			# 先在本组找；本组站不下了就去别的组找（别白白丢掉一只）
			var pos := _find_spawn_in_groups(groups, g)
			if pos == Vector3.INF:
				pos = _find_spawn_in_groups(groups)
			if pos == Vector3.INF:
				# 组里都满了 → 全岛随便找个站得住的地方
				pos = _find_spot_anywhere()
			if pos == Vector3.INF:
				continue
			add_dinosaur(-1, pos)
	# 还差几只（岛面被树 / 山体占掉了一些）→ 全岛兜底补足
	var guard := 0
	while dinosaurs.size() < initial_count and guard < initial_count * 4:
		guard += 1
		var pos := _find_spot_anywhere()
		if pos == Vector3.INF:
			break
		add_dinosaur(-1, pos)


## 量岛面高度：在离岛心 0.6 倍半径的一圈上取样，取**中位数**。
##
## 为什么不取岛心：岛心往往正好是山脚，量出来偏高。
func _measure_base_height() -> void:
	var world := get_world_3d()
	if world == null:
		return
	var profile := PatrolScript.edge_profile(world, 32)
	var max_r := 0.0
	for r in profile:
		max_r = maxf(max_r, r)
	if max_r <= 0.0:
		return
	var min_r := max_r
	for r in profile:
		if r > 0.0:
			min_r = minf(min_r, r)
	_min_edge = min_r
	var samples: Array[float] = []
	for i in 32:
		var a := TAU * float(i) / 32.0
		var y := PatrolScript.ground_height(world, cos(a) * max_r * 0.6, sin(a) * max_r * 0.6)
		if not is_nan(y):
			samples.append(y)
	if samples.is_empty():
		return
	samples.sort()
	_base_y = samples[samples.size() / 2]
	_base_y_ready = true


## 恐龙能到的最高处（世界坐标）。
func _max_y() -> float:
	if not _base_y_ready:
		return INF
	return _base_y + max_altitude


## 恐龙的**活动半径上限**（米）：岛缘再往里收 edge_margin。
##
## 取"最小岛缘半径"是故意的：岛的轮廓不规则，用圆是最保守的，
## 保证恐龙怎么走都还在岛上。
func _max_radius() -> float:
	if _min_edge <= 0.0:
		return INF
	return maxf(50.0, _min_edge - edge_margin)


## 体型 → 身边要留的净空（米）：身长的 1/10，最少 1 m。
func _clearance_for(body_size: float) -> float:
	if tree_clearance > 0.0:
		return tree_clearance
	return maxf(1.0, body_size * 0.1)


## 有权重的组（权重 > 0 的）。
func _weighted_groups() -> Array[Resource]:
	var out: Array[Resource] = []
	for g in spawn_groups:
		if g != null and g.weight > 0.0:
			out.append(g)
	if out.is_empty():
		out = _auto_groups()
	return out


## 没配出生点组时的**兜底**：按岛的大小自动摊出几处聚居地。
##
## 做法：量出岛缘半径，然后在离岛心 **0.62 倍半径**的环上摊 N 块地 ——
## 岛心留给玩家和山体，恐龙在环上各占一块。这样组件放在任何大小的岛上
## 都能用，不用手填坐标。
func _auto_groups() -> Array[Resource]:
	var world := get_world_3d()
	if world == null:
		return []
	var profile := PatrolScript.edge_profile(world, 48)
	if profile.is_empty():
		return []
	var max_r := 0.0
	for r in profile:
		max_r = maxf(max_r, r)
	if max_r <= 0.0:
		return []
	var limit := _max_radius()
	var ring := minf(max_r * 0.55, limit * 0.65)
	var group_r := maxf(60.0, minf(max_r * 0.25, limit * 0.32))
	var out: Array[Resource] = []
	for i in AUTO_GROUP_COUNT:
		var a := TAU * float(i) / float(AUTO_GROUP_COUNT)
		var g: Resource = GroupScript.new()
		g.display_name = "Sector%d" % i
		g.center = Vector3(cos(a) * ring, 0.0, sin(a) * ring)
		g.radius = group_r
		g.weight = 1.0
		out.append(g)
	return out


## 在聚居地里找一个站得住的位置。没指定组就在所有组里轮着找。
##
## ⚠️ [method DinosaurPatrol.find_spot] 找不到位置时返回的是
## **NAN**，不是 [constant Vector3.INF] —— 曾经这里只判 `!= INF`，
## 于是"第一组满了"被当成"找到了一个点是 NaN"，后面的组再也没试过：
## 恐龙数量停在第一组的容量上（测试场按 R 重置时只放出 9 只）。
func _find_spawn_in_groups(groups: Array[Resource] = [],
		only: Resource = null) -> Vector3:
	var world := get_world_3d()
	if world == null:
		return Vector3.INF
	var pool_groups: Array[Resource] = groups
	if pool_groups.is_empty():
		pool_groups = _weighted_groups()
	if pool_groups.is_empty():
		return Vector3.INF
	for g in pool_groups:
		if only != null and g != only:
			continue
		var pos := PatrolScript.find_spot(world, g, _taken, min_spacing,
				max_slope, slope_baseline, _clearance_for(_current_body_size),
				_max_y(), _max_radius())
		if pos != Vector3.INF and not is_nan(pos.x):
			return pos
	return Vector3.INF


## 全岛随便找个站得住的位置（聚居地都满了的时候兜底）。
func _find_spot_anywhere(tries: int = 200) -> Vector3:
	var world := get_world_3d()
	if world == null:
		return Vector3.INF
	var profile := PatrolScript.edge_profile(world, 24)
	if profile.is_empty():
		return Vector3.INF
	var max_r := 0.0
	for r in profile:
		max_r = maxf(max_r, r)
	if max_r <= 0.0:
		return Vector3.INF
	var limit := minf(max_r * 0.95, _max_radius())
	for _i in tries:
		var a := randf() * TAU
		var r := limit * sqrt(randf())
		var x := cos(a) * r
		var z := sin(a) * r
		var y := PatrolScript.ground_height(world, x, z)
		if is_nan(y):
			continue
		if not PatrolScript.is_flat(world, x, z, slope_baseline, max_slope):
			continue
		if y > _max_y():
			continue
		var p := Vector2(x, z)
		var too_close := false
		for q in _taken:
			if p.distance_squared_to(q) < min_spacing * min_spacing:
				too_close = true
				break
		if too_close:
			continue
		return Vector3(x, y, z)
	return Vector3.INF


## 给恐龙围一圈**隐形围栏**（边界层，只挡恐龙）。
##
## 按岛缘轮廓围：每个角度量出岛缘半径，往里缩 boundary_inset 放一段盒子。
func _build_boundary_fence() -> void:
	var world := get_world_3d()
	if world == null:
		return
	var profile := PatrolScript.edge_profile(world)
	if profile.is_empty():
		return
	var body := StaticBody3D.new()
	body.name = "Boundary"
	body.collision_layer = 32       # boundary
	body.collision_mask = 1
	var shape := BoxShape3D.new()
	shape.size = Vector3(1.0, 5.0, 0.6)     # 沿切向 1 m、高 5 m、厚 0.6 m
	var segments := profile.size()
	for i in segments:
		var a := TAU * float(i) / float(segments)
		var r := profile[i] - boundary_inset
		if r <= 0.0:
			continue
		var x := cos(a) * r
		var z := sin(a) * r
		var y := PatrolScript.ground_height(world, x, z)
		if is_nan(y):
			continue
		var col := CollisionShape3D.new()
		col.name = "Shape_%03d" % i
		col.shape = shape
		# 盒子沿**切线**摆：角度 a 处的切线是 (-sin a, cos a)，对应 yaw = -a - 90°
		col.transform = Transform3D(Basis(Vector3.UP, -a - PI * 0.5),
				Vector3(x, y + 2.0, z))
		# 段的长度按弧长算，免得圈上有缝
		col.scale = Vector3(TAU * r / float(segments) + 0.4, 1.0, 1.0)
		body.add_child(col)
	add_child(body)

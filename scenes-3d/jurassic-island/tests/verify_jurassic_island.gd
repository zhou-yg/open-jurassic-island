extends SceneTree
## 侏罗纪岛主场景自检脚本（无需编辑器，直接跑无头模式）。
##
## 校验 requirements/scenes/juraasic-main.md 描述的三部分是否齐备且互相吻合：
## [br]1. 随机地图： walls 使用树木单元，出入口 / 中心出口齐全；
## [br]2. 岛屿： sky-island-basic.glb 已实例化且带碰撞；
## [br]3. 海： sea.tscn 存在且足够大。
## 另外校验随机地图与树墙都坐落在岛屿台面上、四角不悬空、玩家出生点可站立、
## [TreeWalls] 把随机地图矩形之外的剩余部分铺满且不侵入地图内部。
##
## 运行方式（在项目根目录执行）：
## [codeblock]
## /Applications/Godot.app/Contents/MacOS/Godot --headless --script res://scenes-3d/jurassic-island/tests/verify_jurassic_island.gd
## [/codeblock]
## 全部通过时进程退出码为 0，否则为 1。

## 岛屿台面在 glb 本地坐标下的高度（与 jurassic-island.gd 的默认值一致）。
const ISLAND_PLATEAU_LOCAL_HEIGHT: float = 0.71
## 生成依赖射线检测，需要等物理世界准备好。
const SETTLE_FRAMES: int = 30
## 抽查地面时相对地板中心偏移的距离，避开树干自身的碰撞体。
const SAMPLE_OFFSET: float = 1.0

var _checks := 0
var _failures := 0
var _frames := 0
var _scene: Node3D


func _check(ok: bool, msg: String) -> void:
	_checks += 1
	if not ok:
		_failures += 1
		print("  [FAIL] ", msg)


func _initialize() -> void:
	_scene = load("res://scenes-3d/jurassic-island/jurassic-island.tscn").instantiate()
	get_root().add_child(_scene)


func _process(_d: float) -> bool:
	_frames += 1
	if _frames < SETTLE_FRAMES:
		return false
	var map: RandomMap = _scene.get_node("RandomMap")
	var island: Node3D = _scene.get_node("Island")
	var sea: Node3D = _scene.get_node("Sea")
	var player: CharacterBody3D = _scene.get_node("Player")
	var tree_walls: TreeWalls = _scene.get_node("TreeWalls")
	var plateau := _plateau(island)

	_test_island(island)
	_test_sea(sea)
	_test_random_map(map)
	_test_alignment(map, plateau)
	_test_player(player, map, plateau)
	_test_tree_walls(tree_walls, map, plateau)

	print("=== 主场景检查项 %d，失败 %d ===" % [_checks, _failures])
	print("全部通过 ✅" if _failures == 0 else "存在失败 ❌")
	quit(1 if _failures > 0 else 0)
	return true


## 岛屿台面的世界高度。
func _plateau(island: Node3D) -> float:
	return island.position.y + ISLAND_PLATEAU_LOCAL_HEIGHT * island.scale.y


## 1. 岛屿：glb 已实例化、有网格、有碰撞。
func _test_island(island: Node3D) -> void:
	_check(island.get_child_count() > 0, "岛屿 glb 未实例化")
	if island.get_child_count() == 0:
		return
	var glb: Node = island.get_child(0)
	_check(glb.find_children("*", "MeshInstance3D", true, false).size() > 0, "岛屿没有网格")
	_check(glb.find_children("*", "CollisionShape3D", true, false).size() > 0, "岛屿没有碰撞体")


## 3. 海：存在且面积远大于岛屿。
func _test_sea(sea: Node3D) -> void:
	_check(sea is MeshInstance3D, "海组件不是 MeshInstance3D")
	var mesh := (sea as MeshInstance3D).mesh as PlaneMesh
	_check(mesh != null, "海没有 PlaneMesh")
	if mesh != null:
		_check(mesh.size.x >= 500.0, "海面太小")


## 1. 随机地图：墙用树、出入口与中心出口齐备、树墙带碰撞。
func _test_random_map(map: RandomMap) -> void:
	_check(map.wall_scene != null, "random_map 没有 wall_scene")
	if map.wall_scene != null:
		_check(
			str(map.wall_scene.resource_path).contains("tree-wall-unit"),
			"random_map 的 wall_scene 不是 tree-wall-unit"
		)
	_check(map.get_maze() != null, "随机地图没有生成")
	var walls := map.get_node("Walls")
	_check(walls.get_child_count() > 0, "地图没有墙壁")
	_check(map.get_entrance_positions().size() > 0, "地图没有入口")
	_check(map.get_exit_positions().size() > 0, "地图没有出口")
	if walls.get_child_count() > 0:
		var first_wall: Node = walls.get_child(0)
		_check(
			first_wall.find_children("*", "CollisionShape3D", true, false).size() > 0,
			"树木墙单元没有碰撞体"
		)


## 随机地图必须坐在岛屿台面上，且四角都有岛屿地面（不悬空在海面上）。
func _test_alignment(map: RandomMap, plateau: float) -> void:
	_check(
		absf(map.position.y - plateau) < 0.05,
		"随机地图没有对齐到岛屿台面 (map_y=%.2f plateau=%.2f)" % [map.position.y, plateau]
	)
	var half: Vector2 = map.get_actual_map_size() * 0.5
	for corner in [
		Vector2(half.x, half.y), Vector2(-half.x, half.y),
		Vector2(half.x, -half.y), Vector2(-half.x, -half.y)
	]:
		_check(
			absf(_ground_height(corner, plateau) - plateau) < 0.1,
			"地图角落 %s 悬空（不在岛屿台面上）" % corner
		)


## 玩家站在地图地板上，且出生点不在墙里。
func _test_player(player: CharacterBody3D, map: RandomMap, plateau: float) -> void:
	_check(player.is_on_floor(), "玩家没有站在地面上")
	_check(absf(player.global_position.y - (plateau + 0.7)) < 0.6, "玩家高度异常")
	var cell := map.get_cell_from_world(player.global_position)
	_check(cell.x >= 0 and not map.is_wall(cell), "玩家出生在墙里或地图外")


## TreeWalls：把岛屿剩余部分铺满，且不侵入随机地图矩形。
func _test_tree_walls(tree_walls: TreeWalls, map: RandomMap, plateau: float) -> void:
	_check(tree_walls != null, "场景里没有 TreeWalls 节点")
	if tree_walls == null:
		return
	_check(
		absf(tree_walls.position.y - plateau) < 0.05,
		"TreeWalls 没有对齐到岛屿台面 (y=%.2f plateau=%.2f)" % [tree_walls.position.y, plateau]
	)
	var floors := tree_walls.get_node_or_null(NodePath("Floors"))
	var trees := tree_walls.get_node_or_null(NodePath("Trees"))
	_check(floors != null and floors.get_child_count() > 0, "TreeWalls 没有铺地板")
	_check(trees != null and trees.get_child_count() > 0, "TreeWalls 没有种树")
	if floors == null or trees == null:
		return
	# 每个格子一套地板 + 一棵树。
	_check(
		floors.get_child_count() == trees.get_child_count(),
		"TreeWalls 地板(%d)与树(%d)数量不一致" % [
			floors.get_child_count(), trees.get_child_count()
		]
	)
	# 不该越过随机地图的边界。
	var size: Vector2 = map.get_actual_map_size()
	var center := Vector2(map.global_position.x, map.global_position.z)
	var rect := Rect2(center - size * 0.5, size).grow(-0.01)
	var intruders := 0
	for node in trees.get_children():
		var p := (node as Node3D).global_position
		if rect.has_point(Vector2(p.x, p.z)):
			intruders += 1
	_check(intruders == 0, "%d 棵树长进了随机地图矩形里" % intruders)
	# 抽查若干地板：脚下确实踩在岛屿台面上。
	var sampled := 0
	var grounded := 0
	for node in floors.get_children():
		if sampled >= 12:
			break
		var p := (node as Node3D).global_position
		sampled += 1
		var probe := Vector2(p.x + SAMPLE_OFFSET, p.z + SAMPLE_OFFSET)
		if absf(_ground_height(probe, plateau) - plateau) < 0.1:
			grounded += 1
	_check(sampled > 0 and grounded == sampled, "抽查 %d/%d 个填充格站在台面上" % [grounded, sampled])


## 从 [param from_y] 附近向下打射线，返回地面高度；没打中返回 -INF。
func _ground_height(point: Vector2, from_y: float) -> float:
	var query := PhysicsRayQueryParameters3D.create(
		Vector3(point.x, from_y + 60.0, point.y), Vector3(point.x, from_y - 60.0, point.y)
	)
	var hit := get_root().world_3d.direct_space_state.intersect_ray(query)
	if not hit.has("position"):
		return -INF
	return (hit["position"] as Vector3).y

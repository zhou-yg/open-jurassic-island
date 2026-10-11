@tool
class_name TreeWalls
extends Node3D
## 用树木 + 地板单元填充岛屿上[color=red]随机地图矩形以外[/color]的剩余部分。
##
## 随机地图生成的是一个规整矩形，而岛屿（sky-island-basic.glb）是一块不规则的
## 台地，两者形状对不上：矩形之外会露出一圈光秃秃的岩石。本组件按固定间隔在
## 台地上铺满地板与树木，把剩余部分补成森林，让整座岛看起来都是树。
##
## 工作方式：
## [br]1. 以本节点为原点，在 [member fill_extent] 范围内按 [member spacing] 打网格；
## [br]2. 每个格点向下打一条射线，只有落在"本节点所在高度附近"的平整地面上才保留
##   （这就是岛屿台地，坡度大的岩壁与悬崖会被自动舍弃）；
## [br]3. 再检查格子四角是否也平整（[member edge_check]），避免地板悬在崖边；
## [br]4. 跳过随机地图所占的矩形（[member maze_path] / [member maze_size]），
##   其余格点摆一个地板单元 + 一棵树。
##
## 使用方式：把本节点放在岛屿台面高度上（y = 台面高度），
## 它就会以自己为基准面铺满周围的地面。主场景 jurassic-island.tscn 就是这么用的。

## 填充完成后发出，便于外部确认规模。
signal filled(tree_count: int, floor_count: int)

## 子节点容器名称。
const CONTAINER_FLOORS: StringName = &"Floors"
const CONTAINER_TREES: StringName = &"Trees"
const CONTAINER_NAMES: Array[StringName] = [CONTAINER_FLOORS, CONTAINER_TREES]

## 单元尺寸下限，防止退化几何。
const MIN_UNIT_SIZE: float = 0.001

@export_group("基本单元")
## 树木单元（PackedScene）。默认复用随机地图的树墙单元。
@export var tree_scene: PackedScene = preload(
	"res://components/map/random_map/tree-wall-unit.tscn"
)
## 地板单元（PackedScene）。默认复用随机地图的地板单元。
@export var floor_scene: PackedScene = preload(
	"res://components/map/random_map/floor_unit.tscn"
)
## 地板厚度（米）。地板顶面与本节点同高，向下延伸这个厚度。
@export_range(0.01, 4.0, 0.01) var floor_thickness: float = 0.2

@export_group("铺设范围")
## 要填充的矩形范围（米），以本节点原点为中心。
@export var fill_extent: Vector2 = Vector2(120.0, 120.0)
## 树与地板的间隔（米）。这是唯一的疏密参数：越小越密。
## 3m 比树冠（约 1.8m）略大，既有森林感又留得出人走的缝隙。
@export_range(0.5, 20.0, 0.1) var spacing: float = 3.0
## 随机地图节点。设置后会自动读取它实际占用的矩形并整块跳过。
@export var maze_path: NodePath
## [member maze_path] 未设置时使用的随机地图矩形尺寸（米）。
@export var maze_size: Vector2 = Vector2(44.0, 44.0)
## 跳过区域额外外扩的边距（米），避免树木贴到迷宫墙上。
@export_range(0.0, 20.0, 0.1) var maze_margin: float = 1.0

@export_group("贴合地面")
## 允许的地面高度误差（米）。超出这个范围说明不是台地（是岩壁或悬崖），跳过。
@export_range(0.01, 2.0, 0.01) var ground_tolerance: float = 0.1
## 是否检查格子四角也平整，避免地板探出崖边。
@export var edge_check: bool = true
## 树木位置抖动幅度（相对间隔的比例）。0 表示严格对齐网格。
@export_range(0.0, 0.5, 0.01) var jitter: float = 0.18
## 是否给树木随机朝向。
@export var random_rotation: bool = true

@export_group("生成")
## 随机种子。0 表示每次生成都换一组随机抖动。
@export var fill_seed: int = 0
## 进入场景树时是否自动生成一次。
@export var auto_generate: bool = true
## 是否在控制台输出本次生成的统计信息。
@export var print_debug_stats: bool = false

## 最近一次生成实际使用的种子。
var _last_seed: int = 0
## 防止树 / 地板单元误指向本组件时无限递归。
var _generating: bool = false


func _ready() -> void:
	if auto_generate:
		_generate_deferred()


## 等一个物理帧再生成。
##
## 生成依赖射线检测来贴合地面，而刚进入场景树时物理服务器还没处理好碰撞形状；
## 同时父节点的 [method Node._ready]（负责把本节点摆到台面高度）也还没跑完。
## 等一帧后这两件事都就绪了。
func _generate_deferred() -> void:
	if not is_inside_tree():
		return
	await get_tree().physics_frame
	generate()


## ---------------- 公开接口 ----------------

## 用 [member fill_seed] 生成（0 表示随机种子）。
func generate() -> void:
	generate_with_seed(_resolve_seed())


## 用固定种子生成，便于复现。
func generate_with_seed(p_seed: int) -> void:
	if _generating:
		push_warning("TreeWalls: 检测到嵌套生成，已跳过。")
		return
	if not is_inside_tree():
		return
	_generating = true
	_last_seed = p_seed
	clear()
	_ensure_containers()
	var rng := RandomNumberGenerator.new()
	rng.seed = p_seed

	var surface_y: float = global_position.y
	var step: float = maxf(spacing, MIN_UNIT_SIZE)
	var count: Vector2i = Vector2i(
		maxi(1, roundi(fill_extent.x / step)),
		maxi(1, roundi(fill_extent.y / step))
	)
	var origin_x: float = global_position.x - float(count.x) * step * 0.5 + step * 0.5
	var origin_z: float = global_position.z - float(count.y) * step * 0.5 + step * 0.5
	var keep_rect := _resolve_maze_rect()
	var floors := get_node_or_null(NodePath(CONTAINER_FLOORS))
	var trees := get_node_or_null(NodePath(CONTAINER_TREES))
	var tree_count := 0
	var floor_count := 0

	# 第一趟：只做判定，记录要摆放的位置。
	#
	# 必须与摆放分开：射线检测会打到本组件自己刚生成的树干上，
	# 若边判定边摆放，后面的格子会被前面的树挡住而误判成"地面不平"，
	# 在地图上留下一道道斜向的空缺。抖动后的落点也在这里一并算好。
	var floor_points: Array[Vector2] = []
	var tree_points: Array[Vector2] = []
	var tree_yaws: Array[float] = []
	for iz in count.y:
		for ix in count.x:
			var x: float = origin_x + float(ix) * step
			var z: float = origin_z + float(iz) * step
			var point := Vector2(x, z)
			if keep_rect.has_area() and keep_rect.grow(maze_margin).has_point(point):
				continue
			if not _is_flat_ground(point, surface_y):
				continue
			if edge_check and not _tile_is_flat(point, step, surface_y):
				continue
			floor_points.append(point)
			var placed := _jittered_point(point, step, surface_y, rng)
			tree_points.append(placed)
			tree_yaws.append(rng.randf_range(0.0, TAU) if random_rotation else 0.0)

	# 第二趟：摆地板与树。
	for index in floor_points.size():
		if _spawn_floor(floor_points[index], surface_y, step, floors):
			floor_count += 1
		if _spawn_tree(tree_points[index], tree_yaws[index], surface_y, trees):
			tree_count += 1

	_generating = false
	if print_debug_stats:
		print(
			"[TreeWalls] seed=%d 间隔=%.1fm 地板=%d 树=%d"
			% [_last_seed, step, floor_count, tree_count]
		)
	filled.emit(tree_count, floor_count)


## 清空已生成的地板与树木。
func clear() -> void:
	for container_name in CONTAINER_NAMES:
		var container := get_node_or_null(NodePath(container_name))
		if container == null:
			continue
		for child in container.get_children():
			container.remove_child(child)
			child.queue_free()


## 最近一次生成使用的种子。
func get_last_seed() -> int:
	return _last_seed


## ---------------- 内部实现 ----------------

func _resolve_seed() -> int:
	if fill_seed != 0:
		return fill_seed
	return randi()


func _ensure_containers() -> void:
	for container_name in CONTAINER_NAMES:
		if get_node_or_null(NodePath(container_name)) == null:
			var container := Node3D.new()
			container.name = container_name
			add_child(container)


## 需要跳过的随机地图矩形（世界坐标）。取不到时返回空 Rect2。
func _resolve_maze_rect() -> Rect2:
	var maze := get_node_or_null(maze_path)
	if maze is RandomMap:
		var size: Vector2 = (maze as RandomMap).get_actual_map_size()
		var center: Vector2 = Vector2(
			(maze as RandomMap).global_position.x, (maze as RandomMap).global_position.z
		)
		return Rect2(center - size * 0.5, size)
	if maze_size.x <= 0.0 or maze_size.y <= 0.0:
		return Rect2()
	return Rect2(global_position.x - maze_size.x * 0.5, global_position.z - maze_size.y * 0.5,
		maze_size.x, maze_size.y)


## 该点是否落在"本节点所在高度的平整地面"上。
func _is_flat_ground(point: Vector2, surface_y: float) -> bool:
	var space := get_world_3d().direct_space_state
	var query := PhysicsRayQueryParameters3D.create(
		Vector3(point.x, surface_y + 100.0, point.y),
		Vector3(point.x, surface_y - 100.0, point.y)
	)
	var hit := space.intersect_ray(query)
	if hit.is_empty():
		return false
	return absf((hit["position"] as Vector3).y - surface_y) <= ground_tolerance


## 整个格子是否平整：中心 + 四角都要满足，否则地板会探出崖边。
func _tile_is_flat(center: Vector2, step: float, surface_y: float) -> bool:
	var half: float = maxf(step * 0.5 - 0.02, MIN_UNIT_SIZE)
	for offset in [
		Vector2(-half, -half), Vector2(half, -half), Vector2(-half, half), Vector2(half, half)
	]:
		if not _is_flat_ground(center + offset, surface_y):
			return false
	return true


func _spawn_floor(point: Vector2, surface_y: float, step: float, container: Node) -> bool:
	if container == null:
		return false
	var packed := _resolve_scene(floor_scene)
	if packed == null:
		return false
	var unit := packed.instantiate() as Node3D
	if unit == null:
		push_warning("TreeWalls: floor_scene 的根节点必须是 Node3D。")
		return false
	unit.name = "Floor_%d_%d" % [roundi(point.x), roundi(point.y)]
	container.add_child(unit)
	# 顶面与地面同高，向下延伸 floor_thickness。
	var height: float = maxf(floor_thickness, MIN_UNIT_SIZE)
	unit.global_position = Vector3(point.x, surface_y - height * 0.5, point.y)
	_apply_unit_size(unit, Vector3(step, height, step))
	return true


## 抖动后的树木落点（相对格子中心的偏移不超过 [member jitter] x 间隔）。
## 抖动后若离开平整地面，就退回格子中心。
func _jittered_point(
	point: Vector2, step: float, surface_y: float, rng: RandomNumberGenerator
) -> Vector2:
	if jitter <= 0.0:
		return point
	var offset := Vector2(
		rng.randf_range(-jitter, jitter), rng.randf_range(-jitter, jitter)
	) * step
	var placed := point + offset
	return placed if _is_flat_ground(placed, surface_y) else point


func _spawn_tree(
	point: Vector2, yaw: float, surface_y: float, container: Node
) -> bool:
	if container == null:
		return false
	var packed := _resolve_scene(tree_scene)
	if packed == null:
		return false
	var unit := packed.instantiate() as Node3D
	if unit == null:
		push_warning("TreeWalls: tree_scene 的根节点必须是 Node3D。")
		return false
	unit.name = "Tree_%d_%d" % [roundi(point.x), roundi(point.y)]
	container.add_child(unit)
	# 树单元自身的原点就在树干根部，直接摆到地面上。
	unit.global_position = Vector3(point.x, surface_y, point.y)
	unit.rotation.y = yaw
	return true


## 按目标尺寸配置单元：CSGBox3D 直接用 size，BoxMesh 换 mesh，其它按等比缩放。
func _apply_unit_size(unit: Node3D, target_size: Vector3) -> void:
	if unit is CSGBox3D:
		(unit as CSGBox3D).size = target_size
		return
	if unit is MeshInstance3D:
		var mesh_instance := unit as MeshInstance3D
		if mesh_instance.mesh is BoxMesh:
			var box := (mesh_instance.mesh as BoxMesh).duplicate() as BoxMesh
			box.size = target_size
			mesh_instance.mesh = box
			return
	# 其它场景：按自身包围盒等比缩放到目标尺寸。
	var aabb := _scene_aabb(unit)
	var native := Vector3(
		maxf(aabb.size.x, MIN_UNIT_SIZE),
		maxf(aabb.size.y, MIN_UNIT_SIZE),
		maxf(aabb.size.z, MIN_UNIT_SIZE)
	)
	unit.scale = Vector3(
		target_size.x / native.x, target_size.y / native.y, target_size.z / native.z
	)


func _scene_aabb(node: Node3D) -> AABB:
	var found := false
	var box := AABB()
	for child in node.find_children("*", "MeshInstance3D", true, false):
		var mesh_instance := child as MeshInstance3D
		var aabb := mesh_instance.get_aabb()
		aabb = mesh_instance.transform * aabb
		if found:
			box = box.merge(aabb)
		else:
			box = aabb
			found = true
	return box


func _resolve_scene(scene: PackedScene) -> PackedScene:
	return scene

@tool
class_name RandomMap
extends Node3D
## 迷宫般风格的随机地图组件。
##
## 用元胞自动机生成"较为稀疏、像迷宫一样"的平面布局，再按格子实例化墙壁 /
## 地板单元。地图是平的（所有格子地面高度为 0），四周是封闭的矩形边缘，
## 边缘上有多个入口，中心是出口目标。
##
## 使用方式：
## [codeblock]
## var map: RandomMap = $RandomMap
## map.generate()                       # 用节点上的参数生成一张随机地图
## map.generate_with_seed(12345)        # 用固定种子复现同一张地图
## for entrance in map.get_entrance_positions():
##     print(entrance)
## print(map.get_goal_position())       # 中心出口
## [/codeblock]
##
## 约束：
## [br]- 地图平整：所有格子地面高度均为 0，没有起伏；
## [br]- 入口在矩形边缘，数量为 [member entrance_count]；
## [br]- 出口集中在中心房间，数量为 [member exit_count]；
## [br]- 所有空地一定连通（可走通）。

## 生成完成后发出，参数为自身，便于外部读取入口 / 出口位置。
signal map_generated(map: RandomMap)
## [method clear] 清空地图后发出。
signal map_cleared()

## 子节点容器名称。顺序即生成顺序：先铺地板，再在地板上摆墙。
const CONTAINER_FLOORS: StringName = &"Floors"
const CONTAINER_WALLS: StringName = &"Walls"
const CONTAINER_ENTRANCES: StringName = &"Entrances"
const CONTAINER_EXITS: StringName = &"Exits"
const CONTAINER_NAMES: Array[StringName] = [
	CONTAINER_FLOORS, CONTAINER_WALLS, CONTAINER_ENTRANCES, CONTAINER_EXITS
]

## 单个单元允许的最小尺寸，防止退化几何导致报错。
const MIN_UNIT_SIZE: float = 0.001
## 地图总长 / 总宽的最小值（米）。
const MIN_MAP_EXTENT: float = 1.0
## 地图最少格子数（每条边），与 [MazeCellularAutomata] 保持一致。
const MIN_GRID_SIZE: int = 5

@export_group("基本单元")
## 迷宫墙壁的基本单元（PackedScene）。默认是一个 1x1x1 的 CSGBox3D，
## 组件会按格子尺寸缩放它。若传入的不是 CSGBox3D / BoxMesh，
## 则按 [member wall_scene_size] 作为"单元原始尺寸"进行等比缩放。
@export var wall_scene: PackedScene = preload("res://components/map/random_map/wall_unit.tscn")
## 迷宫地板单元（PackedScene）。默认是一个 1x1x1 的 CSGBox3D。
@export var floor_scene: PackedScene = preload("res://components/map/random_map/floor_unit.tscn")
## 入口标记单元，默认是 Marker3D，会朝向地图内部。
@export var entrance_scene: PackedScene = preload("res://components/map/random_map/entrance_marker.tscn")
## 出口标记单元，默认是 Marker3D，位于中心房间。
@export var exit_scene: PackedScene = preload("res://components/map/random_map/exit_marker.tscn")
## 非 CSGBox3D / BoxMesh 墙壁单元时，单元的原始尺寸（米）。
@export var wall_scene_size: Vector3 = Vector3.ONE
## 非 CSGBox3D / BoxMesh 地板单元时，单元的原始尺寸（米）。
@export var floor_scene_size: Vector3 = Vector3.ONE
## 自定义墙壁场景（非 CSGBox3D / BoxMesh）是否按 [member wall_scene_size] 缩放到格子尺寸。
## 关闭时保留场景自身的缩放与位置，只把它摆到地板顶面上，适合树木 / 石头等装饰墙。
@export var scale_custom_wall_scene: bool = false

@export_group("尺寸")
## 地图总长度（沿 X 方向，单位：米）。
## 格子数 = round(总长度 / 单元长)，至少 5 格；实际总长度用
## [method get_actual_map_size] 查询（因为格子数是整数）。
@export_range(1.0, 2000.0, 0.5) var map_length: float = 64.0:
	set(value):
		map_length = maxf(value, MIN_MAP_EXTENT)
		_update_map_size()
## 地图总宽度（沿 Z 方向，单位：米）。
## 格子数 = round(总宽度 / 单元宽)，至少 5 格。
@export_range(1.0, 2000.0, 0.5) var map_width: float = 64.0:
	set(value):
		map_width = maxf(value, MIN_MAP_EXTENT)
		_update_map_size()
## 墙壁基本单元的长(x) x 宽(z)，默认 1m x 1m。
@export var cell_size: Vector2 = Vector2(1.0, 1.0):
	set(value):
		cell_size = Vector2(maxf(value.x, MIN_UNIT_SIZE), maxf(value.y, MIN_UNIT_SIZE))
		_update_map_size()
## 墙壁高度，默认 2m。
@export_range(0.1, 20.0, 0.1) var wall_height: float = 2.0
## 地板厚度（米）。地图是平的，地板从地面向下延伸这个厚度。
@export_range(0.01, 4.0, 0.01) var floor_thickness: float = 0.2

@export_group("出入口")
## 入口数量：分布在矩形边缘上。
@export_range(0, 32, 1) var entrance_count: int = 4
## 出口数量：全部位于中心房间内，第一个永远是地图正中心。
@export_range(0, 16, 1) var exit_count: int = 1
## 中心房间半径（格）。0 表示只有中心 1 格；出口放不下时会自动扩大。
@export_range(0, 16, 1) var center_room_radius: int = 1

@export_group("元胞自动机")
## 元胞自动机参数（墙壁疏密、生长 / 存活阈值等）。
@export var ca_config: MazeCAConfig

@export_group("生成")
## 随机种子。0 表示每次生成都使用随机种子。
@export var map_seed: int = 0
## 进入场景树时是否自动生成一次。
@export var auto_generate: bool = true
## 是否在控制台输出本次生成的统计信息。
@export var print_debug_stats: bool = false

## 由 [member map_length] / [member map_width] 与 [member cell_size] 推导出的格子数
## （只读）。需要按格子数指定大小时，请用 [method set_map_size_in_cells]。
var map_size: Vector2i = Vector2i(32, 32)

## 最近一次生成实际使用的种子。
var _last_seed: int = 0
## 当前的格子布局。
var _maze: MazeCellularAutomata
var _fallback_wall_scene: PackedScene
var _fallback_floor_scene: PackedScene
## 生成中标记：防止 wall_scene / floor_scene 误指向本组件（或包含本组件的场景）
## 时无限递归生成、耗尽引擎资源。
var _generating: bool = false


func _ready() -> void:
	_update_map_size()
	if auto_generate:
		generate()


## ---------------- 公开接口 ----------------

## 用节点上的 [member map_seed] 生成地图（0 表示随机种子）。
func generate() -> void:
	generate_with_seed(_resolve_seed())


## 用固定种子生成地图，便于复现与联机同步。
func generate_with_seed(p_seed: int) -> void:
	if _generating:
		push_warning("RandomMap: 检测到嵌套生成（wall_scene / floor_scene 引用了本组件？），已跳过。")
		return
	if not _validate_unit_scenes():
		return
	_generating = true
	_clear_generated()
	_update_map_size()
	_last_seed = p_seed
	_maze = MazeCellularAutomata.new(map_size, ca_config)
	_maze.generate(p_seed, entrance_count, exit_count, center_room_radius)
	_ensure_containers()
	_build_units()
	_build_markers()
	_generating = false
	if print_debug_stats:
		_print_stats()
	map_generated.emit(self)


## 直接按"格子数"设置地图大小（内部会换算成总长度 / 总宽度）。
func set_map_size_in_cells(cells: Vector2i) -> void:
	var grid := Vector2i(maxi(cells.x, MIN_GRID_SIZE), maxi(cells.y, MIN_GRID_SIZE))
	map_length = float(grid.x) * cell_size.x
	map_width = float(grid.y) * cell_size.y
	_update_map_size()


## 地图实际总尺寸（米）= 格子数 x 单元尺寸，返回值 (总长度, 总宽度)。
## 因为格子数只能取整，实际尺寸可能与 [member map_length] / [member map_width] 略有出入。
func get_actual_map_size() -> Vector2:
	return Vector2(
		float(map_size.x) * maxf(cell_size.x, MIN_UNIT_SIZE),
		float(map_size.y) * maxf(cell_size.y, MIN_UNIT_SIZE)
	)


## 由总长度 / 总宽度与单元尺寸推导格子数。
func _update_map_size() -> void:
	var unit_length: float = maxf(cell_size.x, MIN_UNIT_SIZE)
	var unit_width: float = maxf(cell_size.y, MIN_UNIT_SIZE)
	map_size = Vector2i(
		maxi(MIN_GRID_SIZE, roundi(maxf(map_length, MIN_MAP_EXTENT) / unit_length)),
		maxi(MIN_GRID_SIZE, roundi(maxf(map_width, MIN_MAP_EXTENT) / unit_width))
	)


## 清空已生成的墙壁 / 地板 / 标记。
func clear() -> void:
	_clear_generated()
	map_cleared.emit()


## 取本次生成的随机种子，可用于复现。
func get_last_seed() -> int:
	return _last_seed


## 取底层格子布局（高级用法，例如自己做寻路）。
func get_maze() -> MazeCellularAutomata:
	return _maze


## 地图格子数（不是米）。总尺寸用 [method get_actual_map_size]。
func get_map_size() -> Vector2i:
	return map_size


func get_cell(cell: Vector2i) -> int:
	return _maze.get_cell(cell) if _maze != null else MazeCellularAutomata.CELL_WALL


func is_wall(cell: Vector2i) -> bool:
	return _maze == null or _maze.is_wall(cell)


func is_inside(cell: Vector2i) -> bool:
	return _maze != null and _maze.is_inside(cell)


## 该格是不是入口（位于矩形边缘）。
func is_entrance_cell(cell: Vector2i) -> bool:
	return _maze != null and _maze.is_entrance(cell)


## 该格是不是出口（位于中心房间）。
func is_exit_cell(cell: Vector2i) -> bool:
	return _maze != null and _maze.is_exit(cell)


func get_center_cell() -> Vector2i:
	return _maze.center_cell if _maze != null else Vector2i.ZERO


func get_center_room_radius() -> int:
	return _maze.center_room_radius if _maze != null else 0


func get_entrance_cells() -> Array[Vector2i]:
	return _maze.entrance_cells.duplicate() if _maze != null else []


func get_exit_cells() -> Array[Vector2i]:
	return _maze.exit_cells.duplicate() if _maze != null else []


## 入口位置（本地坐标，位于地面之上，标记朝向地图内部）。
func get_entrance_positions() -> Array[Vector3]:
	var positions: Array[Vector3] = []
	if _maze == null:
		return positions
	for cell in _maze.entrance_cells:
		positions.append(get_cell_surface_position(cell))
	return positions


## 出口位置（本地坐标，位于中心房间的地面之上）。
func get_exit_positions() -> Array[Vector3]:
	var positions: Array[Vector3] = []
	if _maze == null:
		return positions
	for cell in _maze.exit_cells:
		positions.append(get_cell_surface_position(cell))
	return positions


## 推荐的角色出生点：第一个入口的地面位置。
func get_spawn_position() -> Vector3:
	if _maze == null or _maze.entrance_cells.is_empty():
		return Vector3.ZERO
	return get_cell_surface_position(_maze.entrance_cells[0])


## 中心出口（目标）位置。
func get_goal_position() -> Vector3:
	if _maze == null or _maze.exit_cells.is_empty():
		return Vector3.ZERO
	return get_cell_surface_position(_maze.exit_cells[0])


## 某一格中心的"地面表面"位置（本地坐标，y = 0，因为地图是平的）。
func get_cell_surface_position(cell: Vector2i) -> Vector3:
	var half_x: float = float(map_size.x) * cell_size.x * 0.5
	var half_z: float = float(map_size.y) * cell_size.y * 0.5
	return Vector3(
		(float(cell.x) + 0.5) * cell_size.x - half_x,
		0.0,
		(float(cell.y) + 0.5) * cell_size.y - half_z
	)


## 世界坐标 → 格子坐标，越界时返回 (-1, -1)。
func get_cell_from_world(world_position: Vector3) -> Vector2i:
	var local_position: Vector3 = to_local(world_position) if is_inside_tree() else world_position
	var half_x: float = float(map_size.x) * cell_size.x * 0.5
	var half_z: float = float(map_size.y) * cell_size.y * 0.5
	var x: int = int(floor((local_position.x + half_x) / maxf(cell_size.x, MIN_UNIT_SIZE)))
	var y: int = int(floor((local_position.z + half_z) / maxf(cell_size.y, MIN_UNIT_SIZE)))
	var cell := Vector2i(x, y)
	if _maze != null and not _maze.is_inside(cell):
		return Vector2i(-1, -1)
	return cell


## ---------------- 内部实现 ----------------

func _resolve_seed() -> int:
	if map_seed != 0:
		return map_seed
	return randi()


func _ensure_containers() -> void:
	for container_name in CONTAINER_NAMES:
		if get_node_or_null(NodePath(container_name)) == null:
			var container := Node3D.new()
			container.name = container_name
			add_child(container)


func _container(container_name: StringName) -> Node3D:
	var node := get_node_or_null(NodePath(container_name)) as Node3D
	if node == null:
		_ensure_containers()
		node = get_node_or_null(NodePath(container_name)) as Node3D
	return node


func _clear_generated() -> void:
	for container_name in CONTAINER_NAMES:
		var container := get_node_or_null(NodePath(container_name))
		if container == null:
			continue
		for child in container.get_children():
			container.remove_child(child)
			child.queue_free()
	_maze = null


## 把整张地图实例化成地板与墙壁。
##
## 分两趟进行：先给所有格子（墙壁格也包含在内）铺一层地板，再在地板顶面上
## 摆墙壁单元。这样墙壁是"立在地板上"的，不会出现地板缺口。
func _build_units() -> void:
	var walls := _container(CONTAINER_WALLS)
	var floors := _container(CONTAINER_FLOORS)
	var wall_packed := _resolve_unit_scene(wall_scene, true)
	var floor_packed := _resolve_unit_scene(floor_scene, false)
	var half_x: float = float(map_size.x) * cell_size.x * 0.5
	var half_z: float = float(map_size.y) * cell_size.y * 0.5
	var wall_packed_is_box: bool = _unit_scene_is_box(wall_packed)
	# 第一趟：所有格子都铺地板。
	for y in map_size.y:
		for x in map_size.x:
			_spawn_floor(Vector2i(x, y), _cell_base(Vector2i(x, y), half_x, half_z), floors, floor_packed)
	# 第二趟：在墙壁格的地板顶面上摆墙壁。
	for y in map_size.y:
		for x in map_size.x:
			var cell := Vector2i(x, y)
			if not _maze.is_wall(cell):
				continue
			_spawn_wall(
				cell,
				_cell_base(cell, half_x, half_z),
				walls,
				wall_packed,
				wall_packed_is_box
			)


## 某一格中心的本地坐标（y = 地面高度 0）。
func _cell_base(cell: Vector2i, half_x: float, half_z: float) -> Vector3:
	return Vector3(
		(float(cell.x) + 0.5) * cell_size.x - half_x,
		0.0,
		(float(cell.y) + 0.5) * cell_size.y - half_z
	)


## 单元场景是否为"可用尺寸直接控制的盒子"（CSGBox3D / BoxMesh）。
func _unit_scene_is_box(packed: PackedScene) -> bool:
	if packed == null:
		return false
	var instance := packed.instantiate()
	var is_box := instance is CSGBox3D
	if not is_box and instance is MeshInstance3D:
		is_box = (instance as MeshInstance3D).mesh is BoxMesh
	instance.free()
	return is_box


## 校验基本单元场景：不能包含 RandomMap（含本组件自身或任何引用它的场景），
## 否则会嵌套生成、无限递归直到耗尽引擎资源。返回 false 表示拒绝生成。
func _validate_unit_scenes() -> bool:
	var self_scene := _own_packed_scene()
	for scene in [wall_scene, floor_scene]:
		if scene == null or scene == self_scene:
			if scene == self_scene and scene != null:
				push_warning("RandomMap: wall_scene / floor_scene 不能是本组件场景，已拒绝生成。")
				return false
			continue
		if _scene_contains_random_map(scene):
			push_warning(
				"RandomMap: wall_scene / floor_scene 引用了 RandomMap 组件（%s），会嵌套生成，已拒绝生成。"
				% scene.resource_path
			)
			return false
	return true


## 本节点对应的 PackedScene（如果是场景实例化出来的）。
func _own_packed_scene() -> PackedScene:
	var current: Node = self
	while current != null:
		if current.scene_file_path != "":
			return load(current.scene_file_path) as PackedScene
		current = current.get_parent()
	return null


## 场景里是否（递归地）包含 RandomMap 节点或带 RandomMap 子场景的节点。
func _scene_contains_random_map(scene: PackedScene) -> bool:
	if scene == null:
		return false
	var instance := scene.instantiate()
	var found := _tree_contains_random_map(instance)
	instance.free()
	return found


func _tree_contains_random_map(node: Node) -> bool:
	if node is RandomMap:
		return true
	for child in node.get_children():
		if _tree_contains_random_map(child):
			return true
	return false


func _spawn_wall(
	cell: Vector2i,
	base: Vector3,
	container: Node3D,
	packed: PackedScene,
	packed_is_box: bool
) -> void:
	if packed == null or container == null:
		return
	var instance := _instantiate_unit(packed, container, "Wall_%d_%d" % [cell.x, cell.y])
	if instance == null:
		return
	# 场景自己声明的锚点偏移（相对格子中心的地面），保留作者的摆放意图。
	var anchor: Vector3 = instance.position
	if packed_is_box:
		# 盒子墙：铺满整格，从地板底面一直砌到 wall_height。
		var top: float = wall_height
		var bottom: float = -floor_thickness
		var height: float = maxf(top - bottom, MIN_UNIT_SIZE)
		instance.position = base + anchor + Vector3(0.0, (top + bottom) * 0.5, 0.0)
		_apply_unit_size(instance, Vector3(cell_size.x, height, cell_size.y), wall_scene_size)
		return
	if not scale_custom_wall_scene:
		# 自定义场景：保留自身尺寸，摆在格子中心的地板顶面上（y = 0）。
		instance.position = base + anchor
		return
	var size := Vector3(cell_size.x, maxf(wall_height, MIN_UNIT_SIZE), cell_size.y)
	instance.position = base + anchor + Vector3(0.0, wall_height * 0.5, 0.0)
	_apply_unit_size(instance, size, wall_scene_size)


func _spawn_floor(
	cell: Vector2i,
	base: Vector3,
	container: Node3D,
	packed: PackedScene
) -> void:
	if packed == null or container == null:
		return
	# 地板顶面 = 地面高度 0，向下延伸 floor_thickness。
	var top: float = 0.0
	var bottom: float = -floor_thickness
	var height: float = maxf(top - bottom, MIN_UNIT_SIZE)
	var instance := _instantiate_unit(packed, container, "Floor_%d_%d" % [cell.x, cell.y])
	if instance == null:
		return
	instance.position = base + Vector3(0.0, (top + bottom) * 0.5, 0.0)
	_apply_unit_size(instance, Vector3(cell_size.x, height, cell_size.y), floor_scene_size)


func _build_markers() -> void:
	var entrances := _container(CONTAINER_ENTRANCES)
	var exits := _container(CONTAINER_EXITS)
	for index in _maze.entrance_cells.size():
		var cell: Vector2i = _maze.entrance_cells[index]
		var marker := _spawn_marker(
			entrance_scene, entrances, "Entrance_%d" % index, get_cell_surface_position(cell)
		)
		if marker != null:
			marker.rotation.y = _entrance_yaw(cell)
	for index in _maze.exit_cells.size():
		var cell: Vector2i = _maze.exit_cells[index]
		_spawn_marker(exit_scene, exits, "Exit_%d" % index, get_cell_surface_position(cell))


## 入口标记的朝向：面朝地图内部。
func _entrance_yaw(cell: Vector2i) -> float:
	if cell.y <= 0:
		return PI
	if cell.y >= map_size.y - 1:
		return 0.0
	if cell.x <= 0:
		return -PI * 0.5
	return PI * 0.5


func _instantiate_unit(packed: PackedScene, container: Node3D, node_name: String) -> Node3D:
	if packed == null or container == null:
		return null
	var instance := packed.instantiate() as Node3D
	if instance == null:
		push_warning("RandomMap: 基本单元场景的根节点必须是 Node3D。")
		return null
	instance.name = node_name
	container.add_child(instance)
	return instance


func _spawn_marker(
	packed: PackedScene,
	container: Node3D,
	node_name: String,
	position: Vector3
) -> Node3D:
	if container == null:
		return null
	var marker: Node3D
	if packed == null:
		marker = Marker3D.new()
		marker.name = node_name
		container.add_child(marker)
	else:
		marker = _instantiate_unit(packed, container, node_name)
		if marker == null:
			return null
	marker.position = position
	return marker


## 按"目标尺寸"配置单元：CSGBox3D 直接用 size，BoxMesh 替换 mesh，
## 其它场景则按 [param native_size] 等比缩放。
func _apply_unit_size(unit: Node3D, target_size: Vector3, native_size: Vector3) -> void:
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
	var safe_native := Vector3(
		maxf(native_size.x, MIN_UNIT_SIZE),
		maxf(native_size.y, MIN_UNIT_SIZE),
		maxf(native_size.z, MIN_UNIT_SIZE)
	)
	unit.scale = Vector3(
		target_size.x / safe_native.x,
		target_size.y / safe_native.y,
		target_size.z / safe_native.z
	)


## 基本单元为空时用代码生成的替代品，保证组件始终可用。
func _resolve_unit_scene(scene: PackedScene, is_wall: bool) -> PackedScene:
	if scene != null:
		return scene
	if is_wall:
		if _fallback_wall_scene == null:
			_fallback_wall_scene = _build_fallback_unit(Color(0.42, 0.44, 0.48))
		return _fallback_wall_scene
	if _fallback_floor_scene == null:
		_fallback_floor_scene = _build_fallback_unit(Color(0.28, 0.33, 0.24))
	return _fallback_floor_scene


func _build_fallback_unit(color: Color) -> PackedScene:
	var box := CSGBox3D.new()
	box.size = Vector3.ONE
	box.use_collision = true
	var material := StandardMaterial3D.new()
	material.albedo_color = color
	box.material = material
	var packed := PackedScene.new()
	var result := packed.pack(box)
	box.free()
	if result != OK:
		push_warning("RandomMap: 无法创建默认单元场景。")
		return null
	return packed


func _print_stats() -> void:
	if _maze == null:
		return
	var actual_size := get_actual_map_size()
	print(
		"[RandomMap] seed=%d 尺寸=%d格x%d格（%.1fm x %.1fm）空地=%.0f%% 入口=%d 出口=%d"
		% [
			_last_seed,
			map_size.x,
			map_size.y,
			actual_size.x,
			actual_size.y,
			_maze.floor_ratio() * 100.0,
			_maze.entrance_cells.size(),
			_maze.exit_cells.size(),
		]
	)

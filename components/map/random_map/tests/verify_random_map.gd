extends SceneTree
## RandomMap 组件自检脚本（无需编辑器，直接跑无头模式）。
##
## 运行方式（在项目根目录执行）：
## [codeblock]
## /Applications/Godot.app/Contents/MacOS/Godot --headless --script res://components/map/random_map/tests/verify_random_map.gd
## [/codeblock]
## 全部通过时进程退出码为 0，否则为 1。

const MAP_SCENE: PackedScene = preload("res://components/map/random_map/random_map.tscn")
const SEEDS: Array[int] = [1, 7, 42, 1234, 20260101, 999983]
const EPSILON: float = 0.001

var _checks: int = 0
var _failures: int = 0
var _ran: bool = false


## 注意：要等到第一帧再跑测试，因为在 [method _initialize] 阶段
## 根节点还没有进入场景树，节点的 [method Node._ready] 不会被调用。
func _process(_delta: float) -> bool:
	if _ran:
		return true
	_ran = true
	_run_all()
	return true


func _run_all() -> void:
	print("=== RandomMap 组件自检 ===")
	_test_generation_invariants()
	_test_determinism()
	_test_component_default()
	_test_component_custom_config()
	_test_component_without_scenes()
	_test_two_pass_layering()
	_test_regenerate_and_clear()
	_test_map_extent_parameters()
	_test_split_blocks_config()

	print("=== 检查项 %d，失败 %d ===" % [_checks, _failures])
	if _failures == 0:
		print("全部通过 ✅")
	else:
		print("存在失败 ❌")
	quit(1 if _failures > 0 else 0)


func _check(condition: bool, message: String) -> void:
	_checks += 1
	if not condition:
		_failures += 1
		print("  [FAIL] ", message)


func _section(title: String) -> void:
	print("-- ", title)


## ---------------- 1. 纯格子生成的不变量 ----------------

func _test_generation_invariants() -> void:
	_section("格子生成不变量")
	var size := Vector2i(32, 32)
	var config := MazeCAConfig.new()
	var ratios: Array[float] = []
	for seed in SEEDS:
		var maze := MazeCellularAutomata.new(size, config)
		var started := Time.get_ticks_usec()
		maze.generate(seed, 4, 1, 1)
		var elapsed := float(Time.get_ticks_usec() - started) / 1000.0
		ratios.append(maze.floor_ratio())

		_check(maze.size == size, "seed=%d 尺寸正确" % seed)
		_check(maze.floor_ratio() > 0.2 and maze.floor_ratio() < 0.65,
			"seed=%d 空地占比在合理区间（实际 %.0f%%）" % [seed, maze.floor_ratio() * 100.0])
		_check(_open_block_ratio(maze) < 0.25,
			"seed=%d 是迷宫般的窄通道结构（2x2 空地占比 %.3f）" % [seed, _open_block_ratio(maze)])
		_check(_wall_block_count(maze, 3) == 0,
			"seed=%d 无 3x3 及以上实心墙块（实际 %d 个）" % [seed, _wall_block_count(maze, 3)])
		_check(_wall_block_count(maze, 4) == 0,
			"seed=%d 无 4x4 及以上实心墙块（实际 %d 个）" % [seed, _wall_block_count(maze, 4)])
		_check(_open_block_count(maze, 4) == 0,
			"seed=%d 无 4x4 及以上整块空地（实际 %d 个）" % [seed, _open_block_count(maze, 4)])
		_check(maze.is_fully_connected(), "seed=%d 所有空地连通（可走通）" % seed)
		_check(maze.is_floor(maze.center_cell), "seed=%d 地图中心是空地" % seed)

		# 入口：数量正确、位于矩形边缘、是空地、且能走到中心
		_check(maze.entrance_cells.size() == 4,
			"seed=%d 入口数量 = 4（实际 %d）" % [seed, maze.entrance_cells.size()])
		for entrance in maze.entrance_cells:
			_check(maze.is_border_cell(entrance), "seed=%d 入口 %s 位于边缘" % [seed, entrance])
			_check(maze.is_floor(entrance), "seed=%d 入口 %s 是空地" % [seed, entrance])
			var reachable := maze.find_reachable_cells(entrance)
			_check(reachable.has(maze.center_cell),
				"seed=%d 入口 %s 可以走到中心" % [seed, entrance])
		# 边缘上除了入口之外不应有别的缺口
		for y in size.y:
			for x in size.x:
				var cell := Vector2i(x, y)
				if not maze.is_border_cell(cell):
					continue
				if maze.is_floor(cell):
					_check(maze.is_entrance(cell),
						"seed=%d 边缘缺口 %s 必须是入口" % [seed, cell])

		# 出口：位于中心房间
		_check(maze.exit_cells.size() == 1,
			"seed=%d 出口数量 = 1（实际 %d）" % [seed, maze.exit_cells.size()])
		_check(maze.exit_cells.has(maze.center_cell), "seed=%d 出口就在中心格" % seed)
		for exit_cell in maze.exit_cells:
			var distance: int = maxi(
				absi(exit_cell.x - maze.center_cell.x), absi(exit_cell.y - maze.center_cell.y)
			)
			_check(distance <= maze.center_room_radius,
				"seed=%d 出口 %s 在中心房间内（半径 %d）" % [seed, exit_cell, maze.center_room_radius])
		print("   seed=%d 空地=%.0f%% 生成耗时=%.1fms" % [seed, maze.floor_ratio() * 100.0, elapsed])
	var min_ratio: float = ratios[0]
	var max_ratio: float = ratios[0]
	for ratio in ratios:
		min_ratio = minf(min_ratio, ratio)
		max_ratio = maxf(max_ratio, ratio)
	_check(max_ratio - min_ratio > 0.01, "不同种子会产生不同的地图（空地占比 %.0f%%~%.0f%%）"
		% [min_ratio * 100.0, max_ratio * 100.0])

	# 不同尺寸都要能生成连通且带出入口的地图
	for map_dimension in [12, 16, 24, 32, 48]:
		var dimension := Vector2i(map_dimension, map_dimension)
		var maze := MazeCellularAutomata.new(dimension, config)
		maze.generate(20260101, 4, 3, 2)
		_check(maze.is_fully_connected(), "%dx%d 地图连通" % [map_dimension, map_dimension])
		_check(maze.entrance_cells.size() == 4,
			"%dx%d 地图有 4 个边缘入口（实际 %d）" % [map_dimension, map_dimension, maze.entrance_cells.size()])
		for entrance in maze.entrance_cells:
			_check(maze.is_border_cell(entrance), "%dx%d 入口 %s 在边缘" % [map_dimension, map_dimension, entrance])
		_check(maze.exit_cells.size() == 3,
			"%dx%d 地图有 3 个中心出口（实际 %d）" % [map_dimension, map_dimension, maze.exit_cells.size()])
		for exit_cell in maze.exit_cells:
			var distance: int = maxi(
				absi(exit_cell.x - maze.center_cell.x), absi(exit_cell.y - maze.center_cell.y)
			)
			_check(distance <= maze.center_room_radius,
				"%dx%d 出口 %s 在中心房间内" % [map_dimension, map_dimension, exit_cell])
		print("   %dx%d 空地=%.0f%% 房间半径=%d" % [
			map_dimension, map_dimension, maze.floor_ratio() * 100.0, maze.center_room_radius])


## 2x2 全空地比例：越低说明越接近"窄通道"的迷宫，而不是大片洞窟。
func _open_block_ratio(maze: MazeCellularAutomata) -> float:
	var blocks: int = 0
	for y in maze.size.y - 1:
		for x in maze.size.x - 1:
			if (
				maze.is_floor(Vector2i(x, y))
				and maze.is_floor(Vector2i(x + 1, y))
				and maze.is_floor(Vector2i(x, y + 1))
				and maze.is_floor(Vector2i(x + 1, y + 1))
			):
				blocks += 1
	var floors := maze.count_floor_cells()
	return 0.0 if floors == 0 else float(blocks) / float(floors)


## block x block 全墙方块（或全空方块）的个数。
func _wall_block_count(maze: MazeCellularAutomata, block: int) -> int:
	var count := 0
	for y in maze.size.y - block + 1:
		for x in maze.size.x - block + 1:
			var matched := true
			for dy in block:
				for dx in block:
					if not maze.is_wall(Vector2i(x + dx, y + dy)):
						matched = false
						break
				if not matched:
					break
			if matched:
				count += 1
	return count


## block x block 全空方块的个数。
func _open_block_count(maze: MazeCellularAutomata, block: int) -> int:
	var count := 0
	for y in maze.size.y - block + 1:
		for x in maze.size.x - block + 1:
			var matched := true
			for dy in block:
				for dx in block:
					if not maze.is_floor(Vector2i(x + dx, y + dy)):
						matched = false
						break
				if not matched:
					break
			if matched:
				count += 1
	return count


## ---------------- 2. 可复现性 ----------------

func _test_determinism() -> void:
	_section("可复现性")
	var size := Vector2i(24, 24)
	var first := MazeCellularAutomata.new(size, MazeCAConfig.new())
	first.generate(20260101, 4, 1, 1)
	var second := MazeCellularAutomata.new(size, MazeCAConfig.new())
	second.generate(20260101, 4, 1, 1)
	_check(first.cells == second.cells, "相同种子生成完全相同的格子布局")

	var third := MazeCellularAutomata.new(size, MazeCAConfig.new())
	third.generate(20260102, 4, 1, 1)
	_check(first.cells != third.cells, "不同种子生成不同的格子布局")


## ---------------- 3. 组件（默认参数） ----------------

func _test_component_default() -> void:
	_section("组件：默认参数（32x32 / 4 入口 / 1 出口）")
	var map := _spawn_map(true)
	_check(map != null, "组件实例化成功")
	if map == null:
		return
	_check(map.get_maze() != null, "auto_generate 在 _ready 中自动生成了地图")
	var started := Time.get_ticks_msec()
	map.generate_with_seed(20260101)
	var elapsed := float(Time.get_ticks_msec() - started)

	var cell_total: int = map.get_map_size().x * map.get_map_size().y
	_check(map.get_maze() != null, "固定种子重新生成成功")
	# 第一趟铺满地板：所有格子都有地板
	_check(_child_count(map, &"Floors") == cell_total,
		"地板铺满所有格子（%d）" % cell_total)
	# 第二趟在地板上摆墙：墙数 = 墙壁格数，且墙与地板都有
	var wall_cell_count: int = map.get_maze().get_wall_cells().size()
	_check(_child_count(map, &"Walls") == wall_cell_count,
		"墙壁数量 = 墙壁格数（%d）" % wall_cell_count)
	_check(_child_count(map, &"Walls") > 0 and wall_cell_count < cell_total,
		"墙壁格同时也是地板格，两者不是互斥关系")
	_check(_child_count(map, &"Entrances") == 4, "入口标记 4 个")
	_check(_child_count(map, &"Exits") == 1, "出口标记 1 个")

	for cell in map.get_entrance_cells():
		_check(map.is_inside(cell) and map.is_entrance_cell(cell), "入口格 %s 合法" % cell)
	for position in map.get_entrance_positions():
		var cell := map.get_cell_from_world(map.to_global(position))
		_check(map.is_entrance_cell(cell), "入口标记位置落在入口格上（%s）" % cell)
	_check(map.is_exit_cell(map.get_center_cell()), "中心格就是出口")

	# 墙壁尺寸：地图是平的，墙高恒为 wall_height + 地板厚度（墙底与地板底面齐平）
	var tallest_wall: float = 0.0
	var wall_bottom_lowest: float = INF
	for child in map.get_node(NodePath("Walls")).get_children():
		if child is CSGBox3D:
			var box := child as CSGBox3D
			tallest_wall = maxf(tallest_wall, box.size.y)
			wall_bottom_lowest = minf(wall_bottom_lowest, box.position.y - box.size.y * 0.5)
	_check(tallest_wall > 0.0, "墙壁单元生成了有效高度（最大 %.2fm）" % tallest_wall)
	_check(is_equal_approx(tallest_wall, map.wall_height + map.floor_thickness),
		"平地地图墙高 = wall_height + floor_thickness（实际 %.2fm）" % tallest_wall)
	_check(is_equal_approx(wall_bottom_lowest, -map.floor_thickness),
		"墙底与地板底面齐平（实际 %.2f）" % wall_bottom_lowest)

	# 墙在地板上：抽样检查地板顶面在 y = 0，且每个墙壁格下方都能找到同名地板
	var floors := map.get_node(NodePath("Floors"))
	var sampled_cells: Array[Vector2i] = [
		map.get_center_cell(), Vector2i(5, 7), map.get_entrance_cells()[0]
	]
	var wall_cells: Array[Vector2i] = map.get_maze().get_wall_cells()
	if not wall_cells.is_empty():
		sampled_cells.append(wall_cells[0])
	for cell in sampled_cells:
		var floor_node := floors.get_node_or_null(NodePath("Floor_%d_%d" % [cell.x, cell.y]))
		_check(floor_node != null, "格 %s 铺了地板" % cell)
		var floor_box := floor_node as CSGBox3D
		if floor_box != null:
			_check(is_equal_approx(floor_box.position.y + floor_box.size.y * 0.5, 0.0),
				"格 %s 的地板顶面在 y = 0" % cell)

	# 地面是平的：所有格子的地面坐标 y 都是 0
	for cell in [map.get_center_cell(), Vector2i(5, 7), map.get_entrance_cells()[0]]:
		_check(is_zero_approx(map.get_cell_surface_position(cell).y),
			"格 %s 的地面高度为 0" % cell)
	var cell_round_trip := map.get_cell_from_world(map.to_global(map.get_cell_surface_position(Vector2i(5, 7))))
	_check(cell_round_trip == Vector2i(5, 7), "世界坐标与格子坐标可以互相转换")
	print("   32x32 组件生成耗时 = %.0fms" % elapsed)
	_free_map(map)


## ---------------- 4. 组件（自定义参数） ----------------

func _test_component_custom_config() -> void:
	_section("组件：自定义参数（16x16 / 2 入口 / 2 出口 / 房间半径 0）")
	var map := _spawn_map()
	if map == null:
		_check(false, "组件实例化成功")
		return
	map.set_map_size_in_cells(Vector2i(16, 16))
	map.cell_size = Vector2(1.5, 1.5)
	map.wall_height = 3.0
	map.entrance_count = 2
	map.exit_count = 2
	map.center_room_radius = 0
	map.ca_config = MazeCAConfig.new()
	map.ca_config.wall_fill_ratio = 0.5
	map.ca_config.birth_limit = 5
	map.generate_with_seed(777)
	var maze := map.get_maze()
	_check(maze != null, "自定义参数生成成功")
	if maze == null:
		_free_map(map)
		return
	_check(maze.entrance_cells.size() == 2, "入口数量 = 2（实际 %d）" % maze.entrance_cells.size())
	_check(maze.exit_cells.size() == 2, "出口数量 = 2（实际 %d）" % maze.exit_cells.size())
	_check(maze.center_room_radius >= 1, "出口放不下时自动扩大中心房间（半径 %d）" % maze.center_room_radius)
	_check(_child_count(map, &"Entrances") == 2, "入口标记数量与参数一致")
	_check(_child_count(map, &"Exits") == 2, "出口标记数量与参数一致")
	# 所有出口都能从入口走到
	for entrance in maze.entrance_cells:
		var reachable := maze.find_reachable_cells(entrance)
		for exit_cell in maze.exit_cells:
			_check(reachable.has(exit_cell), "入口 %s 能走到出口 %s" % [entrance, exit_cell])
	_check(map.get_cell_from_world(map.to_global(map.get_spawn_position())) == maze.entrance_cells[0],
		"出生点坐标对应第一个入口")
	_check(map.get_cell_from_world(map.to_global(map.get_goal_position())) == maze.exit_cells[0],
		"目标点坐标落在第一个出口格上")
	_free_map(map)


## ---------------- 6. 未提供基本单元时的兜底 ----------------

func _test_component_without_scenes() -> void:
	_section("组件：未指定基本单元（使用内置兜底单元）")
	var map := RandomMap.new()
	map.wall_scene = null
	map.floor_scene = null
	map.entrance_scene = null
	map.exit_scene = null
	map.set_map_size_in_cells(Vector2i(12, 12))
	map.auto_generate = false
	get_root().add_child(map)
	map.generate_with_seed(314159)
	_check(map.get_maze() != null, "兜底场景也能生成地图")
	_check(_child_count(map, &"Walls") > 0, "生成了兜底墙壁单元")
	_check(_child_count(map, &"Floors") > 0, "生成了兜底地板单元")
	_check(_child_count(map, &"Entrances") == 4, "生成了入口标记")
	_check(_child_count(map, &"Exits") == 1, "生成了出口标记")
	_free_map(map)


## ---------------- 7. 两趟分层：先铺地板，再在地板上放墙 ----------------

func _test_two_pass_layering() -> void:
	_section("两趟分层：先铺地板，再在地板上放墙")
	var map := _spawn_map()
	if map == null:
		_check(false, "组件实例化成功")
		return
	map.set_map_size_in_cells(Vector2i(20, 20))
	map.generate_with_seed(4242)
	var maze := map.get_maze()
	var cell_total: int = map.get_map_size().x * map.get_map_size().y

	# 1. 每一格都有地板，包括墙壁格
	var floors := map.get_node(NodePath("Floors"))
	var walls := map.get_node(NodePath("Walls"))
	var missing_floor: int = 0
	var checked_wall_floors: int = 0
	for y in map.get_map_size().y:
		for x in map.get_map_size().x:
			var cell := Vector2i(x, y)
			var floor_node := floors.get_node_or_null(NodePath("Floor_%d_%d" % [cell.x, cell.y]))
			if floor_node == null:
				missing_floor += 1
			elif maze.is_wall(cell):
				checked_wall_floors += 1
	_check(_child_count(map, &"Floors") == cell_total, "地板覆盖全部 %d 格" % cell_total)
	_check(missing_floor == 0, "没有缺失的地板格（缺失 %d）" % missing_floor)
	_check(checked_wall_floors == maze.get_wall_cells().size(),
		"每个墙壁格都铺了地板（%d 格）" % checked_wall_floors)

	# 2. 墙壁立在地板顶面上：墙底不高于 y = 0，墙顶高于 y = 0
	var wall_below: int = 0
	var wall_above: int = 0
	for child in walls.get_children():
		var box := child as CSGBox3D
		if box == null:
			continue
		var bottom: float = box.position.y - box.size.y * 0.5
		var top: float = box.position.y + box.size.y * 0.5
		if bottom > EPSILON:
			wall_below += 1
		if top <= EPSILON:
			wall_above += 1
	_check(wall_below == 0, "没有悬空在地板之上的墙（%d 个）" % wall_below)
	_check(wall_above == 0, "所有墙都高出地面（%d 个没有）" % wall_above)

	# 3. 容器顺序体现两趟：Floors 先于 Walls 生成
	_check(floors.get_index() < walls.get_index(),
		"Floors 容器排在 Walls 之前（%d < %d）" % [floors.get_index(), walls.get_index()])
	_free_map(map)


## ---------------- 8. 重新生成与清空 ----------------

func _test_regenerate_and_clear() -> void:
	_section("重新生成与清空")
	var map := _spawn_map()
	if map == null:
		_check(false, "组件实例化成功")
		return
	map.set_map_size_in_cells(Vector2i(14, 14))
	map.generate_with_seed(1)
	var first_seed: int = map.get_last_seed()
	map.generate_with_seed(2)
	_check(map.get_last_seed() == 2 and first_seed == 1, "重新生成会更新种子")
	var cell_total: int = 14 * 14
	_check(_child_count(map, &"Floors") == cell_total,
		"重新生成后地板仍铺满 %d 格（不累积）" % cell_total)
	_check(_child_count(map, &"Walls") == map.get_maze().get_wall_cells().size(),
		"重新生成后墙壁数量 = 墙壁格数")
	map.clear()
	_check(map.get_maze() == null, "clear() 清空地图数据")
	_check(_child_count(map, &"Walls") == 0 and _child_count(map, &"Floors") == 0,
		"clear() 移除所有墙壁与地板")
	_check(_child_count(map, &"Entrances") == 0 and _child_count(map, &"Exits") == 0,
		"clear() 移除所有出入口标记")
	_free_map(map)


## ---------------- 9. 地图总长度 / 总宽度 ----------------

func _test_map_extent_parameters() -> void:
	_section("尺寸参数：地图总长度 / 地图总宽度")
	var probe := RandomMap.new()
	probe.auto_generate = false

	probe.cell_size = Vector2.ONE
	probe.map_length = 48.0
	probe.map_width = 32.0
	_check(probe.get_map_size() == Vector2i(48, 32),
		"48m x 32m（1m 单元）→ 48 x 32 格（实际 %s）" % probe.get_map_size())
	_check(probe.get_actual_map_size().is_equal_approx(Vector2(48, 32)),
		"实际总尺寸 = 48m x 32m（实际 %s）" % probe.get_actual_map_size())

	probe.cell_size = Vector2(1.5, 1.5)
	_check(probe.get_map_size() == Vector2i(32, 21),
		"换成 1.5m 单元后格子数随之变化（实际 %s）" % probe.get_map_size())
	_check(probe.get_actual_map_size().is_equal_approx(Vector2(48, 31.5)),
		"总宽 32m 取整后实际 31.5m（实际 %s）" % probe.get_actual_map_size())

	probe.map_length = 10.0
	probe.map_width = 10.0
	_check(probe.get_map_size() == Vector2i(7, 7),
		"10m / 1.5m 四舍五入为 7 格（实际 %s）" % probe.get_map_size())
	_check(is_equal_approx(probe.get_actual_map_size().x, 10.5),
		"实际总长度 = 10.5m（实际 %.2f）" % probe.get_actual_map_size().x)

	probe.cell_size = Vector2.ONE
	probe.map_length = 1.0
	probe.map_width = 1.0
	_check(probe.get_map_size() == Vector2i(5, 5),
		"总长 / 总宽过小时至少 5 格（实际 %s）" % probe.get_map_size())
	_check(probe.get_actual_map_size() == Vector2(5, 5), "最小时实际总尺寸 = 5m x 5m")

	probe.set_map_size_in_cells(Vector2i(20, 10))
	_check(probe.map_length == 20.0 and probe.map_width == 10.0,
		"按格子数设置会换算成总长 20m / 总宽 10m（实际 %.1f / %.1f）"
		% [probe.map_length, probe.map_width])
	_check(probe.get_map_size() == Vector2i(20, 10),
		"按格子数设置后格子数正确（实际 %s）" % probe.get_map_size())
	probe.free()

	# 实际几何：24m x 18m + 1.5m 单元 → 16 x 12 格，占地范围应正好是 24m x 18m
	var map := _spawn_map()
	if map == null:
		_check(false, "组件实例化成功")
		return
	map.cell_size = Vector2(1.5, 1.5)
	map.map_length = 24.0
	map.map_width = 18.0
	map.generate_with_seed(20260101)
	_check(map.get_map_size() == Vector2i(16, 12),
		"24m x 18m（1.5m 单元）→ 16 x 12 格（实际 %s）" % map.get_map_size())
	_check(_child_count(map, &"Floors") == 16 * 12,
		"地板数量 = 格子总数（%d）" % (16 * 12))
	_check(_child_count(map, &"Walls") == map.get_maze().get_wall_cells().size(),
		"墙壁数量 = 墙壁格数（%d）" % map.get_maze().get_wall_cells().size())
	var bounds := _unit_bounds(map)
	_check(
		is_equal_approx(bounds.position.x, -12.0) and is_equal_approx(bounds.end.x, 12.0),
		"地图沿 X 方向总长 24m（实际 %.2f ~ %.2f）" % [bounds.position.x, bounds.end.x]
	)
	_check(
		is_equal_approx(bounds.position.z, -9.0) and is_equal_approx(bounds.end.z, 9.0),
		"地图沿 Z 方向总宽 18m（实际 %.2f ~ %.2f）" % [bounds.position.z, bounds.end.z]
	)
	var footprint_ok := true
	for child in map.get_node(NodePath("Floors")).get_children():
		var box := child as CSGBox3D
		if box == null:
			continue
		if not (is_equal_approx(box.size.x, 1.5) and is_equal_approx(box.size.z, 1.5)):
			footprint_ok = false
	_check(footprint_ok, "地板单元占位 = 墙壁基本单元长宽 1.5m x 1.5m")
	_check(map.get_cell_from_world(Vector3.ZERO) == map.get_center_cell(),
		"地图以原点为中心（原点落在中心格上）")
	_free_map(map)


## ---------------- 10. 防大块后处理参数 ----------------

func _test_split_blocks_config() -> void:
	_section("防大块后处理参数")
	var size := Vector2i(32, 32)
	for seed in SEEDS:
		# 关闭后处理：会出现大块实心墙（CA 的天然倾向）。
		var config := MazeCAConfig.new()
		config.split_wall_chunks = false
		config.split_open_rooms = false
		var legacy := MazeCellularAutomata.new(size, config)
		legacy.generate(seed, 4, 1, 1)
		_check(_wall_block_count(legacy, 3) > 0,
			"seed=%d 关闭后处理时会出现 3x3 实心墙块（实际 %d 个）"
			% [seed, _wall_block_count(legacy, 3)])

		# 开启后处理（默认）：无 3x3 以上实心墙块、无 4x4 以上整块空地。
		var maze := MazeCellularAutomata.new(size, MazeCAConfig.new())
		maze.generate(seed, 4, 1, 1)
		_check(_wall_block_count(maze, 3) == 0,
			"seed=%d 打散大墙块后无 3x3 实心墙块（实际 %d 个）"
			% [seed, _wall_block_count(maze, 3)])
		_check(_open_block_count(maze, 4) == 0,
			"seed=%d 拆分大空房后无 4x4 整块空地（实际 %d 个）"
			% [seed, _open_block_count(maze, 4)])
		_check(maze.is_fully_connected(),
			"seed=%d 防大块处理后地图仍然连通" % seed)

		# 放宽阈值：允许 5x5 实心墙块时，最多只应出现 5x5。
		var loose := MazeCAConfig.new()
		loose.max_wall_thickness = 2
		loose.max_open_room = 5
		var loose_maze := MazeCellularAutomata.new(size, loose)
		loose_maze.generate(seed, 4, 1, 1)
		_check(_wall_block_count(loose_maze, 6) == 0,
			"seed=%d 放宽阈值后无 6x6 实心墙块（实际 %d 个）"
			% [seed, _wall_block_count(loose_maze, 6)])
		_check(loose_maze.is_fully_connected(),
			"seed=%d 放宽阈值后地图仍然连通" % seed)


## ---------------- 工具函数 ----------------

func _spawn_map(auto: bool = false) -> RandomMap:
	if MAP_SCENE == null:
		return null
	var map := MAP_SCENE.instantiate() as RandomMap
	if map == null:
		return null
	map.auto_generate = auto
	get_root().add_child(map)
	return map


func _child_count(map: RandomMap, container_name: StringName) -> int:
	var container := map.get_node_or_null(NodePath(container_name))
	if container == null:
		return -1
	return container.get_child_count()


func _free_map(map: RandomMap) -> void:
	if map.get_parent() != null:
		map.get_parent().remove_child(map)
	map.queue_free()


## 所有墙壁 / 地板单元合起来的世界包围盒（地图原点在中心）。
func _unit_bounds(map: RandomMap) -> AABB:
	var minimum := Vector3(INF, INF, INF)
	var maximum := Vector3(-INF, -INF, -INF)
	for container_name in [&"Walls", &"Floors"]:
		var container := map.get_node_or_null(NodePath(container_name))
		if container == null:
			continue
		for child in container.get_children():
			var box := child as CSGBox3D
			if box == null:
				continue
			var half := box.size * 0.5
			var low := box.position - half
			var high := box.position + half
			minimum = Vector3(minf(minimum.x, low.x), minf(minimum.y, low.y), minf(minimum.z, low.z))
			maximum = Vector3(maxf(maximum.x, high.x), maxf(maximum.y, high.y), maxf(maximum.z, high.z))
	return AABB(minimum, maximum - minimum)

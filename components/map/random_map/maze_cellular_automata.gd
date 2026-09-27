class_name MazeCellularAutomata
extends RefCounted
## 元胞自动机迷宫生成器。
##
## 只负责"格子层面"的生成，不涉及任何 3D 节点：
## [codeblock]
## 随机填充 → CA 平滑 → 打散大块墙 → 拆分大空房 → 外圈墙壁
## → 中心出口房间 → 区域连通 → 出入口开凿
## [/codeblock]
## 生成结果通过 [member cells]（1 = 墙壁，0 = 空地）、[member entrance_cells]、
## [member exit_cells] 暴露给上层，由 [RandomMap] 负责变成 3D 场景。

## 空地。
const CELL_FLOOR: int = 0
## 墙壁。
const CELL_WALL: int = 1

## 4 邻接与 8 邻接（Moore）方向。
const NEIGHBOURS_4: Array[Vector2i] = [
	Vector2i(0, -1), Vector2i(1, 0), Vector2i(0, 1), Vector2i(-1, 0)
]
## 边缘顺序：上、右、下、左。出入口按该顺序轮流分配，保证分布在不同边缘上。
const EDGES: Array[Vector2i] = [
	Vector2i(0, -1), Vector2i(1, 0), Vector2i(0, 1), Vector2i(-1, 0)
]

## 地图尺寸（单位：格）。
var size: Vector2i = Vector2i(32, 32)
## 元胞自动机参数。
var config: MazeCAConfig
## 格子数据，[code]1 = 墙壁, 0 = 空地[/code]，索引为 [code]x + y * size.x[/code]。
var cells: PackedByteArray = PackedByteArray()
## 中心格（出口目标所在位置）。
var center_cell: Vector2i = Vector2i.ZERO
## 实际使用的中心房间半径（格）。
var center_room_radius: int = 0
## 入口格（位于矩形边缘，从外圈墙壁上打通）。
var entrance_cells: Array[Vector2i] = []
## 出口格（位于中心房间内）。
var exit_cells: Array[Vector2i] = []

## 与"主区域"（最大空地）连通的格子掩码，用于连通性开凿。
var _main_mask: PackedByteArray = PackedByteArray()
var _rng := RandomNumberGenerator.new()


func _init(p_size: Vector2i = Vector2i(32, 32), p_config: MazeCAConfig = null) -> void:
	size = Vector2i(maxi(p_size.x, 5), maxi(p_size.y, 5))
	config = p_config if p_config != null else MazeCAConfig.new()
	center_cell = Vector2i(size.x / 2, size.y / 2)
	cells.resize(size.x * size.y)
	_main_mask.resize(size.x * size.y)


## 生成整张迷宫地图。
## [param p_seed] 随机种子；相同种子会得到完全相同的地图。
## [param p_entrance_count] 边缘入口数量。
## [param p_exit_count] 中心出口数量。
## [param p_center_room_radius] 中心房间半径（格，0 表示只有中心 1 格）。
func generate(
	p_seed: int,
	p_entrance_count: int,
	p_exit_count: int,
	p_center_room_radius: int
) -> void:
	_rng.seed = p_seed
	entrance_cells.clear()
	exit_cells.clear()
	_fill_random()
	_smooth()
	_apply_border()
	# 先拆分大空房再挖中心房间，避免中心房间被加柱子；
	# 连通开凿放在最后修复所有断裂，打散大墙块则必须在连通之后，
	# 否则小区域填充（墙壁化）会重新制造大块墙体。
	_split_open_rooms()
	center_room_radius = _resolve_room_radius(p_center_room_radius, p_exit_count)
	_carve_center_room()
	_connect_regions()
	_break_wall_chunks()
	_place_exits(p_exit_count)
	_carve_entrances(p_entrance_count)


## ---------------- 查询接口 ----------------

func index_of(cell: Vector2i) -> int:
	return cell.y * size.x + cell.x


func cell_of(index: int) -> Vector2i:
	return Vector2i(index % size.x, index / size.x)


func is_inside(cell: Vector2i) -> bool:
	return cell.x >= 0 and cell.y >= 0 and cell.x < size.x and cell.y < size.y


func get_cell(cell: Vector2i) -> int:
	if not is_inside(cell):
		return CELL_WALL
	return cells[index_of(cell)]


func is_wall(cell: Vector2i) -> bool:
	return get_cell(cell) == CELL_WALL


func is_floor(cell: Vector2i) -> bool:
	return is_inside(cell) and get_cell(cell) == CELL_FLOOR


func is_entrance(cell: Vector2i) -> bool:
	return entrance_cells.has(cell)


func is_exit(cell: Vector2i) -> bool:
	return exit_cells.has(cell)


## 该格是否位于外圈墙壁上（出入口会从这里打通）。
func is_border_cell(cell: Vector2i) -> bool:
	var thickness := _border_thickness()
	if thickness <= 0:
		return false
	return (
		cell.x < thickness
		or cell.y < thickness
		or cell.x >= size.x - thickness
		or cell.y >= size.y - thickness
	)


func _border_thickness() -> int:
	return clampi(config.border_thickness, 0, mini(size.x, size.y) / 2)


func get_floor_cells() -> Array[Vector2i]:
	var result: Array[Vector2i] = []
	for y in size.y:
		for x in size.x:
			if cells[y * size.x + x] == CELL_FLOOR:
				result.append(Vector2i(x, y))
	return result


func get_wall_cells() -> Array[Vector2i]:
	var result: Array[Vector2i] = []
	for y in size.y:
		for x in size.x:
			if cells[y * size.x + x] == CELL_WALL:
				result.append(Vector2i(x, y))
	return result


func count_floor_cells() -> int:
	var total: int = 0
	for value in cells:
		if value == CELL_FLOOR:
			total += 1
	return total


## 空地占比（0 ~ 1）。
func floor_ratio() -> float:
	if cells.is_empty():
		return 0.0
	return float(count_floor_cells()) / float(cells.size())


## 从 [param origin] 出发能到达的全部空地格（4 邻接）。
func find_reachable_cells(origin: Vector2i) -> Array[Vector2i]:
	var reachable: Array[Vector2i] = []
	if not is_floor(origin):
		return reachable
	var visited := PackedByteArray()
	visited.resize(cells.size())
	var queue: Array[Vector2i] = [origin]
	visited[index_of(origin)] = 1
	var head: int = 0
	while head < queue.size():
		var cell: Vector2i = queue[head]
		head += 1
		reachable.append(cell)
		for direction in NEIGHBOURS_4:
			var next_cell: Vector2i = cell + direction
			if not is_floor(next_cell):
				continue
			var next_index: int = index_of(next_cell)
			if visited[next_index] == 1:
				continue
			visited[next_index] = 1
			queue.append(next_cell)
	return reachable


## 整张地图的空地是否两两连通。
func is_fully_connected() -> bool:
	var floors := count_floor_cells()
	if floors == 0:
		return false
	for y in size.y:
		for x in size.x:
			var cell := Vector2i(x, y)
			if is_floor(cell):
				return find_reachable_cells(cell).size() == floors
	return false


## 两格之间的最短通路（允许穿墙，用于验证连通性），无通路返回空数组。
func find_path(from: Vector2i, to: Vector2i) -> Array[Vector2i]:
	var path: Array[Vector2i] = []
	if not is_inside(from) or not is_inside(to):
		return path
	var parent := PackedInt32Array()
	parent.resize(cells.size())
	parent.fill(-1)
	var start_index: int = index_of(from)
	parent[start_index] = start_index
	var queue: Array[Vector2i] = [from]
	var head: int = 0
	var target_index: int = index_of(to)
	while head < queue.size():
		var cell: Vector2i = queue[head]
		head += 1
		if index_of(cell) == target_index:
			var current: int = target_index
			while true:
				path.append(cell_of(current))
				if parent[current] == current:
					break
				current = parent[current]
			path.reverse()
			return path
		for direction in NEIGHBOURS_4:
			var next_cell: Vector2i = cell + direction
			if not is_inside(next_cell):
				continue
			var next_index: int = index_of(next_cell)
			if parent[next_index] != -1:
				continue
			parent[next_index] = index_of(cell)
			queue.append(next_cell)
	return path


## ---------------- 生成步骤 ----------------

func _fill_random() -> void:
	var wall_ratio: float = clampf(config.wall_fill_ratio, 0.0, 1.0)
	for index in cells.size():
		cells[index] = CELL_WALL if _rng.randf() < wall_ratio else CELL_FLOOR


## Moore 邻域的 CA 规则：地图外的格子一律视作墙壁，因此边缘会自然收敛为实心。
func _smooth() -> void:
	for iteration in maxi(config.smoothing_iterations, 0):
		var next := PackedByteArray()
		next.resize(cells.size())
		for y in size.y:
			for x in size.x:
				var index: int = y * size.x + x
				var walls: int = _wall_neighbour_count(Vector2i(x, y))
				if cells[index] == CELL_WALL:
					next[index] = CELL_WALL if walls >= config.death_limit else CELL_FLOOR
				else:
					next[index] = CELL_WALL if walls >= config.birth_limit else CELL_FLOOR
		cells = next


func _wall_neighbour_count(cell: Vector2i) -> int:
	var count: int = 0
	for dy in range(-1, 2):
		for dx in range(-1, 2):
			if dx == 0 and dy == 0:
				continue
			var neighbour := Vector2i(cell.x + dx, cell.y + dy)
			if not is_inside(neighbour):
				count += 1
			elif cells[index_of(neighbour)] == CELL_WALL:
				count += 1
	return count


## 打散大块实心墙体：CA 收敛后经常留下大片"实心墙芯"——离最近空地很远、
## 玩家完全看不见也碰不到的墙。这里反复找出"埋得最深"的墙芯，沿 BFS
## 距离场一路下坡开凿到最近的空地，直到所有墙都离空地足够近为止。
##
## 凿出的走廊沿距离场单调下降，因此必然与已有空地连通，不会产生新的孤岛。
func _break_wall_chunks() -> void:
	var max_thickness: int = maxi(config.max_wall_thickness, 0)
	if not config.split_wall_chunks or max_thickness <= 0:
		return
	# 墙芯判定：距离最近空地 > max_thickness 步的墙格属于"埋没墙"。
	var depth_limit: int = max_thickness
	var guard: int = 0
	var guard_limit: int = cells.size()
	while guard < guard_limit:
		guard += 1
		var distances := _distance_to_floor()
		# 找出埋得最深的墙芯（外圈墙壁不参与，避免破坏封闭边缘）。
		var best := Vector2i(-1, -1)
		var best_depth: int = depth_limit
		for y in size.y:
			for x in size.x:
				var cell := Vector2i(x, y)
				if not is_wall(cell) or is_border_cell(cell):
					continue
				if distances[index_of(cell)] > best_depth:
					best_depth = distances[index_of(cell)]
					best = cell
		if best.x < 0:
			break
		# 沿距离场下坡开凿：每一步都走"更靠近空地"的墙格，直到接上空地。
		var cursor := best
		cells[index_of(cursor)] = CELL_FLOOR
		while true:
			var next_cell := _step_downhill(cursor, distances)
			if next_cell.x < 0:
				break
			cells[index_of(next_cell)] = CELL_FLOOR
			cursor = next_cell


## 找到 [param cell] 的 4 邻中距离场更低的墙格（下坡方向），没有返回 (-1, -1)。
func _step_downhill(cell: Vector2i, distances: PackedInt32Array) -> Vector2i:
	var best := Vector2i(-1, -1)
	var best_distance: int = distances[index_of(cell)]
	for direction in NEIGHBOURS_4:
		var neighbour: Vector2i = cell + direction
		if not is_inside(neighbour) or not is_wall(neighbour):
			continue
		var distance: int = distances[index_of(neighbour)]
		if distance < best_distance:
			best_distance = distance
			best = neighbour
	return best


## 拆分大块空房间：出现 [code](max_open_room + 1) x (max_open_room + 1)[/code]
## 的整块空地时，在中心立一根柱子。反复执行直到没有超大的整块空地。
func _split_open_rooms() -> void:
	if not config.split_open_rooms:
		return
	var block: int = maxi(config.max_open_room, 1) + 1
	var guard: int = 0
	var guard_limit: int = cells.size()
	while guard < guard_limit:
		guard += 1
		var pillar := _find_open_block(block)
		if pillar.x < 0:
			break
		cells[index_of(pillar)] = CELL_WALL


## 找出第一个 [param block] x [param block] 整块空地的"中心柱"位置，
## 找不到返回 (-1, -1)。
func _find_open_block(block: int) -> Vector2i:
	for y in range(size.y - block + 1):
		for x in range(size.x - block + 1):
			if _is_open_block(Vector2i(x, y), block):
				return Vector2i(x + block / 2, y + block / 2)
	return Vector2i(-1, -1)


func _is_open_block(origin: Vector2i, block: int) -> bool:
	for dy in block:
		for dx in block:
			if is_wall(Vector2i(origin.x + dx, origin.y + dy)):
				return false
	return true


## 每个格子到最近空地的 4 邻接 BFS 距离（空地自身为 0）。
func _distance_to_floor() -> PackedInt32Array:
	var distances := PackedInt32Array()
	distances.resize(cells.size())
	distances.fill(-1)
	var queue: Array[Vector2i] = []
	for index in cells.size():
		if cells[index] == CELL_FLOOR:
			distances[index] = 0
			queue.append(cell_of(index))
	var head: int = 0
	while head < queue.size():
		var cell: Vector2i = queue[head]
		head += 1
		var cell_index: int = index_of(cell)
		for direction in NEIGHBOURS_4:
			var next_cell: Vector2i = cell + direction
			if not is_inside(next_cell):
				continue
			var next_index: int = index_of(next_cell)
			if distances[next_index] != -1:
				continue
			distances[next_index] = distances[cell_index] + 1
			queue.append(next_cell)
	return distances


func _apply_border() -> void:
	if _border_thickness() <= 0:
		return
	for y in size.y:
		for x in size.x:
			var cell := Vector2i(x, y)
			if is_border_cell(cell):
				cells[index_of(cell)] = CELL_WALL


## 计算一个能容纳 [param exit_count] 个出口的中心房间半径。
func _resolve_room_radius(requested: int, exit_count: int) -> int:
	var max_radius: int = maxi(0, mini(size.x, size.y) / 2 - 2)
	var radius: int = clampi(requested, 0, max_radius)
	var needed: int = maxi(exit_count, 1)
	while radius < max_radius and (2 * radius + 1) * (2 * radius + 1) < needed:
		radius += 1
	return radius


func _carve_center_room() -> void:
	for dy in range(-center_room_radius, center_room_radius + 1):
		for dx in range(-center_room_radius, center_room_radius + 1):
			var cell := center_cell + Vector2i(dx, dy)
			if is_inside(cell):
				cells[index_of(cell)] = CELL_FLOOR


## 找出所有空地连通区域：保留最大区域作为主区域，其余区域用走廊打通；
## 太小的碎块直接填成墙壁。这样保证整张地图 100% 可达。
##
## 注意：必须先把"太小的碎块"填成墙壁，再做连通开凿。
## 否则后填的碎块有可能落在之前开凿出来的走廊上，把走廊重新堵死。
func _connect_regions() -> void:
	var regions := _collect_regions()
	if regions.is_empty():
		# 极端情况（全墙）：直接在中心挖一格，保证地图至少有一块空地。
		cells[index_of(center_cell)] = CELL_FLOOR
		regions = [([center_cell] as Array[Vector2i])]
	regions.sort_custom(
		func(a: Array, b: Array) -> bool: return a.size() > b.size()
	)
	# 第一步：挑出要保留的区域，其余（含过小的碎块）全部填成墙壁。
	var kept: Array = [regions[0]]
	for region_index in range(1, regions.size()):
		var region: Array = regions[region_index]
		if config.connect_regions and region.size() >= maxi(config.min_region_size, 1):
			kept.append(region)
			continue
		for cell in region:
			cells[index_of(cell)] = CELL_WALL
	# 第二步：主区域 = 最大的保留区域。
	_main_mask.fill(0)
	for cell in kept[0]:
		_main_mask[index_of(cell)] = 1
	# 第三步：把其它保留区域用走廊接到主区域上。
	for region_index in range(1, kept.size()):
		var region: Array = kept[region_index]
		var path := _find_path_to_main(region)
		for cell in path:
			cells[index_of(cell)] = CELL_FLOOR
			_main_mask[index_of(cell)] = 1
		for cell in region:
			_main_mask[index_of(cell)] = 1


func _collect_regions() -> Array:
	var visited := PackedByteArray()
	visited.resize(cells.size())
	var regions: Array = []
	for y in size.y:
		for x in size.x:
			var start := Vector2i(x, y)
			var start_index: int = index_of(start)
			if visited[start_index] == 1 or cells[start_index] == CELL_WALL:
				continue
			var region: Array[Vector2i] = []
			var queue: Array[Vector2i] = [start]
			visited[start_index] = 1
			var head: int = 0
			while head < queue.size():
				var cell: Vector2i = queue[head]
				head += 1
				region.append(cell)
				for direction in NEIGHBOURS_4:
					var next_cell: Vector2i = cell + direction
					if not is_inside(next_cell):
						continue
					var next_index: int = index_of(next_cell)
					if visited[next_index] == 1 or cells[next_index] == CELL_WALL:
						continue
					visited[next_index] = 1
					queue.append(next_cell)
			regions.append(region)
	return regions


## 从 [param sources] 出发做 BFS（可以穿墙），找到最近的主区域格子并返回通路。
func _find_path_to_main(sources: Array) -> Array[Vector2i]:
	var path: Array[Vector2i] = []
	var parent := PackedInt32Array()
	parent.resize(cells.size())
	parent.fill(-1)
	var queue: Array[Vector2i] = []
	for source in sources:
		var cell: Vector2i = source
		parent[index_of(cell)] = index_of(cell)
		queue.append(cell)
	var head: int = 0
	var target_index: int = -1
	while head < queue.size():
		var cell: Vector2i = queue[head]
		head += 1
		var cell_index: int = index_of(cell)
		if _main_mask[cell_index] == 1:
			target_index = cell_index
			break
		for direction in NEIGHBOURS_4:
			var next_cell: Vector2i = cell + direction
			# 开凿时不允许破坏外圈墙壁，否则地图边缘会出现莫名其妙的缺口。
			if not is_inside(next_cell) or is_border_cell(next_cell):
				continue
			var next_index: int = index_of(next_cell)
			if parent[next_index] != -1:
				continue
			parent[next_index] = cell_index
			queue.append(next_cell)
	if target_index == -1:
		return path
	var current: int = target_index
	while true:
		path.append(cell_of(current))
		if parent[current] == current:
			break
		current = parent[current]
	path.reverse()
	return path


## 出口放在中心房间里：中心格优先，然后逐圈向外。
func _place_exits(exit_count: int) -> void:
	var ordered: Array[Vector2i] = [center_cell]
	for radius in range(1, center_room_radius + 1):
		for dy in range(-radius, radius + 1):
			for dx in range(-radius, radius + 1):
				if maxi(absi(dx), absi(dy)) != radius:
					continue
				var cell := center_cell + Vector2i(dx, dy)
				if is_inside(cell):
					ordered.append(cell)
	var wanted: int = clampi(exit_count, 0, ordered.size())
	for index in wanted:
		exit_cells.append(ordered[index])


## 在矩形四条边上轮流开凿入口，每条入口都是一条笔直向内掘进的走廊，
## 最后再用 BFS 把它接到主区域上，保证"从入口能走到地图里"。
func _carve_entrances(entrance_count: int) -> void:
	if entrance_count <= 0:
		return
	var count: int = clampi(entrance_count, 0, 64)
	var edge_offset: int = _rng.randi_range(0, EDGES.size() - 1)
	var max_depth: int = maxi(size.x, size.y)
	for index in count:
		var edge: Vector2i = EDGES[(index + edge_offset) % EDGES.size()]
		# 同一条边上随机取点时可能撞车，重试几次保证每个入口位置都不同。
		var start := Vector2i(-1, -1)
		for attempt in 8:
			start = _pick_edge_cell(edge)
			if start.x < 0 or not entrance_cells.has(start):
				break
		if start.x < 0:
			continue
		var inward: Vector2i = -edge
		var corridor: Array[Vector2i] = [start]
		cells[index_of(start)] = CELL_FLOOR
		var cell: Vector2i = start
		var depth: int = 0
		while depth < max_depth:
			var next_cell: Vector2i = cell + inward
			if not is_inside(next_cell) or is_floor(next_cell):
				break
			cell = next_cell
			cells[index_of(cell)] = CELL_FLOOR
			corridor.append(cell)
			depth += 1
		# 把这条走廊接到主区域（如果它还没接上的话）。
		var path := _find_path_to_main(corridor)
		for path_cell in path:
			cells[index_of(path_cell)] = CELL_FLOOR
			_main_mask[index_of(path_cell)] = 1
		for corridor_cell in corridor:
			_main_mask[index_of(corridor_cell)] = 1
		entrance_cells.append(start)


## 在某条边上随机选一个入口位置（避开四个角），返回 (-1, -1) 表示该边太短。
func _pick_edge_cell(edge: Vector2i) -> Vector2i:
	var margin: int = maxi(config.border_thickness, 1) + 1
	if edge.y != 0:
		# 上 / 下边缘：沿 x 方向分布
		var min_x: int = margin
		var max_x: int = size.x - margin - 1
		if max_x < min_x:
			return Vector2i(-1, -1)
		var x: int = _rng.randi_range(min_x, max_x)
		var y: int = 0 if edge.y < 0 else size.y - 1
		return Vector2i(x, y)
	# 左 / 右边缘：沿 y 方向分布
	var min_y: int = margin
	var max_y: int = size.y - margin - 1
	if max_y < min_y:
		return Vector2i(-1, -1)
	var y: int = _rng.randi_range(min_y, max_y)
	var x: int = 0 if edge.x < 0 else size.x - 1
	return Vector2i(x, y)

class_name TerrainHeightField
extends RefCounted
## 地形高度场：按格记录地面高度（单位：米，y 轴向上）。
##
## 生成流程：
## [codeblock]
## 分形噪声 → 出入口/中心区域压平 → 平滑 → 相邻格最大高差约束 → 归一化
## [/codeblock]
## 最后一步的约束保证 [code]|h(a) - h(b)| <= max_step_height[/code] 对任意
## 4 邻接的格子成立，也就是"地势是连续的、没有断崖"。

## 相邻格方向（上/右/下/左）。
const NEIGHBOURS_4: Array[Vector2i] = [
	Vector2i(0, -1), Vector2i(1, 0), Vector2i(0, 1), Vector2i(-1, 0)
]

## 地图尺寸（单位：格）。
var size: Vector2i = Vector2i.ZERO
## 按 [code]x + y * size.x[/code] 索引的高度数组。
var heights: PackedFloat32Array = PackedFloat32Array()
## 生成后的最低 / 最高高度。
var min_height: float = 0.0
var max_height: float = 0.0

var _config: TerrainHeightConfig


func _init(p_size: Vector2i = Vector2i.ZERO, p_config: TerrainHeightConfig = null) -> void:
	_config = p_config if p_config != null else TerrainHeightConfig.new()
	if p_size.x > 0 and p_size.y > 0:
		generate(p_size, [], 0)


## 生成高度场。
## [param flat_anchors] 中的格子及其邻域会被压平（出入口、中心目标等）。
func generate(p_size: Vector2i, flat_anchors: Array[Vector2i], p_seed: int) -> void:
	size = Vector2i(maxi(p_size.x, 1), maxi(p_size.y, 1))
	heights = PackedFloat32Array()
	heights.resize(size.x * size.y)
	_sample_noise(p_seed)
	_flatten_anchors(flat_anchors)
	_smooth(_config.smoothing_passes)
	_enforce_max_step(_config.max_step_height)
	_finalize()


## 取某一格的地面高度；越界时返回最近格子的高度。
func height_at(cell: Vector2i) -> float:
	if heights.is_empty():
		return 0.0
	var x: int = clampi(cell.x, 0, size.x - 1)
	var y: int = clampi(cell.y, 0, size.y - 1)
	return heights[y * size.x + x]


## 取某一格的地面高度；越界返回 0。
func height_at_or_zero(cell: Vector2i) -> float:
	if not is_inside(cell) or heights.is_empty():
		return 0.0
	return heights[cell.y * size.x + cell.x]


func is_inside(cell: Vector2i) -> bool:
	return cell.x >= 0 and cell.y >= 0 and cell.x < size.x and cell.y < size.y


## 相对高差（最高点 - 最低点）。
func height_range() -> float:
	return max_height - min_height


func _sample_noise(p_seed: int) -> void:
	var noise := FastNoiseLite.new()
	noise.seed = p_seed
	noise.noise_type = FastNoiseLite.TYPE_SIMPLEX_SMOOTH
	noise.frequency = _config.noise_frequency
	noise.fractal_type = FastNoiseLite.FRACTAL_FBM
	noise.fractal_octaves = _config.noise_octaves
	noise.fractal_gain = 0.5
	noise.fractal_lacunarity = 2.0
	var variation: float = maxf(_config.height_variation, 0.0)
	for y in size.y:
		for x in size.x:
			# 噪声输出 [-1, 1]，映射到 [0, height_variation]
			var value: float = noise.get_noise_2d(float(x), float(y))
			heights[y * size.x + x] = (value + 1.0) * 0.5 * variation


## 把锚点及其邻域压成一块平地，高度取该邻域的平均值，避免出现尖顶。
func _flatten_anchors(anchors: Array[Vector2i]) -> void:
	var radius: int = maxi(_config.anchor_flat_radius, 0)
	if radius <= 0 or anchors.is_empty():
		return
	for anchor in anchors:
		if not is_inside(anchor):
			continue
		var total: float = 0.0
		var count: int = 0
		for dy in range(-radius, radius + 1):
			for dx in range(-radius, radius + 1):
				var cell := anchor + Vector2i(dx, dy)
				if not is_inside(cell):
					continue
				total += heights[cell.y * size.x + cell.x]
				count += 1
		if count <= 0:
			continue
		var average: float = total / float(count)
		for dy in range(-radius, radius + 1):
			for dx in range(-radius, radius + 1):
				var cell := anchor + Vector2i(dx, dy)
				if not is_inside(cell):
					continue
				heights[cell.y * size.x + cell.x] = average


## 3x3 均值模糊，让坡面过渡更自然。
func _smooth(passes: int) -> void:
	for pass_index in maxi(passes, 0):
		var smoothed := PackedFloat32Array()
		smoothed.resize(heights.size())
		for y in size.y:
			for x in size.x:
				var total: float = 0.0
				var count: int = 0
				for dy in range(-1, 2):
					for dx in range(-1, 2):
						var cell := Vector2i(x + dx, y + dy)
						if not is_inside(cell):
							continue
						total += heights[cell.y * size.x + cell.x]
						count += 1
				smoothed[y * size.x + x] = total / float(count)
		heights = smoothed


## 强制相邻格高差不超过 [param step]，保证地势连续（无断崖）。
## 采用 Gauss-Seidel 式松弛，每轮都会把过高的格子压低 / 过低的格子抬高，
## 直到没有违例或达到迭代上限。
func _enforce_max_step(step: float) -> void:
	if step <= 0.0:
		return
	var max_iterations: int = maxi(4, size.x + size.y)
	for iteration in max_iterations:
		var changed := false
		for y in size.y:
			for x in size.x:
				var index: int = y * size.x + x
				for direction in NEIGHBOURS_4:
					var neighbour := Vector2i(x + direction.x, y + direction.y)
					if not is_inside(neighbour):
						continue
					var neighbour_index: int = neighbour.y * size.x + neighbour.x
					var difference: float = heights[index] - heights[neighbour_index]
					if difference > step:
						heights[index] = heights[neighbour_index] + step
						changed = true
					elif difference < -step:
						heights[neighbour_index] = heights[index] + step
						changed = true
		if not changed:
			break


func _finalize() -> void:
	_update_range()
	if not _config.normalize_to_zero or is_zero_approx(min_height):
		return
	var offset: float = min_height
	for index in heights.size():
		heights[index] = heights[index] - offset
	_update_range()


func _update_range() -> void:
	if heights.is_empty():
		min_height = 0.0
		max_height = 0.0
		return
	var lowest: float = heights[0]
	var highest: float = heights[0]
	for value in heights:
		lowest = minf(lowest, value)
		highest = maxf(highest, value)
	min_height = lowest
	max_height = highest

extends SceneTree
## 开发用脚本：统计高度场的"平地块"情况，辅助判断地势是否过于平坦。
##
## 运行方式：
## /Applications/Godot.app/Contents/MacOS/Godot --headless --path . \
##   --script res://components/map/random_map/tests/dump_height_stats.gd

const SEEDS: Array[int] = [1, 7, 42, 1234, 20260101, 999983]
const FLAT_EPSILON := 0.03


func _process(_delta: float) -> bool:
	_run()
	quit(0)
	return true


func _run() -> void:
	var config := TerrainHeightConfig.new()
	print("=== 高度场平坦度统计（默认参数 noise_frequency=%.3f）===" % config.noise_frequency)
	for dimension in [32, 64]:
		var size := Vector2i(dimension, dimension)
		for seed in SEEDS:
			var field := TerrainHeightField.new()
			field.generate(size, [], seed)
			var plateaus := _flat_plateaus(field)
			var largest: int = 0
			var flat_cells: int = 0
			for plateau in plateaus:
				largest = maxi(largest, plateau)
				if plateau >= 20:
					flat_cells += plateau
			print("  %dx%d seed=%d: 高差=%.2fm 平地块数=%d 最大平地=%d格 (>=20格的平地占%.0f%%)" % [
				dimension, dimension, seed, field.height_range(),
				plateaus.size(), largest,
				100.0 * float(flat_cells) / float(size.x * size.y),
			])


## 相邻格高差 < FLAT_EPSILON 视为同一块平地，返回每块平地的格数。
func _flat_plateaus(field: TerrainHeightField) -> Array[int]:
	var visited := {}
	var plateaus: Array[int] = []
	for y in field.size.y:
		for x in field.size.x:
			var start := Vector2i(x, y)
			if visited.has(start):
				continue
			var queue: Array[Vector2i] = [start]
			visited[start] = true
			var head := 0
			while head < queue.size():
				var cell: Vector2i = queue[head]
				head += 1
				for direction in TerrainHeightField.NEIGHBOURS_4:
					var next_cell: Vector2i = cell + direction
					if visited.has(next_cell) or not field.is_inside(next_cell):
						continue
					if absf(field.height_at(cell) - field.height_at(next_cell)) < FLAT_EPSILON:
						visited[next_cell] = true
						queue.append(next_cell)
			plateaus.append(queue.size())
	return plateaus

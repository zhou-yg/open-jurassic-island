extends SceneTree
## 开发用统计脚本：打印若干种子下迷宫的"大块空地"指标，辅助调参。
##
## 运行方式：
## /Applications/Godot.app/Contents/MacOS/Godot --headless --path . \
##   --script res://components/map/random_map/tests/dump_maze_stats.gd

const SEEDS: Array[int] = [1, 7, 42, 1234, 20260101, 999983, 555, 88888]
const SIZES: Array[int] = [32, 48, 64]


func _process(_delta: float) -> bool:
	_run_stats()
	quit(0)
	return true


func _run_stats() -> void:
	var config := MazeCAConfig.new()
	print("=== Maze 结构统计（默认参数，含防大块后处理）===")
	for dimension in SIZES:
		var size := Vector2i(dimension, dimension)
		var open_ratios: Array[float] = []
		var block_ratios: Array[float] = []
		var open3_ratios: Array[float] = []
		var region_sizes: Array[int] = []
		var wall3_counts: Array[int] = []
		var wall4_counts: Array[int] = []
		for seed in SEEDS:
			var maze := MazeCellularAutomata.new(size, config)
			maze.generate(seed, 4, 1, 1)
			var open2 := _open_block_ratio(maze, 2)
			var open3 := _open_block_ratio(maze, 3)
			open_ratios.append(maze.floor_ratio())
			block_ratios.append(open2)
			open3_ratios.append(open3)
			region_sizes.append(_largest_open_region(maze))
			wall3_counts.append(_wall_block_count(maze, 3))
			wall4_counts.append(_wall_block_count(maze, 4))
		print("  %dx%d: 空地 %.0f%%~%.0f%% | 2x2空地 %.1f%%~%.1f%% | 3x3空地 %.1f%%~%.1f%% | 3x3实心墙 %d~%d 个 | 4x4实心墙 %d~%d 个 | 最大空地面积 %d~%d" % [
			dimension, dimension,
			_min(open_ratios) * 100.0, _max(open_ratios) * 100.0,
			_min(block_ratios) * 100.0, _max(block_ratios) * 100.0,
			_min(open3_ratios) * 100.0, _max(open3_ratios) * 100.0,
			_min_int(wall3_counts), _max_int(wall3_counts),
			_min_int(wall4_counts), _max_int(wall4_counts),
			_min_int(region_sizes), _max_int(region_sizes),
		])


func _open_block_ratio(maze: MazeCellularAutomata, block: int) -> float:
	var blocks: int = 0
	for y in maze.size.y - block + 1:
		for x in maze.size.x - block + 1:
			var all_open := true
			for dy in block:
				for dx in block:
					if not maze.is_floor(Vector2i(x + dx, y + dy)):
						all_open = false
						break
				if not all_open:
					break
			if all_open:
				blocks += 1
	var floors := maze.count_floor_cells()
	return 0.0 if floors == 0 else float(blocks) / float(floors)


func _largest_open_region(maze: MazeCellularAutomata) -> int:
	var visited := {}
	var largest := 0
	for y in maze.size.y:
		for x in maze.size.x:
			var start := Vector2i(x, y)
			if visited.has(start) or not maze.is_floor(start):
				continue
			var queue: Array[Vector2i] = [start]
			visited[start] = true
			var head := 0
			var count := 0
			while head < queue.size():
				var cell: Vector2i = queue[head]
				head += 1
				count += 1
				for direction in MazeCellularAutomata.NEIGHBOURS_4:
					var next_cell: Vector2i = cell + direction
					if visited.has(next_cell) or not maze.is_floor(next_cell):
						continue
					visited[next_cell] = true
					queue.append(next_cell)
			largest = maxi(largest, count)
	return largest


## 全墙 block x block 方块的个数。
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


func _min(values: Array) -> float:
	var result: float = values[0]
	for value in values:
		result = minf(result, value)
	return result


func _max(values: Array) -> float:
	var result: float = values[0]
	for value in values:
		result = maxf(result, value)
	return result


func _min_int(values: Array) -> int:
	var result: int = values[0]
	for value in values:
		result = mini(result, value)
	return result


func _max_int(values: Array) -> int:
	var result: int = values[0]
	for value in values:
		result = maxi(result, value)
	return result

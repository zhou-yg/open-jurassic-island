extends SceneTree
## 开发用脚本：把指定种子 / 参数的迷宫用字符画打印出来，便于人工观察"大块"情况。
##
## 运行方式：
## /Applications/Godot.app/Contents/MacOS/Godot --headless --path . \
##   --script res://components/map/random_map/tests/render_maze_text.gd

const SEEDS: Array[int] = [1, 7, 42, 1234, 20260101, 999983]
const SIZE := Vector2i(32, 32)


func _process(_delta: float) -> bool:
	_render_all()
	quit(0)
	return true


func _render_all() -> void:
	var config := MazeCAConfig.new()
	print("=== 默认参数（已启用防大块后处理）===")
	for seed in SEEDS:
		var maze := MazeCellularAutomata.new(SIZE, config)
		maze.generate(seed, 4, 1, 1)
		print("=== seed=%d %dx%d ===" % [seed, SIZE.x, SIZE.y])
		_render(maze)
	print("=== 关闭防大块后处理（旧行为）===")
	var legacy := MazeCAConfig.new()
	legacy.split_wall_chunks = false
	legacy.split_open_rooms = false
	for seed in SEEDS:
		var maze := MazeCellularAutomata.new(SIZE, legacy)
		maze.generate(seed, 4, 1, 1)
		print("=== legacy seed=%d %dx%d ===" % [seed, SIZE.x, SIZE.y])
		_render(maze)


func _render(maze: MazeCellularAutomata) -> void:
	for y in SIZE.y:
		var row := ""
		for x in SIZE.x:
			var cell := Vector2i(x, y)
			if maze.is_entrance(cell):
				row += "E"
			elif maze.is_exit(cell):
				row += "X"
			elif maze.is_floor(cell):
				row += "."
			else:
				row += "#"
		print(row)
	print("")

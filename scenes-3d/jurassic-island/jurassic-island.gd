extends Node3D
## 侏罗纪岛主场景。
##
## 由三部分组成（见 requirements/scenes/juraasic-main.md 与
## requirements/components/jurassic-island.md）：
## [br]1. 随机地图： [RandomMap] 组件，墙壁换成树木单元，让整座岛长满树；
## [br]2. 岛屿： assets/island/sky-island-basic.glb；
## [br]3. 海： components/sea/sea.tscn。
##
## 本脚本只做三件事：把随机地图对齐到岛屿的平整台面上、在入口处生成玩家、
## 打印一次生成摘要。三部分的具体摆放仍然写在场景文件里（见 .tscn）。

## 随机地图组件。
@onready var random_map: RandomMap = $RandomMap
## 岛屿节点（其子节点是 sky-island-basic.glb 实例）。
@onready var island: Node3D = $Island
## 玩家（第一人称）。
@onready var player: CharacterBody3D = $Player

## 岛屿模型里"平整台面"的本地高度（未乘节点缩放的原始 glb 单位）。
## sky-island-basic.glb 的顶面是一块平的台地，本地 y = 0.71，正好用来承载随机地图。
@export var island_plateau_local_height: float = 0.71
## 随机地图底面相对岛屿台面的抬升量，避免两者共面产生 z-fighting。
@export var maze_clearance: float = 0.02
## 是否把玩家放到随机地图的第一个入口。
@export var spawn_player_at_entrance: bool = true
## 出生点相对地面的抬升，避免玩家卡进地板。
@export var spawn_height_offset: float = 0.7
## 出生后是否让玩家面朝地图中心（也就是入口走廊的方向）。
@export var face_map_center_on_spawn: bool = true


func _ready() -> void:
	_align_maze_to_island()
	random_map.map_generated.connect(_on_map_generated)
	# 子节点的 _ready 早于本节点，地图在进入场景树时就可能已经生成好了。
	if random_map.get_maze() != null:
		_on_map_generated(random_map)


## 把随机地图摆到"岛屿台面正上方"。
##
## 岛屿台面的世界高度 = 岛屿节点 y + 局部台面高度 x 节点缩放，
## 所以只要改岛屿的缩放 / 位置，随机地图会自动跟着对齐。
func _align_maze_to_island() -> void:
	var plateau_height: float = (
		island.position.y + island_plateau_local_height * island.scale.y
	)
	random_map.position.y = plateau_height + maze_clearance


## 地图（重新）生成后：把玩家放到第一个入口，并朝向地图中心。
func _on_map_generated(map: RandomMap) -> void:
	if not spawn_player_at_entrance:
		return
	var spawn: Vector3 = map.to_global(map.get_spawn_position())
	if face_map_center_on_spawn:
		var goal: Vector3 = map.to_global(map.get_goal_position())
		var forward := goal - spawn
		forward.y = 0.0
		if forward.length_squared() > 0.0001:
			# 玩家朝 -Z 前进（见 player.gd 的 Input.get_vector 用法）。
			player.rotation.y = atan2(-forward.x, -forward.z)
	player.global_position = spawn + Vector3(0.0, spawn_height_offset, 0.0)
	print(
		"[JurassicIsland] 种子=%d 尺寸=%dx%d 格 入口=%d 出口=%d 玩家=%s 中心目标=%s"
		% [
			map.get_last_seed(),
			map.get_map_size().x,
			map.get_map_size().y,
			map.get_entrance_positions().size(),
			map.get_exit_positions().size(),
			player.global_position,
			map.to_global(map.get_goal_position()),
		]
	)

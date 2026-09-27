@tool
extends Node3D
## [RandomMap] 组件的演示场景脚本。
##
## 演示内容：
## [br]- 读取 [method RandomMap.get_entrance_positions] / [method RandomMap.get_exit_positions]
##   并生成可视化柱子（绿色 = 入口，金色 = 出口）；
## [br]- 按 [member regenerate_key]（默认 R）用随机种子重新生成一张地图。
##
## 运行方式：直接用 Godot 打开本场景运行即可（[code]components/map/random_map/random_map_demo.tscn[/code]）。

## 重新生成地图的按键。
@export var regenerate_key: Key = KEY_R

const ENTRANCE_COLOR: Color = Color(0.2, 0.9, 0.35)
const EXIT_COLOR: Color = Color(1.0, 0.75, 0.15)

@onready var _map: RandomMap = $RandomMap
@onready var _camera: Camera3D = $Camera3D
@onready var _sun: DirectionalLight3D = $Sun

var _visuals: Node3D


func _ready() -> void:
	_visuals = Node3D.new()
	_visuals.name = "DebugVisuals"
	add_child(_visuals)

	_sun.rotation_degrees = Vector3(-52.0, -38.0, 0.0)
	_camera.look_at_from_position(_camera.position, Vector3.ZERO, Vector3.UP)

	_map.map_generated.connect(_on_map_generated)
	_map.map_cleared.connect(_clear_visuals)
	# 子节点的 _ready 先于本节点执行，所以第一张地图可能已经生成好了。
	if _map.get_maze() != null:
		_on_map_generated(_map)


func _unhandled_key_input(event: InputEvent) -> void:
	var key_event := event as InputEventKey
	if key_event == null or not key_event.pressed or key_event.echo:
		return
	if key_event.keycode == regenerate_key:
		_map.generate_with_seed(randi())


func _on_map_generated(map: RandomMap) -> void:
	print(
		"[RandomMapDemo] 种子=%d 入口=%d 个 出口=%d 个 出生点=%s 目标点=%s 按 %s 重新生成"
		% [
			map.get_last_seed(),
			map.get_entrance_positions().size(),
			map.get_exit_positions().size(),
			map.get_spawn_position(),
			map.get_goal_position(),
			OS.get_keycode_string(regenerate_key),
		]
	)
	_clear_visuals()
	for entrance_position in map.get_entrance_positions():
		_add_pillar(entrance_position, ENTRANCE_COLOR, "EntrancePillar")
	for exit_position in map.get_exit_positions():
		_add_pillar(exit_position, EXIT_COLOR, "ExitPillar")


func _add_pillar(local_position: Vector3, color: Color, prefix: String) -> void:
	var pillar := CSGBox3D.new()
	pillar.name = "%s_%d" % [prefix, _visuals.get_child_count()]
	pillar.size = Vector3(0.35, 2.6, 0.35)
	var material := StandardMaterial3D.new()
	material.albedo_color = color
	material.emission_enabled = true
	material.emission = color
	material.emission_energy_multiplier = 0.6
	pillar.material = material
	_visuals.add_child(pillar)
	pillar.global_position = _map.to_global(local_position) + Vector3(0.0, 1.3, 0.0)


func _clear_visuals() -> void:
	if _visuals == null:
		return
	for child in _visuals.get_children():
		_visuals.remove_child(child)
		child.queue_free()

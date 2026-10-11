extends SceneTree
## 香蕉树组装预览：把组件实例化到场景里，用正交相机渲染几个角度，
## 存成 PNG 供人工检查（无头模式下用 Godot 自己的渲染管线，所见即游戏里所得）。
##
## 运行：
## [codeblock]
## /Applications/Godot.app/Contents/MacOS/Godot --path . --script res://components/vegetation/tests/render_banana_preview.gd
## [/codeblock]

const TREE_SCENE: PackedScene = preload("res://components/vegetation/banana_tree/banana_tree.tscn")
const OUT_DIR: String = "res://components/vegetation/tests/"

# (名称, 树高, 把数, 每把根数, 圈数)
const CASES := [
	["tall_3x7", 4.77, 3, 7, 3],
	["tall_5x9", 4.77, 5, 9, 3],
	["short_2x6", 2.66, 2, 6, 2],
	["short_4x8", 2.66, 4, 8, 3],
]
## 单独一把香蕉的特写，用来检查香蕉串本身的排布是否好看。
const BUNCH_CASES := [
	["bunch_7x3", 7, 3],
	["bunch_12x4", 12, 4],
]

var _ran: bool = false
var _finished: bool = false


## 返回 true 表示结束主循环。渲染是异步的（要等 process_frame），
## 所以这里不能在调用 _render_all 之后立刻返回 true，否则场景还没渲染完就退出了。
func _process(_delta: float) -> bool:
	if _finished:
		return true
	if not _ran:
		_ran = true
		_render_all()
	return false


func _render_all() -> void:
	var scene_root := Node3D.new()
	scene_root.name = "PreviewRoot"
	root.add_child(scene_root)
	_add_environment(scene_root)
	_add_lights(scene_root)

	for case in CASES:
		await _render_case(scene_root, case[0], case[1], case[2], case[3], case[4])
	for case in BUNCH_CASES:
		await _render_bunch_case(scene_root, case[0], case[1], case[2])

	print("PREVIEW_DONE")
	_finished = true


func _add_environment(parent: Node3D) -> void:
	var world_env := WorldEnvironment.new()
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color(0.86, 0.90, 0.95)
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.75, 0.78, 0.82)
	env.ambient_light_energy = 0.9
	world_env.environment = env
	parent.add_child(world_env)


func _add_lights(parent: Node3D) -> void:
	var key := DirectionalLight3D.new()
	key.rotation_degrees = Vector3(-52.0, 35.0, 0.0)
	key.light_energy = 1.4
	key.shadow_enabled = false
	parent.add_child(key)


## 单独渲染一把香蕉（不含树），用于检查香蕉串的排布细节。
func _render_bunch_case(parent: Node3D, name: String, count: int, rows: int) -> void:
	var bunch := load("res://components/vegetation/banana_bunch/banana_bunch.tscn").instantiate() as BananaBunch
	bunch.auto_generate = false
	bunch.banana_count = count
	bunch.rows = rows
	bunch.show_flower = true
	parent.add_child(bunch)
	bunch.rebuild()
	for i in 3:
		await process_frame

	var camera := Camera3D.new()
	camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	camera.size = 1.5
	parent.add_child(camera)
	camera.position = Vector3(0.75, -0.15, 1.15)
	camera.look_at(Vector3(0.0, -0.28, 0.0))

	await RenderingServer.frame_post_draw
	var img := root.get_viewport().get_texture().get_image()
	img.save_png(ProjectSettings.globalize_path(OUT_DIR + name + "_preview.png"))
	print("rendered ", name, " bananas=", bunch.get_banana_count())

	camera.queue_free()
	bunch.queue_free()
	await process_frame


func _render_case(parent: Node3D, name: String, height: float, bunches: int,
		per_bunch: int, rows: int) -> void:
	var tree := TREE_SCENE.instantiate() as BananaTree
	tree.auto_generate = false
	tree.tree_height = height
	tree.bunch_count = bunches
	tree.bananas_per_bunch = per_bunch
	tree.rows_per_bunch = rows
	tree.random_seed = 7
	parent.add_child(tree)
	# 先摆好参数再 rebuild，避免初始化阶段多生成一次
	tree.rebuild()

	# 等若干帧让子节点进入场景树、并且真的画出来一帧
	for i in 3:
		await process_frame
	await RenderingServer.frame_post_draw

	var camera := Camera3D.new()
	camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	camera.size = height * 1.35
	parent.add_child(camera)
	camera.position = Vector3(height * 0.75, height * 0.55, height * 1.55)
	camera.look_at(Vector3(0.0, height * 0.5, 0.0))

	await RenderingServer.frame_post_draw
	var img := root.get_viewport().get_texture().get_image()
	img.save_png(ProjectSettings.globalize_path(OUT_DIR + name + "_preview.png"))
	print("rendered ", name, " bunches=", tree.get_bunch_count(),
		" bananas=", tree.get_total_banana_count())

	camera.queue_free()
	tree.queue_free()
	await process_frame
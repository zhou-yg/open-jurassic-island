@tool
extends Node3D
## 低模岛组件的碰撞补全。
##
## 场景里摆放的 GLB（plain_terrain / nest_mountain / low_poly_rock）导入时只有网格，
## 没有碰撞。游戏里玩家要能走在草地和山上、撞到石头，所以这里在运行时给这些网格
## 各挂一个 [StaticBody3D] + [CollisionShape3D]（三角面碰撞，低模面数很少，开销可接受）。
##
## 岛屿本体不需要处理：sky-island-basic.glb 的台面节点名带 `-col`，导入时已经自带
## 了一个带碰撞的 StaticBody3D。
##
## 草地不参与碰撞（玩家直接穿过去），这也让草可以放心地摆得很密。

## 关掉后场景里只有视觉，没有碰撞（例如纯展示 / 截图时）。
@export var build_collision: bool = true
## 是否显示组件自带的天空 / 三盏灯 / 预览相机。接进大世界时设为 false。
@export var show_presentation: bool = true
## 是否显示组件自带的草石。接进大世界时设为 false（放大后会变成巨型道具）。
@export var show_scatter: bool = true
## 需要补碰撞的节点组（相对本节点）。默认覆盖草地、山体和石头。
@export var collision_groups: Array[NodePath] = [
	NodePath("Ground"),
	NodePath("Mountain"),
	NodePath("Scatter/Rocks"),
]


func _ready() -> void:
	_apply_visibility()
	# 编辑器里只切显示，不往场景树里塞临时碰撞体。
	if Engine.is_editor_hint() or not build_collision:
		return
	for path in collision_groups:
		if path == NodePath("Scatter/Rocks") and not show_scatter:
			continue
		var root := get_node_or_null(path)
		if root == null:
			continue
		_add_collision_recursive(root)


## 组件自带的展示节点 / 草石是否可见。主场景会把这两个开关设为 false。
func _apply_visibility() -> void:
	for node_name in ["WorldEnvironment", "Sun", "FillLight", "BounceLight"]:
		var node := get_node_or_null(node_name)
		if node == null:
			continue
		if node is WorldEnvironment:
			(node as WorldEnvironment).environment = null if not show_presentation else (node as WorldEnvironment).environment
		elif node is Node3D:
			(node as Node3D).visible = show_presentation
	var preview := get_node_or_null("PreviewCamera")
	if preview is Camera3D:
		(preview as Camera3D).current = show_presentation
	var scatter := get_node_or_null("Scatter")
	if scatter is Node3D:
		(scatter as Node3D).visible = show_scatter


func _add_collision_recursive(root: Node) -> void:
	for node in root.find_children("*", "MeshInstance3D", true, false):
		_add_collision(node as MeshInstance3D)
	if root is MeshInstance3D:
		_add_collision(root as MeshInstance3D)


func _add_collision(mesh_instance: MeshInstance3D) -> void:
	if mesh_instance.mesh == null or _has_collision(mesh_instance):
		return
	var body := StaticBody3D.new()
	body.name = "StaticBody3D"
	body.collision_layer = 1
	body.collision_mask = 1
	var shape := CollisionShape3D.new()
	shape.name = "CollisionShape3D"
	shape.shape = mesh_instance.mesh.create_trimesh_shape()
	body.add_child(shape)
	mesh_instance.add_child(body)


## 网格自身或祖先上已经有碰撞体时不要重复添加。
func _has_collision(node: Node) -> bool:
	var current := node
	while current != null:
		if current is StaticBody3D:
			return true
		current = current.get_parent()
	for child in node.get_children():
		if child is StaticBody3D:
			return true
	return false

#@tool
extends Node3D
## 低模岛组件的碰撞补全。
##
## 场景里摆放的 GLB（plain_terrain / low_poly_low_mountain）导入时只有网格，
## 没有碰撞。游戏里玩家要能走在草地和山上、撞到石头，所以这里在运行时给这些网格
## 各挂一个 [StaticBody3D] + [CollisionShape3D]（三角面碰撞，低模面数很少，开销可接受）。
##
## 岛屿本体不需要处理：sky-island-basic.glb 的台面节点名带 `-col`，导入时已经自带
## 了一个带碰撞的 StaticBody3D。
##
## 草地不参与碰撞（玩家直接穿过去），这也让草可以放心地摆得很密。
##
## Ground 是一整片 MultiMesh（116 块 plain_terrain 合成 1 个节点，见
## `components/island/ground/`）：MultiMesh 不是 MeshInstance3D，用逐网格那套扫不到，
## 所以这里单独处理 —— **1 个 StaticBody3D + N 个 CollisionShape3D，全部分享同一份
## 三角面形状**（同一块地形只生成一次形状数据，内存几乎不涨）。

## 关掉后场景里只有视觉，没有碰撞（例如纯展示 / 截图时）。
@export var build_collision: bool = true
## 是否显示组件自带的天空 / 三盏灯 / 预览相机。接进大世界时设为 false。
@export var show_presentation: bool = true
## 是否显示组件自带的草石。接进大世界时设为 false（放大后会变成巨型道具）。
@export var show_scatter: bool = true
## 是否显示组件自带的园区围墙 / 大门（`ParkPerimeter`，按 62 m 岛尺度烘的）。
## 接进大世界时设为 false：主场景 `Island` 节点放大 32 倍，围墙会变成半径
## 近 1 km 的一圈"巨墙"，大门也会被拉成几百米宽。
@export var show_perimeter: bool = true
## 是否显示组件自带的香蕉树林（`Vegetation`，按 62 m 岛尺度烘的）。
## 接进大世界时设为 false：主场景 `Island` 节点放大 32 倍，4.8 m 的香蕉树
## 会变成 150 m 高的巨树。
@export var show_vegetation: bool = true
## 是否显示组件自带的恐龙（`Dinosaurs`，按 62 m 岛尺度烘的）。
## 接进大世界时设为 false：主场景 `Island` 节点放大 32 倍，11 m 的霸王龙
## 会变成 350 m 长。
@export var show_dinosaurs: bool = true
## 需要补碰撞的节点组（相对本节点）。默认覆盖地形和山体。
##
## 注意：草/石头**不在这里**。它们已经被合并成 MultiMesh（见
## components/island/ground_scatter/），MultiMesh 不是 MeshInstance3D，
## 用本文件的三角面方案扫不到；石头的碰撞由 ground_scatter.gd 在运行时
## 用"一个 StaticBody3D + N 个共享凸包 CollisionShape3D"补出来，比逐块
## 三角面便宜得多。草不参与碰撞。
@export var collision_groups: Array[NodePath] = [
	NodePath("Ground"),
	NodePath("Mountain"),
]


## 显示开关必须在子节点的 `_ready()` **之前**生效：
## 被隐藏的草石 / 围墙不应该再补碰撞（见 `_apply_visibility`），而它们补碰撞是在
## 各自的 `_ready()` 里做的。`_enter_tree()` 比子节点的 `_ready()` 早，正好。
func _enter_tree() -> void:
	_apply_visibility()


func _ready() -> void:
	# 编辑器里只切显示，不往场景树里塞临时碰撞体。
	if Engine.is_editor_hint() or not build_collision:
		return
	for path in collision_groups:
		var root := get_node_or_null(path)
		if root == null:
			continue
		_add_collision_recursive(root)


## 组件自带的展示节点 / 草石 / 围墙是否可见。主场景会把这三个开关设为 false。
##
## 隐藏的同时还会关掉子组件自己的 `build_collision`：草石和围墙的碰撞是它们
## 按 62 m 尺度在运行时补的，如果只隐藏不关碰撞，接进 32 倍的主场景后就会留下
## 一圈看不见的巨型碰撞体。
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
		if not show_scatter:
			_disable_collision(scatter)
	var perimeter := get_node_or_null("ParkPerimeter")
	if perimeter is Node3D:
		(perimeter as Node3D).visible = show_perimeter
		if not show_perimeter:
			_disable_collision(perimeter)
	var vegetation := get_node_or_null("Vegetation")
	if vegetation is Node3D:
		(vegetation as Node3D).visible = show_vegetation
		if not show_vegetation:
			_disable_collision(vegetation)
	var dinosaurs := get_node_or_null("Dinosaurs")
	if dinosaurs is Node3D:
		(dinosaurs as Node3D).visible = show_dinosaurs


## 把整棵子树里所有带 `build_collision` 开关的子组件关掉。
## 用属性名而不是类型判断，这样 Scatter（ground_scatter.gd）和围墙里的大门
## （park_gate.gd）都能覆盖到，不用在这里 import 任何具体脚本。
func _disable_collision(root: Node) -> void:
	if "build_collision" in root:
		root.set("build_collision", false)
	for node in root.find_children("*", "", true, false):
		if "build_collision" in node:
			node.set("build_collision", false)


func _add_collision_recursive(root: Node) -> void:
	for node in root.find_children("*", "MeshInstance3D", true, false):
		_add_collision(node as MeshInstance3D)
	if root is MeshInstance3D:
		_add_collision(root as MeshInstance3D)
	for node in root.find_children("*", "MultiMeshInstance3D", true, false):
		_add_multimesh_collision(node as MultiMeshInstance3D)


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


## MultiMesh 用一个 body + N 个形状补碰撞：所有实例共用同一份三角面形状资源
## （同一块地形只生成一次形状数据），每个 CollisionShape3D 只带自己的实例变换。
func _add_multimesh_collision(multi_mesh_instance: MultiMeshInstance3D) -> void:
	var multimesh := multi_mesh_instance.multimesh
	if multimesh == null or multimesh.mesh == null or multimesh.instance_count == 0:
		return
	if _has_collision(multi_mesh_instance):
		return
	var shape := multimesh.mesh.create_trimesh_shape()
	if shape == null:
		push_warning("地形网格生成不了三角面碰撞：%s" % multi_mesh_instance.name)
		return
	var body := StaticBody3D.new()
	body.name = "StaticBody3D"
	body.collision_layer = 1
	body.collision_mask = 1
	# body 是 MultiMeshInstance3D 的子节点 → 形状变换就是实例变换本身
	for i in multimesh.instance_count:
		var collision := CollisionShape3D.new()
		collision.name = "CollisionShape3D_%03d" % i
		collision.shape = shape
		collision.transform = multimesh.get_instance_transform(i)
		body.add_child(collision)
	multi_mesh_instance.add_child(body)


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

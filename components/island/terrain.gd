extends Node3D
## **岛体地形**（岩台 + 山体）—— 岛只有这一份定义，谁要地形就实例化它。
##
## 组件岛（`island.tscn`，62 m 的展示岛）和大世界（`jurassic-island.tscn`，
## 放大 22.8 倍的游戏世界）都实例化这个场景，所以两边的岛**永远长得一样**，
## 不会各改各的漂移。
##
## ## 碰撞
##
## 岛面（岩台）**不用处理**：`sky-island-basic.glb` 的台面节点名带 `-col`，
## 导入时自带一个 [StaticBody3D] —— 岛面就是它那份碰撞面，高度固定在 y = 0。
##
## 山体要补：`low_poly_low_mountain.glb` 导入时只有网格、没有碰撞。
## 游戏里玩家要能走在山上，所以运行时给它挂一个 [StaticBody3D] +
## [CollisionShape3D]（三角面碰撞，低模面数很少，开销可接受）。
##
## ## 为什么从 `island.gd` 拆出来
##
## 原来岛体和"展示用内容"（草石 / 围墙 / 香蕉林 / 恐龙）挤在同一个场景里，
## 大世界要它们不出现，就只能靠几个 `show_xxx` 开关在**运行时**隐藏 ——
## 而脚本不是 `@tool`，编辑器里开关不生效：**编辑器里看得见一堆巨树巨恐龙，
## 跑起来又全没了**。拆开之后，大世界干脆**不实例化**那些东西，
## 编辑器里看到的和跑起来的一致，也不需要任何隐藏逻辑。

## 关掉后场景里只有视觉、没有碰撞（例如纯展示 / 截图时）。
@export var build_collision: bool = true
## 需要补碰撞的节点组（相对本节点）。默认只覆盖山体。
##
## 草 / 石头**不在这里**：它们是 MultiMesh（见 `ground_scatter/`），
## 不是 MeshInstance3D，三角面那套扫不到；石头的碰撞由 ground_scatter.gd
## 在运行时用"一个 StaticBody3D + N 个共享凸包 CollisionShape3D"补出来。
@export var collision_groups: Array[NodePath] = [
	NodePath("Mountain"),
]


func _ready() -> void:
	if not build_collision:
		return
	for path in collision_groups:
		var root := get_node_or_null(path)
		if root == null:
			continue
		_add_collision_recursive(root)


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

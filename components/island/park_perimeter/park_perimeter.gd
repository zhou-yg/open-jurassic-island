@tool
extends Node3D
## 园区围墙的**碰撞**：给残墙、倒伏的墙、碎石补上三角面碰撞。
##
## 围墙的场景（`park_perimeter.tscn`）是**烘出来的静态节点**，本身没有碰撞体 ——
## 以前玩家和恐龙都能直接穿过残墙。现在这里在运行时补一份：
##
## - 1 个 [StaticBody3D] + 每个网格 1 个 [CollisionShape3D]；
## - 形状**按网格共享**：所有残墙用的是同一个 glb，所以只生成一份三角面数据，
##   40 段墙 + 碎石一共只占 2 份形状数据；
## - 碰撞在**建筑层**（`LAYER_STRUCTURE`）：玩家推得开、恐龙也撞得到，
##   但恐龙的行为树会用避让绕开它们（巡逻不会被卡住）。
##
## 大门（`Gate`）有自己的一套碰撞（`park_gate.gd`），这里**跳过**它，
## 免得补两遍。

## 碰撞层：建筑（围墙 / 大门）。
const LAYER_STRUCTURE := 4

## 是否给围墙补碰撞。关掉就只有视觉。
@export var build_collision: bool = true

var _built := false


func _ready() -> void:
	if Engine.is_editor_hint() or not build_collision:
		return
	_build_wall_collision()


## 给围墙 / 碎石补碰撞。
func _build_wall_collision() -> void:
	if _built:
		return
	_built = true
	var gate := get_node_or_null("Gate")
	var body := StaticBody3D.new()
	body.name = "WallCollision"
	body.collision_layer = LAYER_STRUCTURE
	body.collision_mask = 1
	# 形状按网格共享：同一款残墙 / 碎石只生成一次三角面数据
	var shape_cache: Dictionary = {}
	var count := 0
	for mesh_inst in _wall_meshes(self):
		if not (mesh_inst is MeshInstance3D):
			continue
		if gate != null and _is_inside(mesh_inst, gate):
			continue      # 大门自己有碰撞
		var mesh: Mesh = (mesh_inst as MeshInstance3D).mesh
		if mesh == null:
			continue
		var key: int = mesh.get_instance_id()
		if not shape_cache.has(key):
			shape_cache[key] = mesh.create_trimesh_shape()
		var shape: Shape3D = shape_cache[key]
		if shape == null:
			continue
		var col := CollisionShape3D.new()
		col.name = "Shape"
		col.shape = shape
		# body 是本节点的子节点 → 形状变换要是"相对本节点"的
		col.transform = global_transform.affine_inverse() * mesh_inst.global_transform
		body.add_child(col)
		count += 1
	if count == 0:
		return
	add_child(body)


## 围墙和碎石里的所有网格（不含大门）。
func _wall_meshes(root: Node) -> Array:
	var out: Array = []
	for child in root.get_children():
		if child is MeshInstance3D:
			out.append(child)
		out.append_array(_wall_meshes(child))
	return out


## 某个节点是不是在另一个节点的子树里。
func _is_inside(node: Node, ancestor: Node) -> bool:
	var current: Node = node
	while current != null:
		if current == ancestor:
			return true
		current = current.get_parent()
	return false

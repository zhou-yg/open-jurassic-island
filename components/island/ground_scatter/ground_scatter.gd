@tool
extends Node3D
## 地面散布物（草 / 石头）的批量渲染与碰撞。
##
## 为什么是 MultiMesh：一片草地上千棵草，如果每棵都是一个场景实例，
## 节点树、`_ready()`、可见性判断和 draw call 全都要乘上千。改成
## **每个资产一个 MultiMeshInstance3D** 之后：
##   - 节点数：上千 → 3（草 ×2 + 石头 ×1）
##   - draw call：上千 → 3
##   - 每棵草的变换仍然独立（MultiMesh 里逐实例存 3×4 矩阵），外观不变
##
## 碰撞：MultiMesh 本身不产生碰撞，所以石头的碰撞在**运行时**补：
## 一个 [StaticBody3D] 下面挂 N 个 [CollisionShape3D]，全部共享同一个凸包形状
## （同一块石头的网格只生成一次形状资源，内存几乎不涨）。
## 草不参与碰撞 —— 玩家直接穿过去，这也是草能放心铺很密的原因。
##
## 本组件由 `components/island/ground_scatter/` 下的生成脚本烘出来，
## 一般不需要手改；要挪草石的位置，重新跑生成脚本。

## 碰撞层：地面（地形 / 山体 / 岛体）。
const LAYER_WORLD := 1
## 碰撞层：杂物（石头 / 碎石）。
const LAYER_PROP := 8

## 哪些 MultiMesh 节点需要补碰撞：按**节点名前缀**匹配。
## 石头层在烘场景时叫 Rock（分组层级保留为 Rocks/RimBoulders/Rock 这种），
## 所以用前缀递归找，不写死在某条路径上。
@export var collision_name_prefix: String = "Rock"

## 关掉后只有视觉、没有石头碰撞。
@export var build_collision: bool = true

## 用凸包还是精确三角面做石头碰撞。凸包便宜得多，石头也够用。
@export var use_convex_shape: bool = true

var _built := false


func _ready() -> void:
	if Engine.is_editor_hint() or not build_collision:
		return
	_build_rock_collision()


## 各层实例总数（调试 / 自检用）。
func instance_count() -> int:
	var total := 0
	for child in get_children():
		if child is MultiMeshInstance3D and child.multimesh != null:
			total += child.multimesh.instance_count
	return total


func _build_rock_collision() -> void:
	if _built:
		return
	_built = true
	var sources: Array[MultiMeshInstance3D] = []
	for child in find_children("*", "MultiMeshInstance3D", true, false):
		var mmi := child as MultiMeshInstance3D
		if mmi.multimesh != null and mmi.multimesh.mesh != null \
				and String(mmi.name).begins_with(collision_name_prefix):
			sources.append(mmi)
	if sources.is_empty():
		return

	var body := StaticBody3D.new()
	body.name = "RockCollision"
	# 石头在**杂物层**：玩家撞得到，恐龙不撞（巡逻不能被石头卡住）。
	body.collision_layer = LAYER_PROP
	body.collision_mask = LAYER_WORLD
	# 形状资源共享：同一块石头的网格只生成一份形状数据，N 个实例共用它
	var shape_cache := {}
	for mmi in sources:
		var mm := mmi.multimesh
		var key := mm.mesh.get_instance_id()
		if not shape_cache.has(key):
			shape_cache[key] = mm.mesh.create_convex_shape() if use_convex_shape \
					else mm.mesh.create_trimesh_shape()
		var shape: Shape3D = shape_cache[key]
		if shape == null:
			continue
		# body 是 self 的子节点 → 形状变换要是"相对 self"的
		var rel := global_transform.affine_inverse() * mmi.global_transform
		for i in mm.instance_count:
			var cs := CollisionShape3D.new()
			cs.shape = shape
			cs.transform = rel * mm.get_instance_transform(i)
			body.add_child(cs)
	add_child(body)

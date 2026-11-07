@tool
extends Node3D
## 岛屿植被组件：**香蕉树林**（MultiMesh）。
##
## 恐龙不在这里 —— 它们是独立组件（`components/vegetation/dinosaur/`），
## 单独烘成 `island_dinosaurs.tscn`，跟树不耦合。
##
## ## 为什么树是 MultiMesh
##
## 岛上有几百棵树。逐棵摆成场景实例 = 几百个节点、几百个 draw call、
## 几百份网格内存；烘成 [MultiMesh] 之后只有 **2 个节点 / 4 个 draw call**
## （2 种树 × 每种 2 个表面：叶片 + 假茎），网格也只有 2 份。
## 每棵树的变换仍然独立，外观和位置**逐点不变**。
##
## 布局是**烘死的**（`bake_vegetation.gd` 按噪声图采样后写进 JSON 再烘成
## `.res`），所以每次打开位置完全一致 —— 没有运行时随机、没有程序化生成。
##
## ## 碰撞
##
## MultiMesh 本身不产生碰撞，所以树干碰撞在**运行时**补：一个
## [StaticBody3D] 下面挂 N 个 [CollisionShape3D]，同一种树的形状**共享一份**
## [CylinderShape3D]（几百棵树只占两份形状数据）。
##
## 树干是实心的：冒险者可以贴着树躲，恐龙也不会从树干里穿过去。

## 碰撞层：地面（地形 / 山体 / 岛体）。
const LAYER_WORLD := 1
## 碰撞层：植被（香蕉树干）。
const LAYER_VEGETATION := 2

## 矮款香蕉树的树干碰撞半径（米，未乘实例缩放）。
@export var short_trunk_radius: float = 0.30
## 矮款香蕉树的假茎高度（米，未乘实例缩放）。
@export var short_trunk_height: float = 1.69
## 高款香蕉树的树干碰撞半径（米，未乘实例缩放）。
@export var tall_trunk_radius: float = 0.36
## 高款香蕉树的假茎高度（米，未乘实例缩放）。
@export var tall_trunk_height: float = 3.26
## 关掉后只有视觉、没有树干碰撞。
@export var build_collision: bool = true

var _built := false


func _ready() -> void:
	if Engine.is_editor_hint() or not build_collision:
		return
	_build_trunk_collision()


## 树的总棵数（调试 / 自检用）。
func tree_count() -> int:
	var total := 0
	for child in get_children():
		if child is Node3D:
			for node in (child as Node3D).find_children("*", "MultiMeshInstance3D", true, false):
				var mm := (node as MultiMeshInstance3D).multimesh
				if mm != null:
					total += mm.instance_count
	return total


## 给每棵树补一段树干碰撞。
##
## 每种树一份圆柱形状，所有实例共用；形状的变换 = 实例变换再往上抬半个
## 树干高度，所以树怎么缩放、怎么歪，碰撞都跟着走。
func _build_trunk_collision() -> void:
	if _built:
		return
	_built = true
	var body := StaticBody3D.new()
	body.name = "TreeCollision"
	# 树干在**植被层**：玩家要撞得到树，恐龙不撞（它要从林子里穿过去巡逻）。
	body.collision_layer = LAYER_VEGETATION
	body.collision_mask = LAYER_WORLD

	var specs := {
		"ShortTrees": [short_trunk_radius, short_trunk_height],
		"TallTrees": [tall_trunk_radius, tall_trunk_height],
	}
	var count := 0
	for node in find_children("*", "MultiMeshInstance3D", true, false):
		var mmi := node as MultiMeshInstance3D
		if mmi.multimesh == null or mmi.multimesh.mesh == null:
			continue
		if not specs.has(String(mmi.name)):
			continue
		var spec: Array = specs[String(mmi.name)]
		var radius := float(spec[0])
		var height := float(spec[1])
		var shape := CylinderShape3D.new()
		shape.radius = radius
		shape.height = height
		var rel := global_transform.affine_inverse() * mmi.global_transform
		for i in mmi.multimesh.instance_count:
			var cs := CollisionShape3D.new()
			cs.shape = shape
			cs.transform = rel * mmi.multimesh.get_instance_transform(i) \
				* Transform3D(Basis.IDENTITY, Vector3(0.0, height * 0.5, 0.0))
			body.add_child(cs)
			count += 1
	if count == 0:
		return
	add_child(body)

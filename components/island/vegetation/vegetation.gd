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
## 用 **PhysicsServer 直接挂形状**，不生成 CollisionShape3D 节点。
##
## 大世界里要放几千棵树：每棵树一个 CollisionShape3D 就是几千个节点
## （场景树、内存、加载时间全吃紧）。直接往物理服务器挂形状，
## 一个节点都不要 —— 形状还是共享的同一份 CylinderShape3D。
@export var collision_via_physics_server: bool = false

var _built := false
## 用物理服务器挂的形状资源（物理服务器只认 RID，资源得留在内存里）。
var _keep_shapes: Array[Shape3D] = []


func _ready() -> void:
	if not build_collision:
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
	# 树干在**植被层**：玩家要撞得到树，恐龙也撞得到（恐龙是实心的，
	# 树是掩体，得站得住）。巡逻不会被卡住 —— 布局那边沿整条巡逻路线
	# 清出了走廊。
	body.collision_layer = LAYER_VEGETATION
	body.collision_mask = LAYER_WORLD
	# 先入树：物理服务器要等 body 进了场景树才认它，
	# 之后往上面挂形状才有效。
	add_child(body)

	var specs := {
		"ShortTrees": [short_trunk_radius, short_trunk_height],
		"TallTrees": [tall_trunk_radius, tall_trunk_height],
	}
	var count := 0
	var keep_alive: Array[Shape3D] = []   # 物理服务器只认 RID，得把资源留住
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
		if collision_via_physics_server:
			keep_alive.append(shape)
			for i in mmi.multimesh.instance_count:
				PhysicsServer3D.body_add_shape(body.get_rid(), shape.get_rid(),
					rel * mmi.multimesh.get_instance_transform(i)
					* Transform3D(Basis.IDENTITY, Vector3(0.0, height * 0.5, 0.0)))
				count += 1
			continue
		for i in mmi.multimesh.instance_count:
			var cs := CollisionShape3D.new()
			cs.shape = shape
			cs.transform = rel * mmi.multimesh.get_instance_transform(i) \
				* Transform3D(Basis.IDENTITY, Vector3(0.0, height * 0.5, 0.0))
			body.add_child(cs)
			count += 1
	if count == 0:
		body.queue_free()
		return
	if not keep_alive.is_empty():
		# 把形状资源留在内存里，别让 GC 回收了（物理服务器只拿着 RID）
		_keep_shapes = keep_alive

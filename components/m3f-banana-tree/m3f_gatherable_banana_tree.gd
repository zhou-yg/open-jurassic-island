@tool
class_name M3FGatherableBananaTree
extends Node3D
## 可采集的「m3f」香蕉树（用 [code]assets/models/m3f-banana/[/code] 的新资产）。
##
## 树体和果串是[b]两个独立模型[/b]：
## [code]Tree[/code] = [code]m3f_banana_tree.glb[/code]（假茎 + 叶冠 + 根部草被），
## [code]Bunch[/code] = [code]m3f_banana_bunch.glb[/code]（果柄 + 16 根香蕉）。
## 果串里每根香蕉都是[b]独立的网格节点[/b]
## （[code]M3FBanana_Fruit_01[/code] … [code]M3FBanana_Fruit_16[/code]），
## 所以"少一根"就是[b]少一个节点可见[/b]，不是换贴图、不是重新生成。
##
## [b]数量[/b]：导出参数 [member banana_count] 决定树上还剩多少根香蕉（0 = 空树）。
## 树顶上方挂一个 [Label3D] 实时显示当前数量。
##
## [b]采集[/b]：玩家走进 [member interact_radius] 的范围后按输入动作
## [code]interact[/code]（默认 [code]E[/code]）采集 —— 默认[b]一次一根[/b]
## （[member harvest_all_at_once] = false、[member harvest_amount] = 1）。
## 同一时刻只有[b]最近[/b]的一棵树响应按键。
##
## [b]记账[/b]：采到的香蕉会写进全局配置
## （[code]res://config/resources.gd[/code] 的 [method ResourcesConfig.add_collected_bananas]
## → 采集统计 + 全局资源池里的 "banana" 数量）。
##
## 使用方式：
## [codeblock]
## var tree: M3FGatherableBananaTree = $Tree
## tree.banana_count = 8       # 这棵树上有 8 根香蕉
## tree.harvest()              # 采 1 根（返回采到的根数）
## [/codeblock]

## 采集成功时发出，参数为这次采到的根数。
signal bananas_collected(amount: int)
## 采集成功时发出，带上是哪棵树。
signal harvested(tree: M3FGatherableBananaTree, amount: int)

## 所有可采集香蕉树所在的组（外部脚本想遍历/查询时用）。
const GROUP: StringName = &"gatherable_banana_tree"
## 玩家所在的组。
const PLAYER_GROUP: StringName = &"player"
## 树模型节点名（`m3f_banana_tree.glb` 的实例）。
const NODE_TREE: StringName = &"Tree"
## 果串节点名（`m3f_banana_bunch.glb` 的实例）。
const NODE_BUNCH: StringName = &"Bunch"
## 数量标签节点名。
const NODE_LABEL: StringName = &"CountLabel"
## 采集范围节点名（"玩家在附近就把这棵树唤醒"的粗筛，不是目标判定）。
const NODE_AREA: StringName = &"InteractArea"
## 采集范围里的碰撞体节点名。
const NODE_AREA_SHAPE: StringName = &"CollisionShape3D"
## 树干碰撞体节点名。
const NODE_TRUNK: StringName = &"Trunk"
## 树干碰撞体里的碰撞形状节点名。
const NODE_TRUNK_SHAPE: StringName = &"CollisionShape3D"
## 果串里香蕉节点名的前缀（`M3FBanana_Fruit_01` … `M3FBanana_Fruit_16`）。
const FRUIT_PREFIX: String = "M3FBanana_Fruit_"

## 果串自带的香蕉根数 —— 一棵树最多这么多根。
const SLOT_COUNT: int = 16
## 树高（米，模型实测值）—— 找不到树模型时用它摆标签。
const TREE_HEIGHT_M: float = 2.81
## 准星射线的碰撞层：world(1) + vegetation(2) —— 地面和树干都挡射线。
const RAY_MASK: int = 1 | 2

## 全局资源配置（采集统计 + 全局资源池）。
## 用 preload 而不是全局类名，和 top_bar.gd 保持一致：无头校验不依赖类缓存。
const ResourcesConfigRef := preload("res://config/resources.gd")

@export_group("香蕉")
## 树上还剩多少根香蕉。0 = 空树（果串整个藏起来）。
@export_range(0, SLOT_COUNT, 1) var banana_count: int = 0:
	set(value):
		banana_count = clampi(value, 0, SLOT_COUNT)
		_on_param_changed()
## 采空之后多少秒长回一根。0 = 不再长（默认，测试场里保持确定）。
@export_range(0.0, 600.0, 0.1) var regrow_seconds: float = 0.0:
	set(value):
		regrow_seconds = maxf(value, 0.0)
		_update_ticks()

@export_group("采集")
## 采集距离（米）：**准星射线**最长能打多远（也就是隔着多远能采到）。
##
## 目标判定靠[b]射线[/b]而不是距离：玩家必须[b]看着[/b]这棵树（准星打在树干上），
## 光站得近没用。射线长度 = 这个值，[method get_aimed_tree] 用它。
@export_range(0.5, 10.0, 0.1) var interact_radius: float = 2.8:
	set(value):
		interact_radius = maxf(value, 0.1)
		_update_area_shape()
## 一次采完（true）还是只采 [member harvest_amount] 根。
@export var harvest_all_at_once: bool = false
## 一次采多少根（[member harvest_all_at_once] 为 false 时生效）。
@export_range(1, SLOT_COUNT, 1) var harvest_amount: int = 1

@export_group("数量显示")
## 是否在树上方显示香蕉数量。
##
## [b]默认关[/b]：游戏里的树不该顶着一个"香蕉 × N"的牌子，
## 只有[b]测试场景[/b]才把它打开（每个实例把 [member show_count_label] 设成 true）。
@export var show_count_label: bool = false:
	set(value):
		show_count_label = value
		_update_label()
## 数量标签的前缀文字。
@export var label_prefix: String = "香蕉 ×":
	set(value):
		label_prefix = value
		_update_label()
## 标签挂在树顶往上多少米。
@export_range(0.0, 5.0, 0.05) var label_height_offset: float = 0.6:
	set(value):
		label_height_offset = maxf(value, 0.0)
		_update_label()
## 空树（0 根）时把标签藏起来。关掉的话会一直显示 "0"。
@export var hide_label_when_empty: bool = false:
	set(value):
		hide_label_when_empty = value
		_update_label()

## 长回香蕉的计时器（秒）。0 = 不长。
var _regrow_timer: float = 0.0


func _ready() -> void:
	add_to_group(GROUP)
	_update_area_shape()
	_sync_fruits()
	_update_label()
	_update_ticks()
	# 只有玩家走进采集范围，这棵树才开始处理按键输入。
	# 大世界里树有几千棵，每棵都收 _unhandled_input 的话太浪费了。
	var area := get_node_or_null(NodePath(NODE_AREA)) as Area3D
	if area != null:
		area.body_entered.connect(_on_area_body_entered)
		area.body_exited.connect(_on_area_body_exited)
	set_process_unhandled_input(false)


func _process(delta: float) -> void:
	if Engine.is_editor_hint():
		return
	if regrow_seconds <= 0.0 or banana_count > 0:
		return
	_regrow_timer += delta
	if _regrow_timer >= regrow_seconds:
		_regrow_timer = 0.0
		add_bananas(1)


## 采集这棵树上的香蕉，返回采到的根数（0 = 没采到）。
##
## 采到的数量会写进全局配置（[code]res://config/resources.gd[/code]）。
func harvest() -> int:
	if banana_count <= 0:
		return 0
	var taken: int = banana_count if harvest_all_at_once else mini(harvest_amount, banana_count)
	banana_count -= taken
	_regrow_timer = 0.0
	_sync_fruits()
	_update_label()
	# 记账：全局采集统计 + 全局资源池
	ResourcesConfigRef.add_collected_bananas(taken)
	bananas_collected.emit(taken)
	harvested.emit(self, taken)
	return taken


## 给树补上 [param amount] 根香蕉（长果 / 调试用）。
func add_bananas(amount: int) -> void:
	if amount <= 0:
		return
	banana_count = mini(banana_count + amount, SLOT_COUNT)
	_sync_fruits()
	_update_label()


## 玩家在不在采集范围里（**粗筛**：只用来把这棵树唤醒去收按键，不决定目标）。
func has_player_in_range() -> bool:
	return _player_in_range() != null


## 范围内的玩家节点（没有就返回 null）。
func _player_in_range() -> Node3D:
	var area := get_node_or_null(NodePath(NODE_AREA)) as Area3D
	if area == null:
		return null
	for body in area.get_overlapping_bodies():
		var node := body as Node3D
		if node != null and node.is_in_group(PLAYER_GROUP):
			return node
	return null


## 玩家走进采集范围 → 这棵树开始处理按键（**注意：这时还不知道目标是谁**，
## 目标要等按 E 时用准星射线来定）。
func _on_area_body_entered(body: Node3D) -> void:
	if body != null and body.is_in_group(PLAYER_GROUP):
		set_process_unhandled_input(true)


## 玩家离开采集范围 → 不再处理按键。
func _on_area_body_exited(body: Node3D) -> void:
	if body == null or not body.is_in_group(PLAYER_GROUP):
		return
	if _player_in_range() == null:
		set_process_unhandled_input(false)


## 按需开关每帧回调：只有要长果的树才需要 _process。
func _update_ticks() -> void:
	set_process(regrow_seconds > 0.0)


## 按 E 采集。目标是**准星指着的那棵树**（射线判定，不是距离判定）。
func _unhandled_input(event: InputEvent) -> void:
	if Engine.is_editor_hint():
		return
	if not event.is_action_pressed("interact"):
		return
	_try_interact()


func _try_interact() -> void:
	# 目标由**准星射线**决定：射线打到谁就是谁（一条射线只可能命中一棵树，
	# 所以天然不会出现"一次按键采好几棵"）。
	if not is_aimed_at():
		return
	harvest()


## 准星当前指着哪棵树？
##
## 从**相机**沿视线方向打一条射线（长度 = [member interact_radius]），
## 命中的是这棵树的碰撞体才算数。命中别的树 / 命中地面 / 什么都没命中 → null。
##
## 这是**唯一的目标判定**——不再用"玩家离树多近"来判断。
## 玩家自己会被排除（相机就在玩家胶囊里）。
static func get_aimed_tree(scope: Node, reach: float) -> M3FGatherableBananaTree:
	if scope == null or not scope.is_inside_tree():
		return null
	var cam: Camera3D = scope.get_viewport().get_camera_3d()
	if cam == null:
		return null
	var world: World3D = scope.get_world_3d()
	if world == null:
		return null
	var from := cam.global_position
	var to := from + (-cam.global_transform.basis.z).normalized() * maxf(reach, 0.1)
	var params := PhysicsRayQueryParameters3D.create(from, to)
	params.collision_mask = RAY_MASK
	params.collide_with_bodies = true
	params.collide_with_areas = false
	# 排除玩家自己（相机在玩家的胶囊里，否则射线先打中自己）
	var exclude: Array[RID] = []
	for node in scope.get_tree().get_nodes_in_group(PLAYER_GROUP):
		if node is CollisionObject3D:
			exclude.append((node as CollisionObject3D).get_rid())
	params.exclude = exclude
	var hit: Dictionary = world.direct_space_state.intersect_ray(params)
	if hit.is_empty():
		return null
	# 从命中的碰撞体往上找，找到那棵树
	var node := hit.get("collider") as Node
	while node != null:
		if node is M3FGatherableBananaTree:
			return node as M3FGatherableBananaTree
		node = node.get_parent()
	return null


## 准星是不是指着我这棵树？
func is_aimed_at() -> bool:
	return get_aimed_tree(self, interact_radius) == self


## 准星当前指着的那棵树（射线判定，没指着就返回 null）。
##
## 给"HUD 要显示点什么"的外部脚本用 —— 比如测试场的"按 E 采集"提示。
func find_aimed_tree() -> M3FGatherableBananaTree:
	return get_aimed_tree(self, interact_radius)


## ---------------- 内部实现 ----------------

func _on_param_changed() -> void:
	if not is_inside_tree():
		return
	_sync_fruits()
	_update_label()


## 显示前 [member banana_count] 根香蕉，其余藏起来。
##
## 香蕉是果串模型里[b]固定的节点[/b]（不是脚本生成的），脚本只切 `visible`。
func _sync_fruits() -> void:
	var fruits := _find_fruits()
	for index in fruits.size():
		var fruit := fruits[index] as Node3D
		if fruit == null:
			continue
		fruit.visible = index < banana_count


## 果串里的香蕉节点（按编号排好序）。
func _find_fruits() -> Array[Node]:
	var result: Array[Node] = []
	_collect_fruits(get_node_or_null(NodePath(NODE_BUNCH)), result)
	result.sort_custom(func(a: Node, b: Node) -> bool:
		return _fruit_index(a) < _fruit_index(b)
	)
	return result


func _collect_fruits(node: Node, out: Array[Node]) -> void:
	if node == null:
		return
	if String(node.name).begins_with(FRUIT_PREFIX):
		out.append(node)
	for child in node.get_children():
		_collect_fruits(child, out)


## 香蕉节点名里的编号（`M3FBanana_Fruit_07` → 7）。
func _fruit_index(node: Node) -> int:
	return String(node.name).substr(FRUIT_PREFIX.length()).to_int()


## 刷新树顶的数量标签。
func _update_label() -> void:
	var label := get_node_or_null(NodePath(NODE_LABEL)) as Label3D
	if label == null:
		return
	var empty: bool = banana_count <= 0
	label.visible = show_count_label and not (hide_label_when_empty and empty)
	if not label.visible:
		return
	label.text = "%s %d" % [label_prefix, banana_count]
	# 有货的时候是暖黄色，采空以后变灰
	label.modulate = Color(0.72, 0.72, 0.72) if empty else Color(1.0, 0.85, 0.28)
	label.outline_modulate = Color(0.08, 0.08, 0.08, 0.9)
	label.position = Vector3(0.0, _tree_top() + label_height_offset, 0.0)


## 树模型的实际高度（米）—— 标签挂在它上面。
func _tree_top() -> float:
	var tree := get_node_or_null(NodePath(NODE_TREE))
	if tree == null:
		return TREE_HEIGHT_M
	var box := AABB()
	var first := true
	for node in _collect_mesh_instances(tree):
		var mesh_instance := node as MeshInstance3D
		if mesh_instance.mesh == null:
			continue
		var mesh_box: AABB = mesh_instance.get_aabb()
		mesh_box = mesh_instance.transform * mesh_box
		box = mesh_box if first else box.merge(mesh_box)
		first = false
	if first:
		return TREE_HEIGHT_M
	return box.end.y


## 收集一个节点下所有 MeshInstance3D。
func _collect_mesh_instances(node: Node) -> Array[Node]:
	var result: Array[Node] = []
	if node is MeshInstance3D:
		result.append(node)
	for child in node.get_children():
		result.append_array(_collect_mesh_instances(child))
	return result


## 把采集范围同步成半径 [member interact_radius] 的球。
func _update_area_shape() -> void:
	var area := get_node_or_null(NodePath(NODE_AREA)) as Area3D
	if area == null:
		return
	var shape_node := area.get_node_or_null(NodePath(NODE_AREA_SHAPE)) as CollisionShape3D
	if shape_node == null:
		return
	var sphere := shape_node.shape as SphereShape3D
	if sphere == null:
		sphere = SphereShape3D.new()
		shape_node.shape = sphere
	sphere.radius = interact_radius

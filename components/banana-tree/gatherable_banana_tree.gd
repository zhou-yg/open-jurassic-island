@tool
class_name GatherableBananaTree
extends Node3D
## 可采集的香蕉树：树顶固定 10 个挂果位（`banana_0` … `banana_9`），
## 树上剩多少根香蕉就显示多少，走近按 [code]E[/code] 采集。
##
## [b]香蕉不是脚本生成的[/b]：10 个挂果位是场景里[b]固定[/b]的节点
## （`res://assets/models/banana/banana.glb` 的实例），
## 摆在假茎顶部绕一圈。脚本只做两件事：
## 按 [member banana_count] 显示前 N 个挂果位（其余隐藏），以及采集。
## 所以这棵树**最多 10 根香蕉**。
##
## [b]数量[/b]：导出参数 [member banana_count] 决定树上还剩多少根香蕉，
## 默认 [code]0[/code]（空树）。树顶上方挂一个 [Label3D] 实时显示当前数量，
## 采空以后数字跟着变（[member hide_label_when_empty] 可以把空树的标签藏起来）。
##
## [b]采集[/b]：玩家走进 [member interact_radius] 的范围后按输入动作
## [code]interact[/code]（默认 [code]E[/code]）即可采集。同一时刻只有
## [b]最近[/b]的一棵树响应按键 —— 站在树丛里也不会一次采好几棵。
##
## [b]记账[/b]：采到的香蕉会写进全局配置
## （[code]res://config/resources.gd[/code] 的 [method ResourcesConfig.add_collected_bananas]
## → 采集统计 + 全局资源池里的 "banana" 数量）。
##
## 使用方式：
## [codeblock]
## var tree: GatherableBananaTree = $Tree
## tree.banana_count = 8       # 这棵树上有 8 根香蕉（显示 banana_0 … banana_7）
## tree.harvest()              # 采掉全部（返回采到的根数）
## [/codeblock]

## 采集成功时发出，参数为这次采到的根数。
signal bananas_collected(amount: int)
## 采集成功时发出，带上是哪棵树。
signal harvested(tree: GatherableBananaTree, amount: int)

## 所有可采集香蕉树所在的组（用来找最近的一棵）。
const GROUP: StringName = &"gatherable_banana_tree"
## 玩家所在的组。
const PLAYER_GROUP: StringName = &"player"
## 树模型节点名（`banana-tree-tall/low_poly_banana_tree.glb` 的实例）。
const NODE_TREE: StringName = &"Tree"
## 数量标签节点名。
const NODE_LABEL: StringName = &"CountLabel"
## 采集范围节点名。
const NODE_AREA: StringName = &"InteractArea"
## 采集范围里的碰撞体节点名。
const NODE_AREA_SHAPE: StringName = &"CollisionShape3D"
## 树干碰撞体节点名。
const NODE_TRUNK: StringName = &"Trunk"
## 树干碰撞体里的碰撞形状节点名。
const NODE_TRUNK_SHAPE: StringName = &"CollisionShape3D"
## 挂果位节点名的前缀（`banana_0` … `banana_9`）。
const SLOT_PREFIX: String = "banana_"

## 挂果位数量 —— 一棵树最多 10 根香蕉。
const SLOT_COUNT: int = 10

## 全局资源配置（采集统计 + 全局资源池）。
## 用 preload 而不是全局类名，和 top_bar.gd 保持一致：无头校验不依赖类缓存。
const ResourcesConfigRef := preload("res://config/resources.gd")

@export_group("香蕉")
## 树上还剩多少根香蕉。0 = 空树（挂果位全部隐藏）。最多 10。
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
## 采集半径（米）。玩家走进这个范围就能按 E 采集。
@export_range(0.5, 10.0, 0.1) var interact_radius: float = 2.8:
	set(value):
		interact_radius = maxf(value, 0.1)
		_update_area_shape()
## 一次采完（true）还是只采 [member harvest_amount] 根。
@export var harvest_all_at_once: bool = true
## 一次采多少根（[member harvest_all_at_once] 为 false 时生效）。
@export_range(1, SLOT_COUNT, 1) var harvest_amount: int = 1

@export_group("数量显示")
## 是否在树上方显示香蕉数量。
@export var show_count_label: bool = true:
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
	_sync_slots()
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
	_sync_slots()
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
	_sync_slots()
	_update_label()


## 当前范围内有没有可以采集的玩家。
func has_player_in_range() -> bool:
	return _player_in_range() != null


## 当前范围内的玩家节点（没有就返回 null）。
func _player_in_range() -> Node3D:
	var area := get_node_or_null(NodePath(NODE_AREA)) as Area3D
	if area == null:
		return null
	for body in area.get_overlapping_bodies():
		var node := body as Node3D
		if node != null and node.is_in_group(PLAYER_GROUP):
			return node
	return null


## 玩家走进采集范围 → 开始处理按键。
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


## 按 E 采集。只在"自己是最近的一棵"时才响应，避免一次按键采好几棵。
func _unhandled_input(event: InputEvent) -> void:
	if Engine.is_editor_hint():
		return
	if not event.is_action_pressed("interact"):
		return
	_try_interact()


func _try_interact() -> void:
	var player := _player_in_range()
	if player == null:
		return
	var best: GatherableBananaTree = null
	var best_distance: float = INF
	for node in get_tree().get_nodes_in_group(GROUP):
		var tree := node as GatherableBananaTree
		if tree == null or not tree.is_processing_unhandled_input():
			continue
		var distance: float = player.global_position.distance_to(tree.global_position)
		if distance < best_distance:
			best_distance = distance
			best = tree
	if best == self:
		harvest()


## ---------------- 内部实现 ----------------

func _on_param_changed() -> void:
	if not is_inside_tree():
		return
	_sync_slots()
	_update_label()


## 显示前 [member banana_count] 个挂果位，其余藏起来。
##
## 挂果位是场景里固定的节点（`banana_0` … `banana_9`），
## 脚本只切 `visible`，不生成也不删除任何节点。
func _sync_slots() -> void:
	for index in SLOT_COUNT:
		var slot := get_node_or_null(NodePath("%s%d" % [SLOT_PREFIX, index]))
		if slot == null:
			continue
		slot.visible = index < banana_count


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
		return 4.77
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
		return 4.77
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

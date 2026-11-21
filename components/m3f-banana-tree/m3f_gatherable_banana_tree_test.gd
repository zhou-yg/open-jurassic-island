extends Node3D
## 「m3f」香蕉树（树 / 果串分离）的测试场。
##
## 场里排了一排香蕉树，**每棵的香蕉数量都不一样（0 ~ 10）**，
## 放了一个 [code]Player[/code]，走近按 [code]E[/code] 就能采集 ——
## 树顶的数字会变少、**果串上真的少一根香蕉**，
## HUD 上的"全局采集数"和"全局资源池 banana"同步上涨。
##
## 顶栏数值来自 [code]res://config/resources.gd[/code]（全局配置）和
## [code]autoloads/data/resources.gd[/code]（全局资源池）。
##
## 这里刻意[b]不直接引用[/b] [code]M3FGatherableBananaTree[/code] 这个全局类名，
## 而是用"鸭子类型"找树 —— 和 top_bar.gd 一个理由：无头校验不依赖编辑器的
## 全局类缓存。

const ResourcesConfigRef := preload("res://config/resources.gd")

@onready var _stats: Label = $TestHUD/Stats
@onready var _message: Label = $TestHUD/Message
@onready var _prompt: Label = $TestHUD/InteractPrompt

## 场里的香蕉树（按名字排好序，和摆放顺序一致）。
var _trees: Array[Node3D] = []
## 每棵树[b]初始[/b]的香蕉数量（按 [code]R[/code] 重置时用它还原）。
var _initial_counts: Dictionary = {}
var _last_message: String = "按 E 采集香蕉（先走近一棵树）"
var _refresh_timer: float = 0.0


func _ready() -> void:
	_collect_trees()
	for tree in _trees:
		tree.connect(&"harvested", _on_tree_harvested)
		_initial_counts[tree.name] = int(tree.get("banana_count"))
	_refresh()


func _process(delta: float) -> void:
	# HUD 每 0.1 秒刷一次就够了
	_refresh_timer += delta
	if _refresh_timer < 0.1:
		return
	_refresh_timer = 0.0
	_refresh()


## [code]R[/code] = 重置：把每棵树还原成初始数量，采集统计清零。
func _unhandled_input(event: InputEvent) -> void:
	var key := event as InputEventKey
	if key == null or not key.pressed or key.echo:
		return
	if key.keycode != KEY_R:
		return
	_reset_test()


## 重置整个测试场（树上的香蕉 + 全局采集统计 + 全局资源池）。
func _reset_test() -> void:
	for tree in _trees:
		var initial: int = int(_initial_counts.get(tree.name, 0))
		# banana_count 的 setter 会同步果串里每根香蕉的可见性
		tree.set("banana_count", initial)
	_last_message = "已重置（每棵树恢复初始香蕉数量，全局采集数清零）"
	ResourcesConfigRef.reset_collected_bananas()
	_pool_set_amount(0)
	_refresh()


## 把全局资源池里 "banana" 的数量直接设成 [param amount]。
func _pool_set_amount(amount: int) -> void:
	for child in get_tree().root.get_children():
		if child.name == "Resources" and child.has_method("set_amount"):
			child.call("set_amount", ResourcesConfigRef.FOOD["id"], amount)
			return


## 把场景里的香蕉树按名字排好序，方便 HUD 显示。
func _collect_trees() -> void:
	_trees.clear()
	for child in get_children():
		if child is Node3D and child.has_method("harvest"):
			_trees.append(child as Node3D)
	_trees.sort_custom(func(a: Node3D, b: Node3D) -> bool:
		return _tree_order(a) < _tree_order(b)
	)


## 树名末尾的数字（[code]Tree_0[/code] / [code]Tree_10[/code]）——
## 按数字排，别按字符串（按字符串 "Tree_10" 会排到 "Tree_1" 后面）。
func _tree_order(tree: Node3D) -> int:
	var name := String(tree.name)
	var digits := ""
	for i in range(name.length() - 1, -1, -1):
		var ch := name[i]
		if not ch.is_valid_int():
			break
		digits = ch + digits
	return int(digits) if digits != "" else 0


func _on_tree_harvested(tree: Node3D, amount: int) -> void:
	_last_message = "从 %s 采到 %d 根香蕉（还剩 %d 根）" % [
		tree.name, amount, int(tree.get("banana_count"))
	]
	_refresh()


func _refresh() -> void:
	if _stats == null:
		return
	var lines: PackedStringArray = []
	lines.append("全局采集数（config/resources.gd）：%d 根" % ResourcesConfigRef.get_collected_bananas())
	lines.append("全局资源池 banana（autoloads/data/resources.gd）：%d 根" % _pool_amount())
	lines.append("")
	lines.append("树上的香蕉：")
	for tree in _trees:
		var count := int(tree.get("banana_count"))
		lines.append("  %s —— %d 根%s" % [
			tree.name,
			count,
			"" if count > 0 else "（已采完）",
		])
	_stats.text = "\n".join(lines)
	if _message != null:
		_message.text = _last_message
	_update_prompt()


## 交互提示：准星**指着**一棵还有货的香蕉树时，屏幕下方显示"按 E 采集"。
##
## 目标判定和实际采集是同一套逻辑（**准星射线**，见组件的 `get_aimed_tree()`），
## 所以不会出现"提示亮了但按 E 没反应"。
## 树上的香蕉采光了 / 准星没指着树 → 不提示。
func _update_prompt() -> void:
	if _prompt == null:
		return
	var target: Node3D = _aimed_tree()
	if target == null or int(target.get("banana_count")) <= 0:
		_prompt.visible = false
		return
	_prompt.visible = true
	_prompt.text = "按 E 采集"


## 准星当前指着的那棵树（没有就返回 null）。
##
## 用组件自己的射线判定（"鸭子类型"调用，不引用全局类名）。
func _aimed_tree() -> Node3D:
	for tree in _trees:
		if not tree.has_method("find_aimed_tree"):
			continue
		var hit = tree.call("find_aimed_tree")
		if hit != null:
			return hit as Node3D
	return null


## 全局资源池里 "banana" 的当前数量。
##
## 用运行期查找而不是直接引用自动加载名，和 top_bar.gd 保持一致。
func _pool_amount() -> int:
	for child in get_tree().root.get_children():
		if child.name == "Resources" and child.has_method("get_amount"):
			return int(child.get_amount(ResourcesConfigRef.FOOD["id"]))
	return 0

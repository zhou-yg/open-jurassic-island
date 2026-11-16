extends Node3D
## 可采集香蕉树的测试场。
##
## 场里排了一排香蕉树（每棵的香蕉数量不同），放了一个 [code]Player[/code]，
## 走近按 [code]E[/code] 就能采集 —— 树顶的数字会变少，HUD 上的
## "全局采集数" 和 "全局资源池 banana" 会同步上涨。
##
## 顶栏数值来自 [code]res://config/resources.gd[/code]（全局配置）和
## [code]autoloads/data/resources.gd[/code]（全局资源池）。
##
## 这里刻意[b]不直接引用[/b] [code]GatherableBananaTree[/code] 这个全局类名，
## 而是用"鸭子类型"找树 —— 和 top_bar.gd 一个理由：无头校验不依赖编辑器的
## 全局类缓存。

const ResourcesConfigRef := preload("res://config/resources.gd")

@onready var _stats: Label = $TestHUD/Stats
@onready var _message: Label = $TestHUD/Message

## 场里的香蕉树（按名字排好序，和摆放顺序一致）。
var _trees: Array[Node3D] = []
var _last_message: String = "按 E 采集香蕉（先走近一棵树）"
var _refresh_timer: float = 0.0


func _ready() -> void:
	_collect_trees()
	for tree in _trees:
		tree.connect(&"harvested", _on_tree_harvested)
	_refresh()


func _process(delta: float) -> void:
	# HUD 每 0.1 秒刷一次就够了
	_refresh_timer += delta
	if _refresh_timer < 0.1:
		return
	_refresh_timer = 0.0
	_refresh()


## 把场景里的香蕉树按名字排好序，方便 HUD 显示。
func _collect_trees() -> void:
	_trees.clear()
	for child in get_children():
		if child is Node3D and child.has_method("harvest"):
			_trees.append(child as Node3D)
	_trees.sort_custom(func(a: Node3D, b: Node3D) -> bool:
		return String(a.name) < String(b.name)
	)


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


## 全局资源池里 "banana" 的当前数量。
##
## 用运行期查找而不是直接引用自动加载名，和 top_bar.gd 保持一致。
func _pool_amount() -> int:
	for child in get_tree().root.get_children():
		if child.name == "Resources" and child.has_method("get_amount"):
			return int(child.get_amount(ResourcesConfigRef.FOOD["id"]))
	return 0

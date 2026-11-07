class_name BehaviorTree
extends RefCounted
## 一棵**行为树**：一个根节点，每帧 tick。
##
## 行为树是"决策"的骨架：从根往下按优先级试，
## 第一个能走通（成功）的分支就是这一帧的行为。
##
## [codeblock]
## var root := BtComposite.Selector.new("根")
## root.add_child(BtComposite.Sequence.new("追"))
## var tree := BehaviorTree.new(root)
## [/codeblock]

## 根节点。
var root: BtNode
var _status: int = BtNode.Status.FAILURE


func _init(p_root: BtNode = null) -> void:
	root = p_root


## 跑一帧，返回根节点的状态。
func tick(delta: float) -> int:
	if root == null:
		return BtNode.Status.FAILURE
	_status = root.tick(delta)
	return _status


## 整棵树复位（换状态时用）。
func reset() -> void:
	if root != null:
		root.reset()


## 上一次 tick 的状态。
func get_status() -> int:
	return _status


## 打印一棵树的结构（调试用）。
func debug_print(indent: int = 0) -> void:
	if root == null:
		return
	_print_node(root, indent)


func _print_node(node: BtNode, indent: int) -> void:
	var pad := "  ".repeat(indent)
	print(pad, "- ", node.node_name, "  [", _status_name(node.status), "]")
	if node is BtComposite:
		for child in (node as BtComposite).children:
			_print_node(child, indent + 1)


static func _status_name(status: int) -> String:
	match status:
		BtNode.Status.SUCCESS: return "成功"
		BtNode.Status.FAILURE: return "失败"
		BtNode.Status.RUNNING: return "进行中"
	return "未知"

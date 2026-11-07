class_name BtLeaf
extends BtNode
## 行为树的**叶子**：条件（判断）和动作（执行）。
##
## 叶子不持有子节点，只挂一个回调。回调的约定：
## **接收 delta，返回 [enum BtNode.Status]**（返回一个 bool 也认：true = 成功）。
##
## [codeblock]
## BtLeaf.condition("看见了目标", func(_d): return ai.can_see_target())
## BtLeaf.action("追上去", func(d): return ai.chase(d))
## [/codeblock]

var _callback: Callable


func _init(p_name: String, p_callback: Callable) -> void:
	super._init(p_name)
	_callback = p_callback


func tick(delta: float) -> int:
	if not _callback.is_valid():
		push_warning("BtLeaf「%s」的回调无效" % node_name)
		return Status.FAILURE
	var result: Variant = _callback.call(delta)
	if result is int:
		return int(result)
	return Status.SUCCESS if bool(result) else Status.FAILURE


## 建一个条件节点。
static func condition(p_name: String, p_callback: Callable) -> BtLeaf:
	return BtLeaf.new(p_name, p_callback)


## 建一个动作节点。
static func action(p_name: String, p_callback: Callable) -> BtLeaf:
	return BtLeaf.new(p_name, p_callback)

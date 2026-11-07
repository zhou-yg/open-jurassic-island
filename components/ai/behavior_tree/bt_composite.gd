class_name BtComposite
extends BtNode
## 行为树的**组合节点**：把若干子节点按某种规则串起来。
##
## 三种：
## - [b]Sequence[/b] 顺序执行：全成功才成功，有一个失败就失败（"并且"）；
## - [b]Selector[/b] 择一执行：第一个成功的就是结果，有一个成功就成功（"或者"）；
## - [b]Parallel[/b] 并行执行：全都成功才成功，有一个失败就失败。

var children: Array[BtNode] = []


func _init(p_name: String = "") -> void:
	super._init(p_name)


## 加一个子节点，返回自己（方便链式写）。
func add_child(child: BtNode) -> BtComposite:
	children.append(child)
	return self


func tick(_delta: float) -> int:
	return Status.FAILURE


func reset() -> void:
	super.reset()
	for child in children:
		child.reset()


## **并且**：按顺序执行，全成功才成功。
class Sequence extends BtComposite:
	var _index: int = 0

	func tick(delta: float) -> int:
		while _index < children.size():
			var s := children[_index].tick(delta)
			if s == Status.RUNNING:
				status = Status.RUNNING
				return Status.RUNNING
			if s == Status.FAILURE:
				_index = 0
				status = Status.FAILURE
				return Status.FAILURE
			_index += 1
		_index = 0
		status = Status.SUCCESS
		return Status.SUCCESS

	func reset() -> void:
		super.reset()
		_index = 0


## **或者**：按顺序执行，第一个成功的就是结果。
class Selector extends BtComposite:
	var _index: int = 0

	func tick(delta: float) -> int:
		while _index < children.size():
			var s := children[_index].tick(delta)
			if s == Status.RUNNING:
				status = Status.RUNNING
				return Status.RUNNING
			if s == Status.SUCCESS:
				_index = 0
				status = Status.SUCCESS
				return Status.SUCCESS
			_index += 1
		_index = 0
		status = Status.FAILURE
		return Status.FAILURE

	func reset() -> void:
		super.reset()
		_index = 0


## **并行**：所有子节点一起跑，全成功才成功，有一个失败就失败。
class Parallel extends BtComposite:
	var _failed := false

	func tick(delta: float) -> int:
		_failed = false
		var all_ok := true
		for child in children:
			var s := child.tick(delta)
			if s == Status.FAILURE:
				_failed = true
			elif s == Status.RUNNING:
				all_ok = false
		if _failed:
			status = Status.FAILURE
			return Status.FAILURE
		if not all_ok:
			status = Status.RUNNING
			return Status.RUNNING
		status = Status.SUCCESS
		return Status.SUCCESS

	func reset() -> void:
		super.reset()
		_failed = false


## 建一个顺序节点。
static func sequence(p_name: String) -> BtComposite:
	return BtComposite.Sequence.new(p_name)


## 建一个选择节点。
static func selector(p_name: String) -> BtComposite:
	return BtComposite.Selector.new(p_name)


## 建一个并行节点。
static func parallel(p_name: String) -> BtComposite:
	return BtComposite.Parallel.new(p_name)

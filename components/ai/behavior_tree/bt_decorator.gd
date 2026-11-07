class_name BtDecorator
extends BtNode
## 行为树的**装饰器**：只有一个子节点，在它外面套一层规则。
##
## - [b]Inverter[/b] 把成功 / 失败反过来；
## - [b]Cooldown[/b] 冷却：多久才允许跑一次（"刚咬过，别急着再咬"）；
## - [b]Repeat[/b] 重复 N 次；
## - [b]UntilFail[/b] 一直重复直到子节点失败；
## - [b]Timeout[/b] 超时就失败（"追太久就放弃"）。

var child: BtNode


func _init(p_name: String = "", p_child: BtNode = null) -> void:
	super._init(p_name)
	child = p_child


func tick(_delta: float) -> int:
	if child == null:
		return Status.FAILURE
	return child.tick(_delta)


func reset() -> void:
	super.reset()
	if child != null:
		child.reset()


## 把成功 / 失败反过来。
class Inverter extends BtDecorator:
	func tick(delta: float) -> int:
		var s := child.tick(delta)
		if s == Status.SUCCESS:
			status = Status.FAILURE
			return Status.FAILURE
		if s == Status.FAILURE:
			status = Status.SUCCESS
			return Status.SUCCESS
		status = Status.RUNNING
		return Status.RUNNING


## 冷却：上一次成功之后，interval 秒内不再跑。
class Cooldown extends BtDecorator:
	var _interval: float = 1.0
	var _remaining: float = 0.0

	func _init(p_name: String = "", p_child: BtNode = null, p_interval: float = 1.0) -> void:
		super._init(p_name, p_child)
		_interval = p_interval

	func tick(delta: float) -> int:
		if _remaining > 0.0:
			_remaining -= delta
			return Status.FAILURE
		var s := child.tick(delta)
		if s == Status.SUCCESS:
			_remaining = _interval
		status = s
		return s

	func reset() -> void:
		super.reset()
		_remaining = 0.0


## 重复 N 次。
class Repeat extends BtDecorator:
	var _count: int = 1
	var _done: int = 0

	func _init(p_name: String = "", p_child: BtNode = null, p_count: int = 1) -> void:
		super._init(p_name, p_child)
		_count = maxi(1, p_count)

	func tick(delta: float) -> int:
		if _done >= _count:
			_done = 0
			return Status.SUCCESS
		var s := child.tick(delta)
		if s == Status.SUCCESS:
			_done += 1
			if _done >= _count:
				_done = 0
		status = s
		return s

	func reset() -> void:
		super.reset()
		_done = 0


## 一直重复，直到子节点失败。
class UntilFail extends BtDecorator:
	func tick(delta: float) -> int:
		var s := child.tick(delta)
		if s == Status.FAILURE:
			status = Status.SUCCESS
			return Status.SUCCESS
		status = Status.RUNNING
		return Status.RUNNING


## 超时就失败。
class Timeout extends BtDecorator:
	var _limit: float = 5.0
	var _elapsed: float = 0.0

	func _init(p_name: String = "", p_child: BtNode = null, p_limit: float = 5.0) -> void:
		super._init(p_name, p_child)
		_limit = p_limit

	func tick(delta: float) -> int:
		_elapsed += delta
		if _elapsed >= _limit:
			_elapsed = 0.0
			status = Status.FAILURE
			return Status.FAILURE
		var s := child.tick(delta)
		if s == Status.FAILURE:
			_elapsed = 0.0
		status = s
		return s

	func reset() -> void:
		super.reset()
		_elapsed = 0.0


## 建一个反相节点。
static func inverter(p_name: String, p_child: BtNode) -> BtDecorator:
	return BtDecorator.Inverter.new(p_name, p_child)


## 建一个冷却节点。
static func cooldown(p_name: String, p_child: BtNode, interval: float) -> BtDecorator:
	return BtDecorator.Cooldown.new(p_name, p_child, interval)


## 建一个重复节点。
static func repeat(p_name: String, p_child: BtNode, count: int) -> BtDecorator:
	return BtDecorator.Repeat.new(p_name, p_child, count)


## 建一个"直到失败"节点。
static func until_fail(p_name: String, p_child: BtNode) -> BtDecorator:
	return BtDecorator.UntilFail.new(p_name, p_child)


## 建一个超时节点。
static func timeout(p_name: String, p_child: BtNode, limit: float) -> BtDecorator:
	return BtDecorator.Timeout.new(p_name, p_child, limit)

class_name BtNode
extends RefCounted
## 行为树节点的**基类**。
##
## 行为树每帧从上往下 tick，每个节点返回三种状态之一：
##
## | 状态 | 意思 | 父节点怎么办 |
## | --- | --- | --- |
## | `SUCCESS` | 这一支做完了 | 继续下一个兄弟 / 整支成功 |
## | `FAILURE` | 这一支做不成 | 换下一个兄弟（选择器）/ 整支失败（顺序） |
## | `RUNNING` | 还在做 | 下一帧继续 tick 同一个节点 |
##
## 节点是**引用类型**（`RefCounted`），所以要留着引用防止被回收；
## 行为树自己持有根节点，整棵树的生命周期就跟着它。

enum Status {
	SUCCESS,   ## 这一支成功
	FAILURE,   ## 这一支失败
	RUNNING,   ## 这一支还在进行
}

## 节点名（调试 / 日志用）。
var node_name: String = ""
## 上一次 tick 的结果。
var status: int = Status.FAILURE


func _init(p_name: String = "") -> void:
	node_name = p_name


## 执行这一帧。子类覆写。
func tick(_delta: float) -> int:
	return Status.FAILURE


## 重置（切状态时用，让"进行中"的分支从头再来）。
func reset() -> void:
	status = Status.FAILURE


## 是不是还在进行中。
func is_running() -> bool:
	return status == Status.RUNNING

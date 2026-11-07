class_name DinosaurStateMachine
extends RefCounted
## 恐龙的状态机：粗粒度的"**现在是哪个状态**"。
##
## ## 行为树 vs 状态机
##
## - [b]行为树[/b] 负责**决策**：这一帧该干什么（追 / 逃 / 巡逻 …）。
## - [b]状态机[/b] 负责**记账**：当前处在哪个状态、待了多久、切换时发信号。
##
## 动画、游戏逻辑钩子、调试面板读的都是状态机；决策的活儿归行为树。
## 两者不重复：行为树选中一个行为 → 状态机切到对应状态。
##
## ## 预留状态
##
## 下面 [enum State] 里带"预留"注释的状态是**占位** —— 行为还没做，
## 但位置、名字、信号都留好了：想做的时候只要在行为树里把对应分支打开，
## 再填上 [method DinosaurAI.behave_reserved] 的实现就行，
## 不用改状态机、不用改枚举、不用改别的地方。

## 状态切换时发出去。
signal state_changed(from_state: int, to_state: int)

enum State {
	DEAD = 0,          ## 倒了
	REST = 1,          ## 站着歇一会儿
	PATROL = 2,        ## 沿路线巡逻
	INVESTIGATE = 3,   ## 去可疑点看看
	CHASE = 4,         ## 追目标
	ATTACK = 5,        ## 够到了，动手
	FLEE = 6,          ## 逃命
	UNSTICK = 7,       ## 卡住了：往后退一下脱困
	# ---- 以下是**预留**状态：位置占好，行为待实现 ----
	HUNGER = 8,        ## 预留：觅食
	THIRST = 9,        ## 预留：找水
	SLEEP = 10,        ## 预留：睡觉
	SOCIAL = 11,       ## 预留：社交 / 求偶
	STUNNED = 12,      ## 预留：被击晕
	GUARD = 13,        ## 预留：守卫某地
}

## 状态名。
const NAMES := {
	State.DEAD: "倒下",
	State.REST: "休息",
	State.PATROL: "巡逻",
	State.INVESTIGATE: "调查",
	State.CHASE: "追击",
	State.ATTACK: "攻击",
	State.FLEE: "逃跑",
	State.UNSTICK: "脱困",
	State.HUNGER: "觅食（预留）",
	State.THIRST: "找水（预留）",
	State.SLEEP: "睡觉（预留）",
	State.SOCIAL: "社交（预留）",
	State.STUNNED: "眩晕（预留）",
	State.GUARD: "守卫（预留）",
}

## 哪些是预留状态（行为还没实现）。
const RESERVED := [
	State.HUNGER, State.THIRST, State.SLEEP, State.SOCIAL, State.STUNNED, State.GUARD,
]

## 当前状态（-1 = 还没进任何状态）。
var current: int = -1
## 上一个状态。
var previous: int = -1
## 在当前状态里待了多久（秒）。
var time_in_state: float = 0.0


## 切状态。切到同一个状态不算切换。
func change_state(next_state: int) -> bool:
	if next_state == current:
		return false
	previous = current
	current = next_state
	time_in_state = 0.0
	state_changed.emit(previous, current)
	return true


## 推进计时。
func tick(delta: float) -> void:
	time_in_state += delta


## 当前状态的名字。
func get_state_name() -> String:
	if not NAMES.has(current):
		return "未知"
	return String(NAMES[current])


## 当前状态是不是预留的（行为还没实现）。
func is_reserved_state(state: int = -1) -> bool:
	if state < 0:
		state = current
	return RESERVED.has(state)


## 是不是"还在忙"（追击 / 攻击 / 逃跑这种有紧迫感的）。
func is_engaged() -> bool:
	return current == State.CHASE or current == State.ATTACK or current == State.FLEE

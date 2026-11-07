class_name DinosaurBlackboard
extends RefCounted
## 恐龙 AI 的**共享记忆**（黑板）。
##
## 感知（[DinosaurPerception]）负责往这里"写"，决策（[DinosaurAI]）负责
## "读"。两边不直接通信，都只碰黑板 —— 这样加一种感官 / 加一条决策规则
## 都不会牵动另一边。
##
## 记忆会**衰减**：目标看不见了，`last_known_position` 还在，
## 但 `time_since_seen()` 会越来越大，超过 `memory_time` 就该放弃追击了。

## 当前锁定的目标（一般是玩家）。
var target: Node3D = null
## 目标的最后已知位置 —— 看不见的时候，恐龙就奔这儿去。
var last_known_position: Vector3 = Vector3.ZERO
## 最后一次**看见**目标的时刻。
var last_seen_time: float = -9999.0
## 警觉度 0~1：看见 / 听见 / 挨打都会把它推高，时间一长自己降下去。
var alert: float = 0.0
## 兴趣点：听见的动静在这儿，值得去看看。
var interest_position: Vector3 = Vector3.ZERO
## 有没有兴趣点。
var has_interest: bool = false
## 威胁：比自己大的家伙，要躲着走。
var threat: Node3D = null
## 家：巡逻路线的起点。
var home_position: Vector3 = Vector3.ZERO
## 血量。
var health: float = 100.0
## 战斗冷却计时（秒）。
var attack_cooldown: float = 0.0


func _init(max_health: float = 100.0) -> void:
	health = max_health


## 记住"我看见了谁、在哪"。
func remember_target(node: Node3D, position: Vector3, now: float) -> void:
	target = node
	last_known_position = position
	last_seen_time = now


## 听见动静：记下兴趣点，警觉度拉高。
func hear(noise_position: Vector3, strength: float) -> void:
	interest_position = noise_position
	has_interest = true
	alert = minf(1.0, alert + strength)


## 目标跑了 / 没了：忘掉，但**保留**最后已知位置。
func forget_target() -> void:
	target = null


## 警觉度随时间衰减。
func decay_alert(delta: float, rate: float) -> void:
	alert = maxf(0.0, alert - rate * delta)
	attack_cooldown = maxf(0.0, attack_cooldown - delta)


## 距离上一次看见目标过了多久（秒）。
func time_since_seen(now: float) -> float:
	return now - last_seen_time


## 目标现在还"记得住"吗（没超记忆力）。
func remembers_target(now: float, memory_time: float) -> bool:
	return target != null and time_since_seen(now) <= memory_time


## 挨了一下：记下谁打的。
func take_damage(amount: float, attacker: Node3D) -> void:
	health = maxf(0.0, health - amount)
	if attacker != null:
		threat = attacker
		alert = 1.0


## 是不是快没血了。
func is_weak(ratio: float) -> bool:
	return health <= maxf(1.0, 100.0 * ratio)

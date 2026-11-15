class_name DinosaurAI
extends Node
## 恐龙的**大脑**：行为树（决策）+ 状态机（记账）。
##
## ## 分工
##
## ```
##   感知 [DinosaurPerception] ──┐
##                                ├→ 黑板 [DinosaurBlackboard] ─┐
##   转向 [DinosaurSteering]  ──┘                              │
##                                                               ▼
##                                     行为树 [DinosaurBehavior]（决策）
##                                                               │
##                                       状态机 [DinosaurStateMachine]（记账）
##                                                               │
##                                                               ▼
##                                                     身体 [DinosaurBody]
## ```
##
## 行为树决定"干什么"，状态机记住"现在是哪个状态"，身体负责"动起来"。
##
## ## 状态
##
## 见 [enum DinosaurStateMachine.State]。其中"觅食 / 找水 / 睡觉 / 社交 /
## 眩晕 / 守卫"是**预留**状态：位置占好了，行为还没做，行为树里对应分支的
## 条件恒为假。想做的时候打开那一支就行。
##
## ## 三个关键设计
##
## 1. **反应延迟**（`reaction_time`）：看见目标不是立刻追，先愣一下 ——
##    玩家才有时间跑掉，恐龙也才不像自动炮台。
## 2. **记忆**（`memory_time`）：目标跑进树丛看不见了，恐龙会**奔着最后已知
##    位置**去找，而不是当场傻站。记忆过期才放弃。
## 3. **视线被树挡**：感知的射线打在植被层上就算挡住 —— 玩家躲在香蕉树后面
##    恐龙就**看不见**。身体是**实心的**（树、墙都撞得到），但看不见，
##    这是有意为之：撞得到，但看不清。

## 状态切换时发出去（跟 [signal DinosaurStateMachine.state_changed] 一样）。
signal state_changed(from_state: int, to_state: int)
## 挥了一下嘴。
signal attacked(target: Node3D, damage: float)
## 彻底放弃了一个目标。
signal target_lost(target: Node3D)
## 被打了一下。
signal damaged(amount: float, attacker: Node3D)

## 大多少倍才算"威胁"（相对自己的体型）。
const THREAT_SIZE_RATIO := 1.6
## 挨了打之后躲多久（秒）。
##
## 血量见底时恐龙会本能地躲开，但它不能**永远**躲下去 ——
## 所以逃命是有时限的，躲完就回去巡逻。
const FLEE_DURATION := 5.0
## 逃完之后的"缓过来"时间（秒）：这段时间里除非威胁贴到脸上，否则回去干活。
const FLEE_COOLDOWN := 8.0

## 身体节点（默认是父节点）。
@export var body_path: NodePath = ^".."
## 调参表。留空会用一份默认的。
@export var config: DinosaurAIConfig
## 关掉就一动不动（当布景用）。
@export var enabled: bool = true

var _body: DinosaurBody
var _blackboard: DinosaurBlackboard
var _perception: DinosaurPerception
var _steering := DinosaurSteering.new()
var _tree: BehaviorTree
var _fsm := DinosaurStateMachine.new()
## 玩家节点（算 AI 分级用）。
var _player: Node3D = null
## 决策计时器：到点了才做一次"感官 + 决策"。
var _decision_timer := 0.0
var _route_index: int = 0
var _laps: int = 0
var _now: float = 0.0
## 想歇着吗：巡完一圈会被点亮，歇够了再熄掉。
##
## 之前这里是"`_laps >= 1` 就一直歇" —— 于是恐龙巡完第一圈就再也不会动了。
## 现在"想歇"是一个**独立的开关**，歇够 [member DinosaurAIConfig.rest_time] 秒就熄掉。
var _wants_rest: bool = false
## 第一次（重新）看见目标后，要等到什么时候才能开始追（秒）。
var _reaction_ready_at: float = 0.0
## 上一次"看见的目标"是谁：变了才算"重新发现"，才重新算反应延迟。
var _seen_target: Node3D = null
## 调查从什么时候开始（-1 = 没在调查）。
var _investigate_started: float = -1.0
## 躲到什么时候为止（秒）。
var _flee_until: float = 0.0
## "缓过来"到什么时候为止（秒）。
var _flee_cooldown: float = 0.0
## 卡住看门狗：想走却挪不动多久算卡住（秒）。
var _stuck_timer: float = 0.0
## 脱困：往回退的方向 + 还要退多久（秒）。
var _unstick_dir: Vector3 = Vector3.ZERO
var _unstick_timer: float = 0.0


func _ready() -> void:
	if config == null:
		config = DinosaurAIConfig.new()
	_blackboard = DinosaurBlackboard.new(config.max_health)
	_perception = DinosaurPerception.new()
	add_child(_perception)
	_body = get_node_or_null(body_path) as DinosaurBody
	if _body == null:
		push_warning("DinosaurAI: 找不到身体节点（%s）" % body_path)
		return
	_blackboard.home_position = _body.global_position
	_body.respawn_position = _body.global_position
	_player = get_tree().get_first_node_in_group("player") as Node3D
	_tree = DinosaurBehavior.build(self)
	_fsm.state_changed.connect(func(from_state: int, to_state: int) -> void:
		state_changed.emit(from_state, to_state))


func _physics_process(delta: float) -> void:
	if not enabled or _body == null or config == null:
		return
	_now += delta
	# 状态机计时**每帧**都要走 —— 休息时长、反应延迟都靠它。
	_fsm.tick(delta)
	# 感官和决策按**分级**的频率来：感知的射线、避障的射线都很贵，
	# 100 只恐龙全速跑，光射线就要吃掉半个帧。远处的恐龙降频，
	# 身体照常沿用上一次的意图走（恐龙不在玩家眼前，看不出差别）。
	_decision_timer += delta
	var interval := _decision_interval()
	if interval > 0.0 and _decision_timer < interval:
		return
	_decision_timer = 0.0
	# 1. 感官 → 黑板
	_perception.poll(_body, config, _blackboard, _now)
	_blackboard.decay_alert(delta, config.alert_decay)
	_update_reaction()
	# 2. 行为树 → 决策（选中的行为会切状态机）
	_tree.tick(delta)
	# 3. 卡住看门狗
	_watch_stuck(delta)


# ==============================================================================
# 行为树要用的条件
# ==============================================================================

## 血量归零了吗。
func is_dead() -> bool:
	return _blackboard != null and _blackboard.health <= 0.0


## 附近最吓人的那个家伙（没有就是 null）。
##
## "大得多"的门槛是 [constant THREAT_SIZE_RATIO] 倍 —— 不设门槛的话，
## 一头 17 m 的蜥脚龙在附近，满岛的恐龙都在逃命。
func _nearest_threat() -> Node3D:
	if _blackboard == null or _body == null:
		return null
	var best: Node3D = null
	var best_d := INF
	# 打过我的那个（记在黑板里）
	if _blackboard.threat != null and is_instance_valid(_blackboard.threat):
		var threat_body := _blackboard.threat as DinosaurBody
		if threat_body != null:
			best_d = threat_body.global_position.distance_to(_body.global_position)
			best = threat_body
	# 附近的大个子
	for other in _herd():
		if other == _body:
			continue
		var other_ai := other.get_node_or_null("AI") as DinosaurAI
		if other_ai == null or other_ai.config == null:
			continue
		if other_ai.config.body_size < config.body_size * THREAT_SIZE_RATIO:
			continue
		var d: float = (other as Node3D).global_position.distance_to(
			_body.global_position)
		if d < best_d:
			best_d = d
			best = other as Node3D
	return best


## 附近比自己大得多的家伙有多近（米）。没有就是 INF。
func _nearest_threat_distance() -> float:
	var threat := _nearest_threat()
	if threat == null:
		return INF
	return threat.global_position.distance_to(_body.global_position)


## 附近有大得多的家伙（或者刚挨过打）。
func is_threatened() -> bool:
	return _nearest_threat_distance() <= config.threat_radius


## 该不该逃命。
##
## 三种情况：
## 1. 正在逃命期（[constant FLEE_DURATION] 秒）—— 跑完为止；
## 2. 附近有比自己大得多的家伙（[method is_threatened]）—— 开始逃；
## 3. **血量见底**（低于 [member DinosaurAIConfig.flee_health_ratio]）——
##    挨了打、受了伤，本能地躲开。
##
## 逃完有 [constant FLEE_COOLDOWN] 秒的"缓过来"时间：这段时间里除非威胁
## 贴到脸上，否则回去干活。
##
## ## 为什么要这么麻烦
##
## 62 m 的小岛上，迅猛龙（2.2 m）眼里的"大个子"是霸王龙、三角龙、副栉龙……
## 五个都算威胁，而且 threat_radius 有 10 m —— 小恐龙会**永远**在逃，
## 一圈都巡不完。大世界里也是同样的问题：受惊的恐龙一直在跑，
## 巡逻就断了。所以逃跑必须是**有时限**的。
func should_flee() -> bool:
	if _blackboard == null:
		return false
	var dist := _nearest_threat_distance()
	if _now < _flee_until:
		return true
	if _now < _flee_cooldown:
		# 刚逃完：威胁不贴脸就回去干活
		return dist <= config.threat_radius * 0.5
	if dist <= config.threat_radius:
		_flee_until = _now + FLEE_DURATION
		_flee_cooldown = _now + FLEE_DURATION + FLEE_COOLDOWN
		return true
	if _blackboard.is_weak(config.flee_health_ratio):
		_flee_until = _now + FLEE_DURATION
		_flee_cooldown = _now + FLEE_DURATION + FLEE_COOLDOWN
		return true
	return false


## 目标够得着吗（能动手）。
func can_attack() -> bool:
	if _blackboard == null or _blackboard.target == null:
		return false
	if not is_instance_valid(_blackboard.target):
		return false
	if _blackboard.attack_cooldown > 0.0:
		return false
	# 反应延迟没过：先愣着，别一看见就挥嘴
	if _now < _reaction_ready_at:
		return false
	return _distance_to_target() <= config.attack_range


## 还记得目标吗（看得见，或者记忆还没过期），而且**反应延迟已经过去**。
func remembers_target() -> bool:
	if _blackboard == null:
		return false
	if not _blackboard.remembers_target(_now, config.memory_time):
		return false
	# 刚看见目标：先愣 [member DinosaurAIConfig.reaction_time] 秒再追
	return _now >= _reaction_ready_at


## 听见动静了吗（而且警觉度够高）。
func has_interest() -> bool:
	if _blackboard == null:
		return false
	return _blackboard.has_interest and _blackboard.alert >= config.chase_alert_threshold


## 卡住了吗（想走却挪不动）。
func is_stuck() -> bool:
	return _stuck_timer >= config.stuck_timeout


## 该歇了吗（歇够了就回去巡逻）。
##
## "想歇"是一个**独立的开关** [_wants_rest]：巡逻绕完一圈时点亮，
## 歇够 [member DinosaurAIConfig.rest_time] 秒后熄掉。
func should_rest() -> bool:
	return _wants_rest


# ==============================================================================
# 行为树要用的动作
# ==============================================================================

## 倒下。
func behave_dead(_delta: float) -> int:
	_enter(DinosaurStateMachine.State.DEAD)
	_body.stop()
	_body.play_state(&"death")
	return BtNode.Status.SUCCESS


## 远离威胁。
func behave_flee(_delta: float) -> int:
	_enter(DinosaurStateMachine.State.FLEE)
	_drive_towards(_flee_goal(), config.chase_speed_scale, &"run")
	return BtNode.Status.SUCCESS


## 挥击。
func behave_attack(_delta: float) -> int:
	_enter(DinosaurStateMachine.State.ATTACK)
	_body.stop()
	_body.play_state(&"attack")
	if _blackboard.target != null and is_instance_valid(_blackboard.target):
		# 面向目标
		var to_target := (_blackboard.target as Node3D).global_position - _body.global_position
		to_target.y = 0.0
		if to_target.length_squared() > 0.0001:
			_body.face_towards(to_target.normalized())
	if _blackboard.attack_cooldown <= 0.0 and _distance_to_target() <= config.attack_range:
		_blackboard.attack_cooldown = config.attack_cooldown
		var target := _blackboard.target
		if target != null and is_instance_valid(target):
			attacked.emit(target, config.attack_damage)
			# 目标自己处理伤害：建筑（可攻击的那种）实现了 [method take_damage]，
			# 挨完咬血就掉。玩家那边以后接上同样的方法就行。
			if target.has_method("take_damage"):
				target.take_damage(config.attack_damage, _body)
	return BtNode.Status.SUCCESS


## 追上去。
func behave_chase(_delta: float) -> int:
	_enter(DinosaurStateMachine.State.CHASE)
	_drive_towards(_chase_goal(), config.chase_speed_scale, &"run")
	# 追的过程中目标可能跑掉了：记忆过期就转去调查
	if not _blackboard.remembers_target(_now, config.memory_time):
		if _blackboard.target != null:
			target_lost.emit(_blackboard.target)
		_blackboard.interest_position = _blackboard.last_known_position
		_blackboard.has_interest = true
	return BtNode.Status.SUCCESS


## 去可疑点看看。
##
## 最多查 [member DinosaurAIConfig.investigate_time] 秒 —— 查不到就放弃，
## 回去巡逻（不然恐龙会为了一个够不着的动静在原地站到天荒地老）。
func behave_investigate(_delta: float) -> int:
	_enter(DinosaurStateMachine.State.INVESTIGATE)
	if _investigate_started < 0.0:
		_investigate_started = _now
	if _now - _investigate_started >= config.investigate_time:
		# 查够了：没什么好看的，回去巡逻
		_investigate_started = -1.0
		_blackboard.has_interest = false
		return BtNode.Status.SUCCESS
	var goal := _blackboard.interest_position
	if _body.global_position.distance_to(goal) < 2.0:
		# 到了，没什么好看的，回去巡逻
		_investigate_started = -1.0
		_blackboard.has_interest = false
		return BtNode.Status.SUCCESS
	_drive_towards(goal, config.chase_speed_scale, &"walk")
	return BtNode.Status.SUCCESS


## 站着歇一会儿。
##
## 歇够 [member DinosaurAIConfig.rest_time] 秒就熄掉"想歇"的念头，接着巡逻。
## （之前这里没有出口：`_laps >= 1` 之后永远返回 true，恐龙巡完一圈就不动了。）
func behave_rest(_delta: float) -> int:
	# **先切状态，再看计时**：`_fsm.time_in_state` 记的是"在当前状态待了多久"，
	# 刚切进 REST 时它才归零。反过来写（先看计时再切状态）的话，
	# 读到的还是刚才巡逻状态的时长 —— 早就超过 rest_time 了，
	# 于是恐龙**一次都不歇**，直接接着巡逻。
	_enter(DinosaurStateMachine.State.REST)
	if _wants_rest and _fsm.time_in_state >= config.rest_time:
		# 歇够了：熄掉"想歇"的念头
		_wants_rest = false
	if not _wants_rest:
		# 直接接着巡逻（不用等下一帧，行为树下一帧才轮到"巡逻"分支）
		_enter(DinosaurStateMachine.State.PATROL)
		var goal := _current_waypoint()
		if goal != Vector3.INF:
			_drive_towards(goal, config.patrol_speed_scale, &"walk")
			return BtNode.Status.SUCCESS
	_body.stop()
	_body.play_state(&"idle")
	return BtNode.Status.SUCCESS


## 沿路线巡逻。
func behave_patrol(_delta: float) -> int:
	_enter(DinosaurStateMachine.State.PATROL)
	var goal := _current_waypoint()
	if goal == Vector3.INF:
		_body.stop()
		_body.play_state(&"idle")
		return BtNode.Status.SUCCESS
	_drive_towards(goal, config.patrol_speed_scale, &"walk")
	return BtNode.Status.SUCCESS


## 脱困：被树 / 墙 / 石头卡住了，先往后退一下，再回到路线上。
##
## 恐龙的身体是**实心的**，被两个障碍夹在中间就动不了。
## 这时候硬顶是没用的 —— 得先退出来。所以这里记住"上次撞到的法线"，
## 往反方向退，退出来再换个路点继续走。巡逻因此不会停。
func behave_unstick(delta: float) -> int:
	_enter(DinosaurStateMachine.State.UNSTICK)
	if _unstick_timer <= 0.0:
		# 第一次进来：算一个退出去的方向
		_unstick_dir = _unstick_direction()
		_unstick_timer = config.unstick_time
	_unstick_timer -= delta
	var dir := _unstick_dir
	if dir == Vector3.ZERO:
		dir = -_body.get_forward()
	# 退的时候不追求"绕开"，只要能离开卡住的地方。
	# 用**巡逻速度**退：用追击速度退 1.2 s，迅猛龙能倒着蹿出去五六米，
	# 离路线更远了，反而更容易再卡住。
	_body.drive(dir, config.patrol_speed_scale)
	_body.play_state(&"walk")
	if _unstick_timer <= 0.0:
		_unstick_timer = 0.0
		_stuck_timer = 0.0
		# 换个路点，重新上路
		if _route().size() >= 2:
			_advance_route_index()
	return BtNode.Status.SUCCESS


## **预留状态**的统一入口：还没实现，先站住。
func behave_reserved(state: int, _delta: float) -> int:
	_enter(state)
	_body.stop()
	_body.play_state(&"idle")
	return BtNode.Status.SUCCESS


# ==============================================================================
# 内部
# ==============================================================================

## 切状态（走状态机，状态机负责发信号）。
func _enter(state: int) -> void:
	if _fsm.current == state:
		return
	# 从"追击"掉出来的时候，把目标忘掉，免得一直盯着
	if _fsm.current == DinosaurStateMachine.State.CHASE \
			and state != DinosaurStateMachine.State.CHASE:
		if _blackboard.target != null:
			_blackboard.forget_target()
	_fsm.change_state(state)


## 朝目标点走：转向 + 避障 + 群体分离。
func _drive_towards(goal: Vector3, speed_scale: float, anim: StringName) -> void:
	var direction := _steering.compute(_body, goal, _herd(), config, _target_rids())
	if direction == Vector3.ZERO:
		_body.stop()
		_body.play_state(&"idle")
		return
	_body.drive(direction, speed_scale)
	_body.play_state(anim)


## 当前目标的刚体（避障射线要忽略它）。
##
## 目标本身是实心的：玩家是胶囊，建筑是柱子。要是把它们也算成障碍，
## 恐龙就会**围着目标转圈**，永远靠不上去 —— 想啃建筑就啃不到。
func _target_rids() -> Array:
	var out: Array = []
	if _blackboard == null:
		return out
	var target := _blackboard.target
	# ⚠️ **先判有效再判类型**：目标可能刚被拆掉（建筑塌了 / 玩家没了），
	# 对一个已经释放的实例做 `is` 判断会直接报
	# "Left operand of 'is' is a previously freed instance"。
	if target == null or not is_instance_valid(target):
		return out
	if target is CollisionObject3D:
		out.append((target as CollisionObject3D).get_rid())
	return out


## 巡逻路线（在身体上，因为只有实例根的属性能被父场景覆写）。
func _route() -> PackedVector3Array:
	if _body == null:
		return PackedVector3Array()
	return _body.route


## 当前路点；走到就走下一个，绕完一圈算完成。
func _current_waypoint() -> Vector3:
	var route := _route()
	if route.size() < 2:
		return Vector3.INF
	var goal := route[_route_index]
	# 到了没有？两个条件满足其一就算：
	# 1. 离路点够近（2.5 m）；
	# 2. **已经越过这个路点了** —— 离下一个路点更近。
	#
	## 第 2 条很重要：光靠 2.5 m 的半径，快的恐龙（迅猛龙 4 m/s）从路点旁边
	## 擦过去、又被避障推着转圈，就永远差那么几厘米到不了 —— 卡在同一个
	## 路点上，一圈也巡不完。
	var next := route[(_route_index + 1) % route.size()]
	var to_goal := _body.global_position.distance_to(goal)
	if to_goal < 2.5 or _body.global_position.distance_to(next) < to_goal:
		_advance_route_index()
		goal = route[_route_index]
	return goal


## 路点前进一格。绕回开头就记一圈（巡完一圈就该歇一会儿）。
##
## 脱困时也会前进路点，所以绕圈必须**统一走这个函数** ——
## 早先脱困自己改索引，绕回开头时没记圈，恐龙就永远"巡不完一圈"。
func _advance_route_index() -> void:
	var route := _route()
	if route.size() < 2:
		return
	_route_index += 1
	if _route_index >= route.size():
		_route_index = 0
		_laps += 1
		# 巡完一圈：歇一会儿（歇够 rest_time 再回来）
		_wants_rest = true


## 第一次（重新）看见目标时，记下"什么时候才能开始追"。
##
## 看见 ≠ 立刻追：先愣 [member DinosaurAIConfig.reaction_time] 秒，
## 玩家才有时间跑掉，恐龙也才不像自动炮台。
##
## 只有**目标换了**才重新计时 —— 目标一直盯着看的时候，
## 反应延迟不应该每帧重置。
func _update_reaction() -> void:
	if _blackboard == null:
		return
	var target := _blackboard.target
	if target == _seen_target:
		return
	_seen_target = target
	if target != null:
		_reaction_ready_at = _now + config.reaction_time


## 追击的目标点：看得见就用当前位置，看不见就用最后已知位置。
func _chase_goal() -> Vector3:
	if _blackboard.target != null and is_instance_valid(_blackboard.target):
		return _blackboard.target.global_position
	return _blackboard.last_known_position


## 逃命的目标点。
##
## 沿着自己的巡逻路线跑 —— 直线远离威胁会把恐龙直接送到崖边掉下去
## （岛是浮空的，边缘就是悬崖）。沿着路跑既安全，看起来也更像
## "慌不择路地钻进林子"。
##
## ## 为什么往前跑
##
## 往前跑能躲开威胁（威胁多半在身后），而且**不白跑**：往回跑三个路点
## 再折回来，等于把这阵子巡逻的进度倒回去 —— 小恐龙（迅猛龙）跑得慢、
## 逃得勤，一圈永远巡不完。
func _flee_goal() -> Vector3:
	var route := _route()
	if route.size() >= 4:
		# 在后面几个路点里挑一个**离威胁最远**的
		var threat := _nearest_threat()
		var best: Vector3 = route[posmod(_route_index + 2, route.size())]
		var best_d := -INF
		for k in range(1, 7):
			var cand: Vector3 = route[posmod(_route_index + k, route.size())]
			var d := INF
			if threat != null:
				d = cand.distance_to(threat.global_position)
			if d > best_d:
				best_d = d
				best = cand
		return best
	# 没有路线：往远离威胁的方向（作为兜底）
	var away := Vector3.ZERO
	if _blackboard.threat != null and is_instance_valid(_blackboard.threat):
		away = _body.global_position - (_blackboard.threat as Node3D).global_position
	else:
		away = _body.global_position - _blackboard.home_position
	away.y = 0.0
	if away.length_squared() < 0.0001:
		away = Vector3.FORWARD
	return _body.global_position + away.normalized() * 12.0


## 卡住看门狗：想走却挪不动超过 2.5 秒，就换个路点 / 换个目标。
##
## 恐龙的**身体**是实心的（树、墙、石头都撞得到），所以被顶住是可能的；
## 巡逻必须**不间断**，所以这里兜底。
func _watch_stuck(delta: float) -> void:
	if _fsm.current == DinosaurStateMachine.State.DEAD:
		return
	var wants_to_move := _body.get_speed_scale() > 0.1
	var moving := _body.velocity.length() > 0.2
	if wants_to_move and not moving:
		_stuck_timer += delta
		return
	_stuck_timer = 0.0
	_unstick_timer = 0.0


## 脱困的方向：往"上次撞到的东西"的反方向退。
##
## 拿不到碰撞信息（比如身体已经陷进石头里了）就**原路退回** ——
## 退一步总比卡在原地强。
func _unstick_direction() -> Vector3:
	var body := _body
	for i in body.get_slide_collision_count():
		var col: KinematicCollision3D = body.get_slide_collision(i)
		var normal := col.get_normal()
		normal.y = 0.0
		if normal.length_squared() > 0.0001:
			return -normal.normalized()
	# 没有碰撞信息：往后退（身体自己朝的方向的反方向）
	return -body.get_forward()


func _distance_to_target() -> float:
	if _blackboard.target == null or not is_instance_valid(_blackboard.target):
		return INF
	return _body.global_position.distance_to((_blackboard.target as Node3D).global_position)


## 决策间隔（秒）：离玩家越远，越不频繁。
##
## 0 = 每帧都决策（玩家眼前）。远处的恐龙 20 Hz / 5 Hz 一次 ——
## 它们反正看不见玩家，决策再快也没用。
func _decision_interval() -> float:
	if _player == null or not is_instance_valid(_player):
		return 0.0
	var d := _player.global_position.distance_to(_body.global_position)
	if d < 140.0:
		return 0.0
	if d < 450.0:
		return 0.05
	return 0.2


## 同伴恐龙（用于分离和威胁判断）。
##
## 缓存**一帧算一次**：100 只恐龙时，每只每帧都去 get_nodes_in_group()
## 就是白算 100 遍。
static var _herd_cache: Array = []
static var _herd_frame: int = -1
static var _herd_group: String = ""

func _herd() -> Array:
	if config == null:
		return []
	var frame := Engine.get_physics_frames()
	if frame != _herd_frame or String(config.herd_group) != _herd_group:
		_herd_frame = frame
		_herd_group = String(config.herd_group)
		_herd_cache = get_tree().get_nodes_in_group(config.herd_group)
	return _herd_cache


# ==============================================================================
# 对外接口
# ==============================================================================

## 挨了一下（由游戏逻辑调用）。
func take_damage(amount: float, attacker: Node3D = null) -> void:
	if _blackboard == null:
		return
	_blackboard.take_damage(amount, attacker)
	damaged.emit(amount, attacker)
	if _blackboard.health <= 0.0:
		_enter(DinosaurStateMachine.State.DEAD)
	else:
		# 挨了打：先躲一阵子（血量见底时逃命是本能）
		_flee_until = _now + FLEE_DURATION
		_flee_cooldown = _now + FLEE_DURATION + FLEE_COOLDOWN


## 当前状态（调试 / 自检用）。
func get_state() -> int:
	return _fsm.current


## 当前状态的名字（调试 / 自检用）。
func get_state_name() -> String:
	return _fsm.get_state_name()


## 状态机（调试 / 自检用）。
func get_state_machine() -> DinosaurStateMachine:
	return _fsm


## 行为树（调试 / 自检用）。
func get_behavior_tree() -> BehaviorTree:
	return _tree


## 黑板（调试 / 自检用）。
func get_blackboard() -> DinosaurBlackboard:
	return _blackboard


## 现在在第几个路点（调试 / 自检用）。
func get_route_index() -> int:
	return _route_index


## 已经巡了几圈（调试 / 自检用）。
func get_laps() -> int:
	return _laps

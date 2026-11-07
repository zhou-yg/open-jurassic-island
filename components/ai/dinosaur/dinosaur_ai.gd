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
##    恐龙就**看不见**。身体能穿过去，看不见，这是有意为之。

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
var _route_index: int = 0
var _laps: int = 0
var _now: float = 0.0
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
	_tree = DinosaurBehavior.build(self)
	_fsm.state_changed.connect(func(from_state: int, to_state: int) -> void:
		state_changed.emit(from_state, to_state))


func _physics_process(delta: float) -> void:
	if not enabled or _body == null or config == null:
		return
	_now += delta
	# 1. 感官 → 黑板
	_perception.poll(_body, config, _blackboard, _now)
	_blackboard.decay_alert(delta, config.alert_decay)
	# 2. 行为树 → 决策（选中的行为会切状态机）
	_tree.tick(delta)
	# 3. 状态机记账
	_fsm.tick(delta)
	_watch_stuck(delta)


# ==============================================================================
# 行为树要用的条件
# ==============================================================================

## 血量归零了吗。
func is_dead() -> bool:
	return _blackboard != null and _blackboard.health <= 0.0


## 附近有大得多的家伙（或者刚挨过打）。
func is_threatened() -> bool:
	if _blackboard == null:
		return false
	if _blackboard.threat != null and is_instance_valid(_blackboard.threat):
		var threat_body := _blackboard.threat as DinosaurBody
		if threat_body != null:
			if threat_body.global_position.distance_to(_body.global_position) <= config.threat_radius:
				return true
	for other in _herd():
		if other == _body:
			continue
		var other_ai := other.get_node_or_null("AI") as DinosaurAI
		if other_ai == null or other_ai.config == null:
			continue
		# 要"大得多"才算威胁：不然一头 17 m 的蜥脚龙在附近，满岛的恐龙都在逃命
		if other_ai.config.body_size < config.body_size * THREAT_SIZE_RATIO:
			continue
		if other.global_position.distance_to(_body.global_position) <= config.threat_radius:
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
	return _distance_to_target() <= config.attack_range


## 还记得目标吗（看得见，或者记忆还没过期）。
func remembers_target() -> bool:
	if _blackboard == null:
		return false
	return _blackboard.remembers_target(_now, config.memory_time)


## 听见动静了吗（而且警觉度够高）。
func has_interest() -> bool:
	if _blackboard == null:
		return false
	return _blackboard.has_interest and _blackboard.alert >= config.chase_alert_threshold


## 卡住了吗（想走却挪不动）。
func is_stuck() -> bool:
	return _stuck_timer >= config.stuck_timeout


## 该歇了吗（巡完一圈，或者正在休息）。
func should_rest() -> bool:
	if _fsm.current == DinosaurStateMachine.State.REST:
		return true
	return _laps >= 1 and _route().size() >= 2


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
		attacked.emit(_blackboard.target, config.attack_damage)
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
func behave_investigate(_delta: float) -> int:
	_enter(DinosaurStateMachine.State.INVESTIGATE)
	var goal := _blackboard.interest_position
	if _body.global_position.distance_to(goal) < 2.0:
		# 到了，没什么好看的，回去巡逻
		_blackboard.has_interest = false
		return BtNode.Status.SUCCESS
	_drive_towards(goal, config.chase_speed_scale, &"walk")
	return BtNode.Status.SUCCESS


## 站着歇一会儿。
func behave_rest(_delta: float) -> int:
	_enter(DinosaurStateMachine.State.REST)
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
	# 退的时候不追求"绕开"，只要能离开卡住的地方
	_body.drive(dir, config.chase_speed_scale)
	_body.play_state(&"walk")
	if _unstick_timer <= 0.0:
		_unstick_timer = 0.0
		_stuck_timer = 0.0
		# 换个路点，重新上路
		var route := _route()
		if route.size() >= 2:
			_route_index = (_route_index + 1) % route.size()
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
	var direction := _steering.compute(_body, goal, _herd(), config)
	if direction == Vector3.ZERO:
		_body.stop()
		_body.play_state(&"idle")
		return
	_body.drive(direction, speed_scale)
	_body.play_state(anim)


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
	if _body.global_position.distance_to(goal) < 2.5:
		_route_index += 1
		if _route_index >= route.size():
			_route_index = 0
			_laps += 1
		goal = route[_route_index]
	return goal


## 追击的目标点：看得见就用当前位置，看不见就用最后已知位置。
func _chase_goal() -> Vector3:
	if _blackboard.target != null and is_instance_valid(_blackboard.target):
		return _blackboard.target.global_position
	return _blackboard.last_known_position


## 逃命的目标点。
##
## **沿着自己的巡逻路线往后跑**，而不是直线远离威胁 —— 直线远离会把它
## 直接送到崖边掉下去（岛是浮空的，边缘就是悬崖）。
## 沿着路跑既安全，看起来也更像"慌不择路地钻进林子"。
func _flee_goal() -> Vector3:
	var route := _route()
	if route.size() >= 4:
		# 回头跑几个路点
		var idx := posmod(_route_index - 3, route.size())
		return route[idx]
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


## 同伴恐龙（用于分离和威胁判断）。
func _herd() -> Array:
	if config == null:
		return []
	return get_tree().get_nodes_in_group(config.herd_group)


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

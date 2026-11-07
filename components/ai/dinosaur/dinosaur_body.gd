class_name DinosaurBody
extends CharacterBody3D
## 恐龙"身体"的**契约 + 执行器**。
##
## AI（[DinosaurAI]）只通过这几个方法驱动身体，它不碰物理、不碰动画：
##
## - [method drive] 给一个期望方向（世界坐标，水平）+ 速度倍率；
## - [method stop] 站住；
## - [method play_state] 切动画（idle / walk / run / attack / death）。
##
## 身体自己负责：按最大转向速度慢慢转、按速度往前走、重力、贴地、
## 掉了出去送回原地、以及**模型正不正**（Godot 的前方是 -Z，模型不一定）。
##
## 具体型号的实现见 `components/vegetation/dinosaur/dinosaur.gd`。

## 模型节点名（相对本节点）。模型的前方要和 Godot 的 -Z 对上。
@export var model_node_name: String = "Model"
## 巡逻路线（世界坐标路点，首尾相接绕一圈）。留空 = 原地不动。
##
## 为什么路线在"身体"上而不在 AI 上：Godot 的场景实例化**只允许覆写实例根
## 节点的属性**，子节点（AI）的属性存不进父场景。路线是"这一只恐龙的巡逻
## 任务"，本来就属于个体，所以挂在身体上，AI 每帧从这儿读。
@export var route: PackedVector3Array = PackedVector3Array()
## 基础速度（米/秒），实际速度 = 基础速度 × AI 给的速度倍率。
@export var base_speed: float = 2.5
## 最大转向速度（度/秒）。越小转得越"懒"，恐龙看着更自然。
@export var turn_speed_deg: float = 45.0
## 重力（米/秒²）。
@export var gravity: float = 20.0
## 掉到低于这个高度（米）就送回出发点。
@export var fall_out_height: float = -12.0
## 掉出去之后回到哪儿。
@export var respawn_position: Vector3 = Vector3.ZERO

var _desired_dir := Vector3.ZERO
var _speed_scale := 1.0
var _anim_player: AnimationPlayer = null
var _clips: Dictionary = {}
var _current_state: StringName = &""
var _one_shot_until: float = 0.0


func _ready() -> void:
	_setup_animation()
	respawn_position = global_position
	# 身体是**实心的**：地面、树、围墙、石头、同类都撞得到。
	# 所以恐龙不会从树干 / 残墙里穿过去（树是掩体，得站得住）。
	# 代价是可能被顶住 —— 巡逻的连续性由行为树的避让 + 卡住看门狗保证。
	collision_layer = DinosaurAIConfig.LAYER_CREATURE
	collision_mask = (DinosaurAIConfig.LAYER_WORLD
		| DinosaurAIConfig.LAYER_VEGETATION
		| DinosaurAIConfig.LAYER_STRUCTURE
		| DinosaurAIConfig.LAYER_CREATURE
		| DinosaurAIConfig.LAYER_BOUNDARY)
	floor_max_angle = deg_to_rad(50.0)
	floor_snap_length = 0.6


## AI 给的新意图：往哪走、走多快。
func drive(direction: Vector3, speed_scale: float) -> void:
	_desired_dir = direction
	_desired_dir.y = 0.0
	if _desired_dir.length_squared() > 0.0001:
		_desired_dir = _desired_dir.normalized()
	_speed_scale = maxf(0.0, speed_scale)


## 站住。
func stop() -> void:
	_desired_dir = Vector3.ZERO
	_speed_scale = 0.0


## 切动画。state 取 idle / walk / run / attack / death。
func play_state(state: StringName) -> void:
	if state == _current_state:
		return
	_current_state = state
	if _anim_player == null:
		return
	var clip := _clip_for(state)
	if clip == "":
		return
	if state == &"attack" or state == &"death":
		# 一次性动作：播完停在那儿
		var anim := _anim_player.get_animation(clip)
		if anim != null:
			anim.loop_mode = Animation.LOOP_NONE
		_anim_player.play(clip)
		_one_shot_until = _anim_player.current_animation_position + _anim_player.get_animation(clip).length
		return
	var anim := _anim_player.get_animation(clip)
	if anim != null and anim.loop_mode == Animation.LOOP_NONE:
		anim.loop_mode = Animation.LOOP_LINEAR
	_anim_player.play(clip)


## 当前身体"脸"朝哪（水平，Godot 的前方 = -Z）。
func get_forward() -> Vector3:
	var forward := -global_transform.basis.z
	forward.y = 0.0
	if forward.length_squared() < 0.0001:
		return Vector3.FORWARD
	return forward.normalized()


## 当前速度倍率（AI / 自检用）。
func get_speed_scale() -> float:
	return _speed_scale


## 本体的高度（米）：用来决定避让射线打多高。
func get_height() -> float:
	var shape := get_node_or_null("Collision") as CollisionShape3D
	if shape != null and shape.shape is CapsuleShape3D:
		return (shape.shape as CapsuleShape3D).height
	return 1.0


## 立刻把"脸"转向某个方向（不移动）。攻击的时候要面向目标。
func face_towards(direction: Vector3) -> void:
	direction.y = 0.0
	if direction.length_squared() < 0.0001:
		return
	rotation.y = atan2(direction.x, direction.z)


func _physics_process(delta: float) -> void:
	# 转向：慢慢转过去
	if _desired_dir != Vector3.ZERO:
		var target_yaw := atan2(_desired_dir.x, _desired_dir.z)
		rotation.y = rotate_toward(rotation.y, target_yaw,
			deg_to_rad(turn_speed_deg) * delta)
	# 前进：沿身体自己的朝向走（转向和前进分开，弯道是圆的）
	var forward := -global_transform.basis.z
	forward.y = 0.0
	if forward.length_squared() > 0.0001:
		forward = forward.normalized()
		var speed := base_speed * _speed_scale
		velocity.x = forward.x * speed
		velocity.z = forward.z * speed
	else:
		velocity.x = move_toward(velocity.x, 0.0, base_speed * delta)
		velocity.z = move_toward(velocity.z, 0.0, base_speed * delta)
	if not is_on_floor():
		velocity.y -= gravity * delta
	else:
		velocity.y = minf(velocity.y, 0.0)
	move_and_slide()
	_check_fell_out()


func _check_fell_out() -> void:
	if global_position.y > fall_out_height:
		return
	global_position = respawn_position
	velocity = Vector3.ZERO


## 找模型里的 AnimationPlayer，按**关键词**挑出各个动作的片段。
##
## glb 里的动画名是 "Armature|TRex_Walk" 这种格式，所以按"包含"来匹配，
## 跟模型名字解耦 —— 换个 glb 也不用改这里。
func _setup_animation() -> void:
	var model := get_node_or_null(NodePath(model_node_name))
	if model == null:
		return
	_anim_player = model.find_child("AnimationPlayer", true, false) as AnimationPlayer
	if _anim_player == null:
		return
	_clips = {
		&"idle": _find_clip(["Idle", "Stand"]),
		&"walk": _find_clip(["Walk"]),
		&"run": _find_clip(["Run"]),
		&"attack": _find_clip(["Attack"]),
		&"death": _find_clip(["Death"]),
	}


func _find_clip(hints: Array) -> String:
	if _anim_player == null:
		return ""
	for hint in hints:
		for anim_name in _anim_player.get_animation_list():
			if String(anim_name).to_lower().contains(String(hint).to_lower()):
				return String(anim_name)
	return ""


func _clip_for(state: StringName) -> String:
	if _clips.has(state):
		return String(_clips[state])
	# 没有专门的片段就退回走路 / 站着
	match state:
		&"run":
			return String(_clips.get(&"walk", ""))
		&"attack", &"death":
			return String(_clips.get(&"idle", ""))
	return String(_clips.get(&"idle", ""))

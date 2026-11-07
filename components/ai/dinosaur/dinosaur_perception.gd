class_name DinosaurPerception
extends Node
## 恐龙的**感官**：看见什么、听见什么。
##
## 只负责"采集"，不负责"决定"：看到 / 听到的东西都写进
## [DinosaurBlackboard]，由 [DinosaurAI] 去决定要不要反应。
##
## ## 视线会被树挡住
##
## 视线检测是一条**射线**，打在植被 / 建筑 / 地面上就算被挡。
## 所以玩家躲在香蕉树后面，恐龙**看不见** —— 这正是这套 AI 的核心玩法：
## 树不只是掩体，还是"视野的遮蔽物"。
##
## 注意：恐龙的**身体**不跟树碰撞（巡逻不能被挡住），但**视线**会被树挡住。
## 身体能穿过去，看不见 —— 这是有意为之。

## 视线被什么挡住。
@export_flags_3d_physics var sight_blockers: int = (
	DinosaurAIConfig.LAYER_VEGETATION
	| DinosaurAIConfig.LAYER_STRUCTURE
	| DinosaurAIConfig.LAYER_WORLD)
## 视线检测用的射线层（跟 [member sight_blockers] 分开，方便调）。
@export_flags_3d_physics var sight_mask: int = (
	DinosaurAIConfig.LAYER_VEGETATION
	| DinosaurAIConfig.LAYER_STRUCTURE
	| DinosaurAIConfig.LAYER_WORLD)

var _last_sight_ok: Dictionary = {}


## 采集一轮感官信息，写进黑板。
##
## [param body] 恐龙身体（用来取位置、朝向、排除自己），
## [param config] 调参表，[param blackboard] 记忆，[param now] 当前时间（秒）。
func poll(body: Node3D, config: DinosaurAIConfig, blackboard: DinosaurBlackboard,
		now: float) -> void:
	if body == null or config == null:
		return
	var targets := get_tree().get_nodes_in_group(config.target_group)
	var best: Node3D = null
	var best_distance := INF
	for target in targets:
		if target == body or not (target is Node3D):
			continue
		var node := target as Node3D
		var to_target := node.global_position - body.global_position
		var distance := to_target.length()
		if distance > config.sight_range:
			continue
		# 视野锥：得在"脸"朝着的那半边
		var flat := Vector3(to_target.x, 0.0, to_target.z)
		if flat.length_squared() > 0.0001:
			var forward := _body_forward(body)
			var angle := rad_to_deg(forward.angle_to(flat.normalized()))
			if angle > config.sight_half_angle_deg:
				continue
		# 视线：中间被东西挡住就看不见
		if not _has_line_of_sight(body, node, config):
			continue
		if distance < best_distance:
			best_distance = distance
			best = node
	if best != null:
		blackboard.remember_target(best, best.global_position, now)
		blackboard.alert = minf(1.0, blackboard.alert + 0.6)
		blackboard.has_interest = false
		return
	# 看不见 —— 但听得见
	_listen(body, config, blackboard, targets)


## 听觉：目标跑得快就算有声音，声音传多远跟速度成正比。
func _listen(body: Node3D, config: DinosaurAIConfig,
		blackboard: DinosaurBlackboard, targets: Array) -> void:
	for target in targets:
		if not (target is CharacterBody3D):
			continue
		var mover := target as CharacterBody3D
		var speed := mover.velocity.length()
		if speed < config.noise_speed_threshold:
			continue
		var reach := config.hearing_range * (1.0 + config.noise_reach_scale
			* clampf(speed / maxf(config.noise_speed_threshold, 0.01) - 1.0, 0.0, 1.0))
		var distance := mover.global_position.distance_to(body.global_position)
		if distance > reach:
			continue
		var strength := 1.0 - distance / maxf(reach, 0.01)
		blackboard.hear(mover.global_position, strength * 0.5)
		return


## 从眼睛到目标胸口这条线有没有被挡住。
func _has_line_of_sight(body: Node3D, target: Node3D, config: DinosaurAIConfig) -> bool:
	var from := body.global_position + Vector3.UP * config.eye_height
	var to := target.global_position + Vector3.UP * (config.eye_height * 0.6)
	var query := PhysicsRayQueryParameters3D.create(from, to)
	query.collision_mask = sight_mask
	query.exclude = [body.get_rid()]
	# 感知是普通节点，3D 世界从身体那儿拿
	return not body.get_world_3d().direct_space_state.intersect_ray(query).is_empty()


## 身体"脸"朝的方向（水平）。模型是绕 Y 转的，取 -Z（Godot 的前方）。
func _body_forward(body: Node3D) -> Vector3:
	var forward := -body.global_transform.basis.z
	forward.y = 0.0
	if forward.length_squared() < 0.0001:
		return Vector3.FORWARD
	return forward.normalized()


## 上一次感知有没有看见目标（调试 / 自检用）。
func saw_target() -> bool:
	return not _last_sight_ok.is_empty()

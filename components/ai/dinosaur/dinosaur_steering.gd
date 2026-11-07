class_name DinosaurSteering
extends RefCounted
## 恐龙的**转向 / 避障 / 群体分离** —— 决定"这一帧往哪走"。
##
## 恐龙的身体**不跟树、墙碰撞**（不然巡逻会被卡住），
## 所以撞到东西要靠"软避让"绕开：往左右各打一条射线，
## 哪边空就往哪边偏。
##
## 最后还会把同伴推开：几只恐龙挤在同一条路上会互相顶，
## 群体分离让它们自然散开、保持队形。

## 避让射线的高度（米，相对脚底）。压低一点，矮石头也能测到。
const AVOID_RAY_HEIGHT := 0.5
## 悬崖探测：往前探多远（米）。
const CLIFF_PROBE_AHEAD := 3.4
## 前方的地面比脚下低多少算"悬崖"（米）。
const CLIFF_DROP_LIMIT := 1.2

## 算出一个水平方向（世界坐标）。
##
## [param body] 恐龙身体，[param goal] 想去的点，
## [param neighbours] 同伴（[Dinosaur] 或 [Node3D]），
## [param config] 调参表。
func compute(body: Node3D, goal: Vector3, neighbours: Array,
		config: DinosaurAIConfig) -> Vector3:
	var direction := _seek(body, goal)
	if direction == Vector3.ZERO:
		return Vector3.ZERO
	direction = _avoid(body, direction, config)
	direction = _cliff_guard(body, direction)
	direction = _separate(body, direction, neighbours, config)
	return direction.normalized()


## 朝目标点去。
func _seek(body: Node3D, goal: Vector3) -> Vector3:
	var to_goal := goal - body.global_position
	to_goal.y = 0.0
	if to_goal.length_squared() < 0.0001:
		return Vector3.ZERO
	return to_goal.normalized()


## 软避让：**沿着障碍滑行**，而不是转开。
##
## 转开（把方向旋转 30°~150°）会让恐龙**偏离自己的路线** ——
## 躲一下树就偏到路边，躲两下就钻进树丛里，然后被树顶住卡死。
## 沿着障碍的切线方向走就稳多了：路线不变，只是从障碍边上"抹"过去。
##
## 具体做法：往正前方打一条射线，撞到就把期望方向**投影到障碍的切平面**上
## （去掉撞进去的那部分分量），剩下的就是沿着障碍走的方向。
## 正对着障碍（切向分量几乎为零）才挑一边绕。
func _avoid(body: Node3D, direction: Vector3, config: DinosaurAIConfig) -> Vector3:
	if config.avoid_distance <= 0.0:
		return direction
	# 射线压得**低**（0.5 m）：石头最小的才 0.6 m 高，射线打高了会从石头上方
	# 掠过去，恐龙一头撞上去就卡住。树干和残墙更高，0.5 m 一样能测到。
	var origin := body.global_position + Vector3.UP * AVOID_RAY_HEIGHT
	var dist := config.avoid_distance
	var hit := _ray_hit_normal(origin, direction, dist, body, _blockers())
	if hit.is_empty():
		# 正前方是通的：只要躲开两侧有东西的那一边
		return _side_bias(body, direction, origin, dist, config)
	# 正前方被挡：沿着障碍滑行
	var normal: Vector3 = hit["normal"]
	normal.y = 0.0
	if normal.length_squared() < 0.0001:
		normal = Vector3.UP
	normal = normal.normalized()
	var tangent := direction - normal * direction.dot(normal)
	if tangent.length_squared() < 0.01:
		# 正对着障碍：挑一边绕
		return direction.rotated(Vector3.UP, deg_to_rad(90.0))
	return tangent.normalized()


## **悬崖保护**：往前探一步，脚下的地面要是掉下去了，就别走。
##
## 岛是浮空的，边缘是一圈陡崖。外圈巡逻路离崖边只有几米，
## 恐龙偏一点就可能走出去掉下岛 —— 掉下去虽然会被送回起点，
## 但看起来是"瞬移"，很出戏。所以这里先探一下路。
func _cliff_guard(body: Node3D, direction: Vector3) -> Vector3:
	# 看正前、左前、右前三个方向，哪个方向的地面是接得住的
	var center := _ground_ahead(body, direction)
	var left := _ground_ahead(body, direction.rotated(Vector3.UP, deg_to_rad(30.0)))
	var right := _ground_ahead(body, direction.rotated(Vector3.UP, deg_to_rad(-30.0)))
	var center_ok := _ground_ok(body, center)
	if center_ok:
		return direction
	# 前面不行：往左右里能走的那边转
	var left_ok := _ground_ok(body, left)
	var right_ok := _ground_ok(body, right)
	if left_ok and not right_ok:
		return direction.rotated(Vector3.UP, deg_to_rad(45.0))
	if right_ok and not left_ok:
		return direction.rotated(Vector3.UP, deg_to_rad(-45.0))
	if left_ok and right_ok:
		return direction.rotated(Vector3.UP, deg_to_rad(35.0))
	# 三面都是崖：掉头
	return direction.rotated(Vector3.UP, deg_to_rad(150.0))


## 往前探一步，返回那个点的地面高度（打不到返回 -INF）。
func _ground_ahead(body: Node3D, direction: Vector3) -> float:
	var ahead := body.global_position + direction * CLIFF_PROBE_AHEAD
	var query := PhysicsRayQueryParameters3D.create(
		ahead + Vector3.UP * 3.0, ahead + Vector3.DOWN * 10.0)
	query.collision_mask = DinosaurAIConfig.LAYER_WORLD
	query.exclude = [body.get_rid()]
	var hit := body.get_world_3d().direct_space_state.intersect_ray(query)
	if hit.is_empty():
		return -INF
	return (hit["position"] as Vector3).y


## 这个地面高度能不能站：打不到（悬崖外）或者比脚下低太多都不行。
func _ground_ok(body: Node3D, ground: float) -> bool:
	if ground == -INF:
		return false
	return body.global_position.y - ground <= CLIFF_DROP_LIMIT


## 往左右各探一步，挑地面更高的那边转过去。
func _turn_to_ground(body: Node3D, direction: Vector3) -> Vector3:
	var best := direction
	var best_ground := -INF
	for angle in [-90.0, -60.0, -35.0, 35.0, 60.0, 90.0]:
		var probe := direction.rotated(Vector3.UP, deg_to_rad(float(angle)))
		var ahead := body.global_position + probe * CLIFF_PROBE_AHEAD
		var query := PhysicsRayQueryParameters3D.create(
			ahead + Vector3.UP * 3.0, ahead + Vector3.DOWN * 8.0)
		query.collision_mask = DinosaurAIConfig.LAYER_WORLD
		query.exclude = [body.get_rid()]
		var hit := body.get_world_3d().direct_space_state.intersect_ray(query)
		if hit.is_empty():
			continue
		var ground: float = (hit["position"] as Vector3).y
		if ground > best_ground:
			best_ground = ground
			best = probe
	return best


## 两侧有东西就往空的那边偏一点（幅度小，免得偏离路线）。
func _side_bias(body: Node3D, direction: Vector3, origin: Vector3, dist: float,
		config: DinosaurAIConfig) -> Vector3:
	var left_hit := _ray_hit_normal(origin, direction.rotated(Vector3.UP, deg_to_rad(45.0)),
		dist, body, _blockers())
	var right_hit := _ray_hit_normal(origin, direction.rotated(Vector3.UP, deg_to_rad(-45.0)),
		dist, body, _blockers())
	# 幅度要小：偏得太多恐龙就偏离自己的路线，跑到没路的树丛里去
	if left_hit.is_empty() and not right_hit.is_empty():
		return direction.rotated(Vector3.UP, deg_to_rad(-10.0))
	if right_hit.is_empty() and not left_hit.is_empty():
		return direction.rotated(Vector3.UP, deg_to_rad(10.0))
	return direction


## 会挡住恐龙的层：植被 / 建筑 / 杂物。
func _blockers() -> int:
	return (DinosaurAIConfig.LAYER_VEGETATION
		| DinosaurAIConfig.LAYER_STRUCTURE
		| DinosaurAIConfig.LAYER_PROP)


## 群体分离：把离得太近的同伴推开。
func _separate(body: Node3D, direction: Vector3, neighbours: Array,
		config: DinosaurAIConfig) -> Vector3:
	if config.separation_radius <= 0.0 or neighbours.is_empty():
		return direction
	var push := Vector3.ZERO
	for other in neighbours:
		if other == body or not (other is Node3D):
			continue
		var delta := body.global_position - (other as Node3D).global_position
		delta.y = 0.0
		var distance := delta.length()
		if distance < 0.01 or distance > config.separation_radius:
			continue
		push += delta.normalized() * (1.0 - distance / config.separation_radius)
	if push == Vector3.ZERO:
		return direction
	return (direction + push * config.separation_strength).normalized()


## 往前打一条射线。打到就返回命中信息（含法线），打不到返回空字典。
func _ray_hit_normal(origin: Vector3, direction: Vector3, distance: float,
		body: Node3D, mask: int) -> Dictionary:
	var query := PhysicsRayQueryParameters3D.create(
		origin, origin + direction * distance)
	query.collision_mask = mask
	query.exclude = [body.get_rid()]
	# 转向不是节点，所以世界从身体那儿拿
	return body.get_world_3d().direct_space_state.intersect_ray(query)

class_name DinosaurPatrol
extends RefCounted
##
## 出生点组的类型用 **preload** 引（class_name 要靠编辑器的全局类缓存，
## 命令行跑游戏时缓存可能是旧的，会直接解析失败）。

const GroupScript := preload("res://components/dinosaurs/dinosaur_spawn_group.gd")
## 巡逻的**动态计算** —— 不烘焙，运行时按"碰撞"和"恐龙偏好"现场算。
##
## ## 为什么不再烘
##
## 以前每只恐龙的巡逻路线是**烘**进场景的固定坐标：换地形、换岛大小、
## 挪一下场景，都得重新烘一遍；而且路线跟场景焊死了 —— 场景一动，
## 恐龙就沿着空气走。
##
## 路线本质上只是"绕着自己那块地转一圈"，所以运行时算就够了：
##
## - **碰撞**：竖直射线打地面 → 路点的高度贴着地表走；
##   坡太陡的地方（山体陡坎）走不了，路点就往回收。
## - **恐龙偏好**：体型决定领地半径（霸王龙占的地比迅猛龙大），
##   胶囊半径决定走廊要多宽。
##
## 这个类**不依赖任何场景**：所有函数都收一个 [World3D]，
## 所以组件拿到哪个世界的物理都能用。

## 地面层（地形 / 山体 / 岛体 / 绿地表层）。
const LAYER_WORLD := 1
## 植被层（香蕉树干）—— 恐龙是实心的，撞到树会被顶住。
const LAYER_VEGETATION := 2


## 某点正下方的地面高度（米）。打不到返回 [constant NAN]。
static func ground_height(world: World3D, x: float, z: float,
		from_y: float = 900.0, to_y: float = -400.0) -> float:
	if world == null:
		return NAN
	var space := world.direct_space_state
	var q := PhysicsRayQueryParameters3D.create(
			Vector3(x, from_y, z), Vector3(x, to_y, z))
	q.collision_mask = LAYER_WORLD
	var hit := space.intersect_ray(q)
	if hit.is_empty():
		return NAN
	return (hit["position"] as Vector3).y


## 某点的坡度（**米/米**）。
##
## 高度差要**除以基线**才是坡度（基线 12 m 时，"上限 1.0"其实只有
## 0.083 m/m，整座岛都会被判成陡坡）。
static func slope(world: World3D, x: float, z: float, baseline: float) -> float:
	var h0 := ground_height(world, x, z)
	if is_nan(h0):
		return 99.0
	var hx := ground_height(world, x + baseline, z)
	var hz := ground_height(world, x, z + baseline)
	var s := 0.0
	if not is_nan(hx):
		s = maxf(s, absf(hx - h0) / baseline)
	if not is_nan(hz):
		s = maxf(s, absf(hz - h0) / baseline)
	return s


## 这个位置附近有没有树干挡着（米）。
##
## 以前树是**绕着恐龙的巡逻路线**种的（烘焙时留出走廊），所以路线上没树。
## 现在恐龙是运行时放进去的，树已经种好了 —— 得自己躲开。
##
## 从位置往外打几条水平射线（树干是竖直的圆柱），命中就算挡着。
## 返回**最近树干的距离**（米）；够远就没事。
static func tree_distance(world: World3D, x: float, y: float, z: float,
		heights: Array = [1.2, 2.6]) -> float:
	if world == null:
		return 999.0
	var space := world.direct_space_state
	var best := 999.0
	for h in heights:
		for i in 4:
			var a := TAU * float(i) / 4.0
			var dir := Vector3(cos(a), 0.0, sin(a))
			var q := PhysicsRayQueryParameters3D.create(
					Vector3(x, y + float(h), z), Vector3(x, y + float(h), z) + dir * 8.0)
			q.collision_mask = LAYER_VEGETATION
			var hit := space.intersect_ray(q)
			if not hit.is_empty():
				best = minf(best, (hit["position"] as Vector3).distance_to(
						Vector3(x, y + float(h), z)))
	return best


## 这块地能不能站下一只恐龙：踩得到、平得下来、旁边没树。
static func is_flat(world: World3D, x: float, z: float,
		baseline: float, max_slope: float) -> bool:
	var h := ground_height(world, x, z)
	if is_nan(h):
		return false
	return slope(world, x, z, baseline) <= max_slope


## 体型 → 领地半径（米）：**恐龙偏好**的核心映射。
##
## 大个子占地多（11 m 的霸王龙拿满额），小个子挤在边上（2.2 m 的迅猛龙
## 只拿约 1/4）。8.5 m 是"中大型恐龙"的体型，用来归一化。
static func territory_radius(body_size: float, radius_min: float, radius_max: float) -> float:
	return lerpf(radius_min, radius_max, clampf(body_size / 8.5, 0.0, 1.0))


## 绕着一块地转一圈的巡逻路线（世界坐标路点，首尾相接）。
##
## `home` 是领地中心，`radius` 是领地半径（见 [method territory_radius]）。
## 路点的高度按**射线打地面**取，所以路线贴着地表起伏走；
## 落到山体陡坎上（走不了）就把路点往回收。
static func build_route(world: World3D, home: Vector3, radius: float, points: int,
		sink: float = 0.5, wobble: float = 0.24, wobble_freq: float = 0.002,
		max_slope: float = 0.35, slope_baseline: float = 12.0,
		tree_clearance: float = 0.0, max_y: float = INF) -> PackedVector3Array:
	var pts := PackedVector3Array()
	if points < 3:
		return pts
	var noise := FastNoiseLite.new()
	noise.noise_type = FastNoiseLite.TYPE_SIMPLEX_SMOOTH
	noise.seed = int(absf(home.x * 7.3 + home.z * 3.1)) + 1
	noise.frequency = wobble_freq
	for i in points:
		var a := TAU * float(i) / float(points)
		var rr := radius * (1.0 + wobble * noise.get_noise_2d(cos(a) * 2.0, sin(a) * 2.0))
		var p := Vector2(home.x, home.z) + Vector2(cos(a), sin(a)) * rr
		p = _walkable_point(world, p, Vector2(home.x, home.z), max_slope, slope_baseline,
				tree_clearance, max_y)
		var y := ground_height(world, p.x, p.y)
		if is_nan(y):
			y = home.y
		pts.append(Vector3(p.x, y - sink, p.y))
	return pts


## 把路点挪到"走得了的地面"上：太陡（山体陡坎）就往领地中心收。
static func _walkable_point(world: World3D, p: Vector2, home: Vector2,
		max_slope: float, slope_baseline: float, tree_clearance: float = 0.0,
		max_y: float = INF) -> Vector2:
	for _i in 24:
		var y := ground_height(world, p.x, p.y)
		if not is_nan(y) and y <= max_y and slope(world, p.x, p.y, slope_baseline) <= max_slope:
			# 树挡着就往回收（收不动了就在原地转 —— 总比撞树强）
			if tree_clearance > 0.0 and tree_distance(world, p.x, y, p.y) < tree_clearance:
				p = p.lerp(home, 0.12)
				continue
			return p
		p = p.lerp(home, 0.12)
	return home


## 在一处聚居地里找一个站得住、又不跟别的恐龙挨太近的位置。
##
## `taken` 是已经占住的位置（世界坐标 XZ）。找不到就返回 [constant NAN]。
static func find_spot(world: World3D, group: Resource, taken: Array[Vector2],
		min_spacing: float, max_slope: float, slope_baseline: float,
		tree_clearance: float = 0.0, max_y: float = INF,
		max_radius: float = INF, tries: int = 60) -> Vector3:
	var spacing: float = float(group.get("min_spacing")) if group != null and float(group.get("min_spacing")) > 0.0 else min_spacing
	for _i in tries:
		var a := randf() * TAU
		# 半径按 sqrt 分布 —— 面积均匀，不会全挤在圆心
		var r: float = float(group.get("radius")) * sqrt(randf())
		var c: Vector3 = group.get("center")
		var p := Vector2(c.x, c.z) + Vector2(cos(a), sin(a)) * r
		# 别放到岛缘外 —— 浮空岛的边缘是悬崖，掉下去就没了
		if p.length() > max_radius:
			continue
		var y := ground_height(world, p.x, p.y)
		if is_nan(y):
			continue
		if not is_flat(world, p.x, p.y, slope_baseline, max_slope):
			continue
		if tree_clearance > 0.0 and tree_distance(world, p.x, y, p.y) < tree_clearance:
			continue
		if y > max_y:
			continue       # 太高的地方（山腰）不站 —— 恐龙留在岛面上
		var too_close := false
		for q in taken:
			if p.distance_squared_to(q) < spacing * spacing:
				too_close = true
				break
		if too_close:
			continue
		return Vector3(p.x, y, p.y)
	return Vector3(NAN, NAN, NAN)


## 岛缘轮廓：每个角度往外打射线，找最后一个还有地面的半径。
##
## 用来给恐龙围一圈**隐形围栏**（边界层）—— 浮空岛的边缘就是悬崖，
## 恐龙在崖边走很容易掉下去。
static func edge_profile(world: World3D, samples: int = 144,
		max_radius: float = 1400.0, step: float = 4.0) -> PackedFloat32Array:
	var out := PackedFloat32Array()
	out.resize(samples)
	for i in samples:
		var a := TAU * i / samples
		var last := 0.0
		var r := 40.0
		while r < max_radius:
			if not is_nan(ground_height(world, cos(a) * r, sin(a) * r)):
				last = r
			r += step
		out[i] = last
	# 三点滑动平均，抹掉单点抖动
	var smooth := out.duplicate()
	for i in samples:
		var s := 0.0
		for k in [-1, 0, 1]:
			s += out[(i + k + samples) % samples]
		smooth[i] = s / 3.0
	return smooth

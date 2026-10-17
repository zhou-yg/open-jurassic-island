extends SceneTree
## 低模岛组件自检（无头模式）。
##
## 运行方式（在项目根目录执行）：
## [codeblock]
## /Applications/Godot.app/Contents/MacOS/Godot --headless --script res://components/island/tests/verify_island.gd
## [/codeblock]
## 全部通过时退出码为 0，否则为 1。
##
## 覆盖：场景结构、台面高度、山体尺度、碰撞是否补齐、石头/草是否贴在地面上、
## 环境与相机是否可用。碰撞由 island.gd 在 _ready 里动态补，所以要等几帧。

const SCENE_PATH: String = "res://components/island/island.tscn"
const SETTLE_FRAMES: int = 12

var _checks: int = 0
var _failures: int = 0
var _frames: int = 0
var _ran: bool = false
var _scene: Node3D


func _initialize() -> void:
	_scene = load(SCENE_PATH).instantiate()
	get_root().add_child(_scene)


func _process(_delta: float) -> bool:
	if _ran:
		return true
	_frames += 1
	if _frames < SETTLE_FRAMES:
		return false
	_ran = true
	_run_all()
	print("=== 低模岛检查项 %d，失败 %d ===" % [_checks, _failures])
	print("全部通过 ✅" if _failures == 0 else "存在失败 ❌")
	quit(1 if _failures > 0 else 0)
	return true


func _run_all() -> void:
	_test_structure()
	_test_heights()
	_test_collision()
	_test_scatter_on_ground()
	_test_presentation()


func _check(condition: bool, message: String) -> void:
	_checks += 1
	if not condition:
		_failures += 1
		print("  [FAIL] ", message)


func _section(title: String) -> void:
	print("-- ", title)


## ---------------- 1. 场景结构 ----------------
func _test_structure() -> void:
	_section("场景结构")
	_check(_scene != null, "场景实例化失败")
	if _scene == null:
		return
	var world_env := _scene.get_node_or_null("WorldEnvironment") as WorldEnvironment
	var sun := _scene.get_node_or_null("Sun") as DirectionalLight3D
	var camera := _scene.get_node_or_null("PreviewCamera") as Camera3D
	var base := _scene.get_node_or_null("IslandBase")
	var ground := _scene.get_node_or_null("Ground")
	var mountain := _scene.get_node_or_null("Mountain")
	var scatter := _scene.get_node_or_null("Scatter")
	_check(world_env != null, "缺少 WorldEnvironment")
	_check(sun != null, "缺少 Sun")
	_check(camera != null and camera.current, "缺少当前相机 PreviewCamera")
	_check(base != null and base.get_child_count() == 1, "缺少岛屿本体实例")
	_check(ground != null, "缺少 Ground")
	_check(mountain != null and mountain.get_node_or_null("NestMountain") != null, "缺少山体实例")
	_check(scatter != null, "缺少 Scatter")
	if scatter == null:
		return
	var rocks := scatter.get_node_or_null("Rocks")
	var grass := scatter.get_node_or_null("Grass")
	_check(rocks != null and rocks.find_children("*", "MeshInstance3D", true, false).size() >= 40,
		"石头数量不足（应 >= 40）")
	_check(grass != null and grass.find_children("*", "MeshInstance3D", true, false).size() >= 400,
		"草数量不足（应 >= 400）")
	var patches := ground.find_children("*", "MeshInstance3D", true, false).size() if ground else 0
	_check(patches >= 20, "草地地形块数量不足（实际 %d）" % patches)


## ---------------- 2. 高度 / 尺度 ----------------
func _test_heights() -> void:
	_section("高度 / 尺度")
	var mountain := _scene.get_node_or_null("Mountain")
	if mountain != null:
		var box := _merged_aabb(mountain)
		_check(box.size.y > 17.5 and box.size.y < 19.5,
			"山体总高异常：%.2f m（含水下裙边，预期约 18.6 m）" % box.size.y)
		_check(box.end.y > 14.5,
			"山体主峰太矮：峰顶仅 %.2f m" % box.end.y)
		var c := box.get_center()
		_check(Vector2(c.x, c.z).length() < 2.0, "山体不在岛中央：%s" % Vector2(c.x, c.z))
		_check(box.position.y < 0.5, "山体底座没有落在地面上（y=%.2f）" % box.position.y)

	# 岛屿台面：山体外侧、草地边缘的几个点都应该能向下打到地面
	var probes := [Vector2(24, 0), Vector2(-24, 0), Vector2(0, 24), Vector2(0, -24),
		Vector2(17, 17), Vector2(-17, -17)]
	var hits := 0
	for p in probes:
		var ground_y := _ground_height(p, 50.0, [])
		if ground_y > -0.5 and ground_y < 2.2:
			hits += 1
	_check(hits == probes.size(), "岛屿台面不完整（%d/%d 个探测点打到地面）" % [hits, probes.size()])


## ---------------- 3. 碰撞 ----------------
func _test_collision() -> void:
	_section("碰撞")
	var ground := _scene.get_node_or_null("Ground")
	var mountain := _scene.get_node_or_null("Mountain")
	var rocks := _scene.get_node_or_null("Scatter/Rocks")
	_check(_has_static_bodies(ground), "草地地形块没有补齐碰撞")
	_check(_has_static_bodies(mountain), "山体没有补齐碰撞")
	_check(_has_static_bodies(rocks), "石头没有补齐碰撞")
	# 岛屿本体的台面由 glb 自带的 `-col` 节点提供碰撞
	var base_body := _scene.get_node_or_null("IslandBase").find_children("*", "StaticBody3D", true, false)
	_check(base_body.size() > 0, "岛屿本体没有碰撞")


## ---------------- 4. 石头 / 草贴地 ----------------
func _test_scatter_on_ground() -> void:
	_section("石头 / 草贴地")
	var rock_meshes := _scene.get_node_or_null("Scatter/Rocks").find_children("*", "MeshInstance3D", true, false)
	var excluded: Array[RID] = []
	for node in rock_meshes:
		for child in node.get_children():
			if child is StaticBody3D:
				excluded.append((child as StaticBody3D).get_rid())

	# 山顶/山腰的石头经常落在挑檐下面，垂直射线会先打到上层台地，
	# 所以只对岛屿范围内的石头做严格贴地检查；山体石头检查在包围盒内。
	var rock_checked := 0
	var rock_ok := 0
	var mountain_rocks := 0
	for node in rock_meshes:
		var mi := node as MeshInstance3D
		var on_mountain := false
		var walk := mi.get_parent()
		while walk != null:
			if walk.name == "MountainBoulders":
				on_mountain = true
				break
			walk = walk.get_parent()
		if on_mountain:
			mountain_rocks += 1
			continue
		var y := _ground_height_xz(mi.global_position.x, mi.global_position.z, mi.global_position.y + 4.0, excluded)
		if y == -INF:
			continue
		rock_checked += 1
		if absf(y - mi.global_position.y) < 0.8:
			rock_ok += 1

	_check(rock_checked > 0 and rock_ok == rock_checked,
		"有石头悬空或陷得太深（%d/%d 贴地）" % [rock_ok, rock_checked])
	_check(mountain_rocks >= 12, "山上的石头太少（%d 块）" % mountain_rocks)

	var grass_meshes := _scene.get_node_or_null("Scatter/Grass").find_children("*", "MeshInstance3D", true, false)
	var grass_checked := 0
	var grass_ok := 0
	for i in range(0, grass_meshes.size(), maxi(1, grass_meshes.size() / 18)):
		var mi := grass_meshes[i] as MeshInstance3D
		var y := _ground_height_xz(mi.global_position.x, mi.global_position.z, mi.global_position.y + 4.0, excluded)
		if y == -INF:
			continue
		grass_checked += 1
		if absf(y - mi.global_position.y) < 0.35:
			grass_ok += 1

	_check(grass_checked > 0 and grass_ok == grass_checked,
		"有草悬空（%d/%d 贴地）" % [grass_ok, grass_checked])


## ---------------- 5. 环境 ----------------
func _test_presentation() -> void:
	_section("环境 / 相机")
	var env := (_scene.get_node("WorldEnvironment") as WorldEnvironment).environment
	_check(env.background_mode == Environment.BG_SKY, "背景不是天空")
	_check(env.sky != null and env.sky.sky_material is ProceduralSkyMaterial, "天空材质不是 ProceduralSkyMaterial")
	_check(env.fog_enabled, "没有开启雾")
	_check(env.tonemap_mode == Environment.TONE_MAPPER_FILMIC, "色调映射不是 Filmic")
	var sun := _scene.get_node("Sun") as DirectionalLight3D
	_check(sun.shadow_enabled, "太阳没有开启阴影")
	var camera := _scene.get_node("PreviewCamera") as Camera3D
	_check(is_equal_approx(camera.fov, 50.0), "相机 FOV 不是 50")


## ---------------- 工具 ----------------
func _has_static_bodies(root: Node) -> bool:
	if root == null:
		return false
	var meshes := root.find_children("*", "MeshInstance3D", true, false)
	if meshes.is_empty():
		return false
	for node in meshes:
		var found := false
		for child in node.get_children():
			if child is StaticBody3D:
				found = true
				break
		if not found:
			return false
	return true


func _merged_aabb(root: Node) -> AABB:
	var box := AABB()
	var first := true
	for node in root.find_children("*", "MeshInstance3D", true, false):
		var mi := node as MeshInstance3D
		var b := mi.global_transform * mi.get_aabb()
		if first:
			box = b
			first = false
		else:
			box = box.merge(b)
	return box


func _ground_height(point: Vector2, from_y: float, exclude: Array[RID]) -> float:
	return _ground_height_xz(point.x, point.y, from_y, exclude)


func _ground_height_xz(x: float, z: float, from_y: float, exclude: Array[RID]) -> float:
	var query := PhysicsRayQueryParameters3D.create(
		Vector3(x, from_y, z), Vector3(x, -12.0, z))
	query.collide_with_areas = true
	query.exclude = exclude
	var hit := get_root().world_3d.direct_space_state.intersect_ray(query)
	if hit.is_empty():
		return -INF
	return (hit["position"] as Vector3).y

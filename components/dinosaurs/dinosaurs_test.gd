extends Node3D
##
## **恐龙群测试 / 体验场景**（`dinosaurs_test.tscn`）。
##
## 一块 400 m × 400 m 的平地 + **管理员相机** + 一组运行时生成的恐龙。
## 没有树、没有山、没有围墙 —— 只有恐龙的 AI 在跑，方便看行为树每一条分支
## 对不对（巡逻 → 调查 → 追击 → 攻击 / 逃跑 / 脱困）。
##
## 场景里的 `Dinosaurs` 就是 `dinosaurs.tscn` 的实例，只是参数按**小场地**调过：
## 领地半径 20~36 m、间距 14 m、18 只。生产环境（1414 m 大世界）用的是
## 57~106 m 领地和 100 只 —— **不要拿这里的数值去改组件的默认值**。
##
## ## 操作
##
## | 键 | 作用 |
## | --- | --- |
## | `↑` `↓` `←` `→` | 相机前后左右（`Space` 上升 / `Ctrl` 下降） |
## | 鼠标右键拖动 | 转视角（`F` 锁定鼠标 = 第一人称手感） |
## | `1`~`6` | 在相机面前 10 m 放一只（顺序 = 池子顺序） |
## | `0` | 放一只随机种类 |
## | `R` | 清空后按 `initial_count` 重新生成 |
## | `C` | 清空 |
## | `L` | 巡逻路线显示开 / 关 |
## | `O` | 障碍物模式（**灰柱子**：实心，恐龙会绕开） |
## | `B` | 可攻击建筑模式（**红柱子**：恐龙会冲过去啃） |
## | `X` | 清空所有柱子 |
## | `F` | 锁定 / 释放鼠标 |
##
## 左上角 HUD 每 0.2 秒刷新：总数、每种数量、最近三只的**状态**和距离、帧率、
## 柱子统计、当前模式。
## 地上的彩色折线 = 每只恐龙**当前算出来的巡逻路线**（颜色按种类区分），
## 用来确认路线贴着地面、没有跑出场外。
##
## ## 放柱子
##
## 打开"障碍物"或"可攻击建筑"模式以后，**左键点击**场地就放一根柱子：
## 点的位置是光标（锁定鼠标时是屏幕正中的准星）。
## 再点一次柱子就把它删掉。

const PillarScript := preload("res://components/dinosaurs/dinosaurs_test_pillar.gd")

const HUD_INTERVAL := 0.2
const ROUTE_INTERVAL := 0.5
const SPAWN_AHEAD := 10.0
const NEAREST_COUNT := 3
const ROUTE_LIFT := 0.35
## 地面层（射线打地面用）。
const LAYER_WORLD := 1
## 建筑层（柱子）。
const LAYER_STRUCTURE := 4
## 恐龙 AI 盯建筑时找的组。
const STRUCTURE_TARGET_GROUP := "dinosaur_structure"

## 放柱子的模式。
enum BuildMode {
	NONE,      ## 不放柱子
	OBSTACLE,  ## 灰色障碍物：实心，恐龙绕开
	ATTACK,    ## 红色可攻击建筑：恐龙冲过去啃
}

## 池子里六种恐龙的路线颜色（顺序与 `dinosaurs.tscn` 的 pool 一致）。
const SPECIES_COLORS := [
	Color(0.95, 0.36, 0.26),   # 霸王龙
	Color(0.55, 0.86, 0.36),   # 三角龙
	Color(0.95, 0.82, 0.32),   # 剑龙
	Color(0.36, 0.76, 0.95),   # 副栉龙
	Color(0.82, 0.48, 0.95),   # 迅猛龙
	Color(0.55, 0.80, 0.66),   # 蜥脚龙
]

@onready var herd = $Dinosaurs
@onready var camera: Camera3D = $Camera
@onready var camera_script = $Camera
@onready var pillars_root: Node3D = $Pillars
@onready var info: Label = $TestHUD/Info
@onready var obstacle_button: Button = $TestHUD/Bar/Obstacle
@onready var attack_button: Button = $TestHUD/Bar/Attack
@onready var clear_pillars_button: Button = $TestHUD/Bar/ClearPillars
@onready var mouse_button: Button = $TestHUD/Bar/Mouse
@onready var crosshair: Label = $TestHUD/Crosshair

## 是否画巡逻路线。
var show_routes := true
## 当前放柱子的模式。
var build_mode: int = BuildMode.NONE

var _hud_timer := 0.0
var _route_timer := 0.0
## 正在重置（R 是异步的：清空之后要等一帧再生成）。
var _resetting := false
## 每种恐龙各一个线段网格（`PRIMITIVE_LINES`，纯色材质）。
var _route_meshes: Array[MeshInstance3D] = []
## 最近一次被点掉的柱子（HUD 上报一句）。
var _last_event := ""


func _ready() -> void:
	_build_route_layer()
	_connect_ui()
	# 开局摆两根示例柱子：灰色障碍物 + 红色可攻击建筑，
	# 这样一进来就能看到"绕开"和"啃"两种行为。
	_add_pillar(Vector3(-14, 0, -58), false)
	_add_pillar(Vector3(26, 0, -46), true)


func _process(delta: float) -> void:
	# 相机别钻到地面底下（场地下面什么都没有）
	if camera.global_position.y < 1.0:
		camera.global_position.y = 1.0
	_hud_timer -= delta
	_route_timer -= delta
	if _hud_timer <= 0.0:
		_hud_timer = HUD_INTERVAL
		_refresh_hud()
	if _route_timer <= 0.0:
		_route_timer = ROUTE_INTERVAL
		_rebuild_routes()
	_sync_dinosaurs()


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseButton:
		var mouse := event as InputEventMouseButton
		if mouse.button_index == MOUSE_BUTTON_LEFT and mouse.pressed:
			_click_at(_pointer_position())
		return
	if not (event is InputEventKey) or not event.pressed or event.echo:
		return
	match event.keycode:
		KEY_R:
			_reset()
		KEY_C:
			_clear_dinosaurs()
		KEY_0:
			_spawn(-1)
		KEY_1, KEY_2, KEY_3, KEY_4, KEY_5, KEY_6:
			_spawn(event.keycode - KEY_1)
		KEY_L:
			show_routes = not show_routes
			_rebuild_routes()
		KEY_O:
			_toggle_mode(BuildMode.OBSTACLE)
		KEY_B:
			_toggle_mode(BuildMode.ATTACK)
		KEY_X:
			_clear_pillars()


# ==============================================================================
# 界面
# ==============================================================================

func _connect_ui() -> void:
	obstacle_button.toggled.connect(func(on: bool) -> void:
		_set_mode(BuildMode.OBSTACLE if on else BuildMode.NONE))
	attack_button.toggled.connect(func(on: bool) -> void:
		_set_mode(BuildMode.ATTACK if on else BuildMode.NONE))
	clear_pillars_button.pressed.connect(_clear_pillars)
	mouse_button.pressed.connect(_toggle_capture)
	camera_script.capture_changed.connect(_on_capture_changed)
	_on_capture_changed(camera_script.is_captured())


func _toggle_capture() -> void:
	camera_script.toggle_capture()


func _on_capture_changed(captured: bool) -> void:
	mouse_button.text = "释放鼠标 (F)" if captured else "锁定鼠标 (F)"
	mouse_button.button_pressed = captured
	crosshair.visible = captured


## 切到某个放柱子的模式（两个按钮互斥：谁最后开的谁算数）。
func _set_mode(mode: int) -> void:
	build_mode = mode
	obstacle_button.set_pressed_no_signal(mode == BuildMode.OBSTACLE)
	attack_button.set_pressed_no_signal(mode == BuildMode.ATTACK)
	_last_event = ""


func _toggle_mode(mode: int) -> void:
	_set_mode(BuildMode.NONE if build_mode == mode else mode)


# ==============================================================================
# 放 / 删柱子
# ==============================================================================

## 左键点击：点到柱子就删，点到地面就按当前模式放一根。
func _click_at(screen_pos: Vector2) -> void:
	var from := camera.project_ray_origin(screen_pos)
	var to := from + camera.project_ray_normal(screen_pos) * 1000.0
	var query := PhysicsRayQueryParameters3D.create(from, to)
	query.collision_mask = LAYER_WORLD | LAYER_STRUCTURE
	var hit := get_world_3d().direct_space_state.intersect_ray(query)
	if hit.is_empty():
		return
	var collider: Node = hit["collider"]
	if collider != null and collider.is_in_group(PillarScript.PILLAR_GROUP):
		var pillar := collider as Node3D
		pillar.queue_free()
		_last_event = "删掉一根柱子"
		return
	if build_mode == BuildMode.NONE:
		return
	var point: Vector3 = hit["position"]
	point.y = 0.0
	_add_pillar(point, build_mode == BuildMode.ATTACK)


## 放一根柱子。`attackable` = true 是红色可攻击建筑。
func _add_pillar(pos: Vector3, attackable: bool) -> void:
	var pillar: StaticBody3D = PillarScript.new()
	pillar.name = "AttackBuilding" if attackable else "Obstacle"
	pillar.pillar_size = Vector3(3.0, 6.0, 3.0) if attackable else Vector3(1.2, 6.0, 1.2)
	pillar.base_color = Color(0.78, 0.16, 0.12) if attackable else Color(0.42, 0.44, 0.48)
	pillar.max_health = 120.0 if attackable else 0.0
	pillars_root.add_child(pillar)
	pillar.global_position = pos
	pillar.collapsed.connect(_on_pillar_collapsed)
	_last_event = "放了一根%s" % ("红色建筑" if attackable else "灰色障碍物")


func _on_pillar_collapsed(pillar: Node3D) -> void:
	_last_event = "恐龙拆掉了一座建筑！"


func _clear_pillars() -> void:
	for pillar in pillars_root.get_children():
		pillar.queue_free()
	_last_event = "清空了柱子"


## 光标位置（锁定鼠标时 = 屏幕正中）。
func _pointer_position() -> Vector2:
	if camera_script.is_captured():
		return get_viewport().get_visible_rect().size * 0.5
	return get_viewport().get_mouse_position()


# ==============================================================================
# 恐龙
# ==============================================================================

## 在相机前面 10 m 放一只。`species_index` = -1 表示按权重随机。
func _spawn(species_index: int) -> void:
	var forward := -camera.global_transform.basis.z
	forward.y = 0.0
	if forward.length_squared() < 0.0001:
		forward = Vector3.FORWARD
	forward = forward.normalized()
	var point := camera.global_position + forward * SPAWN_AHEAD
	point.y = 0.0
	herd.add_dinosaur(species_index, point)


func _clear_dinosaurs() -> void:
	for dino in herd.dinosaurs.duplicate():
		herd.remove_dinosaur(dino)


## 清空后按 `initial_count` 重新生成。
##
## **要等一帧再生成**：`remove_dinosaur()` 用的是 `queue_free()`，旧的恐龙
## 这一帧还挂在树上、还在物理世界里；等它们真正删掉再生成，免得新旧两批
## 在同一个出生点上叠一帧（节点重名已经由组件的递增序号解决了）。
func _reset() -> void:
	if _resetting:
		return
	_resetting = true
	# 开局那批恐龙是组件 `_ready` 里**等 3 帧之后**才放的。这之前就清空再
	# 生成，会跟还在路上的开局批次叠在一起（总数翻倍）。
	while not herd.is_spawned():
		await get_tree().process_frame
	_clear_dinosaurs()
	await get_tree().process_frame
	for _i in int(herd.initial_count):
		if herd.add_dinosaur() == null:
			break
	_resetting = false


## 给每只恐龙打补丁：让它把"建筑"也当成目标（红色柱子就是靠这个被啃的）。
##
## 复制一份配置再改 —— 直接改会改到**场景里共享的那份**资源，
## 编辑器里一保存就写进生产文件了。
func _sync_dinosaurs() -> void:
	for dino in herd.dinosaurs:
		if not is_instance_valid(dino):
			continue
		var ai: Node = dino.get_node_or_null("AI")
		if ai == null or ai.config == null:
			continue
		if String(ai.config.structure_target_group) == STRUCTURE_TARGET_GROUP:
			continue
		var config: Resource = ai.config.duplicate()
		config.set("structure_target_group", STRUCTURE_TARGET_GROUP)
		ai.set("config", config)


# ==============================================================================
# 巡逻路线可视化
# ==============================================================================

## 每种恐龙建一个专门画线的 MeshInstance3D。
##
## 为什么不用顶点色：移动渲染器对 `PRIMITIVE_LINES` 的顶点色不生效
## （线会画成白色），所以干脆**一种颜色一个网格**，材质里直接给 albedo。
func _build_route_layer() -> void:
	for i in herd.pool.size():
		var mesh_instance := MeshInstance3D.new()
		mesh_instance.name = "Route_%d" % i
		mesh_instance.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		var material := StandardMaterial3D.new()
		material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		material.albedo_color = SPECIES_COLORS[i % SPECIES_COLORS.size()]
		mesh_instance.material_override = material
		add_child(mesh_instance)
		_route_meshes.append(mesh_instance)
	_rebuild_routes()


## 把所有恐龙当前的 `route` 按种类拼成线段网格。
##
## 路线是恐龙出生时算好的（静态），但恐龙会随时被手动加进来，
## 所以这个函数每 0.5 秒重拼一次，几十条线不值几个顶点。
func _rebuild_routes() -> void:
	if _route_meshes.is_empty():
		return
	var buckets: Array[PackedVector3Array] = []
	for _i in _route_meshes.size():
		buckets.append(PackedVector3Array())
	if show_routes:
		for dino in herd.dinosaurs:
			if not is_instance_valid(dino):
				continue
			var route: PackedVector3Array = dino.get("route")
			var species_index := _species_index(dino)
			if route.size() < 2 or species_index < 0:
				continue
			var bucket: PackedVector3Array = buckets[species_index]
			var lift := Vector3.UP * ROUTE_LIFT
			for i in route.size():
				bucket.append(route[i] + lift)
				bucket.append(route[(i + 1) % route.size()] + lift)
			buckets[species_index] = bucket
	for i in _route_meshes.size():
		var mesh := ArrayMesh.new()
		if not buckets[i].is_empty():
			var arrays := []
			arrays.resize(Mesh.ARRAY_MAX)
			arrays[Mesh.ARRAY_VERTEX] = buckets[i]
			mesh.add_surface_from_arrays(Mesh.PRIMITIVE_LINES, arrays)
		_route_meshes[i].mesh = mesh


# ==============================================================================
# HUD
# ==============================================================================

func _refresh_hud() -> void:
	if info == null or herd == null or camera == null:
		return
	var lines: PackedStringArray = []
	lines.append("恐龙群测试场 · %d 只（初始 %d）· %d fps" % [
			herd.count(), int(herd.initial_count), Engine.get_frames_per_second()])
	lines.append("")

	var counts := {}
	for dino in herd.dinosaurs:
		if not is_instance_valid(dino):
			continue
		var label := _species_label(dino)
		counts[label] = int(counts.get(label, 0)) + 1
	var parts: PackedStringArray = []
	for i in herd.pool.size():
		var label := String(herd.pool[i].display_name)
		parts.append("[%d] %s %d" % [i + 1, label, int(counts.get(label, 0))])
	lines.append(" · ".join(parts))
	lines.append("")

	var nearest: Array = []
	for dino in herd.dinosaurs:
		if not is_instance_valid(dino):
			continue
		nearest.append({
			"dino": dino,
			"distance": dino.global_position.distance_to(camera.global_position),
		})
	nearest.sort_custom(func(a: Dictionary, b: Dictionary) -> bool:
		return float(a["distance"]) < float(b["distance"]))
	lines.append("最近的 %d 只：" % mini(NEAREST_COUNT, nearest.size()))
	for i in mini(NEAREST_COUNT, nearest.size()):
		var entry: Dictionary = nearest[i]
		var dino: Node3D = entry["dino"]
		var ai: Node = dino.get_node_or_null("AI")
		var state := "—"
		if ai != null:
			state = String(ai.get_state_name())
		lines.append("   %-16s %6.1f m   %s" % [
				String(dino.name), float(entry["distance"]), state])
	lines.append("")

	lines.append("柱子：%s" % _pillar_summary())
	lines.append("模式：%s" % _mode_name())
	if not _last_event.is_empty():
		lines.append("（%s）" % _last_event)
	lines.append("")
	lines.append("1~6 放恐龙 · 0 随机 · R 重置 · C 清空 · L 路线 · O 障碍物 · B 可攻击建筑 · X 清空柱子 · F 锁鼠标")
	lines.append("视角：右键拖动转视角 · ↑↓←→ 前后左右 · Space/Ctrl 升降 · Shift 加速 · 左键放/删柱子")
	info.text = "\n".join(lines)


## 柱子的统计：灰色几根、红色几根、红柱还剩多少血。
func _pillar_summary() -> String:
	var obstacles := 0
	var buildings := 0
	var health := 0.0
	for pillar in pillars_root.get_children():
		if pillar.has_method("is_attackable") and pillar.is_attackable():
			buildings += 1
			health = float(pillar.health)
		else:
			obstacles += 1
	if buildings > 0:
		return "灰色障碍 %d 根 · 红色建筑 %d 座（血量 %d / 120）" % [
				obstacles, buildings, int(health)]
	return "灰色障碍 %d 根 · 红色建筑 %d 座" % [obstacles, buildings]


func _mode_name() -> String:
	match build_mode:
		BuildMode.OBSTACLE:
			return "障碍物（左键放灰柱子，恐龙会绕开）"
		BuildMode.ATTACK:
			return "可攻击建筑（左键放红柱子，恐龙会啃；再点一次删掉）"
		_:
			return "查看（左键点柱子可以删掉）"


## 恐龙节点名是 `种类_序号`（见 [method DinosaurHerd.add_dinosaur]）。
func _species_label(dino: Node3D) -> String:
	return String(dino.name).get_slice("_", 0)


func _species_index(dino: Node3D) -> int:
	var label := _species_label(dino)
	for i in herd.pool.size():
		if String(herd.pool[i].display_name) == label:
			return i
	return -1

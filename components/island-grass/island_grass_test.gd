extends Node3D
##
## **岛屿植被地面测试场**（`island_grass_test.tscn`）。
##
## 场景里就是**组件岛的地形**（`terrain.tscn`：岩台 + 山体）加上
## **植被地面组件**（`island-grass-base.tscn`：和岛面同形的底板 + 铺满的草）。
## 两者都在原点，所以能直接看出"底板和岛面是不是严丝合缝"。
##
## ## 操作
##
## | 键 | 作用 |
## | --- | --- |
## | `↑` `↓` `←` `→` | 相机前后左右（`Space` 上升 / `Ctrl` 下降） |
## | 鼠标右键拖动 | 转视角（`F` 锁定鼠标 = 第一人称手感） |
## | `1` `2` `3` `4` | 地面宽度预设：31 / 62 / 125 / 200 m（长度按固定比例跟着变） |
## | `Z` / `X` | 草密度 −/+（每平方米几团） |
## | `R` | 换个随机种子（重新撒一遍草） |
## | `G` | 两种草染色（红 / 蓝）—— 看清"各自成团、片与片交错" |
## | `C` | 摇曳开 / 关 |
## | `T` | 地形开 / 关（只看底板和草） |
##
## 左上角 HUD 每 0.2 秒刷新：宽度 / 长度 / 固定比例、草密度、草团数、草株数、帧率。

const HUD_INTERVAL := 0.2

## 地面宽度预设（米）。
const WIDTH_PRESETS := [31.207, 62.413, 124.826, 200.0]

@onready var grass_base: Node3D = $GrassBase
@onready var camera: GodViewportCamera = $Camera
@onready var info: Label = $TestHUD/Info

var _hud_timer := 0.0
## 上次"摇曳开 / 关"之前的强度。
var _sway_saved := 0.06
## 两种草的染色开关。
var _tinted := false


func _ready() -> void:
	_sway_saved = grass_base.sway_strength


func _process(delta: float) -> void:
	_hud_timer -= delta
	if _hud_timer <= 0.0:
		_hud_timer = HUD_INTERVAL
		_refresh_hud()


func _unhandled_input(event: InputEvent) -> void:
	if not (event is InputEventKey) or not event.pressed or event.echo:
		return
	match event.keycode:
		KEY_1:
			_set_width(0)
		KEY_2:
			_set_width(1)
		KEY_3:
			_set_width(2)
		KEY_4:
			_set_width(3)
		KEY_Z:
			grass_base.clump_density = maxf(0.1, grass_base.clump_density - 0.2)
			_apply_tint()
		KEY_X:
			grass_base.clump_density = minf(8.0, grass_base.clump_density + 0.2)
			_apply_tint()
		KEY_R:
			grass_base.seed = randi()
			_apply_tint()
		KEY_G:
			_tinted = not _tinted
			_apply_tint()
		KEY_C:
			_toggle_sway()
		KEY_T:
			_toggle_terrain()


## 切到第几个宽度预设。
func _set_width(index: int) -> void:
	grass_base.width = float(WIDTH_PRESETS[index])
	# 改宽度会重建草（材质也是新的），染色要重新刷一遍
	_apply_tint()


## 两种草染成红 / 蓝：一株一簇不混个体，各自成片、片与片交错。
func _apply_tint() -> void:
	var tuft := grass_base.get_node("Grass/GrassTuft") as MultiMeshInstance3D
	var clump := grass_base.get_node("Grass/GrassClump") as MultiMeshInstance3D
	var tuft_tint := Color(1.0, 0.2, 0.2) if _tinted else Color(1, 1, 1, 1)
	var clump_tint := Color(0.2, 0.35, 1.0) if _tinted else Color(1, 1, 1, 1)
	for pair in [[tuft, tuft_tint], [clump, clump_tint]]:
		var mmi: MultiMeshInstance3D = pair[0]
		var mat := mmi.material_override as ShaderMaterial
		if mat != null:
			mat.set_shader_parameter("albedo_tint", pair[1])


func _toggle_sway() -> void:
	if grass_base.sway_strength > 0.0:
		_sway_saved = grass_base.sway_strength
		grass_base.sway_strength = 0.0
	else:
		grass_base.sway_strength = _sway_saved


func _toggle_terrain() -> void:
	var terrain: Node3D = $Terrain
	terrain.visible = not terrain.visible


func _refresh_hud() -> void:
	if info == null or grass_base == null:
		return
	var stats: Dictionary = grass_base.get("_stats")
	var lines: PackedStringArray = []
	lines.append("岛屿植被地面测试场 · %d fps" % Engine.get_frames_per_second())
	lines.append("")
	lines.append("地面：宽 %.2f m × 长 %.2f m（固定比例 %.5f）" % [
		float(grass_base.width), float(grass_base.get_length()),
		float(grass_base.get_length()) / maxf(0.01, float(grass_base.width))])
	lines.append("草：密度 %.1f 团/m² · 每团 %d 株 · 团半径 %.2f m · 类型片 %d×%d" % [
		float(grass_base.clump_density), int(grass_base.blades_per_clump),
		float(grass_base.clump_radius), int(grass_base.patch_ratio),
		int(grass_base.patch_ratio)])
	lines.append("草量：%d 团 / %d 株（草丛 %d · 草簇 %d）" % [
		int(stats.get("clumps", 0)), int(stats.get("tuft", 0)) + int(stats.get("clump", 0)),
		int(stats.get("tuft", 0)), int(stats.get("clump", 0))])
	lines.append("摇曳：强度 %.3f m（%s）" % [
		float(grass_base.sway_strength), "开" if grass_base.sway_strength > 0.0 else "关"])
	lines.append("染色：%s" % ("红 / 蓝" if _tinted else "关"))
	lines.append("")
	lines.append("1~4 宽度预设（31 / 62 / 125 / 200 m）· Z/X 密度 · R 换种子 · G 染色 · C 摇曳 · T 地形")
	lines.append("视角：右键拖动转视角 · ↑↓←→ 前后左右 · Space/Ctrl 升降 · Shift 加速 · F 锁鼠标")
	info.text = "\n".join(lines)

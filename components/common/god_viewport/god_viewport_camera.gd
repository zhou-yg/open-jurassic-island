class_name GodViewportCamera
extends Camera3D
##
## **测试 / 体验用的自由相机**：自由飞行 + 环顾，不受地形限制。
##
## 抽出来给所有测试场共用（原来只有 `components/dinosaurs/` 有，
## 现在 `components/island-grass/` 也用同一套操作）。
##
## ## 操作
##
## | 键 | 作用 |
## | --- | --- |
## | `↑` `↓` | 水平面前进 / 后退（`W` `S` 同义） |
## | `←` `→` | 水平面左右平移（`A` `D` 同义） |
## | `Space` | 上升（`E` 同义） |
## | `Ctrl` | 下降（`Q` 同义） |
## | `Shift` | 加速 |
## | `Alt` | 减速 |
## | 鼠标**右键拖动** | 转视角 |
## | `F` | 锁定 / 释放鼠标 |
##
## ## 鼠标为什么默认不锁定
##
## HUD 上有按钮（放障碍物 / 切模式），鼠标锁定了就点不到。
## 所以默认**不锁**：右键拖动转视角，左键点击在光标处操作。
## 按 `F` 锁上以后就是第一人称那种手感 —— 视角跟着鼠标走，
## 准星在屏幕正中，左键在准星处操作。
##
## 锁定状态变了会发 [signal capture_changed]。
## HUD 上的「锁定鼠标 (F)」按钮用
## `res://components/common/god_viewport/god_viewport_capture_button.gd` 自动联动，
## 不用自己写接线。
##
## ## 怎么找到这个相机
##
## 相机启动时会把自己加进 **`god_viewport_camera`** 组，
## 所以 HUD 上的按钮不用配路径就能找到它。

## 锁定状态变了（true = 鼠标被锁定）。
signal capture_changed(captured: bool)

## 相机所在的组（HUD 按钮靠它找相机）。
const GROUP := "god_viewport_camera"

@export_group("移动")
## 基础速度（米 / 秒）。
@export var move_speed: float = 25.0
## 按住 Shift 的加速倍率。
@export var sprint_multiplier: float = 3.0
## 按住 Alt 的减速倍率。
@export var slow_multiplier: float = 0.25
## 相机最低高度（世界坐标）。默认不限制。
## 测试场一般给一个正值，免得相机钻到地面底下。
@export var min_height: float = -INF

@export_group("视角")
## 鼠标灵敏度（弧度 / 像素）。
@export var mouse_sensitivity: float = 0.0025
## 俯仰上限（度）。
@export var pitch_limit_deg: float = 85.0
## 开局看向哪个点（世界坐标）。给 [constant Vector3.ZERO] 就保持场景里的朝向。
@export var start_look_at: Vector3 = Vector3.ZERO

var _yaw: float = 0.0
var _pitch: float = 0.0
var _dragging: bool = false
var _captured: bool = false


func _ready() -> void:
	add_to_group(GROUP)
	_yaw = rotation.y
	_pitch = rotation.x
	if start_look_at != Vector3.ZERO:
		_look_at_point(start_look_at)
	_apply_rotation()
	# 鼠标**不**自动锁定：HUD 的按钮要能点。
	Input.set_mouse_mode(Input.MOUSE_MODE_VISIBLE)


func _process(delta: float) -> void:
	var direction := Vector3.ZERO
	# 前后左右走**水平面**（跟着视角的偏航转），升降单独用 Space / Ctrl。
	# 俯视着看的时候按方向键是平移，不会一头扎进地里。
	var forward := -global_transform.basis.z
	forward.y = 0.0
	if forward.length_squared() < 0.0001:
		forward = Vector3.FORWARD
	forward = forward.normalized()
	var right := global_transform.basis.x
	right.y = 0.0
	if right.length_squared() < 0.0001:
		right = Vector3.RIGHT
	right = right.normalized()
	if _pressed([KEY_UP, KEY_W]):
		direction += forward
	if _pressed([KEY_DOWN, KEY_S]):
		direction -= forward
	if _pressed([KEY_LEFT, KEY_A]):
		direction -= right
	if _pressed([KEY_RIGHT, KEY_D]):
		direction += right
	if _pressed([KEY_SPACE, KEY_E]):
		direction += Vector3.UP
	if _pressed([KEY_CTRL, KEY_Q]):
		direction -= Vector3.UP
	if direction != Vector3.ZERO:
		var speed := move_speed
		if _pressed([KEY_SHIFT]):
			speed *= sprint_multiplier
		if _pressed([KEY_ALT]):
			speed *= slow_multiplier
		global_position += direction.normalized() * speed * delta
	# 别钻到地面底下
	if global_position.y < min_height:
		global_position.y = min_height


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseMotion:
		# 右键拖动转视角；锁定鼠标时直接跟鼠标走
		if not (_dragging or _captured):
			return
		_yaw -= event.relative.x * mouse_sensitivity
		_pitch = clampf(_pitch - event.relative.y * mouse_sensitivity,
				-deg_to_rad(pitch_limit_deg), deg_to_rad(pitch_limit_deg))
		_apply_rotation()
	elif event is InputEventMouseButton:
		var button := event as InputEventMouseButton
		if button.button_index == MOUSE_BUTTON_RIGHT:
			_dragging = button.pressed
	elif event is InputEventKey:
		var key := event as InputEventKey
		if key.pressed and not key.echo and key.keycode == KEY_F:
			toggle_capture()


## 锁定 / 释放鼠标。
func toggle_capture() -> void:
	_captured = not _captured
	Input.set_mouse_mode(
			Input.MOUSE_MODE_CAPTURED if _captured else Input.MOUSE_MODE_VISIBLE)
	capture_changed.emit(_captured)


## 鼠标是不是锁着的（锁着的时候操作点在屏幕正中）。
func is_captured() -> bool:
	return _captured


## 转视角：拖动右键 / 锁定鼠标时用。
func _apply_rotation() -> void:
	rotation = Vector3(_pitch, _yaw, 0.0)


## 开局看向某个点。
func _look_at_point(point: Vector3) -> void:
	var to_point := point - global_position
	if to_point.length_squared() < 0.0001:
		return
	_yaw = atan2(-to_point.x, -to_point.z)
	_pitch = clampf(atan2(to_point.y, Vector2(to_point.x, to_point.z).length()),
			-deg_to_rad(pitch_limit_deg), deg_to_rad(pitch_limit_deg))


## 某个键按着没（[constant KEY_W] 这种物理键位，跟键盘布局无关）。
func _pressed(keys: Array) -> bool:
	for key in keys:
		if Input.is_physical_key_pressed(int(key)):
			return true
	return false

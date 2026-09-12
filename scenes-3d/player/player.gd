extends CharacterBody3D

# 基本属性
@export var normal_speed: float = 3.0
@export var sprint_speed: float = 6.0
@export var jump_velocity: float = 8.0     # 跳跃初速度加倍（原 4.0）
@export var gravity: float = 4.0           # 重力加倍（原 2.0），让上升下降更干脆
@export var mousensity: float = 0.005

# 视角上下限制（单位：度）
@export var min_pitch_deg: float = -70.0
@export var max_pitch_deg: float = 70.0

# 内部变量
var current_speed: float = 0.0
var mouse_captured: bool = true

@onready var camera: Camera3D = $Head/Camera3D

func _ready() -> void:
	# 捕获鼠标
	Input.set_mouse_mode(Input.MOUSE_MODE_CAPTURED)
	current_speed = normal_speed

func _unhandled_input(event: InputEvent) -> void:
	# 鼠标视角控制
	if event is InputEventMouseMotion and mouse_captured:
		rotate_y(-event.relative.x * mousensity)
		camera.rotate_x(-event.relative.y * mousensity)
		# 限制俯仰角度为 -70° ~ +70°
		camera.rotation.x = clamp(
			camera.rotation.x,
			deg_to_rad(min_pitch_deg),
			deg_to_rad(max_pitch_deg)
		)

	# 按ESC释放/捕获鼠标
	if event.is_action_pressed("ui_cancel"):
		if mouse_captured:
			Input.set_mouse_mode(Input.MOUSE_MODE_VISIBLE)
			mouse_captured = false
		else:
			Input.set_mouse_mode(Input.MOUSE_MODE_CAPTURED)
			mouse_captured = true

func _physics_process(delta: float) -> void:
	# 重力
	if not is_on_floor():
		velocity.y -= gravity * delta

	# 跳跃（使用 jump 动作）
	if Input.is_action_just_pressed("jump") and is_on_floor():
		velocity.y = jump_velocity

	# 冲刺
	if Input.is_action_pressed("sprint"):
		current_speed = sprint_speed
	else:
		current_speed = normal_speed

	# 移动输入
	var input_dir := Input.get_vector("left", "right", "forward", "back")
	var direction := (transform.basis * Vector3(input_dir.x, 0, input_dir.y)).normalized()

	if direction:
		velocity.x = direction.x * current_speed
		velocity.z = direction.z * current_speed
	else:
		velocity.x = move_toward(velocity.x, 0, current_speed)
		velocity.z = move_toward(velocity.z, 0, current_speed)

	move_and_slide()

extends StaticBody3D
##
## 测试场的**柱子**：两种角色，同一个脚本。
##
## - **障碍物**（灰色，`max_health = 0`）：实心的，恐龙会撞上，
##   也会**提前绕开** —— 用来检查碰撞 / 避障逻辑。
## - **可攻击建筑**（红色，`max_health > 0`）：恐龙会把它当成目标，
##   冲过去啃，血量掉光就塌 —— 用来检查攻击逻辑。
##
## ## 碰撞层：建筑层（structure）
##
## 恐龙的碰撞掩码里有建筑层（**撞得到**），转向的避障射线也查建筑层
## （**会绕开**）。所以柱子放建筑层正合适：
## 灰色柱子 = 绕着走，红色柱子 = 冲上去啃。
##
## ## 视线
##
## 建筑层同时也是"挡视线"的层 —— 恐龙隔着柱子看不见后面的东西，
## 但**能看见柱子自己**（感知的视线射线会排除目标自己的刚体，
## 见 [code]DinosaurPerception._has_line_of_sight[/code]）。
##
## 红色柱子还在 [constant TARGET_GROUP] 组里，AI 把它当目标。

## 恐龙 AI 盯建筑时找的组（跟 [code]DinosaurAIConfig.structure_target_group[/code] 对上）。
const TARGET_GROUP := "dinosaur_structure"
## 场景里识别"这是根柱子"用的组。
const PILLAR_GROUP := "dinos_test_pillar"
## 建筑层（structure）。
const LAYER_STRUCTURE := 4

## 塌了的时候发出去（自己会 [method Node.queue_free]）。
signal collapsed(pillar: Node3D)

## 柱子的尺寸（米）。原点在**底面中心**。
@export var pillar_size: Vector3 = Vector3(1.2, 6.0, 1.2)
## 血量上限。0 = 打不坏（普通障碍物）。
@export var max_health: float = 0.0
## 完好时的颜色。
@export var base_color: Color = Color(0.55, 0.57, 0.6)

## 当前血量。
var health: float = 0.0
var _mesh: MeshInstance3D
var _material: StandardMaterial3D


func _ready() -> void:
	health = max_health
	collision_layer = LAYER_STRUCTURE
	collision_mask = 0
	add_to_group(PILLAR_GROUP)
	if max_health > 0.0:
		# 只有"可攻击建筑"才是目标；普通障碍物不进这个组
		add_to_group(TARGET_GROUP)
	_build_body()


## 能不能被啃（普通障碍物不能）。
func is_attackable() -> bool:
	return max_health > 0.0


## 挨了一下（恐龙咬的）。普通障碍物直接无视。
func take_damage(amount: float, attacker: Node3D = null) -> void:
	if not is_attackable() or amount <= 0.0:
		return
	health = maxf(0.0, health - amount)
	_update_color()
	if health <= 0.0:
		collapsed.emit(self)
		queue_free()


## 当前血量比例（0~1），HUD 用。
func health_ratio() -> float:
	if not is_attackable():
		return 1.0
	return clampf(health / maxf(1.0, max_health), 0.0, 1.0)


## 自己长出网格 + 碰撞体（这样脚本里就能定尺寸，不用在场景里摆节点）。
func _build_body() -> void:
	var mesh := BoxMesh.new()
	mesh.size = pillar_size
	_mesh = MeshInstance3D.new()
	_mesh.name = "Mesh"
	_mesh.mesh = mesh
	_mesh.position = Vector3(0, pillar_size.y * 0.5, 0)
	_material = StandardMaterial3D.new()
	_material.albedo_color = base_color
	_material.roughness = 0.85
	_mesh.material_override = _material
	add_child(_mesh)

	var shape := BoxShape3D.new()
	shape.size = pillar_size
	var collision := CollisionShape3D.new()
	collision.name = "Collision"
	collision.shape = shape
	collision.position = Vector3(0, pillar_size.y * 0.5, 0)
	add_child(collision)


## 血量越低颜色越暗（快塌了看得出来）。
func _update_color() -> void:
	if _material == null:
		return
	var ratio := health_ratio()
	_material.albedo_color = Color(
			base_color.r * (0.35 + 0.65 * ratio),
			base_color.g * (0.35 + 0.65 * ratio),
			base_color.b * (0.35 + 0.65 * ratio))

@tool
extends Node3D
## 侏罗纪园区入口大门（门楣写 "dinosaur"）—— 可复用的场景组件。
##
## 模型：`assets/models/jurassic-gate/low_poly_jurassic_gate.glb`
##   - 尺寸 **10.41 × 1.26 × 5.64 m**（含两侧破墙），门洞净宽 **3.20 m**、净高 **2.95 m**
##   - 门楣上的匾额已撤：**"dinosaur" 沿拱券排成 98° 的弧形铭文**（节点 `SignText`）
##   - 原点在**门洞地面中线**，所以 position 就是"门槛落地点"
##   - 正面朝 **+Z**（门扇朝 +Z 向外开）
##   - 静止姿态是**合**（两扇铁门关闭），GLB 内置两条动画：
##       `Gate_Open`  0.00s 合 → 0.40s 开(88°) → 保持到 1.20s
##       `Gate_Close` 0.00s 开 → 0.40s 合(0°)  → 保持到 1.20s
##
## 用法：
## [codeblock]
## var gate := $ParkGate
## gate.open()       # 播 Gate_Open
## gate.close()      # 播 Gate_Close
## gate.toggle()
## if gate.is_open: ...
## [/codeblock]
##
## 门轴：两扇门的网格是**镜像**的，动画里已经处理成"都朝门外(+Z)摆出去"，
## 所以这里只负责选片段，不要再自己算角度。

signal opened
signal closed

## 门当前是否处于打开状态。改这个值（编辑器里也可以）会立刻切姿态。
@export var is_open: bool = false:
	set(value):
		if is_open == value:
			return
		is_open = value
		_apply_state()

## 是否给玩家/物理解算碰撞。门洞内部的碰撞体挂在门扇下面，会跟着门轴一起转，
## 所以关着门能挡人，开了门就能走过去。
@export var build_collision: bool = true

## 关掉后只切姿态、不播动画（远景装饰门用）。
@export var animate: bool = true

## 开门/关门的播放速度倍率（1.0 = 原速，0.4 s 开完）。
@export_range(0.25, 4.0, 0.05) var speed: float = 1.0

## 碰撞层：地面。
const LAYER_WORLD := 1
## 碰撞层：建筑（围墙 / 大门）。
const LAYER_STRUCTURE := 4

const ANIM_OPEN := "Gate_Open"
const ANIM_CLOSE := "Gate_Close"

var _anim: AnimationPlayer
var _built_collision := false


func _ready() -> void:
	_anim = find_child("AnimationPlayer", true, false) as AnimationPlayer
	if _anim != null:
		_anim.speed_scale = speed
	if not Engine.is_editor_hint() and build_collision:
		_build_collision()
	# 静止姿态统一由 is_open 决定，不依赖 GLB 的 autoplay / rest pose。
	_apply_state(true)


## 打开大门（播 Gate_Open）。
func open() -> void:
	is_open = true


## 关上大门（播 Gate_Close）。
func close() -> void:
	is_open = false


func toggle() -> void:
	is_open = not is_open


func _apply_state(instant: bool = false) -> void:
	if _anim == null:
		return
	var clip := ANIM_OPEN if is_open else ANIM_CLOSE
	var anim := _anim.get_animation(clip)
	if anim == null:
		push_warning("ParkGate: 动画片段缺失 '%s'" % clip)
		return

	if not animate or instant:
		# 直接摆到片段末帧（合 / 开），不播放。
		_anim.play(clip)
		_anim.seek(maxf(0.0, anim.length - 0.001), true)
		# 用 pause() 而不是 stop()：stop() 会把姿态复位到片段第 0 帧，
		# 而 Gate_Close 的第 0 帧恰好是"开"，门就会自己弹开。
		_anim.pause()
	else:
		_anim.play(clip)

	if not instant:
		if is_open:
			opened.emit()
		else:
			closed.emit()


## 给每个网格挂 StaticBody3D + 三角面碰撞。
## 门扇的碰撞体是**门扇节点的子节点**，所以会跟着门轴旋一起转。
func _build_collision() -> void:
	if _built_collision:
		return
	_built_collision = true
	for mesh_inst in _all_meshes(self):
		if mesh_inst.mesh == null or mesh_inst.get_node_or_null("Body") != null:
			continue
		var body := StaticBody3D.new()
		body.name = "Body"
		# 大门在**建筑层**：玩家推得开，恐龙不撞（巡逻不能被门卡住）。
		body.collision_layer = LAYER_STRUCTURE
		body.collision_mask = LAYER_WORLD
		var col := CollisionShape3D.new()
		col.name = "Shape"
		col.shape = mesh_inst.mesh.create_trimesh_shape()
		body.add_child(col)
		mesh_inst.add_child(body)


func _all_meshes(root: Node) -> Array:
	var out: Array = []
	for child in root.get_children():
		if child is MeshInstance3D:
			out.append(child)
		out.append_array(_all_meshes(child))
	return out

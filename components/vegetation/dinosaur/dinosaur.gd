class_name Dinosaur
extends DinosaurBody
## 具体的恐龙：**身体 + 模型**。
##
## 行为全在 AI 模块（`components/ai/dinosaur/`）里，这个脚本只管：
##
## 1. 找到自己的模型（[member DinosaurBody.model_node_name]）；
## 2. **把模型摆正** —— 这批 glb 的模型是**朝 +Z** 的（吻在 +Z），
##    而 Godot 的"前方"是 -Z（`look_at`、`-basis.z` 都按 -Z 算），
##    不转过来的话恐龙就是**倒着走**的；
## 3. 掉出岛外时送回自己的出生点。
##
## 模型的**缩放（体型）写在各自的场景里**，因为每种的原生尺寸不一样。

## 模型要转多少度才能对上 Godot 的前方（-Z）。
## glb 模型的吻在 +Z，转 180° 之后吻才朝 -Z。
@export var model_yaw_correction_deg: float = 180.0


func _ready() -> void:
	super._ready()
	_align_model()


## 把模型转到 Godot 的前方（-Z）上。
func _align_model() -> void:
	var model := get_node_or_null(NodePath(model_node_name)) as Node3D
	if model == null:
		return
	model.rotation.y = deg_to_rad(model_yaw_correction_deg)

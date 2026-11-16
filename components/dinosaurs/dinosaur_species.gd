class_name DinosaurSpecies
extends Resource
## 恐龙**内置池**里的一种恐龙。
##
## 池子里的每一项 = 一个恐龙的场景 + 它的"偏好"：
## 出现权重（随机抽到它的概率）和领地大小倍率。
##
## ## 数值不在这里
##
## 体型、血量、伤害、感官、速度这些**数值**全在
## `components/dinosaurs/dinosaur_species_config.gd` 里（真源，见 [DinosaurSpeciesConfig]）。
## 这里只放**资源引用**（模型场景）和身份：
##
## - [member species_id] —— JSON 里的键（"t_rex" / "triceratops" / …）；
## - [member scene] —— 这一种的模型场景；
## - [member display_name] —— 显示名（调试 / 统计用）；
## - [member territory_scale] —— 领地半径的倍率（大个子占地多）。
##
## 改数值只改 JSON，不用动场景，也不用动这个资源。

## 恐龙数值的真源：`dinosaur_species_config.gd`。
const SpeciesConfig := preload("res://components/dinosaurs/dinosaur_species_config.gd")

## 种类 id：对应 `dinosaur_species_config.gd` 里 `SPECIES` 的键。
## 留空 = 这项没有配置（权重按 1.0 算、体型按场景里读的算）。
@export var species_id: String = ""
## 恐龙的场景（`components/vegetation/dinosaur/*.tscn`）。
@export var scene: PackedScene
## 显示名（调试 / 统计用）。
@export var display_name: String = ""
## 领地半径的倍率：大个子占地多，小个子挤在边上。
@export var territory_scale: float = 1.0


## 出现权重（相对概率）：来自配置。
##
## 权重和 = 100 = 大世界里的恐龙总数（`initial_count = 100`），
## 所以权重**就是**这一种在大世界里的期望只数。
##
## 配置里没有这一种时按 1.0 算（等权重）。
func weight() -> float:
	if species_id.is_empty():
		return 1.0
	return SpeciesConfig.get_weight(species_id)


## 恐龙的**体型**（米）：领地大小、身边净空、"谁更可怕"都用它。
##
## 从配置里读；配置里没有这一种时，退回从场景里读
## （老做法：把场景实例化一次，问它的 `DinosaurAIConfig.body_size`）。
func body_size() -> float:
	if not species_id.is_empty():
		var size := SpeciesConfig.get_body_size(species_id)
		if size > 0.0:
			return size
	return _body_size_from_scene()


## 从场景里读体型（JSON 里没有时的兜底）。
func _body_size_from_scene() -> float:
	if scene == null:
		return 4.0
	var inst := scene.instantiate()
	var size := 4.0
	var ai := inst.get_node_or_null("AI")
	if ai != null and ai.get("config") != null:
		var cfg = ai.get("config")
		if cfg != null and "body_size" in cfg:
			size = float(cfg.get("body_size"))
	inst.free()
	return size

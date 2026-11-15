class_name DinosaurSpecies
extends Resource
## 恐龙**内置池**里的一种恐龙。
##
## 池子里的每一项 = 一个恐龙的场景 + 它的"偏好"：
## 出现权重（随机抽到它的概率）和领地大小倍率。
##
## 体型不在这里写 —— 每种恐龙的体型已经在它自己场景里的
## [DinosaurAIConfig]（`body_size`，单位米）里了，组件按那个算领地半径，
## 不用两处维护。

## 恐龙的场景（`components/vegetation/dinosaur/*.tscn`）。
@export var scene: PackedScene
## 显示名（调试 / 统计用）。
@export var display_name: String = ""
## 出现权重（相对概率）。0 = 这一轮不放它。
@export var weight: float = 1.0
## 领地半径的倍率：大个子占地多，小个子挤在边上。
@export var territory_scale: float = 1.0


## 从场景里读出体型（米）。读不到就按 4 m 算（一只中等体型的恐龙）。
func body_size() -> float:
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

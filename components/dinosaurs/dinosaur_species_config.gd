class_name DinosaurSpeciesConfig
extends RefCounted
## 恐龙数值的**唯一真源**（就在这个文件里）。
##
## ## 为什么数值写在代码里而不是 JSON
##
## 数值以前散在 6 个 `.tscn` 的 `DinosaurAIConfig` 子资源上，改一个数要翻 6 个文件，
## 而且看不出它们之间的关系（谁 DPS 高、谁跑得快）。
## 现在：**所有数值集中在下面两张表里** —— 一张共用的、一张每种恐龙的，
## 一眼能看出六种恐龙的强弱关系，改数值只动这一个文件。
##
## ## 用法
##
## ```gdscript
## var data := DinosaurSpeciesConfig.get_species("t_rex")  # 共用默认值 + 这一种自己的值
## var hp := float(data.get("max_health", 100.0))
## var w := DinosaurSpeciesConfig.get_weight("t_rex")       # 出现权重（= 大世界里的只数）
## ```
##
## 数值设计（为什么是这些数）见 `requirements/numerical/dinosaur.md`，
## 全量表格也记在那份文档里。

## 所有恐龙**共用**的参数。
##
## `species` 里的同名参数覆盖这里的值。
const DEFAULTS: Dictionary = {
	## 目标要跑多快才算"有声音"（米/秒）。玩家步行 5 / 冲刺 10 m/s
	## （见 requirements/numerical/organism.md §1.1），所以走路安静、冲刺才吵。
	## **本作没有潜行玩法**，噪音只用来放大"冲刺时被发现的距离"。
	"noise_speed_threshold": 6.0,
	## 跑得比这快时，声音传播范围的额外倍率。
	"noise_reach_scale": 1.6,
	## 警觉度每秒钟下降多少（0~1）。
	"alert_decay": 0.25,
	## 警觉度达到多少才会追（0~1）。
	"chase_alert_threshold": 0.45,
	## 调查可疑点最多花多久（秒）。
	"investigate_time": 8.0,
	## 休息多久（秒）。巡逻完一圈会歇一会儿。
	"rest_time": 6.0,
	## 撞住多久算卡住（秒）。
	"stuck_timeout": 2.0,
	## 脱困时往后退多久（秒）。
	"unstick_time": 1.2,
	## 脱困时**一次转多少度**（度）。
	"unstick_turn_step_deg": 30.0,
}

## 每种恐龙的数值。**键 = species_id = 场景根节点上的 species_id**。
##
## 字段说明：
## - `role` —— 角色（一句说明，给人看）
## - `weight` —— 出现权重。**权重和 = 100 = 大世界里的恐龙总数**
##   （`initial_count = 100`），所以权重就是这一种在大世界里的期望只数
## - `armor` —— 护甲。**暂定 0**（见 dinosaur.md §3.2）
## - `body_size` —— 体型（米）：领地半径、身边净空、"谁更可怕"都用它
## - `base_speed` / `turn_speed_deg` —— 身体的基础速度与转向速度
## - 其余 —— 写进 [DinosaurAIConfig] 的调参表（见 `apply_species`）
const SPECIES: Dictionary = {
	"t_rex": {
		"role": "拆家主力",
		"weight": 12.0,
		"armor": 0,
		"body_size": 11.0,
		"base_speed": 3.0,
		"turn_speed_deg": 40.0,
		"max_health": 140.0,
		"attack_damage": 24.0,
		"attack_cooldown": 2.2,
		"attack_range": 4.2,
		"flee_health_ratio": 0.25,
		"sight_range": 24.0,
		"sight_half_angle_deg": 55.0,
		"hearing_range": 16.0,
		"eye_height": 4.0,
		"reaction_time": 0.3,
		"memory_time": 8.0,
		"patrol_speed_scale": 1.0,
		"chase_speed_scale": 1.5,
		"threat_radius": 12.0,
		"separation_radius": 5.0,
		"separation_strength": 0.9,
		"avoid_distance": 4.5,
	},
	"triceratops": {
		"role": "常规拆家",
		"weight": 18.0,
		"armor": 0,
		"body_size": 8.0,
		"base_speed": 2.0,
		"turn_speed_deg": 35.0,
		"max_health": 130.0,
		"attack_damage": 14.0,
		"attack_cooldown": 3.0,
		"attack_range": 3.6,
		"flee_health_ratio": 0.2,
		"sight_range": 18.0,
		"sight_half_angle_deg": 65.0,
		"hearing_range": 12.0,
		"eye_height": 3.0,
		"reaction_time": 0.45,
		"memory_time": 6.0,
		"patrol_speed_scale": 1.0,
		"chase_speed_scale": 1.6,
		"threat_radius": 8.0,
		"separation_radius": 4.5,
		"separation_strength": 0.8,
		"avoid_distance": 4.0,
	},
	"stegosaurus": {
		"role": "肉盾",
		"weight": 16.0,
		"armor": 0,
		"body_size": 8.5,
		"base_speed": 1.8,
		"turn_speed_deg": 30.0,
		"max_health": 160.0,
		"attack_damage": 12.0,
		"attack_cooldown": 3.6,
		"attack_range": 3.4,
		"flee_health_ratio": 0.15,
		"sight_range": 16.0,
		"sight_half_angle_deg": 70.0,
		"hearing_range": 10.0,
		"eye_height": 3.0,
		"reaction_time": 0.55,
		"memory_time": 6.0,
		"patrol_speed_scale": 1.0,
		"chase_speed_scale": 1.5,
		"threat_radius": 8.0,
		"separation_radius": 5.0,
		"separation_strength": 0.8,
		"avoid_distance": 4.0,
	},
	"parasaurolophus": {
		"role": "骚扰",
		"weight": 20.0,
		"armor": 0,
		"body_size": 6.0,
		"base_speed": 3.2,
		"turn_speed_deg": 60.0,
		"max_health": 75.0,
		"attack_damage": 9.0,
		"attack_cooldown": 2.0,
		"attack_range": 3.0,
		"flee_health_ratio": 0.45,
		"sight_range": 22.0,
		"sight_half_angle_deg": 55.0,
		"hearing_range": 18.0,
		"eye_height": 2.2,
		"reaction_time": 0.3,
		"memory_time": 7.0,
		"patrol_speed_scale": 1.0,
		"chase_speed_scale": 1.7,
		"threat_radius": 9.0,
		"separation_radius": 4.0,
		"separation_strength": 1.0,
		"avoid_distance": 3.5,
	},
	"velociraptor": {
		"role": "猎手",
		"weight": 24.0,
		"armor": 0,
		"body_size": 2.2,
		"base_speed": 4.0,
		"turn_speed_deg": 90.0,
		"max_health": 45.0,
		"attack_damage": 7.0,
		"attack_cooldown": 1.6,
		"attack_range": 2.4,
		"flee_health_ratio": 0.5,
		"sight_range": 20.0,
		"sight_half_angle_deg": 70.0,
		"hearing_range": 22.0,
		"eye_height": 0.8,
		"reaction_time": 0.2,
		"memory_time": 9.0,
		"patrol_speed_scale": 1.0,
		"chase_speed_scale": 1.9,
		"threat_radius": 6.0,
		"separation_radius": 3.0,
		"separation_strength": 1.2,
		"avoid_distance": 3.0,
	},
	"apatosaurus": {
		"role": "巨型 / 威慑",
		"weight": 10.0,
		"armor": 0,
		"body_size": 17.0,
		"base_speed": 1.4,
		"turn_speed_deg": 25.0,
		"max_health": 200.0,
		"attack_damage": 18.0,
		"attack_cooldown": 3.6,
		"attack_range": 4.6,
		"flee_health_ratio": 0.1,
		"sight_range": 16.0,
		"sight_half_angle_deg": 80.0,
		"hearing_range": 10.0,
		"eye_height": 4.0,
		"reaction_time": 0.6,
		"memory_time": 5.0,
		"patrol_speed_scale": 0.85,
		"chase_speed_scale": 1.45,
		"threat_radius": 7.0,
		"separation_radius": 6.0,
		"separation_strength": 0.7,
		"avoid_distance": 5.0,
	},
}

## 合并后的表（缓存）：species.<id> 覆盖 DEFAULTS。
static var _merged: Dictionary = {}


## 一种恐龙的**全部**数值 = 共用默认值 + 这一种自己的值（同名后者覆盖前者）。
##
## 找不到这一种时返回空字典（调用方要自己兜底）。
static func get_species(id: String) -> Dictionary:
	if _merged.has(id):
		return _merged[id]
	var entry: Variant = SPECIES.get(id, {})
	if typeof(entry) != TYPE_DICTIONARY or (entry as Dictionary).is_empty():
		return {}
	var merged: Dictionary = DEFAULTS.duplicate(true)
	for key in (entry as Dictionary).keys():
		merged[key] = (entry as Dictionary)[key]
	_merged[id] = merged
	return merged


## 配置里有没有这一种。
static func has_species(id: String) -> bool:
	return not get_species(id).is_empty()


## 这一种的**出现权重**（相对概率）。
##
## 权重和 = 100 = 大世界里的恐龙总数（`initial_count = 100`），
## 所以权重**就是**这一种在大世界里的期望只数。
static func get_weight(id: String) -> float:
	return float(get_species(id).get("weight", 1.0))


## 这一种的**体型**（米）：领地半径、净空、威胁判定都用它。
static func get_body_size(id: String) -> float:
	return float(get_species(id).get("body_size", 0.0))


## 这一种的**角色**（一句说明，调试时看）。
static func get_role(id: String) -> String:
	return String(get_species(id).get("role", ""))


## 所有种类 id。
static func species_ids() -> Array[String]:
	var out: Array[String] = []
	for id in SPECIES.keys():
		out.append(String(id))
	return out


## 所有种类的**权重和**（应该 = 100 = 大世界里的恐龙总数）。
static func total_weight() -> float:
	var total := 0.0
	for id in SPECIES.keys():
		total += get_weight(String(id))
	return total

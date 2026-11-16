class_name DinosaurAIConfig
extends Resource
## 恐龙 AI 的调参表 —— 每种恐龙一份。
##
## 这张表是"行为差异"的唯一入口：同样是"看到玩家就追"，
## 霸王龙追得远、记得久、伤害高；迅猛龙一吓就散、听觉远、掉头快。
## 改数值就能改性格，不用碰逻辑。
##
## ## 数值从哪来
##
## **真源是 `components/dinosaurs/dinosaur_species_config.gd`**（见 [DinosaurSpeciesConfig]）。
## 这里的 @export 只是**兜底默认值** —— 恐龙进场景时，
## AI 会按身体的 `species_id` 去 JSON 里把这一种的数值写进来
## （[method apply_species]）。JSON 里没有这一种时，才用这里的默认值。
##
## 设计意图见 `requirements/numerical/dinosaur.md`。

## ---- 碰撞层（跟 project.godot 的 layer_names 对应）----
## 地面（地形 / 山体 / 岛体）。
const LAYER_WORLD := 1
## 植被（香蕉树干）—— **会挡视线**，所以玩家能躲树。
const LAYER_VEGETATION := 2
## 建筑（围墙 / 大门）。
const LAYER_STRUCTURE := 4
## 杂物（石头 / 碎石）。
const LAYER_PROP := 8
## 生物（玩家 / 恐龙）。
const LAYER_CREATURE := 16
## 边界（浮空岛的隐形围栏）：只挡恐龙，玩家不受影响。
const LAYER_BOUNDARY := 32

@export_group("感官")
## 能看多远（米）。
@export var sight_range: float = 18.0
## 视野半角（度）。180 = 全向，60 = 窄。
@export var sight_half_angle_deg: float = 60.0
## 听多远（米）。目标跑得越快听得越远。
@export var hearing_range: float = 12.0
## 眼睛的高度（米，相对脚底）。
@export var eye_height: float = 2.0
## 目标要跑多快才算"有声音"（米/秒）。
## 玩家步行 5 m/s / 冲刺 10 m/s（见 requirements/numerical/organism.md §1.1），
## 所以阈值取 6：走路安静、冲刺才吵。**本作没有潜行玩法**，
## 噪音只用来放大"冲刺时被发现的距离"。
@export var noise_speed_threshold: float = 6.0
## 跑得比这快时，声音传播范围的额外倍率。
@export var noise_reach_scale: float = 1.6

@export_group("反应")
## 发现目标到真正开始追之间的反应时间（秒）。反应慢 = 更呆。
@export var reaction_time: float = 0.35
## 目标从视线里消失后，还追多久（秒）。= 记忆力。
@export var memory_time: float = 6.0
## 警觉度每秒钟下降多少（0~1）。
@export var alert_decay: float = 0.25
## 警觉度达到多少才会追（0~1）。
@export var chase_alert_threshold: float = 0.45

@export_group("行为")
## 巡逻时的速度倍率。
@export var patrol_speed_scale: float = 1.0
## 追击时的速度倍率。
@export var chase_speed_scale: float = 1.7
## 调查可疑点最多花多久（秒）。
@export var investigate_time: float = 8.0
## 休息多久（秒）。巡逻完一圈会歇一会儿。
@export var rest_time: float = 6.0
## 撞住多久算卡住（秒）。
@export var stuck_timeout: float = 2.0
## 脱困时往后退多久（秒）。
@export var unstick_time: float = 1.2
## 脱困时**一次转多少度**（度）。
##
## 脱困的流程是"转向 → 前进"：还是卡住就**朝同一个方向**再转一个步长，
## 30° → 60° → 90° …… 一直转到能走为止。步长越大试的次数越少，
## 但每次转过去要花的时间更长（时间 = 步长 / `turn_speed_deg`）。
@export var unstick_turn_step_deg: float = 30.0
## 多近才动手（米）。
@export var attack_range: float = 3.6
## 两次攻击之间的间隔（秒）。
@export var attack_cooldown: float = 2.5
## 一次攻击的伤害。
@export var attack_damage: float = 14.0
## 血量。
@export var max_health: float = 100.0
## 血量低于这个比例就跑。
@export var flee_health_ratio: float = 0.3
## 体型尺寸（米）。用来比"谁更可怕"：大个子吓跑小个子。
@export var body_size: float = 4.0
## 多近以内会注意到比自己大的家伙（米）。
@export var threat_radius: float = 12.0

@export_group("转向 / 群体")
## 最大转向速度（度/秒）。
@export var turn_speed_deg: float = 45.0
## 同伴之间保持多远的距离（米）。
@export var separation_radius: float = 4.5
## 挤开同伴的力度（0~1）。
@export var separation_strength: float = 0.8
## 避障射线的长度（米）。
@export var avoid_distance: float = 4.0

@export_group("目标")
## 要盯着的目标在哪个组里。
@export var target_group: String = "player"
## **建筑**目标在哪个组里。留空 = 不看建筑（默认）。
##
## 玩家盖的房子要能被恐龙拆，就得多一条"盯建筑"的通道：
## 看见了就冲过去啃。留空的话恐龙只追玩家（默认行为不变）。
@export var structure_target_group: String = ""
## 同伴恐龙在哪个组里（用于分离和威胁判断）。
@export var herd_group: String = "dinosaur"


## 把 [DinosaurSpeciesConfig] 里的一种恐龙的数值写进这份配置。
##
## [param data] 是 [method DinosaurSpeciesConfig.get_species] 的返回值
## （全局默认值 + 这一种自己的值）。配置里没有的字段保持原值。
##
## 由 [DinosaurAI] 在 `_ready()` 里调用 —— 场景里不用再写数字。
func apply_species(data: Dictionary) -> void:
	if data.is_empty():
		return
	# 感官
	sight_range = float(data.get("sight_range", sight_range))
	sight_half_angle_deg = float(data.get("sight_half_angle_deg", sight_half_angle_deg))
	hearing_range = float(data.get("hearing_range", hearing_range))
	eye_height = float(data.get("eye_height", eye_height))
	noise_speed_threshold = float(data.get("noise_speed_threshold", noise_speed_threshold))
	noise_reach_scale = float(data.get("noise_reach_scale", noise_reach_scale))
	# 反应
	reaction_time = float(data.get("reaction_time", reaction_time))
	memory_time = float(data.get("memory_time", memory_time))
	alert_decay = float(data.get("alert_decay", alert_decay))
	chase_alert_threshold = float(data.get("chase_alert_threshold", chase_alert_threshold))
	# 行为
	patrol_speed_scale = float(data.get("patrol_speed_scale", patrol_speed_scale))
	chase_speed_scale = float(data.get("chase_speed_scale", chase_speed_scale))
	investigate_time = float(data.get("investigate_time", investigate_time))
	rest_time = float(data.get("rest_time", rest_time))
	stuck_timeout = float(data.get("stuck_timeout", stuck_timeout))
	unstick_time = float(data.get("unstick_time", unstick_time))
	unstick_turn_step_deg = float(data.get("unstick_turn_step_deg", unstick_turn_step_deg))
	# 战斗
	attack_range = float(data.get("attack_range", attack_range))
	attack_cooldown = float(data.get("attack_cooldown", attack_cooldown))
	attack_damage = float(data.get("attack_damage", attack_damage))
	max_health = float(data.get("max_health", max_health))
	flee_health_ratio = float(data.get("flee_health_ratio", flee_health_ratio))
	body_size = float(data.get("body_size", body_size))
	threat_radius = float(data.get("threat_radius", threat_radius))
	# 转向 / 群体
	turn_speed_deg = float(data.get("turn_speed_deg", turn_speed_deg))
	separation_radius = float(data.get("separation_radius", separation_radius))
	separation_strength = float(data.get("separation_strength", separation_strength))
	avoid_distance = float(data.get("avoid_distance", avoid_distance))

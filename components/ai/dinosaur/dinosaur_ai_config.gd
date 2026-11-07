class_name DinosaurAIConfig
extends Resource
## 恐龙 AI 的调参表 —— 每种恐龙一份（内嵌在各自的场景里当子资源）。
##
## 这张表是"行为差异"的唯一入口：同样是"看到玩家就追"，
## 霸王龙追得远、记得久、伤害高；迅猛龙一吓就散、听觉远、掉头快。
## 改数值就能改性格，不用碰逻辑。

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
@export var noise_speed_threshold: float = 3.0
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
## 同伴恐龙在哪个组里（用于分离和威胁判断）。
@export var herd_group: String = "dinosaur"

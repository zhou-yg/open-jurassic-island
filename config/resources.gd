## Global resource definitions for the survival game.
##
## Mirrors the design document at [code]design/buildings.md[/code] (resources section).
## Pure static configuration, no instance and no methods needed:
## 	ResourcesConfig.WOOD["name"]
## 	ResourcesConfig.FOOD["id"]
##
## [b]运行期统计[/b]：采集类组件（香蕉树等）把采到的数量写进这里的
## [member collected_bananas]，它是全局的（[code]ResourcesConfig[/code] 是
## 全局类，静态变量在所有场景之间共享），配合全局资源池
## （[code]autoloads/data/resources.gd[/code] 的 "banana"）一起构成"全局配置"。
class_name ResourcesConfig
extends Object

## All resource types used by buildings, units and upgrades.
## One enum value per const below.
enum Type {
	WOOD,  ## Collected by wood monkeys from trees. See [const WOOD].
	STONE, ## Collected by stone monkeys from big stones. See [const STONE].
	FOOD,  ## Bananas. Consumed by food-costed buildings and workers. See [const FOOD].
}

## Each resource const:
## [codeblock]
## {
## 	"type": Type,          # enum value of this resource
## 	"id": String,          # string id used as key in cost dictionaries
## 	"name": String,        # display name
## 	"description": String, # design description
## 	"max_stack": int,      # max amount per stack
## }
## [/codeblock]

const WOOD: Dictionary = {
	"type": Type.WOOD,
	"id": "wood",
	"name": "Wood",
	"description": "Basic building material. Collected from trees by wood monkeys.",
	"max_stack": 999,
}

const STONE: Dictionary = {
	"type": Type.STONE,
	"id": "stone",
	"name": "Stone",
	"description": "Sturdy building material. Collected from big stones by stone monkeys.",
	"max_stack": 999,
}

const FOOD: Dictionary = {
	"type": Type.FOOD,
	"id": "banana",
	"name": "Food (Banana)",
	"description": "Food resource. Provided by banana factories and consumed by food-costed buildings.",
	"max_stack": 999,
}


## ------------------------------------------------------------------
## 运行期统计（全局）
## ------------------------------------------------------------------

## 玩家累计采集到的香蕉根数。
##
## 香蕉树组件采集成功后会调用 [method add_collected_bananas] 写进这里，
## 同时把数量同步到全局资源池（"banana"）。
static var collected_bananas: int = 0

## 累加"采集到的香蕉"统计，并把数量同步到全局资源池。
## 返回累加后的总采集数（不会小于 0）。
static func add_collected_bananas(amount: int) -> int:
	if amount <= 0:
		return collected_bananas
	collected_bananas += amount
	_sync_to_global_pool(amount)
	return collected_bananas

## 累计采集到的香蕉根数。
static func get_collected_bananas() -> int:
	return collected_bananas

## 清零采集统计（重新开局 / 测试时用）。
static func reset_collected_bananas() -> void:
	collected_bananas = 0

## 把数量同步到全局资源池（autoloads/data/resources.gd 里的 "banana"）。
##
## 这里刻意用[b]运行期查找[/b]而不是直接引用自动加载 `Resources`：
## 那个自动加载脚本会 preload 本文件，直接引用会形成循环依赖。
static func _sync_to_global_pool(amount: int) -> void:
	var loop := Engine.get_main_loop() as SceneTree
	if loop == null or loop.root == null:
		return
	var pool := loop.root.get_node_or_null("Resources")
	if pool == null or not pool.has_method("add_amount"):
		return
	pool.add_amount(FOOD["id"], amount)

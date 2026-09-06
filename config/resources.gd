## Global resource definitions for the survival game.
##
## Mirrors the design document at [code]design/buildings.md[/code] (resources section).
## Pure static configuration, no instance and no methods needed:
## 	ResourcesConfig.WOOD["name"]
## 	ResourcesConfig.FOOD["id"]
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

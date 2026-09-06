## Global item definitions for the survival game.
##
## Mirrors the design document at [code]design/items.md[/code].
## Items are ground pickups: the player can pick them up from the ground.
## Pure static configuration, no instance and no methods needed:
## 	ItemsConfig.STONE_FRAGMENT_50["amount"]
## 	ItemsConfig.BANANA_5["resource"]
class_name ItemsConfig
extends Object

## Item types.
enum Type {
	FOOD,      ## Edible items (bananas). Feeds food-costed buildings and workers.
	RESOURCES, ## Raw materials dropped as fragments (wood / stone).
}

## Each item const:
## [codeblock]
## {
## 	"id": String,          # string id, equals the const name in snake_case
## 	"type": Type,          # FOOD or RESOURCES
## 	"name": String,        # display name
## 	"description": String, # design description
## 	"resource": String,    # resource string id granted on pickup
## 	"amount": int,         # resource amount granted on pickup
## }
## [/codeblock]
## "resource" keys match [code]ResourcesConfig[/code] ids: "wood", "stone", "food".

# ------------------------------------------------------ stone fragments
const STONE_FRAGMENT_10: Dictionary = {
	"id": "stone_fragment_10",
	"type": Type.RESOURCES,
	"name": "Stone Fragment (10)",
	"description": "A small pile of stone rubble. Grants 10 stone when picked up.",
	"resource": "stone",
	"amount": 10,
}

const STONE_FRAGMENT_50: Dictionary = {
	"id": "stone_fragment_50",
	"type": Type.RESOURCES,
	"name": "Stone Fragment (50)",
	"description": "A medium pile of stone rubble. Grants 50 stone when picked up.",
	"resource": "stone",
	"amount": 50,
}

const STONE_FRAGMENT_100: Dictionary = {
	"id": "stone_fragment_100",
	"type": Type.RESOURCES,
	"name": "Stone Fragment (100)",
	"description": "A large pile of stone rubble. Grants 100 stone when picked up.",
	"resource": "stone",
	"amount": 100,
}

# ------------------------------------------------------- wood fragments
const WOOD_FRAGMENT_10: Dictionary = {
	"id": "wood_fragment_10",
	"type": Type.RESOURCES,
	"name": "Wood Fragment (10)",
	"description": "A small bundle of wood. Grants 10 wood when picked up.",
	"resource": "wood",
	"amount": 10,
}

const WOOD_FRAGMENT_50: Dictionary = {
	"id": "wood_fragment_50",
	"type": Type.RESOURCES,
	"name": "Wood Fragment (50)",
	"description": "A medium bundle of wood. Grants 50 wood when picked up.",
	"resource": "wood",
	"amount": 50,
}

const WOOD_FRAGMENT_100: Dictionary = {
	"id": "wood_fragment_100",
	"type": Type.RESOURCES,
	"name": "Wood Fragment (100)",
	"description": "A large bundle of wood. Grants 100 wood when picked up.",
	"resource": "wood",
	"amount": 100,
}

# ----------------------------------------------------------------- food
const BANANA_1: Dictionary = {
	"id": "banana_1",
	"type": Type.FOOD,
	"name": "Banana",
	"description": "A single banana. Grants 1 food when picked up.",
	"resource": "food",
	"amount": 1,
}

const BANANA_2: Dictionary = {
	"id": "banana_2",
	"type": Type.FOOD,
	"name": "Banana Bunch (2)",
	"description": "A small bunch of bananas. Grants 2 food when picked up.",
	"resource": "food",
	"amount": 2,
}

const BANANA_5: Dictionary = {
	"id": "banana_5",
	"type": Type.FOOD,
	"name": "Banana Bunch (5)",
	"description": "A large bunch of bananas. Grants 5 food when picked up.",
	"resource": "food",
	"amount": 5,
}

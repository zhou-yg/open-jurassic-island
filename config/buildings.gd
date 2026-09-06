## Global building definitions for the survival game.
##
## Mirrors the design document at [code]design/buildings.md[/code].
## Pure static configuration, no instance and no methods needed:
## 	BuildingsConfig.CAMP["props"]["heal_point"]
## 	BuildingsConfig.WOODEN_WALL["upgrade_to"]
##
## Buildings with levels (colleges, banana factory, turret, mangonel) are
## modeled as independent entities per level, chained by "upgrade_to" and
## grouped in [const LEVEL_SERIES] for easy "next level" lookup.
class_name BuildingsConfig
extends Object

## Building categories. Used for build menus, filtering and tech gating.
enum Category {
	BASIC,   ## Camp and campfire: core survival buildings.
	WORKER,  ## Monkey worker units (wood / stone collectors).
	FOOD,    ## Food (banana) production.
	GUARD,   ## Walls and gates.
	DEFENSE, ## Defense tech buildings and turrets / mangonels.
	ARMY,    ## Army tech buildings and equipment.
	VEHICLE, ## Vehicle tech buildings and vehicles.
}

## Each building const:
## [codeblock]
## {
## 	"id": String,          # string id, equals the const name in snake_case
## 	"category": Category,  # menu / filter group
## 	"name": String,        # display name
## 	"description": String, # design description
## 	"props": Dictionary,   # building specific values (heal, damage, ...)
## 	"cost": Dictionary,    # resource string id -> amount
## 	"build_time": float,   # seconds
## 	"max_hp": int,         # hit points
## 	"upgrade_to": String,  # (optional) id of the upgraded building
## 	"requires": String,    # (optional) id of required tech building
## 	"unlocks": Array,      # (optional) ids unlocked by this tech building
## 	"auto_enabled": bool,  # (optional) available from the start
## }
## [/codeblock]
## Cost keys match [code]ResourcesConfig[/code] ids: "wood", "stone", "food".

# ------------------------------------------------------------------ basic
const CAMP: Dictionary = {
	"id": "camp",
	"category": Category.BASIC,
	"name": "Camp",
	"description": "Heals the HP of nearby monkeys and the player.",
	"props": {
		"heal_point": 5,
	},
	"heal_target": "hp",
	"cost": {"wood": 30},
	"build_time": 10.0,
	"max_hp": 500,
}

const CAMPFIRE: Dictionary = {
	"id": "campfire",
	"category": Category.BASIC,
	"name": "Campfire",
	"description": "Restores the MP of nearby monkeys and the player.",
	"props": {
		"heal_point": 1,
	},
	"heal_target": "mp",
	"cost": {"wood": 10},
	"build_time": 5.0,
	"max_hp": 100,
}

# ---------------------------------------------------------------- worker
const WOOD_MONKEY: Dictionary = {
	"id": "wood_monkey",
	"category": Category.WORKER,
	"name": "Wood Monkey",
	"description": "Collects wood from trees and moves it back to the camp. Needs food to work and stops working when scared.",
	"props": {
		"collect_resource": "wood",
		"collect_rate": 1.0,
		"carry_capacity": 10,
		"needs_food": true,
		"stops_when_scared": true,
	},
	"cost": {"food": 1},
	"build_time": 8.0,
	"max_hp": 40,
}

const STONE_MONKEY: Dictionary = {
	"id": "stone_monkey",
	"category": Category.WORKER,
	"name": "Stone Monkey",
	"description": "Collects stone from big stones and moves it back to the camp. Needs food to work and stops working when scared.",
	"props": {
		"collect_resource": "stone",
		"collect_rate": 0.8,
		"carry_capacity": 8,
		"needs_food": true,
		"stops_when_scared": true,
	},
	"cost": {"food": 1},
	"build_time": 8.0,
	"max_hp": 40,
}

# ------------------------------------------------------------------ food
# banana factory, level 1 -> 2 -> 3 as independent entities
const BANANA_FACTORY_LEVEL_1: Dictionary = {
	"id": "banana_factory_level_1",
	"category": Category.FOOD,
	"name": "Banana Factory Level 1",
	"description": "Hangs on a banana-tree and produces food (bananas). Must be placed at least 10 m away from other banana-trees.",
	"props": {
		"produce_resource": "food",
		"produce_rate": 0.5,
		"min_distance_to_other_tree": 10.0,
	},
	"cost": {"wood": 50},
	"build_time": 15.0,
	"max_hp": 150,
	"upgrade_to": "banana_factory_level_2",
}

const BANANA_FACTORY_LEVEL_2: Dictionary = {
	"id": "banana_factory_level_2",
	"category": Category.FOOD,
	"name": "Banana Factory Level 2",
	"description": "Hangs on a banana-tree and produces food (bananas). Upgraded form of level 1.",
	"props": {
		"produce_resource": "food",
		"produce_rate": 1.0,
		"min_distance_to_other_tree": 10.0,
	},
	"cost": {"wood": 40},
	"build_time": 15.0,
	"max_hp": 180,
	"upgrade_to": "banana_factory_level_3",
}

const BANANA_FACTORY_LEVEL_3: Dictionary = {
	"id": "banana_factory_level_3",
	"category": Category.FOOD,
	"name": "Banana Factory Level 3",
	"description": "Hangs on a banana-tree and produces food (bananas). Upgraded form of level 2.",
	"props": {
		"produce_resource": "food",
		"produce_rate": 1.5,
		"min_distance_to_other_tree": 10.0,
	},
	"cost": {"wood": 80, "stone": 40},
	"build_time": 20.0,
	"max_hp": 220,
}

# ----------------------------------------------------------------- guard
const WOODEN_WALL: Dictionary = {
	"id": "wooden_wall",
	"category": Category.GUARD,
	"name": "Wooden Wall",
	"description": "Cheap wall that blocks ground movement. Can be upgraded to a stone wall by spending time and resources.",
	"cost": {"wood": 5},
	"build_time": 3.0,
	"max_hp": 200,
	"upgrade_to": "stone_wall",
}

const STONE_WALL: Dictionary = {
	"id": "stone_wall",
	"category": Category.GUARD,
	"name": "Stone Wall",
	"description": "Sturdy wall that blocks ground movement. Upgraded form of the wooden wall.",
	"cost": {"wood": 5, "stone": 10},
	"build_time": 5.0,
	"max_hp": 500,
}

const WOODEN_GATE: Dictionary = {
	"id": "wooden_gate",
	"category": Category.GUARD,
	"name": "Wooden Gate",
	"description": "Passable wall segment with open / close states. Can be upgraded to a stone gate.",
	"props": {
		"states": ["open", "close"],
		"default_state": "close",
	},
	"cost": {"wood": 10},
	"build_time": 5.0,
	"max_hp": 250,
	"upgrade_to": "stone_gate",
}

const STONE_GATE: Dictionary = {
	"id": "stone_gate",
	"category": Category.GUARD,
	"name": "Stone Gate",
	"description": "Sturdy passable wall segment with open / close states. Upgraded form of the wooden gate.",
	"props": {
		"states": ["open", "close"],
		"default_state": "close",
	},
	"cost": {"wood": 10, "stone": 20},
	"build_time": 8.0,
	"max_hp": 600,
}

# -------------------------------------------------------------- defense
# defense college, level 1 -> 2 -> 3 as independent entities
const DEFENSE_COLLEGE_LEVEL_1: Dictionary = {
	"id": "defense_college_level_1",
	"category": Category.DEFENSE,
	"name": "Defense College Level 1",
	"description": "Old professor monkey teaching defense techniques. Enables the defense tech level 1.",
	"props": {
		"food_cost_note": "old professor monkey for teaching monkey",
	},
	"cost": {"wood": 100, "stone": 100, "food": 1},
	"build_time": 120.0,
	"max_hp": 400,
	"upgrade_to": "defense_college_level_2",
	"unlocks": [
		"monkey_turret_level_1",
		"monkey_mangonel_level_1",
	],
}

const DEFENSE_COLLEGE_LEVEL_2: Dictionary = {
	"id": "defense_college_level_2",
	"category": Category.DEFENSE,
	"name": "Defense College Level 2",
	"description": "Old professor monkey teaching defense techniques. Upgraded form of level 1.",
	"props": {
		"food_cost_note": "old professor monkey for teaching monkey",
	},
	"cost": {"wood": 100, "stone": 100, "food": 1},
	"build_time": 120.0,
	"max_hp": 500,
	"upgrade_to": "defense_college_level_3",
}

const DEFENSE_COLLEGE_LEVEL_3: Dictionary = {
	"id": "defense_college_level_3",
	"category": Category.DEFENSE,
	"name": "Defense College Level 3",
	"description": "Old professor monkey teaching defense techniques. Upgraded form of level 2.",
	"props": {
		"food_cost_note": "old professor monkey for teaching monkey",
	},
	"cost": {"wood": 150, "stone": 150, "food": 1},
	"build_time": 180.0,
	"max_hp": 600,
}

# fast speed low damage, level 1 -> 2 -> 3 as independent entities
const MONKEY_TURRET_LEVEL_1: Dictionary = {
	"id": "monkey_turret_level_1",
	"category": Category.DEFENSE,
	"name": "Monkey Turret Level 1",
	"description": "Fast attack speed, low damage defense tower.",
	"props": {
		"attack_speed": 1.0,
		"damage": 5,
		"range": 15.0,
	},
	"cost": {"wood": 50, "stone": 25},
	"build_time": 20.0,
	"max_hp": 300,
	"requires": "defense_college_level_1",
	"upgrade_to": "monkey_turret_level_2",
}

const MONKEY_TURRET_LEVEL_2: Dictionary = {
	"id": "monkey_turret_level_2",
	"category": Category.DEFENSE,
	"name": "Monkey Turret Level 2",
	"description": "Fast attack speed, low damage defense tower. Upgraded form of level 1.",
	"props": {
		"attack_speed": 1.2,
		"damage": 8,
		"range": 17.0,
	},
	"cost": {"wood": 75, "stone": 50},
	"build_time": 25.0,
	"max_hp": 350,
	"requires": "defense_college_level_1",
	"upgrade_to": "monkey_turret_level_3",
}

const MONKEY_TURRET_LEVEL_3: Dictionary = {
	"id": "monkey_turret_level_3",
	"category": Category.DEFENSE,
	"name": "Monkey Turret Level 3",
	"description": "Fast attack speed, low damage defense tower. Upgraded form of level 2.",
	"props": {
		"attack_speed": 1.5,
		"damage": 12,
		"range": 20.0,
	},
	"cost": {"wood": 100, "stone": 75, "food": 1},
	"build_time": 30.0,
	"max_hp": 400,
	"requires": "defense_college_level_1",
}

# slow speed high damage, level 1 -> 2 -> 3 as independent entities
const MONKEY_MANGONEL_LEVEL_1: Dictionary = {
	"id": "monkey_mangonel_level_1",
	"category": Category.DEFENSE,
	"name": "Monkey Mangonel Level 1",
	"description": "Slow attack speed, high damage siege defense.",
	"props": {
		"attack_speed": 0.2,
		"damage": 30,
		"range": 25.0,
	},
	"cost": {"wood": 75, "stone": 50},
	"build_time": 30.0,
	"max_hp": 350,
	"requires": "defense_college_level_1",
	"upgrade_to": "monkey_mangonel_level_2",
}

const MONKEY_MANGONEL_LEVEL_2: Dictionary = {
	"id": "monkey_mangonel_level_2",
	"category": Category.DEFENSE,
	"name": "Monkey Mangonel Level 2",
	"description": "Slow attack speed, high damage siege defense. Upgraded form of level 1.",
	"props": {
		"attack_speed": 0.25,
		"damage": 50,
		"range": 28.0,
	},
	"cost": {"wood": 100, "stone": 75},
	"build_time": 35.0,
	"max_hp": 400,
	"requires": "defense_college_level_1",
	"upgrade_to": "monkey_mangonel_level_3",
}

const MONKEY_MANGONEL_LEVEL_3: Dictionary = {
	"id": "monkey_mangonel_level_3",
	"category": Category.DEFENSE,
	"name": "Monkey Mangonel Level 3",
	"description": "Slow attack speed, high damage siege defense. Upgraded form of level 2.",
	"props": {
		"attack_speed": 0.3,
		"damage": 80,
		"range": 32.0,
	},
	"cost": {"wood": 150, "stone": 100, "food": 1},
	"build_time": 40.0,
	"max_hp": 450,
	"requires": "defense_college_level_1",
}

# ------------------------------------------------------------------ army
# army college, level 1 -> 2 -> 3 as independent entities
const ARMY_COLLEGE_LEVEL_1: Dictionary = {
	"id": "army_college_level_1",
	"category": Category.ARMY,
	"name": "Army College Level 1",
	"description": "Old soldier monkey teaching military techniques. Enables the monkey army tech level 1.",
	"props": {
		"food_cost_note": "old soldier monkey for teaching monkey",
	},
	"cost": {"wood": 100, "stone": 100, "food": 1},
	"build_time": 120.0,
	"max_hp": 400,
	"upgrade_to": "army_college_level_2",
	"unlocks": ["armor", "gun", "rpg"],
}

const ARMY_COLLEGE_LEVEL_2: Dictionary = {
	"id": "army_college_level_2",
	"category": Category.ARMY,
	"name": "Army College Level 2",
	"description": "Old soldier monkey teaching military techniques. Upgraded form of level 1.",
	"props": {
		"food_cost_note": "old soldier monkey for teaching monkey",
	},
	"cost": {"wood": 100, "stone": 100, "food": 1},
	"build_time": 120.0,
	"max_hp": 500,
	"upgrade_to": "army_college_level_3",
}

const ARMY_COLLEGE_LEVEL_3: Dictionary = {
	"id": "army_college_level_3",
	"category": Category.ARMY,
	"name": "Army College Level 3",
	"description": "Old soldier monkey teaching military techniques. Upgraded form of level 2.",
	"props": {
		"food_cost_note": "old soldier monkey for teaching monkey",
	},
	"cost": {"wood": 150, "stone": 150, "food": 1},
	"build_time": 180.0,
	"max_hp": 600,
}

const ARMOR: Dictionary = {
	"id": "armor",
	"category": Category.ARMY,
	"name": "Armor",
	"description": "Army equipment: raises the max HP and damage reduction of monkey soldiers.",
	"props": {
		"bonus_hp": 50,
		"damage_reduction": 0.15,
	},
	"cost": {"stone": 100, "food": 1},
	"build_time": 60.0,
	"max_hp": 200,
	"requires": "army_college_level_1",
}

const GUN: Dictionary = {
	"id": "gun",
	"category": Category.ARMY,
	"name": "Gun",
	"description": "Army equipment: standard ranged weapon for monkey soldiers.",
	"props": {
		"damage": 10,
		"attack_speed": 0.8,
		"range": 20.0,
	},
	"cost": {"wood": 50, "stone": 100, "food": 1},
	"build_time": 60.0,
	"max_hp": 200,
	"requires": "army_college_level_1",
}

const RPG: Dictionary = {
	"id": "rpg",
	"category": Category.ARMY,
	"name": "RPG",
	"description": "Army equipment: heavy weapon with high damage and a slow attack speed.",
	"props": {
		"damage": 60,
		"attack_speed": 0.25,
		"range": 25.0,
		"splash_radius": 3.0,
	},
	"cost": {"wood": 100, "stone": 150, "food": 2},
	"build_time": 90.0,
	"max_hp": 200,
	"requires": "army_college_level_1",
}

# --------------------------------------------------------------- vehicle
# vehicle college, level 1 -> 2 -> 3 as independent entities
const VEHICLE_COLLEGE_LEVEL_1: Dictionary = {
	"id": "vehicle_college_level_1",
	"category": Category.VEHICLE,
	"name": "Vehicle College Level 1",
	"description": "Old soldier monkey teaching vehicle techniques. Enables the vehicle tech level 1.",
	"props": {
		"food_cost_note": "old soldier monkey for teaching monkey",
	},
	"cost": {"wood": 100, "stone": 100, "food": 1},
	"build_time": 120.0,
	"max_hp": 400,
	"upgrade_to": "vehicle_college_level_2",
	"unlocks": ["wood_vehicle", "stone_vehicle"],
}

const VEHICLE_COLLEGE_LEVEL_2: Dictionary = {
	"id": "vehicle_college_level_2",
	"category": Category.VEHICLE,
	"name": "Vehicle College Level 2",
	"description": "Old soldier monkey teaching vehicle techniques. Upgraded form of level 1.",
	"props": {
		"food_cost_note": "old soldier monkey for teaching monkey",
	},
	"cost": {"wood": 100, "stone": 100, "food": 1},
	"build_time": 120.0,
	"max_hp": 500,
	"upgrade_to": "vehicle_college_level_3",
}

const VEHICLE_COLLEGE_LEVEL_3: Dictionary = {
	"id": "vehicle_college_level_3",
	"category": Category.VEHICLE,
	"name": "Vehicle College Level 3",
	"description": "Old soldier monkey teaching vehicle techniques. Upgraded form of level 2.",
	"props": {
		"food_cost_note": "old soldier monkey for teaching monkey",
	},
	"cost": {"wood": 150, "stone": 150, "food": 1},
	"build_time": 180.0,
	"max_hp": 600,
}

const STRONG_MONKEY: Dictionary = {
	"id": "strong_monkey",
	"category": Category.VEHICLE,
	"name": "Strong Monkey",
	"description": "A powerful monkey that carries heavy loads. Automatically available from the start.",
	"props": {
		"carry_capacity": 30,
		"move_speed": 5.0,
	},
	"cost": {"food": 2},
	"build_time": 15.0,
	"max_hp": 120,
	"auto_enabled": true,
}

const WOOD_VEHICLE: Dictionary = {
	"id": "wood_vehicle",
	"category": Category.VEHICLE,
	"name": "Wood Vehicle",
	"description": "Vehicle specialized in hauling large amounts of wood.",
	"props": {
		"carry_capacity": 60,
		"move_speed": 7.0,
		"bonus_resource": "wood",
	},
	"cost": {"wood": 150, "food": 1},
	"build_time": 40.0,
	"max_hp": 300,
	"requires": "vehicle_college_level_1",
}

const STONE_VEHICLE: Dictionary = {
	"id": "stone_vehicle",
	"category": Category.VEHICLE,
	"name": "Stone Vehicle",
	"description": "Vehicle specialized in hauling large amounts of stone.",
	"props": {
		"carry_capacity": 60,
		"move_speed": 6.0,
		"bonus_resource": "stone",
	},
	"cost": {"wood": 100, "stone": 100, "food": 1},
	"build_time": 40.0,
	"max_hp": 400,
	"requires": "vehicle_college_level_1",
}

# ---------------------------------------------------------- level series
## Level series linking the independent level / upgrade entities above.
## Key: series id. Value: ordered array of building consts from the base form
## to the max, so the next level is always [code]series[level_index + 1][/code]:
## [codeblock]
## var series: Array = BuildingsConfig.LEVEL_SERIES["monkey_turret"]
## var idx := series.find(BuildingsConfig.MONKEY_TURRET_LEVEL_1)
## if idx + 1 < series.size():
## 	var next: Dictionary = series[idx + 1]
## [/codeblock]
const LEVEL_SERIES: Dictionary = {
	"banana_factory": [
		BANANA_FACTORY_LEVEL_1,
		BANANA_FACTORY_LEVEL_2,
		BANANA_FACTORY_LEVEL_3,
	],
	"wall": [
		WOODEN_WALL,
		STONE_WALL,
	],
	"gate": [
		WOODEN_GATE,
		STONE_GATE,
	],
	"defense_college": [
		DEFENSE_COLLEGE_LEVEL_1,
		DEFENSE_COLLEGE_LEVEL_2,
		DEFENSE_COLLEGE_LEVEL_3,
	],
	"monkey_turret": [
		MONKEY_TURRET_LEVEL_1,
		MONKEY_TURRET_LEVEL_2,
		MONKEY_TURRET_LEVEL_3,
	],
	"monkey_mangonel": [
		MONKEY_MANGONEL_LEVEL_1,
		MONKEY_MANGONEL_LEVEL_2,
		MONKEY_MANGONEL_LEVEL_3,
	],
	"army_college": [
		ARMY_COLLEGE_LEVEL_1,
		ARMY_COLLEGE_LEVEL_2,
		ARMY_COLLEGE_LEVEL_3,
	],
	"vehicle_college": [
		VEHICLE_COLLEGE_LEVEL_1,
		VEHICLE_COLLEGE_LEVEL_2,
		VEHICLE_COLLEGE_LEVEL_3,
	],
}

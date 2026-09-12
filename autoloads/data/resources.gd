class_name DocsResources
extends Node
## Global resource amounts for the survival game.
##
## Single source of truth for the player's current Wood / Stone / Food totals.
## TopBar (and any other HUD) reads from here and listens to [signal changed]
## instead of storing its own values, so all UI stays in sync.
##
## Resource *definitions* (name, id, order, icon color) live in
## [code]config/resources.gd[/code] ([ResourcesConfig]); this autoload only
## tracks the current *amount* of each resource, keyed by the definition's
## [code]id[/code].

signal changed(id: String, amount: int)

const ResourcesConfigRef := preload("res://config/resources.gd")

## Amounts keyed by resource id (e.g. "wood", "stone", "banana").
var amounts: Dictionary = {}

## Default amounts used on first load / when no save exists.
const DEFAULT_AMOUNTS := {
	"wood": 50,
	"stone": 30,
	"banana": 80,
}


func _ready() -> void:
	_reset_to_defaults()


## Resets all resources to their default values and emits [signal changed]
## for each one.
func _reset_to_defaults() -> void:
	amounts.clear()
	for r in _all_defs():
		var id: String = r["id"]
		amounts[id] = int(DEFAULT_AMOUNTS.get(id, 0))
		changed.emit(id, amounts[id])


## Sets the amount for a single resource id and emits [signal changed].
## Returns the new amount.
func set_amount(id: String, amount: int) -> int:
	amounts[id] = maxi(0, int(amount))
	changed.emit(id, amounts[id])
	return amounts[id]


## Adds [param delta] to a resource (may be negative) and emits [signal changed].
func add_amount(id: String, delta: int) -> int:
	return set_amount(id, amounts.get(id, 0) + delta)


## Reads the current amount for a resource id (0 if unknown).
func get_amount(id: String) -> int:
	return int(amounts.get(id, 0))


## All resource definitions from [ResourcesConfig].
func _all_defs() -> Array:
	var defs: Array = []
	for type_value in ResourcesConfigRef.Type.values():
		defs.append(_def_for_type(type_value))
	return defs


func _def_for_type(type_value: int) -> Dictionary:
	match type_value:
		ResourcesConfigRef.Type.STONE:
			return ResourcesConfigRef.STONE
		ResourcesConfigRef.Type.FOOD:
			return ResourcesConfigRef.FOOD
		_:
			return ResourcesConfigRef.WOOD


## ---- persistence (mirrors GameData / PlayerData save interface) ----

func serialize(file: FileAccess) -> void:
	# save the resource ids we track so load mirrors it robustly
	var ids := amounts.keys()
	file.store_32(ids.size())
	for id in ids:
		store_string(file, str(id))
		file.store_32(amounts[id])


func deserialize(file: FileAccess) -> void:
	amounts.clear()
	var count := file.get_32()
	for i in count:
		var id := get_string(file)
		amounts[id] = file.get_32()
		changed.emit(id, amounts[id])


func store_string(file: FileAccess, s: String) -> void:
	var bytes := s.to_utf8_buffer()
	file.store_32(bytes.size())
	file.store_buffer(bytes)


func get_string(file: FileAccess) -> String:
	var len := file.get_32()
	return file.get_buffer(len).get_string_from_utf8()
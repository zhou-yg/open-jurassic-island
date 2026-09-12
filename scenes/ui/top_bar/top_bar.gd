extends Control
## War3-style top bar HUD.
## Preloaded directly (not via the global class name) so headless validation
## and runtime do not depend on the editor's global script-class cache.
const ResourcesConfigRef := preload("res://config/resources.gd")

##
## Layout (mirrors Warcraft 3's top resource/time bar):
##   [ left: title/menu ]   [ center: clock (day/night) ]   [ right: 3 resources ]
##
## Resource definitions are pulled from [ResourcesConfig] (res://config/resources.gd),
## so adding a new resource there automatically adds a counter here.
##
## Public API:
##   set_time(hour, minute)         - set the in-game clock (0-24h), auto day/night
##   set_day_night(is_day)          - force the day/night indicator
##   advance_time(hours)            - advance the clock by N in-game hours
##   set_resource(id, amount)       - update one counter by resource id
##   set_resources(dict)            - update several counters at once
##
## Time flow:
##   The component can drive its own clock when [member auto_advance_time] is on:
##   [member day_length_seconds] = real seconds to cover one full in-game day.
##   Speed = 24h / day_length_seconds, so halving day_length doubles the speed.
##   Turn it off and drive the clock yourself via set_time()/advance_time().
##
## Signals:
##   time_changed(hour, minute)
##   resource_changed(id, amount)

signal time_changed(hour: int, minute: int)
signal resource_changed(id: String, amount: int)

static var DAY_START: float = 6.0   ## 06:00
static var DAY_END: float = 18.0    ## 18:00

## ---- configurable theme ----
@export var bar_height: float = 52.0
@export var bar_color: Color = Color(0.08, 0.08, 0.10, 0.92)
@export var accent_color: Color = Color(0.85, 0.68, 0.28)   ## War3 gold-ish accent
@export var day_color: Color = Color(1.0, 0.88, 0.45)       ## sun
@export var night_color: Color = Color(0.55, 0.65, 0.95)    ## moon

## ---- configurable time flow ----
@export var auto_advance_time: bool = false
	## When true, the component advances its own clock in _process.
@export var start_hour: float = 8.0
	## Clock value when the component is first added.
@export var day_length_seconds: float = 40.0
	## Real seconds per full in-game day. Speed = 24 / day_length_seconds.
	## e.g. 40s -> 1 day / 40s;  400s -> 1 day / ~6.7min.

## ---- runtime ----
var _hour: float = 8.0
var _minute: int = 0
var _is_day: bool = true

var _time_label: Label
var _daynight_label: Label
var _daynight_circle_node: Panel
var _counters: Dictionary = {}   # id -> Label


func _ready() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_TOP_WIDE)
	custom_minimum_size = Vector2(0, bar_height)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	_build_ui()
	_refresh_time_display()
	_register_all_resources()
	set_time(start_hour, 0)
	# Sync from the global Resources autoload and follow its changes.
	var rsrc := _resources_autoload()
	if rsrc != null:
		rsrc.changed.connect(_on_resources_changed)
		_seed_from_resources()


func _resources_autoload() -> Node:
	for child in get_tree().root.get_children():
		if child.name == "Resources" and child.has_method("get_amount"):
			return child
	return null


func _on_resources_changed(id: String, amount: int) -> void:
	set_resource(id, amount)


func _seed_from_resources() -> void:
	var rsrc := _resources_autoload()
	if rsrc == null:
		return
	for id in _counters:
		set_resource(id, rsrc.get_amount(id))


func _process(delta: float) -> void:
	if auto_advance_time:
		var h := float(delta) * (24.0 / day_length_seconds)
		_advance_clock(h)


# ------------------------------------------------------------------ build UI

func _build_ui() -> void:
	# Background frame
	var frame := PanelContainer.new()
	frame.name = "Frame"
	frame.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	frame.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var style := StyleBoxFlat.new()
	style.bg_color = bar_color
	style.border_color = accent_color
	style.set_border_width_all(1)
	style.corner_radius_bottom_left = 8
	style.corner_radius_bottom_right = 8
	style.content_margin_top = 2.0
	style.content_margin_bottom = 2.0
	frame.add_theme_stylebox_override("panel", style)
	add_child(frame)

	var hbox := HBoxContainer.new()
	hbox.name = "MainRow"
	hbox.mouse_filter = Control.MOUSE_FILTER_IGNORE
	hbox.add_theme_constant_override("separation", 10)
	frame.add_child(hbox)

	# Left zone: game title (mirrors War3's faction/menu area)
	var left := HBoxContainer.new()
	left.name = "LeftZone"
	left.mouse_filter = Control.MOUSE_FILTER_IGNORE
	left.add_theme_constant_override("separation", 8)
	left.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	hbox.add_child(left)

	var title := Label.new()
	title.name = "TitleLabel"
	title.text = "Jurassic Island"
	title.add_theme_font_size_override("font_size", 22)
	title.add_theme_color_override("font_color", accent_color)
	title.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	left.add_child(title)

	# Center zone: clock (day/night)
	var center := HBoxContainer.new()
	center.name = "CenterZone"
	center.mouse_filter = Control.MOUSE_FILTER_IGNORE
	center.add_theme_constant_override("separation", 8)
	center.alignment = BoxContainer.ALIGNMENT_CENTER
	center.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	hbox.add_child(center)

	# day/night circle indicator
	var circle := Panel.new()
	circle.name = "DayNightCircle"
	circle.custom_minimum_size = Vector2(26, 26)
	circle.mouse_filter = Control.MOUSE_FILTER_IGNORE
	center.add_child(circle)
	_daynight_circle_node = circle
	_update_circle_color(day_color)

	var time_label := Label.new()
	time_label.name = "TimeLabel"
	time_label.add_theme_font_size_override("font_size", 24)
	time_label.add_theme_color_override("font_color", Color.WHITE)
	time_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	center.add_child(time_label)
	_time_label = time_label

	var daynight_label := Label.new()
	daynight_label.name = "DayNightLabel"
	daynight_label.add_theme_font_size_override("font_size", 16)
	daynight_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	center.add_child(daynight_label)
	_daynight_label = daynight_label

	# Right zone: resource counters
	var right := HBoxContainer.new()
	right.name = "RightZone"
	right.mouse_filter = Control.MOUSE_FILTER_IGNORE
	right.add_theme_constant_override("separation", 16)
	right.alignment = BoxContainer.ALIGNMENT_END
	right.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	hbox.add_child(right)

	# added a right spacer container so the counters hug the right edge
	var right_spacer := Control.new()
	right_spacer.name = "RightSpacer"
	right_spacer.custom_minimum_size = Vector2(24, 0)
	right_spacer.mouse_filter = Control.MOUSE_FILTER_IGNORE
	right.add_child(right_spacer)


# ------------------------------------------------------------------- time

## Set the in-game clock. Auto-derives day/night from the hour.
func set_time(hour: float, minute: int = 0) -> void:
	_hour = fposmod(hour, 24.0)
	_minute = clampi(minute, 0, 59)
	_is_day = _default_is_day(_hour)
	_refresh_time_display()
	time_changed.emit(int(_hour), _minute)


func set_day_night(is_day: bool) -> void:
	_is_day = is_day
	_refresh_time_display()


## Advance the in-game clock by [param hours] and ring around past 24h.
func advance_time(hours: float) -> void:
	_advance_clock(hours)


func _advance_clock(hours: float) -> void:
	var total := fposmod(_hour + hours, 24.0)
	set_time(total)


func get_hour() -> float:
	return _hour


func is_day() -> bool:
	return _is_day


func _default_is_day(h: float) -> bool:
	return h >= DAY_START and h < DAY_END


func _refresh_time_display() -> void:
	var h := int(_hour)
	var mm := _minute
	var period := "AM" if _hour < 12.0 else "PM"
	var h12 := h % 12
	if h12 == 0:
		h12 = 12
	_time_label.text = "%02d:%02d %s" % [h12, mm, period]
	_daynight_label.text = "Day" if _is_day else "Night"
	_daynight_label.add_theme_color_override(
		"font_color", day_color if _is_day else night_color)
	_update_circle_color(day_color if _is_day else night_color)


func _update_circle_color(c: Color) -> void:
	if _daynight_circle_node == null:
		return
	var style := StyleBoxFlat.new()
	style.bg_color = c
	style.corner_radius_top_left = 13
	style.corner_radius_top_right = 13
	style.corner_radius_bottom_left = 13
	style.corner_radius_bottom_right = 13
	_daynight_circle_node.add_theme_stylebox_override("panel", style)


# --------------------------------------------------------------- resources

func _register_all_resources() -> void:
	for r in _all_resource_defs():
		_add_counter(r.id, r.name)


func _all_resource_defs() -> Array:
	var defs := []
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


func _add_counter(id: String, display_name: String) -> void:
	var right := _find_right_zone()
	if right == null:
		return
	var counter := _make_counter(display_name)
	right.add_child(counter)
	_counters[id] = counter.find_child("Count", true, false) as Label


## Public: set or create a counter for a resource id.
func set_resource(id: String, amount: int) -> void:
	if not _counter_exists(id):
		var def := _def_for_id(id)
		_add_counter(id, def["name"])
	if _counters.has(id):
		_counters[id].text = str(amount)
	resource_changed.emit(id, amount)


## Public: bulk-update several resources at once.
func set_resources(dict: Dictionary) -> void:
	for id in dict:
		set_resource(str(id), int(dict[id]))


func _counter_exists(id: String) -> bool:
	return _counters.has(id)


## Registry of known resource ids (so set_resource also auto-creates).
func _def_for_id(id: String) -> Dictionary:
	if id == ResourcesConfigRef.STONE["id"]:
		return ResourcesConfigRef.STONE
	if id == ResourcesConfigRef.FOOD["id"]:
		return ResourcesConfigRef.FOOD
	return ResourcesConfigRef.WOOD


func _find_right_zone() -> HBoxContainer:
	var hbox := find_child("MainRow", true, false) as HBoxContainer
	if hbox == null:
		return null
	return hbox.get_child(2) as HBoxContainer  # RightZone


## Builds one War3-style resource cell: [icon swatch] [name small] [count big].
func _make_counter(name: String) -> PanelContainer:
	var cell := PanelContainer.new()
	cell.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var style := StyleBoxFlat.new()
	style.bg_color = Color(0, 0, 0, 0.25)
	style.border_color = Color(0.35, 0.35, 0.4, 1)
	style.set_border_width_all(1)
	style.corner_radius_top_left = 6
	style.corner_radius_top_right = 6
	style.corner_radius_bottom_left = 6
	style.corner_radius_bottom_right = 6
	style.content_margin_left = 8.0
	style.content_margin_right = 10.0
	style.content_margin_top = 2.0
	style.content_margin_bottom = 2.0
	cell.add_theme_stylebox_override("panel", style)

	var row := HBoxContainer.new()
	row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	row.add_theme_constant_override("separation", 6)
	cell.add_child(row)

	# icon swatch
	var icon := ColorRect.new()
	icon.custom_minimum_size = Vector2(22, 22)
	icon.mouse_filter = Control.MOUSE_FILTER_IGNORE
	icon.color = _color_for_name(name)
	row.add_child(icon)

	var col := VBoxContainer.new()
	col.mouse_filter = Control.MOUSE_FILTER_IGNORE
	col.add_theme_constant_override("separation", 0)
	row.add_child(col)

	var name_label := Label.new()
	name_label.text = name
	name_label.add_theme_font_size_override("font_size", 11)
	name_label.add_theme_color_override("font_color", Color(0.8, 0.8, 0.82))
	name_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	col.add_child(name_label)

	var count := Label.new()
	count.name = "Count"
	count.text = "0"
	count.add_theme_font_size_override("font_size", 20)
	count.add_theme_color_override("font_color", Color.WHITE)
	count.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	col.add_child(count)

	return cell


func _color_for_name(name: String) -> Color:
	var n := name.to_lower()
	if n.find("wood") != -1:
		return Color(0.62, 0.42, 0.20)
	if n.find("stone") != -1:
		return Color(0.55, 0.55, 0.58)
	if n.find("food") != -1 or n.find("banana") != -1:
		return Color(0.85, 0.75, 0.15)
	return accent_color
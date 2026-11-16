extends Button
##
## **「锁定鼠标 (F)」按钮** —— 和 [GodViewportCamera] 自动联动。
##
## 挂在 HUD 的 Button 上就行，**不用写任何接线**：
## 相机启动时会进 `god_viewport_camera` 组，按钮靠组找到它，
## 然后：
##
## - 点按钮 = 锁定 / 释放鼠标
## - 按钮文字跟着锁定状态变（「锁定鼠标 (F)」↔「释放鼠标 (F)」）
## - 锁定时把准星显示出来（准星 = 场景里一个叫 `Crosshair` 的 Label）
##
## 要用自己的相机？把 [member GodViewportCamera.GROUP] 组里的那个换掉就行。

## 准星节点的名字（找到就把 `visible` 打开）。
const CROSSHAIR_NAME := "Crosshair"

@onready var _camera: GodViewportCamera = _find_camera()
@onready var _crosshair: Control = _find_crosshair()


func _ready() -> void:
	if _camera == null:
		# 场景里还没有相机（刚实例化还没进树）：下一帧再找一次
		await get_tree().process_frame
		_camera = _find_camera()
	if _camera == null:
		push_warning("[GodViewportCaptureButton] 没找到 GodViewportCamera，"
				+ "「锁定鼠标」按钮不会工作")
		return
	_camera.capture_changed.connect(_on_capture_changed)
	_on_capture_changed(_camera.is_captured())
	pressed.connect(_toggle_capture)


func _toggle_capture() -> void:
	if _camera != null:
		_camera.toggle_capture()


func _on_capture_changed(captured: bool) -> void:
	text = "释放鼠标 (F)" if captured else "锁定鼠标 (F)"
	set_pressed_no_signal(captured)
	if _crosshair != null:
		_crosshair.visible = captured


func _find_camera() -> GodViewportCamera:
	for node in get_tree().get_nodes_in_group(GodViewportCamera.GROUP):
		var camera := node as GodViewportCamera
		if camera != null:
			return camera
	return null


func _find_crosshair() -> Control:
	# 在同一个 CanvasLayer 里找准星（找不到就当没有）
	var layer := _find_canvas_layer()
	if layer == null:
		return null
	return layer.get_node_or_null(CROSSHAIR_NAME) as Control


func _find_canvas_layer() -> CanvasLayer:
	var node := get_parent()
	while node != null:
		if node is CanvasLayer:
			return node as CanvasLayer
		node = node.get_parent()
	return null

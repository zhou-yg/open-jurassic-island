@tool
extends EditorPlugin

## 本插件把「播放音效」的便捷 API 注册成 [code]QuickAudio[/code] 全局单例。
##
## ⚠️ **不要**再占用 [code]Audio[/code] 这个名字。
##
## 项目自己的音频管理器是 [code]res://autoloads/audio.gd[/code]（注册为全局
## [code]Audio[/code]），它提供 [code]AudioServer[/code] 总线音量接口：
## [code]get_volume()[/code] / [code]set_volume()[/code] /
## [code]mute_bus()[/code] / [code]fade_in()[/code] / [code]fade_out()[/code]。
## 设置菜单（[code]scenes/menus/settings_menu/[/code]）和
## [code]autoloads/user_prefs/user_prefs.gd[/code] 都依赖这些接口。
##
## 本插件自带的 [code]Audio.gd[/code] 只有 [code]play_sound()[/code] 之类的
## 播放接口，两套 API 不能共用一个名字。
## 另外本插件的 [code]_enter_tree()[/code] 每次开编辑器都会执行，
## 会覆盖 [code]project.godot[/code] 里的同名 autoload —— 所以名字必须区分开。

func _enter_tree():
  add_autoload_singleton("QuickAudio", "./Audio.gd")

func _exit_tree():
  remove_autoload_singleton("QuickAudio")

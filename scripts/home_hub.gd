extends Control

const SCENE_BOXING := "res://scenes/main_menu.tscn"
const SCENE_SETTINGS := "res://scenes/ui/settings_panel.tscn"
const SCENE_STATS := "res://scenes/ui/stats_panel.tscn"

@onready var _btn_boxing: Button = $Root/Center/VBox/BtnBoxing
@onready var _btn_settings: Button = $Root/Center/VBox/BtnSettings
@onready var _btn_stats: Button = $Root/Center/VBox/BtnStats
@onready var _btn_quit: Button = $Root/Center/VBox/BtnQuit

var _settings_panel: Control
var _stats_panel: Control


func _ready() -> void:
	if _btn_boxing:
		_btn_boxing.pressed.connect(_on_boxing)
	if _btn_settings:
		_btn_settings.pressed.connect(_on_settings)
	if _btn_stats:
		_btn_stats.pressed.connect(_on_stats)
	if _btn_quit:
		_btn_quit.pressed.connect(_on_quit)


func _on_boxing() -> void:
	get_tree().change_scene_to_file(SCENE_BOXING)


func _on_settings() -> void:
	if _settings_panel:
		return
	var packed := load(SCENE_SETTINGS) as PackedScene
	if not packed:
		return
	_settings_panel = packed.instantiate() as Control
	if _settings_panel:
		add_child(_settings_panel)
		_settings_panel.set_anchors_preset(Control.PRESET_FULL_RECT)
		if _settings_panel.has_signal("back_pressed"):
			_settings_panel.back_pressed.connect(_close_settings)


func _close_settings() -> void:
	if _settings_panel:
		_settings_panel.queue_free()
		_settings_panel = null


func _on_stats() -> void:
	if _stats_panel:
		return
	var packed := load(SCENE_STATS) as PackedScene
	if not packed:
		return
	_stats_panel = packed.instantiate() as Control
	if _stats_panel:
		add_child(_stats_panel)
		_stats_panel.set_anchors_preset(Control.PRESET_FULL_RECT)
		if _stats_panel.has_signal("back_pressed"):
			_stats_panel.back_pressed.connect(_close_stats)


func _close_stats() -> void:
	if _stats_panel:
		_stats_panel.queue_free()
		_stats_panel = null


func _on_quit() -> void:
	GameState.shutdown_webcam_ml_bridge()
	get_tree().quit()


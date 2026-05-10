extends Control

const SCENE_BOXING := "res://scenes/main_menu.tscn"
const SCENE_SETTINGS := "res://scenes/ui/settings_panel.tscn"
const SCENE_USER_INFO := "res://scenes/ui/stats_panel.tscn"
const SCENE_GAME_RECORDS := "res://scenes/ui/game_records_panel.tscn"

@onready var _btn_boxing: Button = $Root/Center/VBox/BtnBoxing
@onready var _btn_settings: Button = $Root/Center/VBox/BtnSettings
@onready var _btn_game_records: Button = $Root/Center/VBox/BtnGameRecords
@onready var _btn_user_info: Button = $Root/Center/VBox/BtnUserInfo
@onready var _btn_quit: Button = $Root/Center/VBox/BtnQuit

var _settings_panel: Control
var _user_info_panel: Control
var _game_records_panel: Control


func _ready() -> void:
	if _btn_boxing:
		_btn_boxing.pressed.connect(_on_boxing)
	if _btn_settings:
		_btn_settings.pressed.connect(_on_settings)
	if _btn_game_records:
		_btn_game_records.pressed.connect(_on_game_records)
	if _btn_user_info:
		_btn_user_info.pressed.connect(_on_user_info)
	if _btn_quit:
		_btn_quit.pressed.connect(_on_quit)
	_beautify_ui()

func _beautify_ui() -> void:
	var root: Control = $Root
	var bg: ColorRect = $Root/Bg
	if bg:
		bg.color = UIThemeHelper.C_BG

	# Title
	var title: Label = $Root/Center/VBox/Title
	if title:
		UIThemeHelper.style_label_title(title)

	var sub: Label = $Root/Center/VBox/SubTitle
	if sub:
		UIThemeHelper.style_label_caption(sub)
		sub.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER

	# Style buttons
	UIThemeHelper.style_button_primary(_btn_boxing)
	UIThemeHelper.style_button_secondary(_btn_settings)
	UIThemeHelper.style_button_secondary(_btn_game_records)
	UIThemeHelper.style_button_secondary(_btn_user_info)
	UIThemeHelper.style_button_danger(_btn_quit)

	# Make buttons wider and add spacing
	var vbox: VBoxContainer = $Root/Center/VBox
	vbox.add_theme_constant_override("separation", 12)
	for btn: Button in [_btn_boxing, _btn_settings, _btn_game_records, _btn_user_info, _btn_quit]:
		if btn == null:
			continue
		btn.custom_minimum_size = Vector2(320, 48)

	# PanelContainer glass style for the whole center area? No, it's a CenterContainer.
	# Instead, wrap the VBox in a PanelContainer with glass style
	var center: CenterContainer = $Root/Center
	var old_vbox: VBoxContainer = $Root/Center/VBox
	if center and old_vbox:
		# Reparent vbox into a PanelContainer
		center.remove_child(old_vbox)
		var glass := PanelContainer.new()
		UIThemeHelper.style_panel_container_glass(glass)
		glass.add_child(old_vbox)
		center.add_child(glass)
		old_vbox.add_theme_constant_override("separation", 14)
		# NOTE: CenterContainer가 자동 중앙정렬하므로 alignment 설정 불필요



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


func _on_user_info() -> void:
	if _user_info_panel:
		return
	var packed := load(SCENE_USER_INFO) as PackedScene
	if not packed:
		return
	_user_info_panel = packed.instantiate() as Control
	if _user_info_panel:
		add_child(_user_info_panel)
		_user_info_panel.set_anchors_preset(Control.PRESET_FULL_RECT)
		if _user_info_panel.has_signal("back_pressed"):
			_user_info_panel.back_pressed.connect(_close_user_info)


func _close_user_info() -> void:
	if _user_info_panel:
		_user_info_panel.queue_free()
		_user_info_panel = null


func _on_game_records() -> void:
	if _game_records_panel:
		return
	var packed := load(SCENE_GAME_RECORDS) as PackedScene
	if not packed:
		return
	_game_records_panel = packed.instantiate() as Control
	if _game_records_panel:
		add_child(_game_records_panel)
		_game_records_panel.set_anchors_preset(Control.PRESET_FULL_RECT)
		if _game_records_panel.has_signal("back_pressed"):
			_game_records_panel.back_pressed.connect(_close_game_records)


func _close_game_records() -> void:
	if _game_records_panel:
		_game_records_panel.queue_free()
		_game_records_panel = null


func _on_quit() -> void:
	GameState.shutdown_webcam_ml_bridge()
	get_tree().quit()

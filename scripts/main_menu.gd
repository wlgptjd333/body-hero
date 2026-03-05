extends Control
## 메인 메뉴: 게임 시작, 게임 설명, 설정, 종료 (오른쪽 세로 버튼)

const SCENE_GAME := "res://scenes/main.tscn"
const SCENE_SETTINGS := "res://scenes/ui/settings_panel.tscn"
const SCENE_HOW_TO_PLAY := "res://scenes/ui/how_to_play_panel.tscn"

@onready var _buttons_container: VBoxContainer = $RightPanel/ButtonBox
@onready var _btn_start: Button = $RightPanel/ButtonBox/BtnStart
@onready var _btn_how_to_play: Button = $RightPanel/ButtonBox/BtnHowToPlay
@onready var _btn_settings: Button = $RightPanel/ButtonBox/BtnSettings
@onready var _btn_quit: Button = $RightPanel/ButtonBox/BtnQuit

var _settings_panel: Control
var _how_to_play_panel: Control


func _ready() -> void:
	var bgm: AudioStreamPlayer = get_node_or_null("BGM")
	if bgm:
		if AudioServer.get_bus_index("Music") >= 0:
			bgm.bus = "Music"
		# 파일이 아직 없으면 씬이 깨질 수 있어, 런타임에 존재하는 경로만 로드
		if bgm.stream == null:
			_try_load_stream(bgm, [
				"res://assets/audio/bgm/mainbgm.ogg",
				"res://assets/audio/bgm/bgm_main.ogg",
				"res://assets/audio/mainbgm.ogg",
				"res://assets/audio/bgm_main.ogg",
			])
		if bgm.stream and bgm.playing == false:
			bgm.play()
	if _btn_start:
		_btn_start.pressed.connect(_on_start)
	if _btn_how_to_play:
		_btn_how_to_play.pressed.connect(_on_how_to_play)
	if _btn_settings:
		_btn_settings.pressed.connect(_on_settings)
	if _btn_quit:
		_btn_quit.pressed.connect(_on_quit)


func _try_load_stream(player: AudioStreamPlayer, paths: Array[String]) -> void:
	for p in paths:
		if ResourceLoader.exists(p):
			var res := load(p)
			if res is AudioStream:
				player.stream = res
				return


func _on_start() -> void:
	get_tree().change_scene_to_file(SCENE_GAME)


func _on_how_to_play() -> void:
	if _how_to_play_panel:
		return
	var packed := load(SCENE_HOW_TO_PLAY) as PackedScene
	if not packed:
		return
	_how_to_play_panel = packed.instantiate() as Control
	if _how_to_play_panel:
		add_child(_how_to_play_panel)
		_how_to_play_panel.set_anchors_preset(Control.PRESET_FULL_RECT)
		if _how_to_play_panel.has_signal("back_pressed"):
			_how_to_play_panel.back_pressed.connect(_close_how_to_play)


func _close_how_to_play() -> void:
	if _how_to_play_panel:
		_how_to_play_panel.queue_free()
		_how_to_play_panel = null


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


func _on_quit() -> void:
	get_tree().quit()

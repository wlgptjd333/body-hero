extends Node2D
## 메인 게임 로직 + UDP로 웹캠(파이썬) 액션 수신
## 데이터 형식: "jab_l" | "jab_r" | "upper_l" | "upper_r" | "hook_l" | "hook_r" | "guard" (행동 발생 시만 전송)

const VALID_ACTIONS := ["jab_l", "jab_r", "upper_l", "upper_r", "hook_l", "hook_r", "guard", "guard_end", "dodge_l", "dodge_r", "jog"]

var _server: UDPServer
var _port := 4242
# true면 레거시 좌표 "x,y,x,y" 도 처리 (디버그용)
var _use_position_mode := false
var _debug_received := true
var _received_count := 0

@onready var _player: Node2D = $Player
@onready var _enemy: Node2D = $Enemy
@onready var _enemy_hp_label: Label = $HUD/TopBar/EnemyHPLabel
@onready var _background: Sprite2D = $Background
# Leftovers KO 스타일 바 (상단 적, 하단 플레이어 HP/스태미너)
@onready var _enemy_hp_fill: ColorRect = $HUD/TopBar/EnemyHPBarFill
@onready var _enemy_hp_bg: ColorRect = $HUD/TopBar/EnemyHPBarBg
@onready var _player_hp_fill: ColorRect = $HUD/BottomBars/PlayerHPBarFill
@onready var _player_stamina_fill: ColorRect = $HUD/BottomBars/PlayerStaminaBarFill
@onready var _bgm: AudioStreamPlayer = $BGM
@onready var _pause_layer: CanvasLayer = $PauseLayer
@onready var _btn_pause_settings: Button = $PauseLayer/PauseVBox/BtnPauseSettings
@onready var _btn_pause_quit: Button = $PauseLayer/PauseVBox/BtnPauseQuit

const SCENE_MAIN_MENU := "res://scenes/main_menu.tscn"
const SCENE_SETTINGS := "res://scenes/ui/settings_panel.tscn"

var _paused := false
var _settings_in_pause: Control


func _ready() -> void:
	if _btn_pause_settings:
		_btn_pause_settings.pressed.connect(_on_pause_settings)
	if _btn_pause_quit:
		_btn_pause_quit.pressed.connect(_on_pause_quit)
	_fit_background_to_viewport()
	var vp := get_viewport()
	if vp.size_changed.is_connected(_fit_background_to_viewport) == false:
		vp.size_changed.connect(_fit_background_to_viewport)
	if _enemy and _enemy.has_signal("hit_received"):
		_enemy.hit_received.connect(_on_enemy_hit)
	if _enemy and _enemy.has_signal("died"):
		_enemy.died.connect(_on_enemy_died)
	_update_enemy_hp_label()
	if _bgm:
		if AudioServer.get_bus_index("Music") >= 0:
			_bgm.bus = "Music"
		if _bgm.stream == null:
			_try_load_stream(_bgm, [
				"res://assets/audio/bgm/mainbgm.ogg",
				"res://assets/audio/bgm/bgm_main.ogg",
				"res://assets/audio/mainbgm.ogg",
				"res://assets/audio/bgm_main.ogg",
			])
		if _bgm.stream and _bgm.playing == false:
			_bgm.play()
	if _enemy:
		var hit_sound: AudioStreamPlayer = _enemy.get_node_or_null("HitSound")
		if hit_sound and AudioServer.get_bus_index("SFX") >= 0:
			hit_sound.bus = "SFX"
		# 사용자가 파일을 assets/audio/sfx/ 로 옮기면 자동으로 반영 (씬 수정 없이도 동작)
		if hit_sound and hit_sound.stream == null:
			_try_load_stream(hit_sound, [
				"res://assets/audio/sfx/sfx_punch_hit.wav",
				"res://assets/audio/sfx_punch_hit.wav",
			])
	_server = UDPServer.new()
	if _server.listen(_port) != OK:
		push_error("UDP 서버 포트 %d 열기 실패" % _port)
	else:
		print("UDP 서버 시작... 포트: ", _port, " (액션: jab, upper, hook, guard, dodge_l/r, jog)")


func _try_load_stream(player: AudioStreamPlayer, paths: Array[String]) -> void:
	for p in paths:
		if ResourceLoader.exists(p):
			var res := load(p)
			if res is AudioStream:
				player.stream = res
				return


func _process(_delta: float) -> void:
	if Input.is_action_just_pressed("ui_cancel"):
		if _settings_in_pause:
			_close_pause_settings()
		else:
			_toggle_pause()
	if _paused:
		return
	_update_ui_bars()
	_server.poll()
	while _server.is_connection_available():
		var peer: PacketPeerUDP = _server.take_connection()
		var packet: PackedByteArray = peer.get_packet()
		var data := packet.get_string_from_utf8().strip_edges()
		if data.is_empty():
			continue
		_received_count += 1
		if _debug_received and _received_count == 1:
			print("UDP 수신됨! (액션 연동 정상) 데이터: ", data)
		_apply_glove_data(data)


func _apply_glove_data(data: String) -> void:
	if data in VALID_ACTIONS:
		if data == "jog":
			GameState.tick_jog()
		elif _player.has_method("play_action"):
			_player.play_action(data)
		return
	# 레거시: "left_x,left_y,right_x,right_y" (디버그용, _use_position_mode 시에만)
	if _use_position_mode:
		var parts := data.split(",")
		if parts.size() >= 4 and _player.has_method("update_gloves_position"):
			var view_size := _get_view_size()
			var player_global := _player.global_position
			var lx := float(parts[0].strip_edges())
			var ly := float(parts[1].strip_edges())
			var rx := float(parts[2].strip_edges())
			var ry := float(parts[3].strip_edges())
			_player.update_gloves_position(
				Vector2(lx * view_size.x, ly * view_size.y) - player_global,
				Vector2(rx * view_size.x, ry * view_size.y) - player_global
			)


func _get_view_size() -> Vector2:
	var vp := get_viewport()
	if vp:
		return vp.get_visible_rect().size
	return Vector2(1152, 648)


## 해상도(뷰포트 크기)에 맞춰 배경 스케일·위치를 자동 보정
## (화면에 공백이 안 보이도록, 넘어가는 부분은 잘리는 방식)
func _fit_background_to_viewport() -> void:
	if not _background or not _background.texture:
		return
	var view_size := _get_view_size()
	var tex_size := _background.texture.get_size()
	if tex_size.x <= 0 or tex_size.y <= 0:
		return
	# 기존: minf(...) → 배경 전체는 보이지만, 화면 비율이 다르면 좌우/상하에 공백이 생김.
	# 변경: maxf(...) → 화면을 꽉 채우고, 남는 부분은 화면 밖으로 잘라냄.
	var scale_factor := maxf(view_size.x / tex_size.x, view_size.y / tex_size.y)
	_background.scale = Vector2(scale_factor, scale_factor)
	_background.position = view_size / 2


func _on_enemy_hit(_damage: float) -> void:
	_update_enemy_hp_label()


func _on_enemy_died() -> void:
	_update_enemy_hp_label()
	if _enemy_hp_label:
		_enemy_hp_label.text = "KO!"


func _update_enemy_hp_label() -> void:
	# 상단 바는 _update_ui_bars에서 갱신. 라벨 텍스트는 적 사망 시 _on_enemy_died에서 "KO!"로 변경
	pass  # 필요 시 여기서 적 이름/HP 텍스트 갱신


func _toggle_pause() -> void:
	_paused = not _paused
	if _pause_layer:
		_pause_layer.visible = _paused


func _on_pause_settings() -> void:
	if _settings_in_pause:
		return
	var packed := load(SCENE_SETTINGS) as PackedScene
	if not packed:
		return
	_settings_in_pause = packed.instantiate() as Control
	if _settings_in_pause:
		_pause_layer.add_child(_settings_in_pause)
		_settings_in_pause.set_anchors_preset(Control.PRESET_FULL_RECT)
		if _settings_in_pause.has_signal("back_pressed"):
			_settings_in_pause.back_pressed.connect(_close_pause_settings)


func _close_pause_settings() -> void:
	if _settings_in_pause:
		_settings_in_pause.queue_free()
		_settings_in_pause = null


func _on_pause_quit() -> void:
	get_tree().paused = false
	get_tree().change_scene_to_file(SCENE_MAIN_MENU)


func _update_ui_bars() -> void:
	# 상단: 적 체력바 (배경과 같은 높이, 왼쪽 정렬 폭만 비율로)
	if _enemy_hp_bg and _enemy_hp_fill and _enemy and "current_hp" in _enemy and "max_hp" in _enemy:
		var w := _enemy_hp_bg.size.x
		if w > 0.0:
			var ratio: float = _enemy.current_hp / _enemy.max_hp if _enemy.max_hp > 0.0 else 1.0
			_enemy_hp_fill.position = _enemy_hp_bg.position
			_enemy_hp_fill.size = Vector2(w * clampf(ratio, 0.0, 1.0), _enemy_hp_bg.size.y)
	# 하단: 플레이어 HP / 스태미너
	var bottom := $HUD/BottomBars
	if bottom:
		var hp_bg := bottom.get_node_or_null("PlayerHPBarBg") as ColorRect
		if hp_bg and _player_hp_fill:
			var r: float = GameState.get_player_hp_ratio()
			_player_hp_fill.position = hp_bg.position
			_player_hp_fill.size = Vector2(hp_bg.size.x * r, hp_bg.size.y)
		var st_bg := bottom.get_node_or_null("PlayerStaminaBarBg") as ColorRect
		if st_bg and _player_stamina_fill:
			var r: float = GameState.get_stamina_ratio()
			_player_stamina_fill.position = st_bg.position
			_player_stamina_fill.size = Vector2(st_bg.size.x * r, st_bg.size.y)

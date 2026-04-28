extends Node2D
## 메인 게임 로직 + UDP로 웹캠(파이썬) 액션 수신
## 데이터 형식: "punch_l" | "punch_r" | "upper_l" | "upper_r" | "guard" | "dodge" (행동 발생 시만 전송)
## 쿨타임·중복 방지: 펀치류 액션 최소 간격(초).
## ML이 이미 MIN_GAP·재장전으로 간격을 맞추므로, 여기는 ML보다 짧게 두면 게임이 추가로 잡아먹지 않음(체감 반응↑).

const VALID_ACTIONS := ["punch_l", "punch_r", "upper_l", "upper_r", "guard", "guard_end", "dodge"]
# 펀치/어퍼: ML MIN_GAP(~0.10~0.22)보다 짧게 두어 Godot이 추가로 잡아먹지 않게.
@export var action_cooldown_sec: float = 0.015
## false면 tools의 udp_send_webcam_ml.py를 자동으로 띄우지 않음(수동 실행·키보드만).
@export var auto_launch_webcam_ml: bool = true
## 씬 로드 직후 즉시 기동하면 Godot I/O와 겹쳐 TensorFlow 첫 로드가 매우 느려질 수 있음. 0이면 1프레임만 양보 후 즉시.
@export var webcam_ml_scene_load_delay_sec: float = 4.0
const PUNCH_ACTIONS := ["punch_l", "punch_r", "upper_l", "upper_r"]

var _server: UDPServer
var _port := 4242
# true면 레거시 좌표 "x,y,x,y" 도 처리 (디버그용)
var _use_position_mode := false
var _debug_received := true
var _received_count := 0
# 마지막으로 펀치류 액션을 수락한 시각 (쿨타임 검사용)
var _last_punch_accepted_time: float = -999.0
@onready var _player: Node2D = $Player
@onready var _enemy: Node2D = $Enemy
@onready var _enemy_hp_label: Label = $HUD/TopBar/EnemyHPLabel
@onready var _background: Sprite2D = $Background
# 상단 적 HP 바, 하단 플레이어 HP/스태미너 바 (ProgressBar)
@onready var _play_time_label: Label = $HUD/PlayTimeCorner
@onready var _combo_label: Label = $Enemy/ComboLabel
@onready var _enemy_hp_bar: ProgressBar = $HUD/TopBar/EnemyHPBar
@onready var _player_hp_bar: ProgressBar = $HUD/BottomBars/PlayerHPBar
@onready var _player_stamina_bar: ProgressBar = $HUD/BottomBars/PlayerStaminaBar
@onready var _bgm: AudioStreamPlayer = $BGM
@onready var _pause_layer: CanvasLayer = $PauseLayer
@onready var _btn_pause_icon: Button = $HUD/BtnPauseIcon
@onready var _btn_pause_resume: Button = $PauseLayer/PauseVBox/BtnPauseResume
@onready var _btn_pause_settings: Button = $PauseLayer/PauseVBox/BtnPauseSettings
@onready var _btn_pause_quit: Button = $PauseLayer/PauseVBox/BtnPauseQuit

const SCENE_MAIN := "res://games/boxing/scenes/main.tscn"
const SCENE_MAIN_MENU := "res://scenes/main_menu.tscn"
const SCENE_SETTINGS := "res://scenes/ui/settings_panel.tscn"

var _paused := false
var _settings_in_pause: Control
var _game_over_shown := false
var _win_shown := false
## 타임어택: 스테이지 진입~KO까지(일시정지 시간 제외)
var _stage_timer_active: bool = true
var _stage_elapsed_sec: float = 0.0
## 연속 타격 콤보 (적에게 플레이어가 맞으면 초기화)
var _combo_count: int = 0

@onready var _game_over_layer: CanvasLayer = $GameOverLayer
@onready var _ko_intro_layer: CanvasLayer = $KoIntroLayer
@onready var _win_layer: CanvasLayer = $WinLayer
@onready var _game_over_calories_label: Label = $GameOverLayer/GameOverVBox/GameOverCaloriesLabel
@onready var _win_calories_label: Label = $WinLayer/WinVBox/WinCaloriesLabel
@onready var _game_over_daily_calories_label: Label = $GameOverLayer/GameOverVBox/GameOverDailyCaloriesLabel
@onready var _win_daily_calories_label: Label = $WinLayer/WinVBox/WinDailyCaloriesLabel
@onready var _win_clear_time_label: Label = $WinLayer/WinVBox/WinClearTimeLabel

func _ready() -> void:
	# 어떤 경로로 진입하든(메뉴/허브/재시작) 이전 씬의 paused가 남아있지 않게 안전장치
	get_tree().paused = false
	_paused = false
	# 일시정지 시에도 일시정지 레이어·게임오버·승리 레이어만 입력/표시되도록 ALWAYS.
	# Main 자체는 ALWAYS가 아니어야 함 → get_tree().paused 시 Enemy, Player, GameState 등이 멈춤.
	if _pause_layer:
		_pause_layer.process_mode = Node.PROCESS_MODE_ALWAYS
		_pause_layer.visible = false
	if _game_over_layer:
		_game_over_layer.process_mode = Node.PROCESS_MODE_ALWAYS
	if _ko_intro_layer:
		_ko_intro_layer.process_mode = Node.PROCESS_MODE_ALWAYS
	if _win_layer:
		_win_layer.process_mode = Node.PROCESS_MODE_ALWAYS
	# 일시정지 중 ESC 해제는 PauseLayer 스크립트(pause_layer.gd)에서 처리
	# 저장된 키 설정 적용 (user://input.cfg) — 게임 씬 진입 시 로드
	_load_input_config_safe()
	GameState.reset_punch_counts()
	GameState.player_hp = GameState.player_max_hp
	GameState.stamina = GameState.stamina_max
	GameState.start_workout_session()
	if _btn_pause_icon:
		_btn_pause_icon.pressed.connect(_toggle_pause)
	if _btn_pause_resume:
		_btn_pause_resume.pressed.connect(_toggle_pause)
	if _btn_pause_settings:
		_btn_pause_settings.pressed.connect(_on_pause_settings)
	if _btn_pause_quit:
		_btn_pause_quit.pressed.connect(_on_pause_quit)
	var btn_go_restart: Button = get_node_or_null("GameOverLayer/GameOverVBox/GameOverButtons/BtnGameOverRestart")
	var btn_go_back: Button = get_node_or_null("GameOverLayer/GameOverVBox/GameOverButtons/BtnGameOverBack")
	if btn_go_restart:
		btn_go_restart.pressed.connect(_on_game_over_restart)
	if btn_go_back:
		btn_go_back.pressed.connect(_on_game_over_back)
	var btn_win_restart: Button = get_node_or_null("WinLayer/WinVBox/WinButtons/BtnWinRestart")
	var btn_win_back: Button = get_node_or_null("WinLayer/WinVBox/WinButtons/BtnWinBack")
	if btn_win_restart:
		btn_win_restart.pressed.connect(_on_win_restart)
	if btn_win_back:
		btn_win_back.pressed.connect(_on_win_back)
	_fit_background_to_viewport()
	var vp := get_viewport()
	if vp.size_changed.is_connected(_fit_background_to_viewport) == false:
		vp.size_changed.connect(_fit_background_to_viewport)
	if _player and _player.has_signal("punch_impact"):
		_player.punch_impact.connect(_on_player_punch_impact)
	if _enemy and _enemy.has_signal("hit_received"):
		_enemy.hit_received.connect(_on_enemy_hit)
	if _enemy and _enemy.has_signal("died"):
		_enemy.died.connect(_on_enemy_died)
	if _enemy and _enemy.has_signal("enemy_attack"):
		_enemy.enemy_attack.connect(_on_enemy_attack)
	_update_enemy_hp_label()
	_update_play_time_label()
	_update_combo_label()
	if _bgm:
		if AudioServer.get_bus_index("Music") >= 0:
			_bgm.bus = "Music"
		if _bgm.stream == null:
			_try_load_stream(_bgm, [
				"res://assets/audio/bgm/Retro_Ring_Rush.ogg",
				"res://assets/audio/bgm/mainbgm.ogg",
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
		print("UDP 서버 시작... 포트: ", _port, " (액션: punch, upper, guard, dodge)")
	if auto_launch_webcam_ml:
		call_deferred("_schedule_webcam_ml_after_scene_idle")


func _load_input_config_safe() -> void:
	SettingsPanelUI.load_input_config_from_disk()


func _try_load_stream(player: AudioStreamPlayer, paths: Array[String]) -> void:
	for p in paths:
		if ResourceLoader.exists(p):
			var res := load(p)
			if res is AudioStream:
				player.stream = res
				return


func _schedule_webcam_ml_after_scene_idle() -> void:
	if not auto_launch_webcam_ml:
		return
	await get_tree().physics_frame
	await get_tree().process_frame
	if GameState.is_webcam_ml_bridge_running():
		GameState.ensure_webcam_ml_bridge(true)
		return
	var delay_sec := maxf(0.0, webcam_ml_scene_load_delay_sec)
	if delay_sec > 0.0:
		await get_tree().create_timer(delay_sec).timeout
	for _i in range(3):
		await get_tree().process_frame
	GameState.ensure_webcam_ml_bridge(true)


func _process(delta: float) -> void:
	if not _game_over_shown and GameState.player_hp <= 0.0:
		_show_game_over()
		return
	# 게임오버/승리 후에는 게임 로직·UDP 처리 중단 (씬 전환 버튼만 동작)
	if _game_over_shown or _win_shown:
		return
	if _stage_timer_active:
		_stage_elapsed_sec += delta
	if Input.is_action_just_pressed("ui_cancel"):
		if _settings_in_pause:
			_close_pause_settings()
		else:
			_toggle_pause()
	if _paused:
		return
	_update_ui_bars()
	if _enemy and _enemy.has_method("is_dead") and _enemy.is_dead():
		return
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


func _apply_glove_data(data: String) -> bool:
	if data in VALID_ACTIONS:
		# 펀치류: 쿨타임 + 동일 펀치 연속(자세 유지 스팸) 방지
		if data in PUNCH_ACTIONS:
			var now := Time.get_ticks_msec() / 1000.0
			if now - _last_punch_accepted_time < action_cooldown_sec:
				return false
		if _player.has_method("play_action"):
			var played: bool = _player.play_action(data, true)
			if not played:
				return false
			if data in PUNCH_ACTIONS:
				_last_punch_accepted_time = Time.get_ticks_msec() / 1000.0
			return true
		return false
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
			return true
	return false


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


func _on_player_punch_impact(damage: float, punch_type: String) -> void:
	# Leftovers KO! 스타일: 적이 회피 중이면 빗나감, 아니면 무조건 히트 (히트박스 없음)
	if not _enemy:
		return
	if _enemy.has_method("is_dead") and _enemy.is_dead():
		return
	if _enemy.has_method("is_evading") and _enemy.is_evading():
		if _enemy.has_signal("attack_missed"):
			_enemy.attack_missed.emit()
		return
	if _enemy.has_method("take_damage"):
		_enemy.take_damage(damage)
		GameState.add_punch_count(punch_type)
		_register_combo_hit()


func _on_enemy_attack(damage: float) -> void:
	if GameState.is_guarding:
		GameState.apply_guard_block_success()
		if _player and _player.has_method("play_guard_block_fx"):
			_player.play_guard_block_fx()
	else:
		_reset_combo()
		GameState.player_hp -= damage
		if GameState.player_hp < 0.0:
			GameState.player_hp = 0.0
		if _player and _player.has_method("play_take_damage_fx"):
			_player.play_take_damage_fx()


func _on_enemy_hit(_damage: float) -> void:
	_update_enemy_hp_label()


func _on_enemy_died() -> void:
	_update_enemy_hp_label()
	if _win_shown:
		return
	GameState.add_sweat(1)
	_reset_combo()
	_stage_timer_active = false
	GameState.record_stage_clear_time(_stage_elapsed_sec)
	_begin_ko_intro_then_win()


func _begin_ko_intro_then_win() -> void:
	# KO 연출(적 스프라이트) 후 2초 뒤에 중앙 KO! + 상단 라벨 표시
	await get_tree().create_timer(1.5).timeout
	if _win_shown:
		return
	if _enemy_hp_label:
		_enemy_hp_label.text = "KO!"
	if _ko_intro_layer:
		_ko_intro_layer.visible = true
	await get_tree().create_timer(3.0).timeout
	if _ko_intro_layer:
		_ko_intro_layer.visible = false
	if not _win_shown:
		_show_win()


func _update_enemy_hp_label() -> void:
	# 상단 바는 _update_ui_bars에서 갱신. 라벨 텍스트는 적 사망 시 _on_enemy_died에서 "KO!"로 변경
	pass  # 필요 시 여기서 적 이름/HP 텍스트 갱신


func _toggle_pause() -> void:
	_paused = not _paused
	get_tree().paused = _paused
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
	GameState.end_workout_session()
	get_tree().paused = false
	get_tree().call_deferred("change_scene_to_file", SCENE_MAIN_MENU)


func _show_game_over() -> void:
	_reset_combo()
	_stage_timer_active = false
	_game_over_shown = true
	var kcal := GameState.end_workout_session()
	var today_kcal := GameState.get_today_calories()
	get_tree().paused = true
	if _game_over_calories_label:
		_game_over_calories_label.text = "소모 칼로리: %.1f kcal" % kcal
	if _game_over_daily_calories_label:
		_game_over_daily_calories_label.text = "오늘 누적: %.1f kcal" % today_kcal
	if _game_over_layer:
		_game_over_layer.visible = true


func _show_win() -> void:
	_win_shown = true
	var kcal := GameState.end_workout_session()
	var today_kcal := GameState.get_today_calories()
	get_tree().paused = true
	if _win_calories_label:
		_win_calories_label.text = "소모 칼로리: %.1f kcal" % kcal
	if _win_daily_calories_label:
		_win_daily_calories_label.text = "오늘 누적: %.1f kcal" % today_kcal
	if _win_clear_time_label:
		var clear_sec: float = GameState.get_last_stage_clear_sec()
		_win_clear_time_label.text = "클리어 시간: %s" % GameState.format_stage_clear_time(clear_sec)
	if _win_layer:
		_win_layer.visible = true


func _on_game_over_restart() -> void:
	GameState.end_workout_session()
	get_tree().paused = false
	get_tree().call_deferred("change_scene_to_file", SCENE_MAIN)


func _on_game_over_back() -> void:
	GameState.end_workout_session()
	get_tree().paused = false
	get_tree().call_deferred("change_scene_to_file", SCENE_MAIN_MENU)


func _on_win_restart() -> void:
	GameState.end_workout_session()
	get_tree().paused = false
	get_tree().call_deferred("change_scene_to_file", SCENE_MAIN)


func _on_win_back() -> void:
	GameState.end_workout_session()
	get_tree().paused = false
	get_tree().call_deferred("change_scene_to_file", SCENE_MAIN_MENU)


func _format_play_time_sec(sec: float) -> String:
	var s: float = maxf(sec, 0.0)
	var mi: int = int(s / 60.0)
	var rem: float = s - float(mi) * 60.0
	if mi > 0:
		return "%d:%05.2f" % [mi, rem]
	return "%.1f초" % s


func _update_play_time_label() -> void:
	if _play_time_label:
		_play_time_label.text = "플레이 %s" % _format_play_time_sec(_stage_elapsed_sec)


func _register_combo_hit() -> void:
	_combo_count += 1
	_update_combo_label()


func _reset_combo() -> void:
	_combo_count = 0
	_update_combo_label()


func _update_combo_label() -> void:
	if not _combo_label:
		return
	if _combo_count < 2:
		_combo_label.visible = false
		_combo_label.text = ""
	else:
		_combo_label.visible = true
		_combo_label.text = "%d COMBO" % _combo_count


func _update_ui_bars() -> void:
	# 상단: 적 체력바 (ProgressBar value 0~100)
	if _enemy_hp_bar and _enemy and "current_hp" in _enemy and "max_hp" in _enemy and _enemy.max_hp > 0.0:
		var ratio: float = clampf(_enemy.current_hp / _enemy.max_hp, 0.0, 1.0)
		_enemy_hp_bar.value = ratio * 100.0
	# 하단: 플레이어 HP / 스태미너
	if _player_hp_bar:
		_player_hp_bar.value = GameState.get_player_hp_ratio() * 100.0
	if _player_stamina_bar:
		_player_stamina_bar.value = GameState.get_stamina_ratio() * 100.0
	_update_play_time_label()

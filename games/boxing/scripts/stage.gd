extends Node2D
## Unified stage scene controller.
## Parameterized by StageConfig resource for stage-specific values.
## 게임 로직은 CombatDirector, UI는 UIDirector, 스테이지는 StageManager에 위임.

const VALID_ACTIONS: Array[String] = ["punch_l", "punch_r", "upper_l", "upper_r", "guard", "guard_end", "squat"]
const PUNCH_ACTIONS: Array[String] = ["punch_l", "punch_r", "upper_l", "upper_r"]

const SCENE_MAIN_MENU: String = "res://scenes/main_menu.tscn"
const SCENE_SETTINGS: String = "res://scenes/ui/settings_panel.tscn"

@export var stage_config: StageConfig

@export var action_cooldown_sec: float = 0.015
@export var auto_launch_webcam_ml: bool = true
@export var webcam_ml_scene_load_delay_sec: float = 0.0

var _server: UDPServer
var _port: int = 4242
var _use_position_mode: bool = false
var _debug_received: bool = true
var _received_count: int = 0
var _last_punch_accepted_time: float = -999.0

@onready var _player: Node2D = $Player
@onready var _enemy: Node2D = $Enemy
@onready var _pause_layer: CanvasLayer = $PauseLayer
@onready var _btn_pause_icon: Button = $HUD/BtnPauseIcon
@onready var _btn_pause_resume: Button = $PauseLayer/PauseVBox/BtnPauseResume
@onready var _btn_pause_settings: Button = $PauseLayer/PauseVBox/BtnPauseSettings
@onready var _btn_pause_quit: Button = $PauseLayer/PauseVBox/BtnPauseQuit

@onready var _ui_director: Node = $UIDirector
@onready var _combat_director: Node = $CombatDirector
@onready var _stage_manager: Node = $StageManager

var _paused: bool = false
var _settings_in_pause: Control
var _game_over_shown: bool = false


func _ready() -> void:
	get_tree().paused = false
	_paused = false
	_game_over_shown = false
	if _pause_layer:
		_pause_layer.process_mode = Node.PROCESS_MODE_ALWAYS as Node.ProcessMode
		_pause_layer.visible = false
	_load_input_config_safe()
	GameState.player_hp = GameState.player_max_hp
	GameState.stamina = GameState.stamina_max
	GameState.set_has_guard_mastery(false)
	var buffs: Dictionary = GameState.consume_buff_for_session()
	if buffs.has("start_hp_bonus"):
		GameState.player_hp = minf(GameState.player_max_hp, GameState.player_hp + GameState.player_max_hp * float(buffs["start_hp_bonus"]))
	if buffs.has("guard_mastery"):
		GameState.set_has_guard_mastery(true)
	GameState.start_workout_session()

	_apply_stage_config()
	_connect_signals()
	_connect_buttons()
	_setup_game_over_buttons()
	_setup_win_buttons()
	_setup_boss_phase_if_needed()
	
	if _btn_pause_icon:
		UIThemeHelper.style_button_secondary(_btn_pause_icon)
		_btn_pause_icon.text = "⚙️ 설정"
	_style_pause_menu()

	call_deferred("_initialize_all")
	if _combat_director:
		GameState.set_last_played_stage_id(_combat_director.stage_id)

	_server = UDPServer.new()
	if _server.listen(_port) != OK:
		push_error("UDP 서버 포트 %d 열기 실패" % _port)
	else:
		print("UDP 서버 시작... 포트: ", _port, " (액션: punch, upper, guard, squat)")
	if auto_launch_webcam_ml:
		call_deferred("_schedule_webcam_ml_after_scene_idle")

	var root := get_tree().root
	if root and not root.close_requested.is_connected(_on_exit_tree_cleanup):
		root.close_requested.connect(_on_exit_tree_cleanup)

	var cam := Camera2D.new()
	cam.name = "GameCamera"
	cam.position_smoothing_enabled = false
	cam.position = Vector2(576, 324)
	add_child(cam)
	cam.make_current()
	HitImpactSystem.set_camera(cam)


func _apply_stage_config() -> void:
	if not stage_config:
		return
	if _enemy:
		# stage_config의 기본값을 먼저 세팅한 뒤,
		# 난이도 배율을 재적용하고 current_hp를 동기화.
		# (enemy._ready()에서 난이도 배율이 이미 적용됐더라도
		#  여기서 max_hp를 원본값으로 덮어쓰므로 재적용 필수)
		_enemy.max_hp = stage_config.enemy_max_hp
		_enemy.attack_damage = stage_config.enemy_attack_damage
		_enemy.attack_delay_min = stage_config.enemy_attack_delay_min
		_enemy.attack_delay_max = stage_config.enemy_attack_delay_max
		_enemy.evade_idle_min = stage_config.enemy_evade_idle_min
		_enemy.evade_idle_max = stage_config.enemy_evade_idle_max
		_enemy.evade_duration = stage_config.enemy_evade_duration
		if _enemy.has_method("reapply_difficulty_and_reset_hp"):
			_enemy.reapply_difficulty_and_reset_hp()


func _connect_signals() -> void:
	if _player and _player.has_signal("punch_impact"):
		_player.punch_impact.connect(_combat_director.on_player_punch_impact)
	if _player and _player.has_signal("action_performed"):
		_player.action_performed.connect(_combat_director.on_player_action_performed)
	if _enemy and _enemy.has_signal("hit_received"):
		_enemy.hit_received.connect(_combat_director.on_enemy_hit)
	if _enemy and _enemy.has_signal("died"):
		_enemy.died.connect(_combat_director.on_enemy_died)
	if _enemy and _enemy.has_signal("enemy_attack"):
		_enemy.enemy_attack.connect(_combat_director.on_enemy_attack)
	_combat_director.stage_cleared.connect(_on_stage_cleared)
	_combat_director.game_over_triggered.connect(_on_game_over_triggered)
	_combat_director.combo_changed.connect(_ui_director.update_combo)
	_combat_director.training_hud_needs_update.connect(_ui_director.update_training)
	_combat_director.bars_need_update.connect(_on_bars_need_update)
	GameState.stamina_changed.connect(_on_stamina_changed)
	GameState.player_hp_changed.connect(_on_player_hp_changed)


func _style_pause_menu() -> void:
	var pause_label: Label = get_node_or_null("PauseLayer/PauseVBox/PauseLabel")
	if pause_label:
		pause_label.add_theme_color_override("font_color", UIThemeHelper.C_ACCENT)
		pause_label.add_theme_color_override("font_outline_color", Color(0.03, 0.06, 0.08, 1))
		pause_label.add_theme_constant_override("outline_size", 6)
		pause_label.add_theme_font_size_override("font_size", 28)
		pause_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	for btn_path: String in ["BtnPauseResume", "BtnPauseSettings", "BtnPauseQuit"]:
		var btn: Button = get_node_or_null("PauseLayer/PauseVBox/%s" % btn_path)
		if btn:
			btn.custom_minimum_size = Vector2(240, 48)
			if btn_path == "BtnPauseQuit":
				UIThemeHelper.style_button_danger(btn)
			else:
				UIThemeHelper.style_button_primary(btn)


func _connect_buttons() -> void:
	if _btn_pause_icon:
		_btn_pause_icon.pressed.connect(_toggle_pause)
	if _btn_pause_resume:
		_btn_pause_resume.pressed.connect(_toggle_pause)
	if _btn_pause_settings:
		_btn_pause_settings.pressed.connect(_on_pause_settings)
	if _btn_pause_quit:
		_btn_pause_quit.pressed.connect(_on_pause_quit)


func _setup_game_over_buttons() -> void:
	var btn_go_restart: Button = get_node_or_null("GameOverLayer/GameOverVBox/GameOverButtons/BtnGameOverRestart")
	var btn_go_back: Button = get_node_or_null("GameOverLayer/GameOverVBox/GameOverButtons/BtnGameOverBack")
	if btn_go_restart:
		btn_go_restart.pressed.connect(_on_game_over_restart)
	if btn_go_back:
		btn_go_back.pressed.connect(_on_game_over_back)


func _setup_win_buttons() -> void:
	var btn_win_next: Button = get_node_or_null("WinLayer/WinVBox/WinButtons/BtnWinNext")
	var btn_win_restart: Button = get_node_or_null("WinLayer/WinVBox/WinButtons/BtnWinRestart")
	var btn_win_back: Button = get_node_or_null("WinLayer/WinVBox/WinButtons/BtnWinBack")
	if btn_win_next:
		if _combat_director and GameState.has_next_stage(_combat_director.stage_id):
			btn_win_next.visible = true
			btn_win_next.pressed.connect(_on_win_next)
		else:
			btn_win_next.visible = false
	if btn_win_restart:
		btn_win_restart.pressed.connect(_on_win_restart)
	if btn_win_back:
		btn_win_back.pressed.connect(_on_win_back)


func _initialize_all() -> void:
	var training_mode: bool = GameState.is_training_mode()
	_stage_manager.setup_stage()
	_stage_manager.setup_audio(stage_config.bgm_paths if stage_config else [], stage_config.hit_sound_paths if stage_config else [])
	if training_mode:
		_stage_manager.setup_training_mode()
		_ui_director.set_enemy_label("TRAINING DUMMY")
	else:
		_ui_director.set_enemy_label(stage_config.monster_name if stage_config else "")
	_combat_director.setup(training_mode)
	_ui_director.update_training(training_mode, 0, _combat_director.get_training_action_counts())
	_ui_director.update_bars(_enemy)
	_ui_director.update_play_time(0.0)
	_ui_director.update_combo(0)


func _load_input_config_safe() -> void:
	SettingsPanelUI.load_input_config_from_disk()


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
	for _i: int in range(3):
		await get_tree().process_frame
	GameState.ensure_webcam_ml_bridge(true)


func _setup_boss_phase_if_needed() -> void:
	if _enemy and _enemy.has_signal("phase_changed"):
		_enemy.phase_changed.connect(_on_boss_phase_changed)


func _on_boss_phase_changed(new_phase: int) -> void:
	get_tree().paused = true
	var packed := load("res://scenes/ui/boss_buff_select.tscn") as PackedScene
	if not packed:
		get_tree().paused = false
		return
	var panel: Control = packed.instantiate() as Control
	panel.process_mode = Node.PROCESS_MODE_ALWAYS as Node.ProcessMode
	add_child(panel)
	panel.set_anchors_preset(Control.PRESET_FULL_RECT)
	var options: Array[Dictionary] = GameState.get_boss_buff_options()
	var rng := RandomNumberGenerator.new()
	rng.randomize()
	var pool: Array[Dictionary] = options.duplicate()
	var picks: Array[Dictionary] = []
	for i in range(3):
		if pool.is_empty():
			break
		var idx: int = rng.randi_range(0, pool.size() - 1)
		picks.append(pool[idx])
		pool.remove_at(idx)
	if panel.has_method("setup"):
		panel.setup(picks, new_phase)
	if panel.has_signal("buff_selected"):
		panel.buff_selected.connect(func(buff: Dictionary) -> void:
			GameState.add_boss_buff(buff)
			panel.queue_free()
			get_tree().paused = false
		)
	if panel.has_signal("skip_pressed"):
		panel.skip_pressed.connect(func() -> void:
			panel.queue_free()
			get_tree().paused = false
		)


func _on_exit_tree_cleanup() -> void:
	if _server:
		_server.stop()
		_server = null
	if _stage_manager:
		_stage_manager.cleanup()


func _process(_delta: float) -> void:
	if not _game_over_shown and GameState.player_hp <= 0.0:
		_show_game_over()
		return
	if _combat_director.is_win_shown():
		return
	if Input.is_action_just_pressed("ui_cancel"):
		if _settings_in_pause:
			_close_pause_settings()
		else:
			_toggle_pause()
	if _paused:
		return
	_ui_director.update_play_time(_combat_director.get_stage_elapsed_sec())
	if _enemy and _enemy.has_method("is_dead") and _enemy.is_dead():
		return
	if _server == null:
		return
	_server.poll()
	var processed: int = 0
	const MAX_UDP_PER_FRAME: int = 20
	while _server.is_connection_available() and processed < MAX_UDP_PER_FRAME:
		processed += 1
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
		if data in PUNCH_ACTIONS:
			var now: float = Time.get_ticks_msec() / 1000.0
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
	if _use_position_mode:
		var parts: PackedStringArray = data.split(",")
		if parts.size() >= 4 and _player.has_method("update_gloves_position"):
			var view_size: Vector2 = _stage_manager.get_view_size()
			var player_global: Vector2 = _player.global_position
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


func _on_bars_need_update() -> void:
	_ui_director.update_bars(_enemy)


func _on_stamina_changed(_new_stamina: float) -> void:
	_ui_director.update_bars(_enemy)


func _on_player_hp_changed(_new_hp: float) -> void:
	_ui_director.update_bars(_enemy)


func _on_stage_cleared(_clear_sec: float) -> void:
	var flawless: bool = _combat_director.get_damage_taken() <= 0.0
	_ui_director.show_ko_intro(flawless)
	await get_tree().create_timer(3.0).timeout
	if not is_inside_tree():
		return
	_ui_director.hide_ko_intro()
	_show_win()


func _on_game_over_triggered() -> void:
	_show_game_over()


func toggle_pause() -> void:
	_toggle_pause()


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
	if _game_over_shown:
		return
	_game_over_shown = true
	_combat_director.stop_timer()
	_combat_director.reset_combo()
	var stage_id: String = _combat_director.stage_id
	GameState.update_stage_record(stage_id, _combat_director.get_stage_elapsed_sec(), _combat_director.get_max_combo(), _combat_director.get_damage_taken())
	_combat_director.set_newly_unlocked_achievements(GameState.check_and_unlock_achievements_after_session(_combat_director.get_stage_elapsed_sec(), _combat_director.get_max_combo(), _combat_director.get_damage_taken(), false))
	var kcal: float = GameState.end_workout_session()
	var today_kcal: float = GameState.get_today_calories()
	get_tree().paused = true
	_ui_director.show_game_over(kcal, today_kcal)
	_flash_achievement_unlocks()


func _show_win() -> void:
	_combat_director.stop_timer()
	var kcal: float = GameState.end_workout_session()
	var today_kcal: float = GameState.get_today_calories()
	var clear_sec: float = GameState.get_last_stage_clear_sec()
	get_tree().paused = true
	_ui_director.show_win(kcal, today_kcal, clear_sec)
	_flash_achievement_unlocks()


func _flash_achievement_unlocks() -> void:
	var unlocked: Array[String] = _combat_director.get_newly_unlocked_achievements()
	if unlocked.is_empty():
		return
	for id: String in unlocked:
		var def: Dictionary = GameState.get_achievement_defs().get(id, {})
		_ui_director.show_achievement_popup(id, str(def.get("title", id)))


func _on_game_over_restart() -> void:
	GameState.end_workout_session()
	get_tree().paused = false
	get_tree().call_deferred("change_scene_to_file", stage_config.scene_path if stage_config else SCENE_MAIN_MENU)


func _on_game_over_back() -> void:
	GameState.end_workout_session()
	get_tree().paused = false
	get_tree().call_deferred("change_scene_to_file", SCENE_MAIN_MENU)


func _on_win_next() -> void:
	GameState.end_workout_session()
	get_tree().paused = false
	if _combat_director:
		var next_id: String = GameState.get_next_stage_id(_combat_director.stage_id)
		var next_scene: String = GameState.get_next_stage_scene(_combat_director.stage_id)
		if not next_id.is_empty():
			GameState.set_last_played_stage_id(next_id)
		if not next_scene.is_empty():
			get_tree().call_deferred("change_scene_to_file", next_scene)


func _on_win_restart() -> void:
	GameState.end_workout_session()
	get_tree().paused = false
	get_tree().call_deferred("change_scene_to_file", stage_config.scene_path if stage_config else SCENE_MAIN_MENU)


func _on_win_back() -> void:
	GameState.end_workout_session()
	get_tree().paused = false
	get_tree().call_deferred("change_scene_to_file", SCENE_MAIN_MENU)

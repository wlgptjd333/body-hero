extends RefCounted

const DISPLAY_SETTINGS_PATH := "user://display_settings.cfg"
const BACKEND_VALUES := ["auto", "dshow", "msmf", "default"]
const PROFILE_VALUES: Array[String] = ["balanced", "fast_react", "fast_combo", "max_speed"]
const DISPLAY_MIN_W := 640
const DISPLAY_MIN_H := 360

var _camera_index: int = 0
var _camera_backend: String = "auto"
var _ml_speed_profile: String = "max_speed"
var _roi_mode: bool = false
var _center_zone_margin: float = 0.3
var _skip_guard_single: bool = false
var _full_body_squat: bool = false
var _window_mode: int = 0  # 0=windowed, 1=fullscreen, 2=borderless
var _saved_width: int = 0
var _saved_height: int = 0
var _webcam_bridge = null  # set externally by GameState
var _bridgify_fn: Callable = Callable()


func set_webcam_bridge(bridge) -> void:
	_webcam_bridge = bridge


func set_bridgify_fn(fn: Callable) -> void:
	_bridgify_fn = fn


# --- Camera ---

func get_camera_index() -> int:
	return _camera_index

func get_camera_backend() -> String:
	return _camera_backend

func get_ml_speed_profile() -> String:
	return _ml_speed_profile

func get_roi_mode() -> bool:
	return _roi_mode

func get_center_zone_margin() -> float:
	return _center_zone_margin

func get_skip_guard_single() -> bool:
	return _skip_guard_single

func get_full_body_squat() -> bool:
	return _full_body_squat



# --- Window ---

func get_window_mode() -> int:
	return _window_mode


func set_window_mode(mode: int) -> void:
	_window_mode = clampi(mode, 0, 2)


func apply_saved_window_size() -> void:
	var tree := Engine.get_main_loop()
	if not tree or not tree.has_method("root"):
		return
	var win = tree.root.get_window()
	if win == null:
		return
	if _saved_width < DISPLAY_MIN_W or _saved_height < DISPLAY_MIN_H:
		return
	match _window_mode:
		0:
			win.set_mode(Window.MODE_WINDOWED)
			win.call_deferred("set_size", Vector2i(_saved_width, _saved_height))
		1:
			win.set_mode(Window.MODE_FULLSCREEN)
		2:
			win.set_mode(Window.MODE_EXCLUSIVE_FULLSCREEN)


# --- Load / Save ---

func load_from_disk() -> void:
	if not FileAccess.file_exists(DISPLAY_SETTINGS_PATH):
		if OS.get_name() == "Windows":
			_camera_backend = "dshow"
		return
	var cfg := ConfigFile.new()
	if cfg.load(DISPLAY_SETTINGS_PATH) != OK:
		return
	if cfg.has_section_key("display", "width") and cfg.has_section_key("display", "height"):
		var w := int(cfg.get_value("display", "width", 0))
		var h := int(cfg.get_value("display", "height", 0))
		if w >= DISPLAY_MIN_W and h >= DISPLAY_MIN_H:
			_saved_width = w
			_saved_height = h
	if cfg.has_section_key("display", "window_mode"):
		_window_mode = clampi(int(cfg.get_value("display", "window_mode", 0)), 0, 2)
	if cfg.has_section_key("camera", "index"):
		_camera_index = clampi(int(cfg.get_value("camera", "index", 0)), 0, 9)
	if cfg.has_section_key("camera", "backend"):
		_camera_backend = _sanitize_backend(str(cfg.get_value("camera", "backend", "auto")))
	elif OS.get_name() == "Windows":
		_camera_backend = "dshow"
	else:
		_camera_backend = "auto"
	if cfg.has_section_key("camera", "ml_speed_profile"):
		_ml_speed_profile = _sanitize_profile(str(cfg.get_value("camera", "ml_speed_profile", "balanced")))
	if cfg.has_section_key("camera", "roi_mode"):
		_roi_mode = bool(cfg.get_value("camera", "roi_mode", false))
	if cfg.has_section_key("camera", "center_zone_margin"):
		_center_zone_margin = clampf(float(cfg.get_value("camera", "center_zone_margin", 0.3)), 0.0, 0.5)
	if cfg.has_section_key("camera", "skip_guard_single"):
		_skip_guard_single = bool(cfg.get_value("camera", "skip_guard_single", false))
	if cfg.has_section_key("camera", "full_body_squat"):
		_full_body_squat = bool(cfg.get_value("camera", "full_body_squat", false))


func save_to_disk(width: int, height: int, camera_index: int, camera_backend: String = "auto", ml_speed_profile: String = "", roi_mode: bool = false, center_zone_margin: float = 0.3, skip_guard_single: bool = false, full_body_squat: bool = false) -> void:
	var old_cam := _camera_index
	var old_back := _camera_backend
	var old_prof := _ml_speed_profile
	var old_roi := _roi_mode
	var old_zone := _center_zone_margin
	var old_skip := _skip_guard_single
	var old_full := _full_body_squat
	_saved_width = maxi(DISPLAY_MIN_W, width)
	_saved_height = maxi(DISPLAY_MIN_H, height)
	_camera_index = clampi(camera_index, 0, 9)
	_camera_backend = _sanitize_backend(camera_backend)
	if ml_speed_profile.strip_edges() != "":
		_ml_speed_profile = _sanitize_profile(ml_speed_profile)
	_roi_mode = roi_mode
	_center_zone_margin = clampf(center_zone_margin, 0.0, 0.5)
	_skip_guard_single = skip_guard_single
	_full_body_squat = full_body_squat
	var cfg := ConfigFile.new()
	if FileAccess.file_exists(DISPLAY_SETTINGS_PATH):
		cfg.load(DISPLAY_SETTINGS_PATH)
	cfg.set_value("display", "width", _saved_width)
	cfg.set_value("display", "height", _saved_height)
	cfg.set_value("display", "window_mode", _window_mode)
	cfg.set_value("camera", "index", _camera_index)
	cfg.set_value("camera", "backend", _camera_backend)
	cfg.set_value("camera", "ml_speed_profile", _ml_speed_profile)
	cfg.set_value("camera", "roi_mode", _roi_mode)
	cfg.set_value("camera", "center_zone_margin", _center_zone_margin)
	cfg.set_value("camera", "skip_guard_single", _skip_guard_single)
	cfg.set_value("camera", "full_body_squat", _full_body_squat)
	cfg.save(DISPLAY_SETTINGS_PATH)
	var changed: bool = (old_cam != _camera_index or old_back != _camera_backend or old_prof != _ml_speed_profile or old_roi != _roi_mode or old_zone != _center_zone_margin or old_skip != _skip_guard_single or old_full != _full_body_squat)
	if changed and _bridgify_fn.is_valid():
		_bridgify_fn.call()


func _sanitize_profile(s: String) -> String:
	if s in PROFILE_VALUES:
		return s
	return PROFILE_VALUES[0]


func _sanitize_backend(s: String) -> String:
	if s in BACKEND_VALUES:
		return s
	return BACKEND_VALUES[0]

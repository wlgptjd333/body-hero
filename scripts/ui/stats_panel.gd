extends Control
## 통계 패널: 1번 가드 ~ 7번 오른손 훅까지 누적 횟수 표시

signal back_pressed

# GameState.STATS_KEYS 순서와 동일: guard, jab_l, jab_r, upper_l, upper_r, hook_l, hook_r
const DISPLAY_NAMES := {
	"guard": "가드",
	"jab_l": "왼손 잽",
	"jab_r": "오른손 잽",
	"upper_l": "왼손 어퍼컷",
	"upper_r": "오른손 어퍼컷",
	"hook_l": "왼손 훅",
	"hook_r": "오른손 훅",
}

@onready var _back_btn: Button = $Panel/VBox/BackButton
@onready var _stats_list: VBoxContainer = $Panel/VBox/Scroll/ScrollInner/StatsList
@onready var _daily_chart: Control = $Panel/VBox/Scroll/ScrollInner/DailyChart
@onready var _weight_spin: SpinBox = $Panel/VBox/Scroll/ScrollInner/WeightRow/WeightSpin
@onready var _weight_save_btn: Button = $Panel/VBox/Scroll/ScrollInner/WeightRow/WeightSaveButton
@onready var _weight_chart: Control = $Panel/VBox/Scroll/ScrollInner/WeightChart


func _ready() -> void:
	if _back_btn:
		_back_btn.pressed.connect(_on_back)
	if _weight_save_btn:
		_weight_save_btn.pressed.connect(_on_weight_save_pressed)
	_refresh_stats()


func _refresh_stats() -> void:
	if not _stats_list:
		return
	# 기존 라벨 제거 후 다시 생성 (씬에 고정 라벨이 있으면 그걸 쓰고, 없으면 동적 생성)
	for c in _stats_list.get_children():
		c.queue_free()
	for key in GameState.STATS_KEYS:
		var name_str: String = DISPLAY_NAMES.get(key, key)
		var count: int = GameState.get_punch_count(key)
		var lbl := Label.new()
		lbl.text = "%s: %d번" % [name_str, count]
		lbl.add_theme_font_size_override("font_size", 18)
		_stats_list.add_child(lbl)
	_refresh_daily_chart()
	_refresh_weight_ui()


func _refresh_daily_chart() -> void:
	if not _daily_chart:
		return
	var points: Array[Dictionary] = GameState.get_recent_daily_calories(30)
	if _daily_chart.has_method("set_points"):
		_daily_chart.set_points(points)


func _refresh_weight_ui() -> void:
	if _weight_spin:
		var logged: float = GameState.get_today_logged_weight_kg()
		if logged > 0.0:
			_weight_spin.value = logged
		else:
			_weight_spin.value = GameState.get_weight_kg()
	if _weight_chart and _weight_chart.has_method("set_points"):
		var wpoints: Array[Dictionary] = GameState.get_recent_daily_weight_log(30)
		_weight_chart.set_points(wpoints, {
			"value_key": "weight",
			"suffix": "kg",
			"color": Color(0.35, 0.75, 0.95, 0.95),
			"zero_based": false,
		})


func _on_weight_save_pressed() -> void:
	if not _weight_spin:
		return
	GameState.log_today_weight_kg(float(_weight_spin.value))
	_refresh_weight_ui()


func _on_back() -> void:
	back_pressed.emit()

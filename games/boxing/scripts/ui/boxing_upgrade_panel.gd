extends Control
## 메인 메뉴 등에서 열림: 스웨트(땀방울)로 체력·스태미너·회복 업그레이드

signal upgrade_closed

@onready var _lbl_sweat: Label = $Dim/Panel/Margin/VBox/LblSweat
@onready var _lbl_hp: Label = $Dim/Panel/Margin/VBox/RowHp/Lbl
@onready var _bar_hp: ProgressBar = $Dim/Panel/Margin/VBox/RowHp/HBox/Bar
@onready var _btn_hp: Button = $Dim/Panel/Margin/VBox/RowHp/HBox/Btn
@onready var _lbl_sta: Label = $Dim/Panel/Margin/VBox/RowSta/Lbl
@onready var _bar_sta: ProgressBar = $Dim/Panel/Margin/VBox/RowSta/HBox/Bar
@onready var _btn_sta: Button = $Dim/Panel/Margin/VBox/RowSta/HBox/Btn
@onready var _lbl_rec: Label = $Dim/Panel/Margin/VBox/RowRec/Lbl
@onready var _bar_rec: ProgressBar = $Dim/Panel/Margin/VBox/RowRec/HBox/Bar
@onready var _btn_rec: Button = $Dim/Panel/Margin/VBox/RowRec/HBox/Btn
@onready var _btn_close: Button = $Dim/Panel/Margin/VBox/BtnClose


func _ready() -> void:
	_btn_hp.pressed.connect(func() -> void: _on_buy("hp"))
	_btn_sta.pressed.connect(func() -> void: _on_buy("stamina"))
	_btn_rec.pressed.connect(func() -> void: _on_buy("recover"))
	_btn_close.pressed.connect(_close_pressed)
	refresh_display()


func refresh_display() -> void:
	var mx: int = GameState.UPGRADE_MAX_STEPS
	_lbl_sweat.text = "스웨트(땀방울): %d  (스테이지 클리어 시 +1)" % GameState.get_sweat()
	var sweat_ok := GameState.get_sweat() >= 1
	_fill_row_hp(mx, sweat_ok)
	_fill_row_sta(mx, sweat_ok)
	_fill_row_rec(mx, sweat_ok)


func _fill_row_hp(mx: int, sweat_ok: bool) -> void:
	var lv: int = GameState.get_upgrade_hp_level()
	var cur_max: float = GameState.BASE_PLAYER_MAX_HP + float(lv) * GameState.UPGRADE_HP_PER_STEP
	_lbl_hp.text = (
		"체력 — 기본 %.0f  →  현재 %.0f\n한 단계당 +%.0f HP (레벨 %d / %d)"
		% [GameState.BASE_PLAYER_MAX_HP, cur_max, GameState.UPGRADE_HP_PER_STEP, lv, mx]
	)
	_bar_hp.max_value = float(mx)
	_bar_hp.value = float(lv)
	_btn_hp.disabled = (not sweat_ok) or lv >= mx
	_btn_hp.text = "업그레이드 (💧1)" if lv < mx else "완료"


func _fill_row_sta(mx: int, sweat_ok: bool) -> void:
	var lv: int = GameState.get_upgrade_stamina_level()
	var cur_max: float = GameState.BASE_STAMINA_MAX + float(lv) * GameState.UPGRADE_STAMINA_PER_STEP
	_lbl_sta.text = (
		"스태미너 — 기본 %.0f  →  현재 %.0f\n한 단계당 +%.0f (레벨 %d / %d)"
		% [GameState.BASE_STAMINA_MAX, cur_max, GameState.UPGRADE_STAMINA_PER_STEP, lv, mx]
	)
	_bar_sta.max_value = float(mx)
	_bar_sta.value = float(lv)
	_btn_sta.disabled = (not sweat_ok) or lv >= mx
	_btn_sta.text = "업그레이드 (💧1)" if lv < mx else "완료"


func _fill_row_rec(mx: int, sweat_ok: bool) -> void:
	var lv: int = GameState.get_upgrade_recover_level()
	var cur: float = (
		GameState.BASE_STAMINA_PASSIVE_RECOVER + float(lv) * GameState.UPGRADE_RECOVER_PER_STEP
	)
	_lbl_rec.text = (
		"스태미너 초당 회복 — 기본 %.1f  →  현재 %.1f /초\n한 단계당 +%.1f (레벨 %d / %d)"
		% [GameState.BASE_STAMINA_PASSIVE_RECOVER, cur, GameState.UPGRADE_RECOVER_PER_STEP, lv, mx]
	)
	_bar_rec.max_value = float(mx)
	_bar_rec.value = float(lv)
	_btn_rec.disabled = (not sweat_ok) or lv >= mx
	_btn_rec.text = "업그레이드 (💧1)" if lv < mx else "완료"


func _on_buy(kind: String) -> void:
	if not GameState.try_purchase_upgrade(kind):
		return
	refresh_display()


func _close_pressed() -> void:
	upgrade_closed.emit()

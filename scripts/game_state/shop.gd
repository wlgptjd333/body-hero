extends RefCounted
## Shop system: purchases, equipment, consumable buffs, hit effect themes.
## Pure state logic — no Node/scene-tree dependency.

const SHOP_ITEMS: Dictionary = {
	"glove_red": {"name": "붉은 글러브", "kind": "glove_skin", "price": 5, "desc": "붉은색 글러브 스킨"},
	"glove_blue": {"name": "푸른 글러브", "kind": "glove_skin", "price": 5, "desc": "푸른색 글러브 스킨"},
	"glove_gold": {"name": "황금 글러브", "kind": "glove_skin", "price": 20, "desc": "화려한 황금 글러브"},
	"buff_speed": {"name": "아드레날린", "kind": "consumable", "price": 3, "desc": "다음 세션 공격 속도 +15%", "effect": {"attack_speed_mul": 1.15}},
	"buff_heal": {"name": "에너지 드링크", "kind": "consumable", "price": 3, "desc": "세션 시작 시 HP +20%", "effect": {"start_hp_bonus": 0.20}},
	"buff_shield": {"name": "바세린", "kind": "consumable", "price": 4, "desc": "다음 세션 피해 무효 1회", "effect": {"damage_block": 1}},
	"guard_mastery": {"name": "가드 마스터리", "kind": "consumable", "price": 8, "desc": "다음 세션 가드 시 데미지 100% 감소", "effect": {"guard_mastery": true}},
}

const HIT_EFFECT_THEMES: Dictionary = {
	"cyan_lightning": {"name": "청록 번개", "kind": "hit_effect", "price": 50, "desc": "청록색 히트 스파크 + 라인"},
	"purple_shock": {"name": "보라 충격", "kind": "hit_effect", "price": 80, "desc": "보라색 임팩트 + 화면 플래시"},
	"golden_star": {"name": "금성", "kind": "hit_effect", "price": 120, "desc": "금색 별 파티클 + 데미지 숫자"},
	"flame": {"name": "화염", "kind": "hit_effect", "price": 100, "desc": "주황/빨강 불꽃 파티클"},
}

const HIT_EFFECT_THEME_COLORS: Dictionary = {
	"default": {"spark_color": Color(1, 0.95, 0.4), "flash_color": Color(1, 1, 1), "particle_color": Color(1, 0.88, 0.35), "splat_color": Color(0.92, 0.28, 0.45)},
	"cyan_lightning": {"spark_color": Color(0.3, 0.8, 0.77), "flash_color": Color(0.3, 0.8, 0.77), "particle_color": Color(0.3, 0.95, 1.0), "splat_color": Color(0.2, 0.6, 0.9)},
	"purple_shock": {"spark_color": Color(0.7, 0.3, 1.0), "flash_color": Color(0.6, 0.2, 0.9), "particle_color": Color(0.8, 0.4, 1.0), "splat_color": Color(0.5, 0.1, 0.8)},
	"golden_star": {"spark_color": Color(1.0, 0.82, 0.2), "flash_color": Color(1.0, 0.9, 0.4), "particle_color": Color(1.0, 0.85, 0.3), "splat_color": Color(0.9, 0.6, 0.1)},
	"flame": {"spark_color": Color(1.0, 0.4, 0.1), "flash_color": Color(1.0, 0.5, 0.2), "particle_color": Color(1.0, 0.55, 0.15), "splat_color": Color(0.95, 0.2, 0.1)},
}

var _owned_items: Dictionary = {}  # item_id -> bool (permanent items)
var _inventory: Dictionary = {}  # item_id -> count (consumables)
var _equipped_glove_skin: String = ""
var _equipped_hit_effect: String = ""

## Callable supplied by GameState to trigger save after mutations.
var _save_fn: Callable = Callable()


func set_save_fn(fn: Callable) -> void:
	_save_fn = fn


func _save() -> void:
	if _save_fn.is_valid():
		_save_fn.call()


# --- Query ---

func get_shop_items() -> Dictionary:
	return SHOP_ITEMS.duplicate()

func get_shop_inventory() -> Dictionary:
	return _inventory.duplicate()

func is_item_owned(item_id: String) -> bool:
	return _owned_items.get(item_id, false)

func get_item_inventory_count(item_id: String) -> int:
	return _inventory.get(item_id, 0)


# --- Purchase ---

## Returns true on success. Deducts from sweat_ref (Array[int] size 1 used as mutable int ref).
func try_purchase_item(item_id: String, sweat_ref: Array[int]) -> bool:
	if not SHOP_ITEMS.has(item_id) and not HIT_EFFECT_THEMES.has(item_id):
		return false
	var def: Dictionary = SHOP_ITEMS.get(item_id, {})
	if def.is_empty():
		def = HIT_EFFECT_THEMES.get(item_id, {})
	if def.is_empty():
		return false
	var price: int = int(def.get("price", 0))
	if sweat_ref[0] < price:
		return false
	var kind: String = def.get("kind", "")
	if kind == "glove_skin" or kind == "hit_effect":
		if _owned_items.get(item_id, false):
			return false
		_owned_items[item_id] = true
	else:
		_inventory[item_id] = _inventory.get(item_id, 0) + 1
	sweat_ref[0] -= price
	_save()
	return true


# --- Equipment ---

func equip_glove_skin(skin_id: String) -> bool:
	if skin_id == "":
		_equipped_glove_skin = ""
		_save()
		return true
	if not _owned_items.get(skin_id, false):
		return false
	var def: Dictionary = SHOP_ITEMS.get(skin_id, {})
	if def.get("kind", "") != "glove_skin":
		return false
	_equipped_glove_skin = skin_id
	_save()
	return true

func get_equipped_glove_skin() -> String:
	return _equipped_glove_skin

func get_hit_effect_themes() -> Dictionary:
	return HIT_EFFECT_THEMES.duplicate()

func get_hit_effect_theme_colors(theme_id: String) -> Dictionary:
	return HIT_EFFECT_THEME_COLORS.get(theme_id, HIT_EFFECT_THEME_COLORS["default"]).duplicate()

func get_equipped_hit_effect() -> String:
	return _equipped_hit_effect

func equip_hit_effect(effect_id: String) -> bool:
	if effect_id == "":
		_equipped_hit_effect = ""
		_save()
		return true
	if not _owned_items.get(effect_id, false):
		return false
	var def: Dictionary = HIT_EFFECT_THEMES.get(effect_id, {})
	if def.get("kind", "") != "hit_effect":
		return false
	_equipped_hit_effect = effect_id
	_save()
	return true


# --- Consumable buffs ---

func consume_buff_for_session() -> Dictionary:
	var consumed: Dictionary = {}
	for item_id: String in _inventory.keys():
		var count: int = _inventory[item_id]
		if count <= 0:
			continue
		var def: Dictionary = SHOP_ITEMS.get(item_id, {})
		if def.get("kind", "") != "consumable":
			continue
		var effect: Dictionary = def.get("effect", {})
		if not effect.is_empty():
			for k: String in effect.keys():
				consumed[k] = effect[k]
		_inventory[item_id] = count - 1
	if not consumed.is_empty():
		_save()
	return consumed


func get_save_data() -> Dictionary:
	return {
		"owned": _owned_items,
		"inventory": _inventory,
		"equipped_glove_skin": _equipped_glove_skin,
		"equipped_hit_effect": _equipped_hit_effect,
	}


func reset_all() -> void:
	_owned_items.clear()
	_inventory.clear()
	_equipped_glove_skin = ""
	_equipped_hit_effect = ""

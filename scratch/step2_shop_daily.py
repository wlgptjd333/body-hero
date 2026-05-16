import re

with open("scripts/game_state.gd", "r", encoding="utf-8") as f:
    c = f.read()

# Fix Daily Challenges calls in add_punch_count and record_guard
c = c.replace('_sync_daily_challenge_calendar()', '_daily.sync_calendar()')
c = c.replace('_daily_bump_for_punch_action(action)', '_daily.bump_for_punch_action(action)')
c = c.replace('_daily_bump_for_kind("guards")', '_daily.bump_for_kind("guards")')

# Add get_daily_challenges_for_ui() back and delegate
daily_funcs_new = """

func get_daily_challenges_for_ui() -> Array[Dictionary]:
	return _daily.get_challenges_for_ui()

"""
c = c.replace('	return _workout.get_daily_goal_punch_hints()\n', '	return _workout.get_daily_goal_punch_hints()\n' + daily_funcs_new)


# Now migrate Shop variables and functions
c = re.sub(r'var _shop_owned_items: Dictionary = \{\}.*?\n', '', c)
c = re.sub(r'var _shop_inventory: Dictionary = \{\}.*?\n', '', c)
c = re.sub(r'var _equipped_glove_skin: String = "".*?\n', '', c)
c = re.sub(r'var _equipped_hit_effect: String = "".*?\n', '', c)
c = re.sub(r'var _active_buffs: Dictionary = \{\}.*?\n', '', c)

shop_funcs_old = r"(?sm)func get_shop_items\(\) -> Dictionary:.*?func consume_buff_for_session\(\) -> Dictionary:\n\tvar consumed: Dictionary = \{\}\n\tfor item_id: String in _shop_inventory.keys\(\):\n\t\tvar count: int = _shop_inventory\[item_id\]\n\t\tif count <= 0:\n\t\t\tcontinue\n\t\tvar def: Dictionary = SHOP_ITEMS.get\(item_id, \{\}\)\n\t\tif def.get\(\"kind\", \"\"\) != \"consumable\":\n\t\t\tcontinue\n\t\tvar effect: Dictionary = def.get\(\"effect\", \{\}\)\n\t\tif not effect.is_empty\(\):\n\t\t\tfor k: String in effect.keys\(\):\n\t\t\t\tconsumed\[k\] = effect\[k\]\n\t\t_shop_inventory\[item_id\] = count - 1\n\tif not consumed.is_empty\(\):\n\t\tsave_stats\(\)\n\treturn consumed\n"

shop_funcs_new = """func get_shop_items() -> Dictionary:
	return _shop_module.get_shop_items()

func get_shop_inventory() -> Dictionary:
	return _shop_module.get_shop_inventory()

func is_item_owned(item_id: String) -> bool:
	return _shop_module.is_item_owned(item_id)

func get_item_inventory_count(item_id: String) -> int:
	return _shop_module.get_item_inventory_count(item_id)

func equip_glove_skin(skin_id: String) -> bool:
	return _shop_module.equip_glove_skin(skin_id)

func get_equipped_glove_skin() -> String:
	return _shop_module.get_equipped_glove_skin()

func get_hit_effect_themes() -> Dictionary:
	return _shop_module.get_hit_effect_themes()

func get_hit_effect_theme_colors(theme_id: String) -> Dictionary:
	return _shop_module.get_hit_effect_theme_colors(theme_id)

func get_equipped_hit_effect() -> String:
	return _shop_module.get_equipped_hit_effect()

func equip_hit_effect(effect_id: String) -> bool:
	return _shop_module.equip_hit_effect(effect_id)

func try_purchase_item(item_id: String) -> bool:
	var sweat_ref: Array[int] = [_sweat]
	var success = _shop_module.try_purchase_item(item_id, sweat_ref)
	if success:
		_sweat = sweat_ref[0]
		save_stats()
	return success

func consume_buff_for_session() -> Dictionary:
	return _shop_module.consume_buff_for_session()
"""
c = re.sub(shop_funcs_old, shop_funcs_new, c)

# Fix save_stats for Shop and Daily Challenges
c = c.replace('_daily_challenge_date', '_daily._challenge_date')
c = c.replace('_daily_sessions_completed', '_daily._sessions_completed')
c = c.replace('_daily_challenge_picks', '_daily._challenge_picks')
c = c.replace('_daily_challenge_progress', '_daily._challenge_progress')

c = c.replace('_shop_owned_items', '_shop_module._owned_items')
c = c.replace('_shop_inventory', '_shop_module._inventory')
c = c.replace('_equipped_glove_skin', '_shop_module._equipped_glove_skin')
c = c.replace('_equipped_hit_effect', '_shop_module._equipped_hit_effect')

# Fix load_stats for Shop and Daily Challenges
c = c.replace('\t\t_daily._challenge_date = str(cfg.get_value("daily_challenges", "date", ""))', '\t\t_daily._challenge_date = str(cfg.get_value("daily_challenges", "date", ""))')
# Oops, let me just do replace of the variables since load_stats writes directly to them.
# The variables are already replaced in save_stats above, I'll let python replace them all.

with open("scripts/game_state.gd", "w", encoding="utf-8") as f:
    f.write(c)

print("Done")

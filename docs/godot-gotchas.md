# Godot 4.6 Gotchas

## All scripts must start with extends

Example:

```gdscript
extends Node
```

Missing extends causes parser/runtime issues.

---

## AutoLoad vs class_name

`class_name` does NOT create a singleton.

Global managers require:

* `extends Node`
* `[autoload]` registration in `project.godot`

---

## Never assign theme_override_* directly

Bad:

```gdscript
node.theme_override_constants.separation = 6
```

Good:

```gdscript
node.add_theme_constant_override("separation", 6)
```

---

## Safe reparenting order

Always:

```gdscript
parent.remove_child(node)
new_parent.add_child(node)
```

---

## _ready() execution order

Parent → Child (Godot default). But a common pitfall:

A parent may set a child's property in its own `_ready()`,
then the child's `_ready()` runs **after** and overwrites it.

Worse: if a sibling or deferred call modifies the property again,
the final value depends on spawn order you don't control.

**Rule of thumb:** If two nodes depend on each other's `_ready()` setup,
don't fight the order — add a **dedicated public method** on the child
that the parent calls explicitly after both `_ready()`s have run.

Example: `enemy.gd` has `reapply_difficulty_and_reset_hp()` that the stage
calls after the full init chain, ensuring stats settle last.

---

## Godot 4.6 API only

Use:
https://docs.godotengine.org/en/stable/

Avoid deprecated enum/constants and Godot 3.x patterns.

# Scene & Resource File Rules

## UID rules

* **NEVER write fake `uid://` values** into `.tscn` or `.tres` files.
  Godot resolves UIDs strictly; an unresolvable UID freezes the editor
  at ~80% "Loading plugin window layout".

## Manual file editing

* **Never manually create `.tres` files.** Use the Godot editor or
  generate them programmatically via `ResourceSaver`.
* **Never manually edit `.tscn` ext_resource references.**
  Use the Godot editor or edit only lines whose format you are
  100% certain of.
* **After any `.tscn`/`.tres` edit, verify the project opens in the editor.**

## Editor hang recovery

* If the editor hangs with "Loading plugin window layout" at ~80%,
  delete `.godot/` and restart Godot. The folder is a cache — it regenerates.

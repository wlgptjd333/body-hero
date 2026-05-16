# UI Rules

## Styling Ownership

All runtime UI styling should go through:

```txt id="5jlwmh"
UIThemeHelper
```

Avoid:

* duplicated StyleBoxFlat creation
* inconsistent inline styling
* per-scene hardcoded colors

---

## Preferred Pattern

Good:

```gdscript id="6jwmlj"
UIThemeHelper.style_button_primary(button)
```

Avoid:

```gdscript id="7jlwmk"
var sb = StyleBoxFlat.new()
```

everywhere.

---

## Theme Override Rules

Never assign:

```gdscript id="8jlwml"
theme_override_*
```

directly.

Bad:

```gdscript id="9jlwmm"
node.theme_override_constants.separation = 6
```

Good:

```gdscript id="0jlwmn"
node.add_theme_constant_override("separation", 6)
```

---

## UI Style & Philosophy: Premium Cyberpunk Glass

We have transitioned from the rusty industrial look to a sleek, premium sci-fi cyberpunk aesthetic that matches the high-quality `premium_home_bg.png` background.

### Design Principles
1. **Glassmorphism**: Panels should use `StyleBoxFlat` with a translucent deep blue/black background (`Color(0.02, 0.02, 0.05, 0.75)`) to allow the beautiful neon background to shine through. No opaque gray or black boxes blocking the view.
2. **Neon Glow (Cyberpunk)**: Use vibrant neon colors (Cyan and Pink/Red) for borders, accents, and hover effects instead of thick, rusty orange lines.
3. **Clean & Minimalist**: Keep corners sharp or very slightly rounded (radius 2), avoid messy textures for interactive elements, and rely on code-generated `StyleBoxFlat` for crisp scaling at any resolution.
4. **Dynamic Interaction**: Hovering over buttons should make them glow with a cyan or red shadow (simulating a neon sign turning on).

### Core Colors (ui_theme_helper.gd)
*   **C_ACCENT (`#00E5FF`)**: Neon Cyan. Used for primary highlights, borders, and general glowing effects.
*   **C_ACCENT_DARK (`#006680`)**: Darker cyan for gradients or unlit states.
*   **C_DANGER (`#FF0055`)**: Neon Red/Pink. Used for destructive actions, 'pressed' states, and HP bars to contrast with cyan.
*   **C_WARN (`#FFD700`)**: Neon Yellow.
*   **C_SUCCESS (`#00FF80`)**: Neon Green.
*   **C_TEXT_PRIMARY**: Pure White (`1.0, 1.0, 1.0`) for maximum readability.
*   **C_TEXT_SECONDARY**: Ice Blue Gray (`0.7, 0.8, 0.9`) for standard text.
*   **C_PANEL**: Translucent Deep Blue/Black (`Color(0.02, 0.02, 0.05, 0.75)`) for glass panels.

### Implementation Guidelines
*   **Never use `StyleBoxTexture` for basic panels/buttons unless it's a specific icon.** Rely on `UIThemeHelper.style_button_primary()` and `style_panel_glass()` which use `StyleBoxFlat` with shadows configured as glowing neon edges.
*   **Backgrounds**: The background should always be assigned directly in the `.tscn` file using a `TextureRect` pointing to `res://assets/textures/ui/premium_home_bg.png` or `apocalyptic_bg.png` (with `expand_mode=1`, `stretch_mode=6`). Do not use `ColorRect` for full-screen dimming unless it's a temporary popup overlay without a texture.

---

## Language Policy

UI text may remain Korean.

Code/comments/helper names stay English.

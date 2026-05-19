shader_type canvas_item;

uniform float distortion_strength : hint_range(-1.0, 1.0) = 0.15;
uniform sampler2D screen_texture : hint_screen_texture, repeat_disable, filter_linear;

void fragment() {
	vec2 uv = SCREEN_UV - 0.5;
	float dist = length(uv);
	uv *= 1.0 + distortion_strength * (dist * dist);
	uv += 0.5;
	if (uv.x < 0.0 || uv.x > 1.0 || uv.y < 0.0 || uv.y > 1.0) {
		COLOR = vec4(0.0, 0.0, 0.0, 1.0);
	} else {
		COLOR = texture(screen_texture, uv);
	}
}

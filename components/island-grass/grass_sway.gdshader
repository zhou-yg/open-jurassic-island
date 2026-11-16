// 草的摇曳（风）—— 给 MultiMesh 里的草实例用。
//
// 用法：MultiMeshInstance3D + 本 shader 的 ShaderMaterial。
// 每株草的相位 / 朝向从 INSTANCE_CUSTOM 读进来：
//   x = 相位（0~2π，每株错开 → 一阵一阵地晃，不是整齐划一）
//   y = cos(实例绕 Y 的转角)
//   z = sin(实例绕 Y 的转角)
//   （w 不用）
//
// 风向是世界坐标的（wind_direction，XZ 平面），但顶点位移发生在实例本地空间，
// 所以要用上面存的 cos/sin 把世界风向转回本地 —— 不然每株草都朝各自的方向倒，
// 一片草看上去像被炸开的蒲公英。
//
// 幅度：根部不动，越往上越弯（h²），末端位移 = sway_strength（米）。
shader_type spatial;
render_mode cull_disabled, diffuse_burley, specular_schlick_ggx;

uniform vec4 albedo_tint : source_color = vec4(1.0, 1.0, 1.0, 1.0);
uniform float roughness : hint_range(0.0, 1.0) = 0.9;

// —— 风 ——
// 顶端最大位移（米）。0.03~0.08 是"轻微"，0.15 以上就明显了。
uniform float sway_strength : hint_range(0.0, 0.5) = 0.06;
// 摆动速度（弧度/秒）。1.0 ≈ 6 秒一个来回。
uniform float sway_speed : hint_range(0.0, 6.0) = 1.2;
// 世界风向（XZ 平面）
uniform vec2 wind_direction = vec2(1.0, 0.35);
// 风力总开关（0 = 完全不动）
uniform float wind_strength : hint_range(0.0, 3.0) = 1.0;
// 草株高度（米）—— 用来把顶点高度归一化，不同草型（草丛 / 草簇）不一样
uniform float plant_height : hint_range(0.05, 3.0) = 0.7;

void vertex() {
	float phase = INSTANCE_CUSTOM.x;
	float cr = INSTANCE_CUSTOM.y;
	float sr = INSTANCE_CUSTOM.z;

	// 根部不动，顶部摆动最大
	float h = clamp(VERTEX.y / max(plant_height, 0.01), 0.0, 1.0);
	float bend = h * h;

	// 两组不同频率叠在一起 = 阵风，不是机械的正弦
	float t = TIME * sway_speed + phase;
	float gust = 0.65 * sin(t) + 0.35 * sin(t * 1.73 + 1.1);

	float amp = sway_strength * wind_strength * gust;

	// 世界风向 -> 实例本地空间
	vec2 wd = vec2(
		wind_direction.x * cr + wind_direction.y * sr,
		-wind_direction.x * sr + wind_direction.y * cr);

	VERTEX.x += wd.x * amp * bend;
	VERTEX.z += wd.y * amp * bend;
}

void fragment() {
	// COLOR_0 = 草的顶点色（脚本里已经烘了层次）
	ALBEDO = COLOR.rgb * albedo_tint.rgb;
	ROUGHNESS = roughness;
	SPECULAR = 0.12;
}

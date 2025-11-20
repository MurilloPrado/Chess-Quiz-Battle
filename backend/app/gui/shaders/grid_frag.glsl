#version 330
uniform float u_time;
uniform vec2  u_resolution;
out vec4 color;

// ===== knobs =====
const float SPACING     = 1.0;   // espaçamento lógico (maior = mais espaçado)
const float THICKNESS   = 0.05;  // espessura da linha
const float SPEED       = 1.2;   // velocidade (subindo)
const float WIDTH_NEAR  = 10.0;  // abertura na base (parte de baixo)
const float WIDTH_FAR   = 4.0;   // abertura no horizonte (topo da metade)
// =================

float grid(vec2 P, float sp, float th) {
    vec2 g = abs(fract(P / sp) - 0.5) * sp;
    float line = min(g.x, g.y);
    return smoothstep(th, th - 0.01, line);
}

void main() {
    // uv em 0..1 na METADE DE BAIXO (usando pixels do FBO)
    vec2 uv = gl_FragCoord.xy / u_resolution;

    // profundidade linear: 0 no topo (horizonte), 1 na base
    float d = uv.y;

    // abertura varia LINEARMENTE -> LINHAS RETAS (sem arcos)
    float width_x = mix(WIDTH_FAR, WIDTH_NEAR, d);

    // X converge ao centro; Y sobe (sinal negativo em u_time)
    vec2 P = vec2(
        (uv.x - 0.5) * width_x,
        (uv.y * 28.0) - u_time * SPEED
    );

    float g = grid(P, SPACING, THICKNESS);
    vec3 neon = vec3(0.05, 0.9, 0.2);
    color = vec4(mix(vec3(0.0), neon, g * 0.9), 1.0);
}

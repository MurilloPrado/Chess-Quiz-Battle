from ursina import *
from ursina.shaders import unlit_shader
from pathlib import Path
import math

app = Ursina(borderless=False)

# Deixa o Ursina procurar modelos na pasta do arquivo
application.asset_folder = Path(__file__).parent

window.title = 'Chess Quiz Battle - Hologram Menu'
window.color = color.black
window.fullscreen = False

# ---------------------------
#  CÂMERA / CENA
# ---------------------------
# posição e ângulo da câmera para lembrar o protótipo
camera.position = (0, 12, -22)
camera.look_at((0, 0, 10))
camera.fov = 60

# um pouquinho de neblina ajuda a dar “profundidade”
scene.fog_color = color.black
scene.fog_density = 0.04


# ---------------------------
#  GRID NEON EM PERSPECTIVA
# ---------------------------

def make_neon_grid():
    grid_color  = color.hex("#27943b")
    parent = Entity()  # tudo do grid fica agrupado aqui

    # --- linhas horizontais (faixas que vêm "pra frente") ---
    grid_lines = 12        # quantas faixas
    spacing_z = 1.5        # distância entre faixas
    start_z = -8          # onde começa o grid
    base_width = 26.0      # largura na faixa mais distante
    width_growth = 3.2     # quanto aumenta a largura a cada faixa

    for i in range(grid_lines):
        z = start_z + i * spacing_z
        width = base_width + i * width_growth
        Entity(
            parent=parent,
            model='cube',
            color=grid_color,
            texture=None,
            shader=unlit_shader,
            position=(0, 0, z),
            scale=(width, 0.03, 0.06),   # (largura, altura, "profundidade" da linha)
        )

    # --- linhas verticais que convergem no "horizonte" ---
    vert_count = 5          # quantidade de linhas verticais
    bottom_width = 20.0      # espalhamento na base (perto da câmera)
    top_width = 60.0          # espalhamento lá no fundo (perto do horizonte)
    horizon_z = start_z - spacing_z   # um pouco antes da primeira faixa
    bottom_z = start_z + grid_lines * spacing_z

    for j in range(-vert_count // 2, vert_count // 2 + 1):
        t = j / float(vert_count // 2)    # -1 .. 1
        x_top = t * top_width * 0.5
        x_bottom = t * bottom_width * 0.5

        # pontos inicial e final da linha
        x1, z1 = x_top, horizon_z
        x2, z2 = x_bottom, bottom_z

        mid_x = (x1 + x2) / 2.0
        mid_z = (z1 + z2) / 2.0
        dx = x2 - x1
        dz = z2 - z1
        length = math.sqrt(dx * dx + dz * dz)

        # ângulo da linha no plano XZ
        angle_y = math.degrees(math.atan2(dx, dz))

        Entity(
            parent=parent,
            model='cube',
            color=grid_color,
            texture=None,
            shader=unlit_shader,
            position=(mid_x, -0.6, mid_z),
            rotation_y=angle_y,
            scale=(0.06, 0.03, length),   # fino em X, comprido em Z
        )

    return parent


grid_entity = make_neon_grid()


# ---------------------------
#  PEÇAS / HOLOGRAMA
# ---------------------------

# Cores base (parecidas com o protótipo)
front_color = color.hex('#14e63c')    # verde
back_color  = color.hex('#00e6ff')   # ciano
shadow_color = color.hex("#1F1F1F")

# Peça grande na frente, à esquerda
pawn_front = Entity(
    model='Queen hologram',                # seu Pawn.obj
    position=(-8, -5, 5),       # x, y, z (mais perto da câmera)
    scale=3.2,
    rotation_y=110,
    color=front_color,
    texture=None,
    shader=unlit_shader,         # não depende de luz -> fica “brilhante”
)


# Sombra da peça da frente (disco translúcido)
shadow_front = Entity(
    model='circle',
    color=shadow_color,
    rotation_x=90,
    position=pawn_front.position + Vec3(0, -0.78, 0),
    scale=(3.6, 3.6, 3.6),
    shader=unlit_shader,
)

# Peça menor ao fundo, à direita
pawn_back = Entity(
    model='Knight hologram',     # seu Knight hologram.obj
    position=(8, -1, 12),     # mais longe -> parece menor
    scale=1.8,
    rotation_y=-50,
    color=back_color,
    texture=None,
    shader=unlit_shader,
)

shadow_back = Entity(
    model='circle',
    color=shadow_color,
    rotation_x=90,
    position=pawn_back.position + Vec3(0, -0.78, 0),
    scale=(2.4, 2.4, 2.4),
    shader=unlit_shader,
)

base_y_front = pawn_front.y
base_y_back = pawn_back.y

# ---------------------------
#  EFEITO "HOLOGRAMA"
# ---------------------------

def update():
    t = time.time()

    # leve pulsar no brilho (altera alpha da cor)
    a1 = 0.7 + 0.15 * math.sin(t * 6)
    a2 = 0.7 + 0.15 * math.sin(t * 6 + 1.8)

    pawn_front.y = base_y_front + 0.35 * math.sin(t * 2.4)
    pawn_back.y  = base_y_back  + 0.28 * math.sin(t * 2.4 + 1.3)

    # sombras acompanham
    shadow_front.y = pawn_front.y - 0.58
    shadow_back.y  = pawn_back.y  - 0.58


app.run()

# backend/app/gui/quiz3d_client.py

import asyncio
import json
import math
import threading
import time
import sys
from pathlib import Path

from ursina import *
from ursina.shaders import unlit_shader

# ================= CONFIG =================

WS_URL = "ws://192.168.100.49:8765/ws"   # <-- AJUSTE AQUI
VIEWER_NAME = "Hologram Viewer"
DEBUG_LOCAL = True

latest_state = None
latest_state_lock = threading.Lock()

FAKE_QUIZ = {
    "battleId": 1,
    "attacker": {
        "color": "white",
        "piece": "knight",
        "model": "Knight hologram",
    },
    "defender": {
        "color": "black",
        "piece": "queen",
        "model": "Queen hologram",
    },
    "currentSide": "white",
    "question": (
        "De acordo com Alan Turing, é possível criar um programa que analisa "
        "outro programa e diz se ele vai entrar em loop?"
    ),
    "choices": [
        "Sim, qualquer algoritmo pode ser analisado dessa forma.",
        "Não, esse problema é indecidível para máquinas de Turing.",
        "Apenas se o programa tiver laços finitos conhecidos.",
        "Somente em linguagens de alto nível com tipagem estática."
    ],
    "correctIndex": 1,
    "remainingTime": 15,
    "maxTime": 15,
}

_fake_timer_value = 15.0
_fake_last_switch = time.time()

def set_latest_state(data: dict):
    global latest_state
    with latest_state_lock:
        latest_state = data


def get_latest_state():
    with latest_state_lock:
        return latest_state
    
def _make_neon_grid():
    grid_color = color.hex("#27943b")
    parent = Entity(parent=camera_pivot)

    # --- linhas horizontais (faixas que vêm "pra frente") ---
    grid_lines = 12        # quantas faixas
    spacing_z = 1.5        # distância entre faixas
    start_z = -8           # onde começa o grid
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
            scale=(width, 0.03, 0.06),
        )

    # --- linhas verticais que convergem no "horizonte" ---
    vert_count = 5          # quantidade de linhas verticais
    bottom_width = 20.0     # espalhamento na base (perto da câmera)
    top_width = 60.0        # espalhamento lá no fundo (perto do horizonte)
    horizon_z = start_z - spacing_z
    bottom_z = start_z + grid_lines * spacing_z

    for j in range(-vert_count // 2, vert_count // 2 + 1):
        t = j / float(vert_count // 2 or 1)  # -1 .. 1
        x_top = t * top_width * 0.5
        x_bottom = t * bottom_width * 0.5

        x1, z1 = x_top, horizon_z
        x2, z2 = x_bottom, bottom_z

        mid_x = (x1 + x2) / 2.0
        mid_z = (z1 + z2) / 2.0
        dx = x2 - x1
        dz = z2 - z1
        length = math.sqrt(dx * dx + dz * dz)

        angle_y = math.degrees(math.atan2(dx, dz))

        Entity(
            parent=parent,
            model='cube',
            color=grid_color,
            texture=None,
            shader=unlit_shader,
            position=(mid_x, -0.6, mid_z),
            rotation_y=angle_y,
            scale=(0.06, 0.03, length),
        )

    return parent


# ================= CENA 3D =================

# comecei aqui

# ponto médio entre as duas peças (centro do duelo)
DUEL_CENTER = Vec3(0, -2, 9)

BASE_CAMERA_POS = Vec3(0, 11, -26)   # posição **relativa** ao centro
BASE_CAMERA_LOOK = DUEL_CENTER  # olhar para o centro do duelo


class DuelScene(Entity):
    GREEN_WHITE = color.hex('#14e63c')   # brancas
    CYAN_BLACK  = color.hex('#00e6ff')   # pretas
    SHADOW_BASE = color.hex("#1F1F1F")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.scene_root = None
        self.is_flipped = False

        # self.grid_entity = self._make_neon_grid()

        self.left_piece = None
        self.right_piece = None
        self.left_shadow = None
        self.right_shadow = None

        self._base_y_left = 0
        self._base_y_right = 0
        self._entry_t = 0.0
        self._do_entry_anim = False

        self.current_side = "white"

        self.ui_player = Text(
            text="",
            parent=camera.ui,
            origin=(0, 0),
            position=(0, 0.21),
            scale=0.8,
            color=color.lime,
        )

        self.enabled = False


    def _make_piece_with_shadow(self, model_name: str, is_left: bool, color_piece):
        """
        Cria uma peça + sombra exatamente nas posições do testeRenderizarPecas.py
        - is_left=True  -> peça da frente, à esquerda (pawn_front)
        - is_left=False -> peça menor, ao fundo, à direita (pawn_back)
        """
        if is_left:
            x, y, z = -12, -5, 5
            scale_val = 3.2
            rot_y = 110
            shadow_scale = (3.6, 3.6, 3.6)
        else:
            x, y, z = 8, -1, 12
            scale_val = 1.8
            rot_y = -50
            shadow_scale = (2.4, 2.4, 2.4)

        piece = Entity(
            parent=self,
            model=model_name,
            position=Vec3(x, y - 15, z),  # começa fora da tela para a animação de entrada
            scale=scale_val,
            rotation_y=rot_y,
            color=color_piece,
            texture=None,
            shader=unlit_shader,
        )

        shadow = Entity(
            parent=self,
            model='circle',
            color=self.SHADOW_BASE,
            rotation_x=90,
            position=piece.position + Vec3(0, -0.78, 0),
            scale=shadow_scale,
            shader=unlit_shader,
        )

        if is_left:
            self._base_y_left = y
        else:
            self._base_y_right = y

        return piece, shadow
    
    def swap_front_back(self, duration=0.6):
        """
        Anima a troca: quem estava na frente e grande vai para trás e menor,
        e quem estava atrás passa para frente e maior.
        """
        if not (self.left_piece and self.right_piece and self.left_shadow and self.right_shadow):
            return

        FRONT = {
            "pos": Vec3(-12, -5, 5),
            "scale": 3.2,
            "rot_y": 110,
            "shadow_scale": (3.6, 3.6, 3.6)
        }
        BACK = {
            "pos": Vec3(8, -1, 12),
            "scale": 1.8,
            "rot_y": -50,
            "shadow_scale": (2.4, 2.4, 2.4)
        }

        if not self.is_flipped:
            # estado atual: esquerda na frente, direita atrás
            # alvo: esquerda vai para trás, direita vem para frente
            piece_L_target = BACK
            piece_R_target = FRONT
        else:
            # estado atual: esquerda atrás, direita na frente
            # alvo: volta pro layout original
            piece_L_target = FRONT
            piece_R_target = BACK

        # Anima LEFT
        self.left_piece.animate_position(piece_L_target["pos"], duration=duration, curve=curve.in_out_quad)
        self.left_piece.animate_scale(piece_L_target["scale"], duration=duration, curve=curve.in_out_quad)
        self.left_piece.animate_rotation_y(piece_L_target["rot_y"], duration=duration, curve=curve.in_out_quad)
        # Sombra LEFT
        self.left_shadow.animate_position(piece_L_target["pos"] + Vec3(0, -0.78, 0), duration=duration, curve=curve.in_out_quad)
        self.left_shadow.animate_scale(piece_L_target["shadow_scale"], duration=duration, curve=curve.in_out_quad)

        # Anima RIGHT
        self.right_piece.animate_position(piece_R_target["pos"], duration=duration, curve=curve.in_out_quad)
        self.right_piece.animate_scale(piece_R_target["scale"], duration=duration, curve=curve.in_out_quad)
        self.right_piece.animate_rotation_y(piece_R_target["rot_y"], duration=duration, curve=curve.in_out_quad)
        # Sombra RIGHT
        self.right_shadow.animate_position(piece_R_target["pos"] + Vec3(0, -0.78, 0), duration=duration, curve=curve.in_out_quad)
        self.right_shadow.animate_scale(piece_R_target["shadow_scale"], duration=duration, curve=curve.in_out_quad)

        # depois que a animação terminar, atualiza as bases do "flutuar"
        def _apply_bases():
            self._base_y_left  = piece_L_target["pos"].y
            self._base_y_right = piece_R_target["pos"].y
            self.is_flipped = not self.is_flipped # <-- ESSA INVERSÃO É FUNDAMENTAL

        invoke(_apply_bases, delay=duration)

    def set_duel_from_quiz(self, quiz: dict):
        if not quiz:
            self.enabled = False
            self.ui_player.text = ""
            return

        atk = quiz.get("attacker") or {}
        dfn = quiz.get("defender") or {}

        attacker_color = atk.get("color", "white")
        defender_color = dfn.get("color", "black")
        attacker_model = atk.get("model", "Pawn hologram")
        defender_model = dfn.get("model", "Pawn hologram")
        current_side = quiz.get("currentSide", "white")
        question = quiz.get("question", "")

        def neon(c):
            return self.GREEN_WHITE if c == "white" else self.CYAN_BLACK

        for ent in (self.left_piece, self.right_piece, self.left_shadow, self.right_shadow):
            if ent:
                destroy(ent)

        self.left_piece, self.left_shadow = self._make_piece_with_shadow(
            model_name=attacker_model,
            is_left=True,
            color_piece=neon(attacker_color),
        )
        self.right_piece, self.right_shadow = self._make_piece_with_shadow(
            model_name=defender_model,
            is_left=False,
            color_piece=neon(defender_color),
        )

        self.is_flipped = False

        self.current_side = current_side
        self._entry_t = 0.0
        self._do_entry_anim = True

        self.ui_player.text = f"Vez das {'Brancas' if current_side == 'white' else 'Pretas'}"

        # reseta o pivot + câmera para a posição base
        camera_pivot.position = DUEL_CENTER
        camera_pivot.rotation_y = 0     # começa sempre na visão do "lado base"

        camera.position = BASE_CAMERA_POS
        camera.look_at(BASE_CAMERA_LOOK)

        # força a câmera já ficar alinhada com o side atual, mas via pivot
        self.current_side = None        # garante que vai detectar mudança
        self.focus_on_side(current_side)

        self.enabled = True

    def focus_on_side(self, side: str):
        if side not in ("white", "black"):
            return

        # se não mudou, não precisa animar
        if side == self.current_side:
            return

        self.current_side = side
        self.ui_player.text = f"Vez das {'Brancas' if side == 'white' else 'Pretas'}"

        # white = ângulo 0°, black = 180° (meia volta)
        if side == "white":
            target_rot = 0
            do_swap = self.is_flipped
        else:
            target_rot = 40
            do_swap = not self.is_flipped


        # gira o pivot, a câmera “dá a volta” mantendo o duelo no centro
        camera_pivot.animate_rotation_y(
            target_rot,
            duration=0.7,
            curve=curve.in_out_quad
        )

        if do_swap:
            self.swap_front_back()

    def step(self, dt: float):
        if not self.enabled:
            return

        t = time.time()

        if getattr(self, "_do_entry_anim", False):
            self._entry_t += dt * 1.5
            k = min(1.0, self._entry_t)

            if self.left_piece:
                self.left_piece.y = lerp(self._base_y_left - 15, self._base_y_left, k)
                self.left_shadow.y = self.left_piece.y - 0.58

            if self.right_piece:
                self.right_piece.y = lerp(self._base_y_right - 15, self._base_y_right, k)
                self.right_shadow.y = self.right_piece.y - 0.58

            if k >= 1.0:
                self._do_entry_anim = False
        else:
            if self.left_piece:
                self.left_piece.y = self._base_y_left + 0.35 * math.sin(t * 2.4)
                self.left_shadow.y = self.left_piece.y - 0.58
            if self.right_piece:
                self.right_piece.y = self._base_y_right + 0.28 * math.sin(t * 2.4 + 1.3)
                self.right_shadow.y = self.right_piece.y - 0.58

        if self.left_piece:
            self.left_piece.rotation_y += 8 * dt
        if self.right_piece:
            self.right_piece.rotation_y -= 8 * dt


class QuizUI(Entity):
    def __init__(self):
        super().__init__(parent=camera.ui)

        self.neon_color = color.hex("#14e63c")
        # self.neon_color = color.hex("#1900ff")
        self.current_side = "white"
        self.enabled = False

        # -----------------------------
        # Caixa da Pergunta
        # -----------------------------
        # origin no topo -> cresce só para baixo
        self.box_question = Entity(
            parent=camera.ui,
            model=Quad(thickness=3),
            color=color.black,          # fundo preto
            origin=(-0.1, 0.5),            # topo central
            position=(0, 0.43),
            scale=(1, 0.20),         # largura / altura base
            z=1,
        )

        # só contorno verde
        self.box_question_border = Entity(
            parent=self.box_question,
            model=Quad(thickness=3),
            color=self.neon_color,
            origin=(-0.1, 0.07),
            position=(0, -0.43),
            scale=(1.02, 1.1),
            z=2,
        )

        # texto da pergunta, alinhado no topo-esquerdo da box
        self.text_question = Text(
            parent=camera.ui,
            text="",
            origin=(-0.5, 0.5),
            scale=1,                  # maior
            color=color.white,
            z=-1,
        )

        # -----------------------------
        # Timer circular (dentro da box, canto direito)
        # -----------------------------
        self.timer_group = Entity(
            parent=self.box_question,
            scale=(0.1, 0.4),
            origin=(-0.5, 0.5),
            position=(0.83, -0.06),
            z=-1,
        )

        self.timer_circle_bg = Entity(
            parent=self.timer_group,
            model='circle',
            color=color.black,
            scale=0.95,
            z=-0.05,
        )

        self.timer_circle_border = Entity(
            parent=self.timer_group,
            model='circle',
            color=color.white,
            scale=1.1,
            z=-0.03,
        )

        # preenchimento preto que vai "comer" a borda
        self.timer_circle_fill = Entity(
            parent=self.timer_group,
            model='circle',
            color=color.black,
            scale=0.0,        # começa sem preencher nada
            z=-0.05,
        )

        self.timer_text = Text(
            parent=camera.ui,
            text="15",
            origin=(0, 0),
            scale=1.6,
            color=color.white,
            z=-1,
        )

        # -----------------------------
        # Barra de tempo (linha branca logo abaixo da box)
        # -----------------------------
        self.timer_bar = Entity(
            parent=camera.ui,
            model='quad',
            color=color.white,
            scale=(0.90, 0.01),
            position=(-0.8, 0.22),
            z=1,
        )

        # -----------------------------
        # Alternativas
        # -----------------------------
        self.answers: list[Entity] = []
        self._create_answer_buttons()

        # -----------------------------
        # K.O e vencedor (por enquanto só placeholder)
        # -----------------------------
        self.ko_label = Text(
            parent=camera.ui,
            text="K.O!",
            origin=(0, 0),
            scale=5,
            color=color.black,
            enabled=False,
            position=(0, 0),
        )

        self.win_label = Text(
            parent=camera.ui,
            text="Vencedor!",
            origin=(0, 0),
            scale=3,
            color=color.white,
            enabled=False,
            position=(0, -0.2),
        )

    # -----------------------------
    # Cria os botões de alternativas
    # -----------------------------
    def _create_answer_buttons(self):
        for i in range(4):
            btn = Entity(
                parent=camera.ui,
                model=Quad(thickness=0.035),
                color=color.black,        # fundo preto
                scale=(0.42, 0.15),
                position=(0, -0.1),       # posição inicial; layout ajusta depois
                origin=(-0.1, 0.5),
                z=1,
            )

            # borda neon
            Entity(
                parent=btn,
                model=Quad(thickness=0.035),
                color=self.neon_color,
                position=(0, -0.1),
                origin=(-0.1, 0.4),
                scale=(1.02, 1.1),
                z=2,
            )

            txt = Text(
                parent=camera.ui,
                text="",
                origin=(-0.5, 0),
                scale=1,
                color=color.white,
                z=-2,
            )

            btn.text_entity = txt
            btn.index = i
            btn.on_click = lambda b=btn: self.select_answer(b.index)

            self.answers.append(btn)

    def autoscale_text(self, txt: Text, max_width: float, max_height: float, min_scale=0.5, max_scale=1.1):
        """
        Ajusta txt.scale automaticamente para caber dentro de max_width x max_height.
        Não usa application.step(), só recalcula de forma aproximada.
        """
        txt.scale = max_scale

        # Faz algumas iterações reduzindo até caber ou chegar no mínimo
        for _ in range(20):
            # width/height do Text usam o texto atual e o scale atual
            if (txt.width <= max_width and txt.height <= max_height) or txt.scale <= min_scale:
                break

            txt.scale *= 0.96

    # -----------------------------
    # Quebra de linha manual (sem usar Text.wordwrap)
    # -----------------------------
    def _wrap_text(self, text: str, limit: int) -> str:
        """
        Quebra o texto em linhas de até 'limit' caracteres, tentando
        quebrar em espaços. Retorna uma string com '\n'.
        """
        words = (text or "").split()
        if not words:
            return ""

        lines = []
        current = words[0]

        for w in words[1:]:
            if len(current) + 1 + len(w) <= limit:
                current += " " + w
            else:
                lines.append(current)
                current = w

        lines.append(current)
        return "\n".join(lines)


    # -----------------------------
    # Layout completo: lado, pergunta, alternativas
    # -----------------------------
    def update_layout(self, side: str, question: str, alternatives: list[str]):
        self.current_side = side

        # Quebra de linha suave
        wrapped_q = self._wrap_text(question, 55)
        self.text_question.text = wrapped_q

        # Ajuste dinâmico da altura da box
        lines = wrapped_q.count("\n") + 1
        new_h = 0.16 + (lines - 1) * 0.035
        self.box_question.scale_y = new_h

        # Posicionamento da box esquerda/direita
        if side == "white":
            bx = -0.45     # peça branca à esquerda → UI à esquerda
            col1_x, col2_x = 0.05, 0.50
        else:
            bx = 0.2      # peça preta à direita → UI à direita
            col1_x, col2_x = -0.05, -0.50

        self.box_question.x = bx

        # topo-esquerdo da box, com padding
        self.text_question.x = self.box_question.x - 0.35
        self.text_question.y = self.box_question.y - 0.03

        # timer dentro da box (canto direito)
        self.timer_group.position = (self.box_question.scale_x * 0.5, -0.5)
        self.timer_text.position = (self.box_question.x + self.box_question.scale_x * 0.495, 0.33)

        # barra branca sempre sob a box
        bottom_y = self.box_question.y - self.box_question.scale_y
        self.timer_bar.x = bx + 0.1
        self.timer_bar.y = bottom_y - 0.025
        
        max_w = self.box_question.scale_x * 2 - 0.06
        max_h = self.box_question.scale_y * 2 - 0.06
        self.autoscale_text(self.text_question, max_w, max_h)

        # Alternativas alinhadas no protótipo
        row1_y = -0.05
        row2_y = -0.28

        positions = [
            (col1_x, row1_y),
            (col2_x, row1_y),
            (col1_x, row2_y),
            (col2_x, row2_y),
        ]

        for i, btn in enumerate(self.answers):
                # 1) posição do botão (local à box_question)
                x, y = positions[i]
                btn.x = x
                btn.y = y

                # 2) texto da alternativa
                alt = alternatives[i] if i < len(alternatives) else ""
                txt = btn.text_entity
                txt.text = f"{chr(97+i)}. {self._wrap_text(alt, 30)}"

                btn_inner_w = btn.scale_x * 2 - 0.04
                btn_inner_h = btn.scale_y * 2 - 0.02
                self.autoscale_text(txt, btn_inner_w, btn_inner_h)
                

                txt.x = x - 0.15    # começa da esquerda do botão
                txt.y = y -0.08               # centralizado na altura

    # -----------------------------
    # Timer (número + barra + círculo)
    # -----------------------------
    def update_timer(self, remaining: float, max_time: float):
        if max_time <= 0:
            frac = 0.0
        else:
            t = max(0.0, min(remaining, max_time))
            frac = t / max_time

        # número
        self.timer_text.text = str(int(math.ceil(remaining)))

        # barra diminuindo
        self.timer_bar.scale_x = 0.80 * frac

        # círculo “esvaziando”
        inner_start = 0.0     # sem preenchimento no início
        inner_end   = 1.10    # círculo preto maior que a borda no final

        self.timer_circle_fill.scale = lerp(inner_start, inner_end, 1 - frac)

    # -----------------------------
    # Clique na alternativa (feedback local)
    # -----------------------------
    def select_answer(self, idx: int):
        for btn in self.answers:
            btn.color = color.black
            btn.text_entity.color = color.white

        self.answers[idx].color = color.rgb(25, 25, 25)
        self.answers[idx].text_entity.color = self.neon_color
        print(f"[quiz3d_client] Resposta clicada no viewer (idx={idx})")

    # -----------------------------
    # Efeitos de fim (placeholder)
    # -----------------------------
    def show_ko(self):
        self.ko_label.enabled = True
        self.ko_label.scale = 1
        self.ko_label.animate_scale(7, duration=0.5, curve=curve.out_expo)

    def show_winner(self, winner: str):
        self.win_label.text = f"{winner} venceu!"
        self.win_label.enabled = True
        self.win_label.scale = 1
        self.win_label.animate_scale(4, duration=0.5, curve=curve.out_expo)



# ================= WS EM THREAD =================

async def ws_consumer():
    import websockets  # pip install websockets

    while True:
        try:
            print(f"[quiz3d_client] Conectando em {WS_URL}...")
            async with websockets.connect(WS_URL) as ws:
                join_msg = {"type": "join", "name": VIEWER_NAME, "avatar": None}
                await ws.send(json.dumps(join_msg))

                async for raw in ws:
                    try:
                        data = json.loads(raw)
                    except Exception:
                        continue

                    if data.get("type") == "state":
                        set_latest_state(data)
        except Exception as e:
            print(f"[quiz3d_client] Erro WS: {e}")
            await asyncio.sleep(2.0)


def start_ws_thread():
    if DEBUG_LOCAL:
        print("[quiz3d_client] DEBUG_LOCAL ativo: WS desabilitado.")
        return None

    loop = asyncio.new_event_loop()

    def runner():
        asyncio.set_event_loop(loop)
        loop.run_until_complete(ws_consumer())

    t = threading.Thread(target=runner, daemon=True)
    t.start()
    return t


# ================= MAIN URSINA =================

app = Ursina(borderless=False)

# raiz do projeto: .../Chess-Quiz-Battle
ROOT_DIR = Path(__file__).resolve().parents[4]

# pasta onde estão os modelos 3D .obj
application.asset_folder = ROOT_DIR / "assets" / "3d"

window.title = 'Chess Quiz Battle - Duelo 3D'
window.color = color.black
window.fullscreen = False

scene.fog_color = color.black
scene.fog_density = 0.04

camera_pivot = Entity(
    name='camera_pivot',
    position=DUEL_CENTER   # centro da órbita: meio entre as peças
)

# câmera fica como "filha" do pivot
camera.parent = camera_pivot

camera.position = BASE_CAMERA_POS     # posição relativa ao pivot
camera.look_at(BASE_CAMERA_LOOK)
camera.fov = 60

scene_pivot = Entity()
duel_scene = DuelScene(parent=scene_pivot)
duel_scene.scene_root = scene_pivot
quiz_ui = QuizUI()
quiz_ui.enabled = False

_grid_entity = _make_neon_grid()

_last_battle_id = None
_last_phase = None
_ever_had_quiz = False  # para saber quando sair do quiz e fechar


def update():
    global _last_battle_id, _last_phase, _ever_had_quiz, _fake_timer_value, FAKE_QUIZ

    dt = time.dt
    duel_scene.step(dt)

    # ======================================================
    #        MODO DEBUG LOCAL (SEM WS, MAS COM PEÇAS)
    # ======================================================
    if DEBUG_LOCAL:

        # reduz timer
        _fake_timer_value -= dt
        if _fake_timer_value <= 0:
            _fake_timer_value = FAKE_QUIZ["maxTime"]

            # alterna o lado, só para você visualizar a câmera girar
            FAKE_QUIZ["currentSide"] = (
                "black" if FAKE_QUIZ["currentSide"] == "white" else "white"
            )
            print("[DEBUG] trocou lado para:", FAKE_QUIZ["currentSide"])

        FAKE_QUIZ["remainingTime"] = max(0, _fake_timer_value)

        # monta o estado igual ao backend REAL monta
        state = {
            "phase": "quiz",
            "quiz": FAKE_QUIZ,
        }

    else:
        # ================= MODO NORMAL (com WS) =================
        state = get_latest_state()
        if not state:
            return

    # ================= fluxo normal continua ====================
    phase = state.get("phase")
    quiz = state.get("quiz")

     # ⬇️ SE JÁ TEVE QUIZ E O BACKEND SAIU DA FASE "quiz", FECHA A JANELA
    if _ever_had_quiz and phase != "quiz":
        print("[quiz3d_client] Quiz terminou, fechando viewer 3D.")
        quiz_ui.enabled = False
        application.quit()
        sys.exit(0)

    # se ainda não tem quiz nesse state, não desenha nada (mas NÃO fecha)
    if not quiz:
        return

    _ever_had_quiz = True

    current_side = quiz.get("currentSide", "white")
    question = quiz.get("question", "")
    alts = quiz.get("alternatives") or quiz.get("choices") or []

    # atualiza UI
    quiz_ui.enabled = True
    quiz_ui.update_layout(current_side, question, alts)
    quiz_ui.update_timer(
        quiz.get("remainingTime", 15),
        quiz.get("maxTime", 15)
    )

    # === PEÇAS 3D (aqui é onde a mágica acontece no debug!) ===
    battle_id = quiz.get("battleId")
    if battle_id != _last_battle_id:
        _last_battle_id = battle_id
        duel_scene.set_duel_from_quiz(quiz)
    else:
        if current_side != duel_scene.current_side:
            duel_scene.focus_on_side(current_side)
            duel_scene.ui_player.text = (
                f"Vez das {'Brancas' if current_side == 'white' else 'Pretas'}"
            )

    # Se já teve quiz e agora phase NÃO é quiz -> FECHA APP
    if _ever_had_quiz and phase != "quiz":
        print("[quiz3d_client] Quiz terminou, fechando viewer 3D.")
        quiz_ui.enabled = False
        application.quit()
        sys.exit(0)


if __name__ == "__main__":
    start_ws_thread()
    app.run()

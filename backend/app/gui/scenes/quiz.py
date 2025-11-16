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

latest_state = None
latest_state_lock = threading.Lock()


def set_latest_state(data: dict):
    global latest_state
    with latest_state_lock:
        latest_state = data


def get_latest_state():
    with latest_state_lock:
        return latest_state


# ================= CENA 3D =================

BASE_CAMERA_POS = Vec3(0, 12, -22)
BASE_CAMERA_LOOK = Vec3(0, 0, 10)


class DuelScene(Entity):
    GREEN_WHITE = color.hex('#14e63c')   # brancas
    CYAN_BLACK  = color.hex('#00e6ff')   # pretas
    SHADOW_BASE = color.hex("#1F1F1F")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.grid_entity = self._make_neon_grid()

        self.left_piece = None
        self.right_piece = None
        self.left_shadow = None
        self.right_shadow = None

        self._base_y_left = 0
        self._base_y_right = 0
        self._entry_t = 0.0
        self._do_entry_anim = False

        self.current_side = "white"

        self.ui_question = Text(
            text="Aguardando batalha...",
            parent=camera.ui,
            origin=(0, 0),
            position=(0, 0.4),
            scale=1,
            color=color.white,
        )
        self.ui_player = Text(
            text="",
            parent=camera.ui,
            origin=(0, 0),
            position=(0, 0.32),
            scale=0.8,
            color=color.lime,
        )

        self.enabled = False

    def _make_neon_grid(self):
        grid_color = color.hex("#27943b")
        parent = Entity()

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

    def _make_piece_with_shadow(self, model_name: str, is_left: bool, color_piece):
        """
        Cria uma peça + sombra exatamente nas posições do testeRenderizarPecas.py
        - is_left=True  -> peça da frente, à esquerda (pawn_front)
        - is_left=False -> peça menor, ao fundo, à direita (pawn_back)
        """
        if is_left:
            x, y, z = -8, -5, 5
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

    def set_duel_from_quiz(self, quiz: dict):
        if not quiz:
            self.enabled = False
            self.ui_question.text = "Aguardando batalha..."
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

        self.current_side = current_side
        self._entry_t = 0.0
        self._do_entry_anim = True

        self.ui_question.text = question or "Sem pergunta"
        self.ui_player.text = f"Vez das {'Brancas' if current_side == 'white' else 'Pretas'}"

        camera.position = BASE_CAMERA_POS
        camera.look_at(BASE_CAMERA_LOOK)
        self.focus_on_side(current_side)

        self.enabled = True

    def focus_on_side(self, side: str):
        if side not in ("white", "black"):
            return
        self.current_side = side

        if side == "white":
            target_pos = Vec3(-2, 10, -20)
            target_look = Vec3(-2, -2, 8)
        else:
            target_pos = Vec3(2, 10, -20)
            target_look = Vec3(2, -2, 10)

        camera.animate_position(target_pos, duration=0.6, curve=curve.in_out_quad)

        def _update_look():
            camera.look_at(target_look)
        invoke(_update_look, delay=0.6)

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

camera.position = BASE_CAMERA_POS
camera.look_at(BASE_CAMERA_LOOK)
camera.fov = 60

duel_scene = DuelScene()

_last_battle_id = None
_last_phase = None
_ever_had_quiz = False  # para saber quando sair do quiz e fechar


def update():
    global _last_battle_id, _last_phase, _ever_had_quiz

    dt = time.dt
    duel_scene.step(dt)

    state = get_latest_state()
    if not state:
        return

    phase = state.get("phase")
    quiz = state.get("quiz")

    if phase != _last_phase:
        print(f"[quiz3d_client] phase -> {phase}")
        _last_phase = phase

    # Se nunca entrou em quiz ainda, só ignora
    if phase == "quiz" and quiz:
        _ever_had_quiz = True
        battle_id = quiz.get("battleId")

        if battle_id != _last_battle_id:
            _last_battle_id = battle_id
            duel_scene.set_duel_from_quiz(quiz)
        else:
            current_side = quiz.get("currentSide", "white")
            if current_side != duel_scene.current_side:
                duel_scene.focus_on_side(current_side)
                duel_scene.ui_player.text = f"Vez das {'Brancas' if current_side == 'white' else 'Pretas'}"
        return

    # Se já teve quiz e agora phase NÃO é quiz -> FECHA APP
    if _ever_had_quiz and phase != "quiz":
        print("[quiz3d_client] Quiz terminou, fechando viewer 3D.")
        application.quit()
        sys.exit(0)


if __name__ == "__main__":
    start_ws_thread()
    app.run()

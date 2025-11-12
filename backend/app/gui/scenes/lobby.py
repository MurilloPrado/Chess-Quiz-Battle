# backend/app/gui/scenes/lobby.py
import math
from pathlib import Path

import pygame
import qrcode
from app.gui.assets import font_consolas
from app.gui.scene_manager import Scene, SceneResult
from realtime.server import create_app, get_local_ip, run_uvicorn_in_bg as run_bg

NEON = (20, 230, 60)
FG   = (220, 255, 220)

# ---------- Helpers de layout (iguais ao menu) ----------
FRAME_MARGIN      = 18
BORDER_THICK      = 3
GRID_SPEED        = 30.0
GRID_SPACING      = 100
GRID_LINES        = 16
HORIZON_OFFSET    = 10
VERT_LINES_N      = 70
VERT_SPREAD_BOTTOM = 400
VERT_SPREAD_TOP    = 30

def BOTTOM_HALF(w,h):
    top_h = int(h * 0.62)
    return pygame.Rect(0, top_h, w, h - top_h)

# ---------- QR ----------
def make_qr_surface(url: str, target_wh: int) -> pygame.Surface:
    img = qrcode.make(url).convert("RGB")
    w, h = img.size
    surf = pygame.image.fromstring(img.tobytes(), (w, h), "RGB").convert()
    return pygame.transform.smoothscale(surf, (target_wh, target_wh))

# ---------- Janela fake ----------
def draw_fake_window(screen: pygame.Surface, rect: pygame.Rect, title: str, neon=NEON):
    pygame.draw.rect(screen, neon, rect, 2)
    title_h = max(24, int(rect.h * 0.12))
    bar = pygame.Rect(rect.x+2, rect.y+2, rect.w-4, title_h)
    pygame.draw.rect(screen, neon, bar, 0)
    # botões fake
    bx = bar.right - 18; by = bar.y + 6
    for i in range(3):
        pygame.draw.rect(screen, (0,0,0), (bx - 18*i, by, 12, 12), 1)
    # título
    font = font_consolas(max(12, title_h - 10))
    label = font.render(title, True, (0,0,0))
    screen.blit(label, (bar.x + 10, bar.y + (bar.h - label.get_height())//2))
    # inner content rect
    return pygame.Rect(rect.x+2, bar.bottom, rect.w-4, rect.h - (bar.bottom-rect.y) - 2)

# ---------- Efeito CRT + Grid ----------
def ensure_crt_overlay(cache, w, h):
    if cache.get("size") == (w,h):
        return
    s = pygame.Surface((w,h), pygame.SRCALPHA)
    s.fill((0,0,0,0))
    # scanlines
    for y in range(0, h, 3):
        pygame.draw.line(s, (0,0,0,28), (0,y), (w,y), 1)
    cache["surf"] = s
    cache["size"] = (w,h)

def draw_crt_overlay(screen, cache, t):
    s = cache["surf"]
    s.set_alpha(165 + int(10 * (1 + math.sin(t * 7)) / 2))
    screen.blit(s, (0,0))

def draw_grid(screen, t, color=NEON):
    w, h = screen.get_size()
    bot = BOTTOM_HALF(w, h)
    horizon_y = bot.top + HORIZON_OFFSET
    center_x  = w // 2
    offset = int((t * GRID_SPEED) % GRID_SPACING)

    # horizontais
    for i in range(GRID_LINES):
        scale = (i + 1) / float(GRID_LINES)
        y = int(horizon_y + offset + i * GRID_SPACING)
        left_x  = int(center_x - (w // 2) * (1 + scale))
        right_x = int(center_x + (w // 2) * (1 + scale))
        pygame.draw.line(screen, color, (left_x, y), (right_x, y), 2)
    pygame.draw.line(screen, color, (0, horizon_y), (w, horizon_y), 2)

    # verticais
    for i in range(-VERT_LINES_N//2, VERT_LINES_N//2 + 1):
        x_bottom = int(center_x + i * VERT_SPREAD_BOTTOM)
        x_top    = int(center_x + i * VERT_SPREAD_TOP)
        pygame.draw.line(screen, color, (x_bottom, bot.bottom), (x_top, horizon_y), 1)

# ---------- Texto neon “glow” ----------
def neon_text(screen, text, center, size, color=NEON):
    f = font_consolas(size)
    base = f.render(text, True, color)
    # glow simples: 3 sombras
    for r in (3, 2, 1):
        shadow = f.render(text, True, color)
        shadow.set_alpha(60 if r==3 else 90 if r==2 else 140)
        screen.blit(shadow, (center[0]-shadow.get_width()//2, center[1]-shadow.get_height()//2))
    screen.blit(base, (center[0]-base.get_width()//2, center[1]-base.get_height()//2))

class LobbyScene(Scene):
    """
    Lobby no tema Matrix:
      - fundo preto + grid animado
      - moldura neon
      - QR central com texto brilhante acima
      - dois painéis (esq/dir) mostrando jogadores conectados
    """

    def __init__(self, window_size: tuple[int,int]):
        self.win_w, self.win_h = window_size

    def enter(self, ctx):
        self.ctx = ctx
        self.screen: pygame.Surface = ctx["screen"]
        self.time = 0.0
        self.crt_cache = {}

        # Fonte pequena para detalhes
        self.font_small = font_consolas(18)

        # ----- Realtime (FastAPI) -----
        advertise_host = get_local_ip()
        port = 8765
        self.http_url = f"http://{advertise_host}:{port}/web"
        self.ws_url   = f"ws://{advertise_host}:{port}/ws"

        # callbacks “no-op” no lobby
        async def noop_move(_s,_d): return False, False
        async def noop_quiz(_c,_a): return False

        self.game_ctx = {
            "phase": "lobby", "board": None, "turn": None, "quiz": None,
            "on_move": noop_move, "on_quiz_answer": noop_quiz,
        }

        # caminho absoluto do /clients/mobile_web
        here = Path(__file__).resolve()
        def find_root(start: Path) -> Path:
            for p in [start, *start.parents]:
                if (p/"backend").is_dir() and (p/"clients").is_dir():
                    return p
            return start.parents[4]
        project_root = find_root(here)
        static_dir = project_root / "clients" / "mobile_web"
        if not static_dir.is_dir():
            raise RuntimeError(f"Pasta estática não encontrada: {static_dir}")

        app = create_app(static_dir=str(static_dir), game_ctx=self.game_ctx)
        run_bg(app, host="0.0.0.0", port=port)
        self.fastapi_app = app
        self.conn_mgr    = app.state.conn_manager

        # QR central (escala responsiva)
        s = min(self.win_w, self.win_h)
        qr_side = max(160, int(s * 0.28))  # ~28% do menor lado da tela
        self.qr = make_qr_surface(self.http_url, qr_side)

    def leave(self): pass

    def _recalc_qr(self):
        w, h = self.screen.get_size()
        # QR maior em telas maiores: 34% do menor lado, com limites
        side = max(180, min(520, int(min(w, h) * 0.34)))
        self.qr = make_qr_surface(self.http_url, side)

    def handle_event(self, ev):
        if ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_ESCAPE:
                return SceneResult(next_scene="menu")
            if ev.key == pygame.K_RETURN:
                # precisa de pelo menos 2 jogadores
                count = self.conn_mgr.client_count() if hasattr(self.conn_mgr,"client_count") else len(getattr(self.conn_mgr, "_clients", {}))
                if count >= 0:
                    payload = {"realtime":{
                        "app": self.fastapi_app,
                        "conn_mgr": self.conn_mgr,
                        "game_ctx": self.game_ctx,
                        "ws_url": self.ws_url,
                    }}
                    return SceneResult(next_scene="game", payload=payload)
        if ev.type == pygame.VIDEORESIZE:
            self._recalc_qr()
            return None
        return None

    def update(self, dt): self.time += dt

    def _players(self):
        if hasattr(self.conn_mgr, "list_players"):
            return self.conn_mgr.list_players()
        if hasattr(self.conn_mgr, "players"):
            return self.conn_mgr.players()
        return [{"id": cid, **meta} for cid,meta in getattr(self.conn_mgr,"_meta",{}).items()]

    def render(self, screen):
        w, h = screen.get_size()
        screen.fill((0,0,0))

        # Grid animado
        draw_grid(screen, self.time, NEON)

        # Moldura externa
        frame = pygame.Rect(FRAME_MARGIN, FRAME_MARGIN, w - 2*FRAME_MARGIN, h - 2*FRAME_MARGIN)
        pygame.draw.rect(screen, NEON, frame, BORDER_THICK)

        # Texto superior (brilho)
        neon_text(screen, "Aguardando Jogadores...", (w//2, int(h*0.16)), max(20, int(h*0.036)))
        neon_text(screen, "Leia o QR Code com seu celular e entre no jogo", (w//2, int(h*0.22)), max(16, int(h*0.026)))

        # QR central
        qr_rect = self.qr.get_rect(center=(w//2, int(h*0.52)))
        screen.blit(self.qr, qr_rect)

       # players conectados
        players = self._players()

        # desenha janelas só se houver jogadores
        if len(players) >= 1:
            pad  = 20
            w, h = screen.get_size()
            qr_rect = self.qr.get_rect(center=(w//2, int(h*0.52)))

            # dimensões responsivas dos painéis
            p_w  = max(220, int(w * 0.22))
            p_h  = max(160, int(h * 0.28))

            # esquerda (primeiro jogador)
            left_rect  = pygame.Rect(qr_rect.left - pad - p_w, qr_rect.centery - p_h//2, p_w, p_h)
            left_inner = draw_fake_window(screen, left_rect, players[0].get("name", "Jogador 1"))
            # (opcional: desenhar avatar/ícone aqui, se você quiser)

            # direita (segundo jogador, se houver)
            if len(players) >= 2:
                right_rect  = pygame.Rect(qr_rect.right + pad, qr_rect.centery - p_h//2, p_w, p_h)
                right_inner = draw_fake_window(screen, right_rect, players[1].get("name", "Jogador 2"))


        # Rodapé pequeno com URL
        s = self.font_small.render(self.http_url, True, FG)
        screen.blit(s, (w//2 - s.get_width()//2, h - s.get_height() - 25))

        # Overlay CRT
        ensure_crt_overlay(self.crt_cache, w, h)
        draw_crt_overlay(screen, self.crt_cache, self.time)

        self._recalc_qr()


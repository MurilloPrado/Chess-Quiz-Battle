from pathlib import Path
import pygame, moderngl, numpy as np
from pyrr import Matrix44
from app.gui.scene_manager import Scene, SceneResult
from app.gui.assets import D3, ui, font_consolas
from PIL import Image
import math

NEON          = (20, 230, 60)
FG            = (220, 255, 220)
TOP_RATIO     = 0.62   # quanto da altura fica para o topo (ex.: 0.60 ~ 60%)
GRID_Y_OFFSET = -18    # ajuste fino do grid em pixels (negativo = sobe, positivo = desce)
TITLE_GAP     = 48      # distância entre as 3 linhas do título
MENU_GAP      = 28      # distância entre itens do menu
BORDER_THICK  = 3       # espessura da moldura externa
BRACKET_THICK = 4       # espessura dos colchetes do título
FRAME_MARGIN  = 18      # margem da moldura externa em relação à janela
CONTAINER_MAX_W = 1100  # largura máxima do "container" central
CONTAINER_PAD   = 40    # padding interno do container
LEFT_COL_RATIO  = 0.55  # % do container para a coluna esquerda (título + menu)
# --- no topo, com os demais "consts" ---
TITLE_PAD_X        = 8     # padding horizontal dentro do bloco do título
TITLE_PAD_TOP      = 24    # padding extra acima do título (mais respiro no topo)
TITLE_PAD_BOTTOM   = 12    # padding abaixo do título
TITLE_TO_MENU_GAP  = 24    # distância entre o bloco do título e o menu
BRACKET_MARGIN_X   = 12    # distância horizontal dos colchetes em relação ao título


# layout/menu
def TOP_HALF(w, h):
    top_h = int(h * TOP_RATIO)
    return pygame.Rect(0, 0, w, top_h)

def BOTTOM_HALF(w, h):
    top = TOP_HALF(w, h)
    return pygame.Rect(0, top.bottom, w, h - top.bottom)

def CONTAINER(w, h):
    # área segura: tela inteira menos a moldura externa
    area = pygame.Rect(FRAME_MARGIN, FRAME_MARGIN, w - 2*FRAME_MARGIN, h - 2*FRAME_MARGIN)
    cw  = min(CONTAINER_MAX_W, area.w - 2*CONTAINER_PAD)
    ch  = area.h - 2*CONTAINER_PAD
    cx  = area.x + (area.w - cw)//2
    cy  = area.y + (area.h - ch)//2
    return pygame.Rect(cx, cy, cw, ch)

def LEFT_COL(w, h):
    """Coluna esquerda (título + menu) dentro do container."""
    c = CONTAINER(w, h)
    lw = int(c.w * LEFT_COL_RATIO)
    return pygame.Rect(c.x, c.y, lw, c.h)

def RIGHT_PANEL(w, h):
    """Painel do tabuleiro (placeholder) espelhado à direita no container."""
    c  = CONTAINER(w, h)
    lc = LEFT_COL(w, h)
    rw = c.w - lc.w
    # deixa uma folga interna
    pad = 16
    return pygame.Rect(lc.right + pad, c.y + pad, rw - 2*pad, c.h - 2*pad)



def _read_utf8(p: Path) -> str:
    # tenta utf-8 e, se falhar, ignora bytes problemáticos
    try:
        return p.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return p.read_bytes().decode("utf-8", errors="ignore")

class MenuScene(Scene):
    def __init__(self, window_size: tuple[int,int]):
        self.win_w, self.win_h = window_size


    def _ensure_crt_overlay(self, w: int, h: int):
        needs_new = (
            not hasattr(self, "crt_overlay") or
            self.crt_overlay is None or
            self.crt_overlay.get_size() != (w, h)
        )
        if needs_new:
            self.crt_overlay = pygame.Surface((w, h), pygame.SRCALPHA)
            s = self.crt_overlay
            s.fill((0, 0, 0, 0))

            # scanlines horizontais
            line_interval = 3  # espaçamento entre linhas
            scan_alpha = 28    # intensidade da linha
            for y in range(0, h, line_interval):
                pygame.draw.line(s, (0, 0, 0, scan_alpha), (0, y), (w, y), 1)

            # vinheta suave (borda escura)
            vignette = pygame.Surface((w, h), pygame.SRCALPHA)
            pygame.draw.rect(vignette, (0, 0, 0, 220), vignette.get_rect(), 0, border_radius=0)
            vignette = pygame.transform.smoothscale(vignette, (int(w*1.2), int(h*1.2)))
            offx = (vignette.get_width() - w) // 2
            offy = (vignette.get_height() - h) // 2
            # usa multiplicação para escurecer bordas sem matar o centro
            s.blit(vignette, (-offx, -offy), special_flags=pygame.BLEND_RGBA_MULT)


    def _draw_crt_overlay(self, screen, t: float):
        # pequeno flicker no alpha global
        self.crt_overlay.set_alpha(165 + int(10 * (1 + math.sin(t * 7)) / 2))
        screen.blit(self.crt_overlay, (0, 0))
        

    def draw_side_brackets(self, screen, rect: pygame.Rect, color=NEON, thick=BRACKET_THICK, tick=34, gap_x=BRACKET_MARGIN_X, gap_y=0):
        # expande a área para afastar as barras do texto
        L = rect.left  - gap_x
        R = rect.right + gap_x
        T = rect.top   - gap_y
        B = rect.bottom + gap_y

        # Barras verticais
        pygame.draw.line(screen, color, (L, T), (L, B), thick)
        pygame.draw.line(screen, color, (R, T), (R, B), thick)
        # 'tics' horizontais na parte superior e inferior
        pygame.draw.line(screen, color, (L, T), (L + tick, T), thick)
        pygame.draw.line(screen, color, (R, T), (R - tick, T), thick)
        pygame.draw.line(screen, color, (L, B), (L + tick, B), thick)
        pygame.draw.line(screen, color, (R, B), (R - tick, B), thick)


    def _grid_for_size(self, w: int, h: int) -> pygame.Surface:
        key = (w, h)
        if key in self._grid_cache:
            return self._grid_cache[key]

        bot = BOTTOM_HALF(w, h)
        iw, ih = self.grid_img.get_size()
        # scale-to-cover (cover): preenche todo o retângulo, podendo cortar sobras
        scale = max(bot.w / iw, bot.h / ih)
        new_size = (max(1, int(iw * scale)), max(1, int(ih * scale)))
        scaled = pygame.transform.smoothscale(self.grid_img, new_size)

        # cria uma surface exatamente do tamanho do "bot" e recorta o excesso
        surf = pygame.Surface((bot.w, bot.h), pygame.SRCALPHA)
        ox = (scaled.get_width()  - bot.w) // 2
        oy = (scaled.get_height() - bot.h) // 2
        surf.blit(scaled, (-ox, -oy))

        # opcional: colorir para neon se a arte for branca
        if self.tint_grid:
            tint = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
            tint.fill((*NEON, 255))
            surf.blit(tint, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)

        self._grid_cache[key] = surf
        return surf

    # CHANGED: se a janela mudar de tamanho, invalida cache (chame quando detectar resize, se quiser)
    def _invalidate_grid_cache(self):
        self._grid_cache.clear()


    def enter(self, ctx):
        self.ctx = ctx
        self.screen = ctx["screen"]
        self.time = 0.0

        # carrega o PNG do grid
        project_root = Path(__file__).resolve().parents[4]   # .../ (sobe de scenes → gui → app → backend → raiz)
        grid_path    = project_root / "assets" / "ui" / "grid_bottom.png"
        self.grid_img = pygame.image.load(str(grid_path)).convert_alpha()
        self._grid_cache = {}    # (w,h) -> Surface pronto
        self.tint_grid = False    # True se o PNG for branco (para tingir de neon)

        # fontes e itens
        self.font_big = font_consolas(36)
        self.font_small = font_consolas(22)
        self.neon = NEON
        self.fg = FG
        self.items = ["Jogar", "Ranking", "Regras", "Configurações", "Sair"]
        self.sel = 0

        # 3D placeholder
        self.board_img = None
        tex_path = D3 / "board.png"
        if tex_path.exists():
            self.board_img = pygame.image.load(str(tex_path)).convert_alpha()


    def leave(self): pass

    def handle_event(self, ev):
        if ev.type == pygame.KEYDOWN:
            if ev.key in (pygame.K_DOWN, pygame.K_s):
                self.sel = (self.sel + 1) % len(self.items)
            elif ev.key in (pygame.K_UP, pygame.K_w):
                self.sel = (self.sel - 1) % len(self.items)
            elif ev.key in (pygame.K_RETURN, pygame.K_SPACE):
                if self.items[self.sel] == "Jogar":
                    return SceneResult(next_scene="game")
                elif self.items[self.sel] == "Sair":
                    pygame.event.post(pygame.event.Event(pygame.QUIT))
        return None

    def update(self, dt):
        self.time += dt


    def render(self, screen):
        w, h = screen.get_size()

        # fundo preto
        screen.fill((0, 0, 0))

        # GRID: ainda usamos BOTTOM_HALF/TOP_RATIO só para posicionar o fundo
        bot = BOTTOM_HALF(w, h)
        grid_surf = self._grid_for_size(w, h)
        screen.blit(grid_surf, (bot.x, bot.y + GRID_Y_OFFSET))

        # Agora o conteúdo usa a TELA TODA via CONTAINER/LEFT_COL/RIGHT_PANEL
        left  = LEFT_COL(w, h)
        right = RIGHT_PANEL(w, h)

        # --- Título ---
        t1 = self.font_big.render("Xadrez", True, NEON)
        t2 = self.font_big.render("Nem Um Pouco", True, NEON)
        t3 = self.font_big.render("Complexo", True, NEON)

        def cx(surf):  # centraliza na coluna esquerda
            return left.x + (left.w - surf.get_width()) // 2

        # Padding do bloco do título (mais respiro no topo)
        TITLE_PAD_X      = 8
        TITLE_PAD_TOP    = 24
        TITLE_PAD_BOTTOM = 12
        TITLE_TO_MENU_GAP = 28  # ajuste fino

        title_lines_h = t1.get_height() + t2.get_height() + t3.get_height() + 2*TITLE_GAP
        title_block_h = TITLE_PAD_TOP + title_lines_h + TITLE_PAD_BOTTOM

        # --- Medida CORRETA do menu ---
        menu_line_h  = self.font_small.get_height()
        menu_total_h = menu_line_h + (len(self.items) - 1) * MENU_GAP  # ✅ correto

        # Altura total do conteúdo (título + gap + menu)
        content_total_h = title_block_h + TITLE_TO_MENU_GAP + menu_total_h

        # Topo centralizado VERTICALMENTE dentro da coluna esquerda
        content_top = left.y + (left.h - content_total_h) // 2

        # --- Desenhar TÍTULO ---
        y0 = content_top + TITLE_PAD_TOP
        screen.blit(t1, (cx(t1), y0))
        screen.blit(t2, (cx(t2), y0 + TITLE_GAP))
        screen.blit(t3, (cx(t3), y0 + 2*TITLE_GAP))

        title_w = max(t1.get_width(), t2.get_width(), t3.get_width()) + 2*TITLE_PAD_X
        title_h = title_block_h
        title_x = left.x + (left.w - title_w) // 2
        title_y = content_top
        title_rect = pygame.Rect(title_x, title_y, title_w, title_h)

        # Colchetes mais afastados do texto
        BRACKET_MARGIN_X = 26
        self.draw_side_brackets(screen, title_rect, NEON, BRACKET_THICK, 34)

        # --- Desenhar MENU (passos de MENU_GAP; 1ª linha conta a altura da fonte) ---
        menu_y = title_rect.bottom + TITLE_TO_MENU_GAP
        menu_x = left.x + (left.w // 2) - 120
        for i, label in enumerate(self.items):
            y = menu_y + i * MENU_GAP  # ✅ passo é só o GAP
            surf = self.font_small.render(label, True, FG)
            screen.blit(surf, (menu_x + 24, y))
        arrow = self.font_small.render("›", True, NEON)
        screen.blit(arrow, (menu_x, menu_y + self.sel * MENU_GAP))

        # Painel direito (inalterado)
        pygame.draw.rect(screen, NEON, right, 2)


        # 4) overlay CRT por cima de tudo
        self._ensure_crt_overlay(w, h)
        self._draw_crt_overlay(screen, self.time)


        # 5) moldura externa
        frame = pygame.Rect(FRAME_MARGIN, FRAME_MARGIN, w - 2*FRAME_MARGIN, h - 2*FRAME_MARGIN)
        pygame.draw.rect(screen, NEON, frame, BORDER_THICK)

        self._ensure_crt_overlay(w, h)
        self._draw_crt_overlay(screen, self.time)

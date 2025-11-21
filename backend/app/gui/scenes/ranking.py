from pathlib import Path
import pygame
import math

from app.gui.scene_manager import Scene, SceneResult
from app.gui.assets import font_consolas
from persistence.database import init_db, get_ranking

# Cores / constantes iguais ao menu
NEON              = (20, 230, 60)
FG                = (220, 255, 220)
TOP_RATIO         = 0.62
GRID_SPEED        = 30.0
GRID_SPACING      = 100
GRID_LINES        = 16
GRID_COLOR        = NEON
HORIZON_OFFSET    = 10
VERT_LINES_N      = 70
VERT_SPREAD_BOTTOM = 400
VERT_SPREAD_TOP    = 30

BORDER_THICK      = 3
FRAME_MARGIN      = 18
CONTAINER_MAX_W   = 1100
CONTAINER_PAD     = 40

TITLE_GAP         = 32
TABLE_HEADER_H    = 40
ROW_H             = 32          # altura de cada linha da tabela
TABLE_PAD_X       = 32
TABLE_PAD_Y       = 32

def BOTTOM_HALF(w, h):
    top_h = int(h * TOP_RATIO)
    return pygame.Rect(0, top_h, w, h - top_h)

def CONTAINER(w, h):
    area = pygame.Rect(FRAME_MARGIN, FRAME_MARGIN,
                       w - 2 * FRAME_MARGIN, h - 2 * FRAME_MARGIN)
    cw = min(CONTAINER_MAX_W, area.w - 2 * CONTAINER_PAD)
    ch = area.h - 2 * CONTAINER_PAD
    cx = area.x + (area.w - cw) // 2
    cy = area.y + (area.h - ch) // 2
    return pygame.Rect(cx, cy, cw, ch)


class RankingScene(Scene):
    def __init__(self, window_size: tuple[int, int]):
        self.win_w, self.win_h = window_size
        self.time = 0.0
        self.crt_overlay: pygame.Surface | None = None

    # --------- CRT overlay / grid (copiado do menu para manter estilo) ---------

    def _ensure_crt_overlay(self, w: int, h: int):
        needs_new = (
            not hasattr(self, "crt_overlay")
            or self.crt_overlay is None
            or self.crt_overlay.get_size() != (w, h)
        )
        if needs_new:
            self.crt_overlay = pygame.Surface((w, h), pygame.SRCALPHA)
            s = self.crt_overlay
            s.fill((0, 0, 0, 0))

            # scanlines horizontais
            line_interval = 3
            scan_alpha = 28
            for y in range(0, h, line_interval):
                pygame.draw.line(s, (0, 0, 0, scan_alpha), (0, y), (w, y), 1)

            # vinheta
            vignette = pygame.Surface((w, h), pygame.SRCALPHA)
            pygame.draw.rect(
                vignette, (0, 0, 0, 220), vignette.get_rect(), 0, border_radius=0
            )
            vignette = pygame.transform.smoothscale(
                vignette, (int(w * 1.2), int(h * 1.2))
            )
            offx = (vignette.get_width() - w) // 2
            offy = (vignette.get_height() - h) // 2
            s.blit(vignette, (-offx, -offy), special_flags=pygame.BLEND_RGBA_MULT)

    def _draw_crt_overlay(self, screen, t: float):
        self.crt_overlay.set_alpha(
            165 + int(10 * (1 + math.sin(t * 7)) / 2)
        )
        screen.blit(self.crt_overlay, (0, 0))

    def _draw_vaporwave_grid(self, screen, t: float):
        w, h = screen.get_size()
        bot = BOTTOM_HALF(w, h)
        horizon_y = bot.top + HORIZON_OFFSET
        center_x = w // 2

        offset = int((t * GRID_SPEED) % GRID_SPACING)

        # linhas horizontais
        for i in range(GRID_LINES):
            scale = (i + 1) / float(GRID_LINES)
            y = horizon_y + offset + i * GRID_SPACING
            y = int(y)
            left_x = int(center_x - (w // 2) * (1 + scale))
            right_x = int(center_x + (w // 2) * (1 + scale))
            pygame.draw.line(screen, GRID_COLOR, (left_x, y), (right_x, y), 2)

        pygame.draw.line(screen, GRID_COLOR, (0, horizon_y), (w, horizon_y), 2)

        # linhas verticais convergindo
        for i in range(-VERT_LINES_N // 2, VERT_LINES_N // 2 + 1):
            x_bottom = int(center_x + i * VERT_SPREAD_BOTTOM)
            x_top = int(center_x + i * VERT_SPREAD_TOP)
            pygame.draw.line(
                screen, GRID_COLOR,
                (x_bottom, bot.bottom), (x_top, horizon_y), 1
            )

    # ----------------- Ciclo de vida -----------------

    def enter(self, ctx):
        self.ctx = ctx
        self.screen = ctx["screen"]
        self.time = 0.0

        self.font_title = font_consolas(40)
        self.font_header = font_consolas(26)
        self.font_row = font_consolas(22)

        # garante banco
        try:
            init_db()
        except Exception as e:
            print("Erro ao inicializar ranking DB:", e)

        self._load_ranking()
        self.scroll = 0
        self.max_scroll = 0

    def _load_ranking(self):
        """Busca o ranking no banco de dados."""
        try:
            data = get_ranking()
        except Exception as e:
            print("Erro ao buscar ranking:", e)
            data = []

        # cada item: (nome, vitorias)
        self.ranking = list(data)

    def leave(self):
        pass

    def handle_event(self, ev):
        if ev.type == pygame.KEYDOWN:
            if ev.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                # volta para o menu
                return SceneResult(next_scene="menu")

            # scroll por teclado
            if ev.key in (pygame.K_DOWN, pygame.K_s):
                self.scroll = min(self.scroll + ROW_H, self.max_scroll)
            elif ev.key in (pygame.K_UP, pygame.K_w):
                self.scroll = max(self.scroll - ROW_H, 0)

        # scroll por mouse
        if ev.type == pygame.MOUSEWHEEL:
            # ev.y > 0 rola pra cima
            self.scroll = max(0, min(self.scroll - ev.y * (ROW_H // 2),
                                     self.max_scroll))

        return None

    def update(self, dt):
        self.time += dt

    # ----------------- Render -----------------

    def render(self, screen):
        w, h = screen.get_size()
        screen.fill((0, 0, 0))

        # grid
        self._draw_vaporwave_grid(screen, self.time)

        # container central
        container = CONTAINER(w, h)

        # título "👑 Ranking 👑"
        title_text = "Ranking"
        title_surf = self.font_title.render(title_text, True, FG)
        title_rect = title_surf.get_rect()
        title_rect.centerx = container.centerx
        title_rect.y = container.y + 24
        screen.blit(title_surf, title_rect)

        # área da tabela (um retângulo menor centralizado)
        table_w = int(container.w * 0.7)
        table_h = int(container.h * 0.6)
        table_x = container.x + (container.w - table_w) // 2
        table_y = title_rect.bottom + 32
        table_rect = pygame.Rect(table_x, table_y, table_w, table_h)

        # desenha moldura da tabela
        pygame.draw.rect(screen, NEON, table_rect, 2)

        # retângulo do cabeçalho
        header_rect = pygame.Rect(
            table_rect.x,
            table_rect.y,
            table_rect.w,
            TABLE_HEADER_H
        )
        pygame.draw.line(
            screen, NEON,
            (header_rect.x, header_rect.bottom),
            (header_rect.right, header_rect.bottom),
            2
        )

        # coluna esquerda/direita
        col_split_x = header_rect.x + int(header_rect.w * 0.65)
        pygame.draw.line(
            screen, NEON,
            (col_split_x, table_rect.y),
            (col_split_x, table_rect.bottom),
            2
        )

        # textos do cabeçalho
        header_player = self.font_header.render("Jogador", True, FG)
        header_wins = self.font_header.render("Vitórias", True, FG)

        player_rect = header_player.get_rect()
        player_rect.centerx = header_rect.x + col_split_x
        player_rect.centerx = header_rect.x + (col_split_x - header_rect.x) // 2
        player_rect.centery = header_rect.centery
        screen.blit(header_player, player_rect)

        wins_rect = header_wins.get_rect()
        wins_rect.centerx = col_split_x + (header_rect.right - col_split_x) // 2
        wins_rect.centery = header_rect.centery
        screen.blit(header_wins, wins_rect)

        # área de linhas (corpo da tabela)
        body_rect = pygame.Rect(
            table_rect.x,
            header_rect.bottom,
            table_rect.w,
            table_rect.h - TABLE_HEADER_H
        )

        # calcula altura total do conteúdo e max_scroll
        total_h = len(self.ranking) * ROW_H
        visible_h = body_rect.h
        self.max_scroll = max(0, total_h - visible_h)

        # clip para não desenhar fora da tabela
        old_clip = screen.get_clip()
        screen.set_clip(body_rect)

        y_start = body_rect.y - self.scroll

        for i, (nome, vitorias) in enumerate(self.ranking):
            row_y = y_start + i * ROW_H
            if row_y + ROW_H < body_rect.y:
                continue
            if row_y > body_rect.bottom:
                break

            # linha horizontal (opcional)
            # pygame.draw.line(screen, NEON,
            #                  (body_rect.x, row_y + ROW_H),
            #                  (body_rect.right, row_y + ROW_H), 1)

            # texto jogador
            txt_player = self.font_row.render(str(nome), True, FG)
            r_player = txt_player.get_rect()
            r_player.midleft = (body_rect.x + TABLE_PAD_X, row_y + ROW_H // 2)
            screen.blit(txt_player, r_player)

            # texto vitórias
            txt_wins = self.font_row.render(str(vitorias), True, FG)
            r_wins = txt_wins.get_rect()
            r_wins.centerx = col_split_x + (body_rect.right - col_split_x) // 2
            r_wins.centery = row_y + ROW_H // 2
            screen.blit(txt_wins, r_wins)

        # remove clip
        screen.set_clip(old_clip)

        # moldura externa da tela
        frame = pygame.Rect(
            FRAME_MARGIN,
            FRAME_MARGIN,
            w - 2 * FRAME_MARGIN,
            h - 2 * FRAME_MARGIN,
        )
        pygame.draw.rect(screen, NEON, frame, BORDER_THICK)

        # CRT overlay
        self._ensure_crt_overlay(w, h)
        self._draw_crt_overlay(screen, self.time)

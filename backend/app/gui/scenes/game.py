import os
import pygame
from app.gui.scene_manager import Scene, SceneResult
from app.gui.widgets.console import ConsoleWidget
from app.gui.widgets.matrix_rain import MatrixRain
from app.gui.assets import font_consolas

# Se seu core expõe BOARD_W/BOARD_H via utils.constants, usamos nos cálculos.
try:
    from app.chess.utils.constants import BOARD_W, BOARD_H, PIECE_SYMBOL, WHITE
except Exception:
    # Fallback seguro (não deve acontecer no seu projeto)
    BOARD_W, BOARD_H, WHITE = 8, 8, 0
    PIECE_SYMBOL = {}

NEON = (20, 230, 60)
BG_BORDER = 3


class GameScene(Scene):
    """
    Cena principal do jogo:
    - esquerda: tabuleiro 2D jogável
    - direita (topo): mock de janela com imagem 3D do tabuleiro
    - direita (baixo): mock de janela com o Console (vez, eventos, etc.)
    """

    def __init__(self, window_size: tuple[int, int], chess_api):
        self.win_w, self.win_h = window_size
        self.api = chess_api

        # imagens opcionais do lado direito
        self._board3d_img = None
        self._try_load_3d_asset()

    # -------------- Ciclo de vida --------------

    def enter(self, ctx):
        self.ctx = ctx
        self.screen: pygame.Surface = ctx["screen"]
        self.font = font_consolas(18)

        # fundo
        self.matrix = MatrixRain((self.win_w, self.win_h))

        # layout calculado dinamicamente
        self._compute_layout(self.win_w, self.win_h)

        # console (logo abaixo do 3D)
        self.console = ConsoleWidget(self.right_console_inner)
        self.console.push("Sua vez... Faça seu movimento")

        # seleção de casa no tabuleiro
        self.sel = None

    def leave(self):
        pass

    # -------------- Layout responsivo --------------

    def _compute_layout(self, w: int, h: int):
        """Calcula todas as áreas com base no tamanho da janela."""
        padding = 24
        gutter = 28  # espaço entre colunas
        top = padding
        left_col_w = int(w * 0.52)  # esquerda ~52%, direita ~48%
        right_col_w = w - left_col_w - padding * 2 - gutter

        # Tamanho do tile máximo respeitando altura e largura disponível
        max_board_side = min(
            left_col_w - padding * 2,
            h - padding * 2,
        )
        tile = max(28, max_board_side // max(BOARD_W, BOARD_H))
        board_w = tile * BOARD_W
        board_h = tile * BOARD_H

        # Centraliza o tabuleiro dentro da coluna esquerda
        board_x = padding + (left_col_w - board_w) // 2
        board_y = top + (h - top - padding - board_h) // 2

        self.tile = tile
        self.board_rect = pygame.Rect(board_x, board_y, board_w, board_h)

        # Coluna direita: duas "janelas" empilhadas
        right_x = padding + left_col_w + gutter
        right_w = right_col_w
        right_total_h = h - padding * 2

        # proporções: 3D ocupa ~55%, console ~45%, com pequeno gutter
        right_gutter = 18
        right_3d_h = int(right_total_h * 0.55)
        right_console_h = right_total_h - right_3d_h - right_gutter

        self.right_3d_rect = pygame.Rect(right_x, top, right_w, right_3d_h)
        self.right_console_rect = pygame.Rect(
            right_x, top + right_3d_h + right_gutter, right_w, right_console_h
        )

        # Áreas internas (conteúdo dentro da "janela" com barra de título)
        self.right_3d_inner = self._window_content_rect(self.right_3d_rect)
        self.right_console_inner = self._window_content_rect(self.right_console_rect)

    def _window_content_rect(self, outer: pygame.Rect) -> pygame.Rect:
        title_h = 28
        border = 2
        return pygame.Rect(
            outer.x + border,
            outer.y + border + title_h,
            outer.w - border * 2,
            outer.h - title_h - border * 2,
        )

    # -------------- Assets --------------

    def _try_load_3d_asset(self):
        """
        Carrega a primeira imagem encontrada em assets/3d (png/jpg), se houver.
        Se não existir, desenhamos um wireframe placeholder no render.
        """
        candidates = []
        base_candidates = [
            os.path.join("assets", "3d"),
            os.path.join("app", "assets", "3d"),
        ]
        exts = (".png", ".jpg", ".jpeg", ".webp")
        for base in base_candidates:
            if os.path.isdir(base):
                for f in os.listdir(base):
                    if f.lower().endswith(exts):
                        candidates.append(os.path.join(base, f))
        if candidates:
            try:
                img = pygame.image.load(candidates[0]).convert_alpha()
                self._board3d_img = img
            except Exception:
                self._board3d_img = None

    # -------------- Eventos --------------

    def handle_event(self, ev):
        if ev.type == pygame.VIDEORESIZE:
            self.win_w, self.win_h = ev.w, ev.h
            self._compute_layout(ev.w, ev.h)

        if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
            return SceneResult(next_scene="menu")

        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            mx, my = ev.pos
            if self.board_rect.collidepoint(mx, my):
                cx = (mx - self.board_rect.x) // self.tile
                cy = (my - self.board_rect.y) // self.tile
                # grade de cima para baixo → y 0 é topo do tabuleiro na tela,
                # mas seu core costuma considerar y 0 na primeira fila (inferior/superior).
                # Mantemos a mesma convenção do desenho (0 em cima) para clicar.
                if 0 <= cx < BOARD_W and 0 <= cy < BOARD_H:
                    if self.sel is None:
                        self.sel = (cx, cy)
                    else:
                        ok = self._try_move_adapter(self.sel, (cx, cy))
                        if ok:
                            self.console.push("Você realizou um movimento")
                            # Aqui: IA/rede se houver...
                            self.console.push("Sua vez... Faça seu movimento")
                        else:
                            self.console.push("Movimento inválido")
                        self.sel = None
        return None

    def _try_move_adapter(self, src_xy, dst_xy) -> bool:
        """
        Adapta a tentativa de movimento para o que seu adapter expõe.
        Preferência:
          1) api.try_move((x,y),(x,y))
          2) api.push_sanlike('a2a3') / api.push_uci('a2a3')
        """
        # 1) Método direto (tuplas)
        if hasattr(self.api, "try_move"):
            try:
                return bool(self.api.try_move(src_xy, dst_xy))
            except Exception:
                pass

        # 2) UCI-like (ex: a2a3). Precisamos converter (x,y) -> algébrica.
        try:
            from app.chess.utils.coordinates import to_algebraic
        except Exception:
            to_algebraic = None

        if to_algebraic and hasattr(self.api, "push_sanlike"):
            try:
                uci = to_algebraic(src_xy) + to_algebraic(dst_xy)
                return bool(self.api.push_sanlike(uci))
            except Exception:
                return False
        return False

    # -------------- Atualização / Render --------------

    def update(self, dt):
        self.matrix.update(dt)

    def render(self, screen: pygame.Surface):
        # fundo
        self.matrix.draw(screen)

        # moldura geral
        pygame.draw.rect(screen, NEON, screen.get_rect(), BG_BORDER)

        # esquerda: tabuleiro 2D
        self._draw_board(screen)

        # direita: mock janelas
        self._draw_mock_window(screen, self.right_3d_rect, "Tabuleiro 3D (visual)")
        self._draw_3d_preview(screen, self.right_3d_inner)

        self._draw_mock_window(screen, self.right_console_rect, "Status da Partida")
        self.console.draw(screen)

    # ---------- Desenho: esquerda (tabuleiro funcional) ----------

    def _draw_board(self, screen: pygame.Surface):
        # moldura do tabuleiro
        pygame.draw.rect(screen, NEON, self.board_rect, 2)

        light = (210, 240, 210)
        dark = (60, 140, 60)

        # casas
        for y in range(BOARD_H):
            for x in range(BOARD_W):
                r = pygame.Rect(
                    self.board_rect.x + x * self.tile,
                    self.board_rect.y + y * self.tile,
                    self.tile,
                    self.tile,
                )
                pygame.draw.rect(screen, light if (x + y) % 2 == 0 else dark, r)

        # realce da seleção
        if self.sel:
            rx = self.board_rect.x + self.sel[0] * self.tile
            ry = self.board_rect.y + self.sel[1] * self.tile
            pygame.draw.rect(screen, (255, 255, 0), (rx, ry, self.tile, self.tile), 3)

        # peças
        for (x, y, glyph, color) in self._iter_pieces():
            tx = self.board_rect.x + x * self.tile + self.tile // 2
            ty = self.board_rect.y + y * self.tile + self.tile // 2
            # aqui você pode substituir por sprites posteriormente
            piece_surf = self.font.render(glyph, True, (0, 0, 0))
            rect = piece_surf.get_rect(center=(tx, ty))
            screen.blit(piece_surf, rect)

    def _iter_pieces(self):
        """
        Estratégia:
        - Se o adapter tiver render_pieces() → usar (x, y, glyph, color)
        - Senão, tentamos ler a matriz do tabuleiro e mapear via PIECE_SYMBOL
        """
        if hasattr(self.api, "render_pieces"):
            try:
                yield from self.api.render_pieces()
                return
            except Exception:
                pass

        # Fallback: tentar self.api.get_board() ou self.api.board
        board = None
        if hasattr(self.api, "get_board"):
            try:
                board = self.api.get_board()
            except Exception:
                board = None
        if board is None and hasattr(self.api, "board"):
            board = getattr(self.api, "board")

        if board is None:
            return

        # board esperado como lista linear ou matriz; mapeia para (x,y)
        # Se for linear: idx -> (x,y)
        from app.chess.utils.coordinates import fr  # idx -> (x,y)

        # board pode conter tuplas (cor, tipo). Usamos PIECE_SYMBOL para desenhar.
        if isinstance(board, list) and len(board) == BOARD_W * BOARD_H:
            for idx, piece in enumerate(board):
                if piece is None:
                    continue
                x, y = fr(idx)
                glyph = PIECE_SYMBOL.get(piece, "?")
                color = "white" if piece[0] == WHITE else "black"
                yield (x, y, glyph, color)

    # ---------- Desenho: direita (mock janelas + 3D) ----------

    def _draw_mock_window(self, screen: pygame.Surface, rect: pygame.Rect, title: str):
        # borda externa
        pygame.draw.rect(screen, NEON, rect, 2)

        # barra de título
        title_h = 28
        title_rect = pygame.Rect(rect.x + 2, rect.y + 2, rect.w - 4, title_h)
        pygame.draw.rect(screen, NEON, title_rect, 0)

        # Título
        label = self.font.render(title, True, (0, 0, 0))
        screen.blit(label, (title_rect.x + 10, title_rect.y + 6))

        # botões fake (min, max, close)
        bx = title_rect.right - 18
        by = title_rect.y + 6
        for i in range(3):
            pygame.draw.rect(screen, (0, 0, 0), (bx - i * 18, by, 12, 12), 1)

    def _draw_3d_preview(self, screen: pygame.Surface, rect: pygame.Rect):
        if self._board3d_img:
            img = self._scale_to_fit(self._board3d_img, rect.size)
            screen.blit(img, img.get_rect(center=rect.center))
        else:
            # placeholder: wireframe de tabuleiro isométrico
            self._draw_wireframe_board(screen, rect)

    def _scale_to_fit(self, surf: pygame.Surface, size: tuple[int, int]) -> pygame.Surface:
        sw, sh = surf.get_size()
        tw, th = size
        scale = min(tw / sw, th / sh)
        nw, nh = max(1, int(sw * scale)), max(1, int(sh * scale))
        return pygame.transform.smoothscale(surf, (nw, nh))

    def _draw_wireframe_board(self, screen: pygame.Surface, rect: pygame.Rect):
        cx, cy = rect.center
        w = int(rect.w * 0.7)
        h = int(rect.h * 0.5)
        # pontos de um losango
        pts = [
            (cx, cy - h // 2),
            (cx + w // 2, cy),
            (cx, cy + h // 2),
            (cx - w // 2, cy),
        ]
        pygame.draw.polygon(screen, NEON, pts, 2)

        # divisões (grade simples)
        divs = min(BOARD_W, 8)
        for i in range(1, divs):
            t = i / divs
            # linhas horizontais (aprox. em perspectiva)
            p1 = self._lerp(pts[0], pts[3], t)
            p2 = self._lerp(pts[1], pts[2], t)
            pygame.draw.line(screen, NEON, p1, p2, 1)
            # linhas verticais
            p3 = self._lerp(pts[0], pts[1], t)
            p4 = self._lerp(pts[3], pts[2], t)
            pygame.draw.line(screen, NEON, p3, p4, 1)

    @staticmethod
    def _lerp(a, b, t):
        return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)

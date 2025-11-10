import pygame
from app.gui.scene_manager import Scene, SceneResult
from app.gui.widgets.console import ConsoleWidget
from app.gui.widgets.matrix_rain import MatrixRain
from app.gui.assets import font_consolas

# PONTOS DE INTEGRAÇÃO com teu core:
# - chess_api.get_board() -> matriz 8x8 com peças
# - chess_api.turn() -> "white" / "black"
# - chess_api.try_move(src, dst) -> bool (ou raise/retorno detalhado)
# Adapta os nomes p/ o que já tens em chess/core.

class GameScene(Scene):
    TILE = 72

    def __init__(self, window_size: tuple[int,int], chess_api):
        self.win_w, self.win_h = window_size
        self.api = chess_api

    def enter(self, ctx):
        self.ctx = ctx
        self.screen = ctx["screen"]
        self.font = font_consolas(18)
        self.neon = (20, 230, 60)

        board_w = self.TILE*8
        self.board_rect = pygame.Rect(40, 40, board_w, board_w)
        self.console = ConsoleWidget(pygame.Rect(self.board_rect.right+40, 260, 360, 240))
        self.matrix = MatrixRain((self.win_w, self.win_h))

        self.sel = None
        self.console.push("Sua vez... Faça seu movimento")

    def leave(self): pass

    def handle_event(self, ev):
        if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
            return SceneResult(next_scene="menu")
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            mx, my = ev.pos
            if self.board_rect.collidepoint(mx, my):
                cx = (mx - self.board_rect.x) // self.TILE
                cy = (my - self.board_rect.y) // self.TILE
                if self.sel is None:
                    self.sel = (cx, cy)
                else:
                    ok = self.api.try_move(self.sel, (cx, cy))
                    if ok:
                        self.console.push("Você realizou um movimento")
                        self.console.push("Vez do adversário... Aguarde")
                        # se tiver IA ou rede, chamar aqui…
                        self.console.push("Sua vez... Faça seu movimento")
                    else:
                        self.console.push("Movimento inválido")
                    self.sel = None
        return None

    def update(self, dt):
        self.matrix.update(dt)

    def render(self, screen: pygame.Surface):
        # fundo matrix
        self.matrix.draw(screen)

        # moldura geral
        pygame.draw.rect(screen, self.neon, screen.get_rect(), 3)

        # tabuleiro 2D
        pygame.draw.rect(screen, self.neon, self.board_rect, 2)
        colors = [(210, 240, 210), (60, 140, 60)]
        for y in range(8):
            for x in range(8):
                r = pygame.Rect(self.board_rect.x + x*self.TILE,
                                self.board_rect.y + y*self.TILE,
                                self.TILE, self.TILE)
                pygame.draw.rect(screen, colors[(x+y)%2], r)
        if self.sel:
            rx = self.board_rect.x + self.sel[0]*self.TILE
            ry = self.board_rect.y + self.sel[1]*self.TILE
            pygame.draw.rect(screen, (255,255,0), (rx,ry,self.TILE,self.TILE), 3)

        # desenhar peças via API (stub de exemplo)
        for (x,y, glyph, color) in self.api.render_pieces():
            tx = self.board_rect.x + x*self.TILE + self.TILE//2
            ty = self.board_rect.y + y*self.TILE + self.TILE//2
            piece = self.font.render(glyph, True, (0,0,0) if color=="white" else (0,0,0))
            rect = piece.get_rect(center=(tx,ty))
            screen.blit(piece, rect)

        # console
        self.console.draw(screen)

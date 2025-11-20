import math
import pygame

from app.gui.scene_manager import Scene, SceneResult
from app.gui.assets import font_consolas

# === CORES E CONSTANTES BÁSICAS (copiadas do menu) ===
NEON          = (20, 230, 60)
FG            = (220, 255, 220)
TOP_RATIO     = 0.62   # quanto da altura fica para o topo
BORDER_THICK  = 3      # espessura da moldura externa
FRAME_MARGIN  = 18     # margem da moldura externa em relação à janela

# === GRID (mesmo estilo do menu) ===
GRID_SPEED         = 30.0   # pixels/seg do deslocamento das linhas horizontais
GRID_SPACING       = 100    # distância base entre linhas
GRID_LINES         = 16     # quantas "faixas" horizontais desenhar
GRID_COLOR         = NEON
HORIZON_OFFSET     = 10     # empurra o horizonte (positivo = desce)
VERT_LINES_N       = 70     # quantidade de linhas verticais
VERT_SPREAD_BOTTOM = 400    # espalhamento das verticais na base
VERT_SPREAD_TOP    = 30     # espalhamento das verticais no horizonte


def TOP_HALF(w: int, h: int) -> pygame.Rect:
    top_h = int(h * TOP_RATIO)
    return pygame.Rect(0, 0, w, top_h)


def BOTTOM_HALF(w: int, h: int) -> pygame.Rect:
    top = TOP_HALF(w, h)
    return pygame.Rect(0, top.bottom, w, h - top.bottom)


class RulesScene(Scene):
    """
    Tela de regras:
      - Fundo com grid neon.
      - Moldura externa.
      - Texto centralizado em uma coluna no centro da tela.
      - Fonte Consolas.
    """

    def __init__(self, window_size: tuple[int, int]):
        self.win_w, self.win_h = window_size

        # fontes (tudo Consolas, só mudando tamanho)
        self.font_title   = font_consolas(36)
        self.font_heading = font_consolas(24)
        self.font_body    = font_consolas(20)
        self.font_hint    = font_consolas(18)

        # texto das regras (exatamente como você mandou)
        self.sections = {
            "1. Objetivo": [
                "O Chess Quiz Battle combina xadrez reduzido com duelo de perguntas de múltipla escolha.",
                "Capture as peças do adversário respondendo corretamente perguntas sobre Computabilidade e Complexidade de Algoritmos.",
            ],
            "2. Duelo de Perguntas": [
                "Sempre que uma peça tenta capturar outra, inicia-se um duelo de perguntas:",
                "- 1. O jogador atacante responde a primeira pergunta.",
                "- 2. Se ele acertar, o ataque continua e aparece outra pergunta, imediatamente.",
                "- 4. O duelo só termina quando o jogador errar uma pergunta.",
                "",
                "Quando o erro acontece:",
                "Quem errar a pergunta perde a peça que estava sendo atacada.",
                "Se o atacante errar, é sua própria peça que desaparece.",
            ],
            "3. Tempo de Resposta": [
                "- Cada duelo começa com 30 segundos totais  para responder.",
                "- Demorar 5s para responder → perde 3s do tempo total.",
                "- Se o tempo zerar durante a vez do jogador → derrota imediata no duelo.",
                "- A cada novo ataque, o tempo total é resetado.",
            ],
        }

    # ------------------------------------------------------------------ #
    # Ciclo de vida da cena
    # ------------------------------------------------------------------ #

    def enter(self, ctx):
        self.ctx = ctx
        self.screen = ctx["screen"]
        self.time = 0.0
        self.crt_overlay = None

    def leave(self):
        pass

    def handle_event(self, ev):
        if ev.type == pygame.KEYDOWN:
            # Qualquer uma dessas teclas volta para o menu
            if ev.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE,
                          pygame.K_RETURN, pygame.K_SPACE):
                return SceneResult(next_scene="menu")
        return None

    def update(self, dt: float):
        self.time += dt

    # ------------------------------------------------------------------ #
    # Helpers de desenho (CRT + GRID)
    # ------------------------------------------------------------------ #

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
            line_interval = 3
            scan_alpha = 28
            for y in range(0, h, line_interval):
                pygame.draw.line(s, (0, 0, 0, scan_alpha), (0, y), (w, y), 1)

            # vinheta suave (borda escura)
            vignette = pygame.Surface((w, h), pygame.SRCALPHA)
            pygame.draw.rect(
                vignette,
                (0, 0, 0, 220),
                vignette.get_rect(),
                0,
                border_radius=0
            )
            vignette = pygame.transform.smoothscale(
                vignette, (int(w * 1.2), int(h * 1.2))
            )
            offx = (vignette.get_width() - w) // 2
            offy = (vignette.get_height() - h) // 2
            s.blit(vignette, (-offx, -offy), special_flags=pygame.BLEND_RGBA_MULT)

    def _draw_crt_overlay(self, screen: pygame.Surface, t: float):
        if self.crt_overlay is None:
            return
        # pequeno flicker no alpha global
        self.crt_overlay.set_alpha(165 + int(10 * (1 + math.sin(t * 7)) / 2))
        screen.blit(self.crt_overlay, (0, 0))

    def _draw_vaporwave_grid(self, screen: pygame.Surface, t: float):
        w, h = screen.get_size()
        bot = BOTTOM_HALF(w, h)

        # Horizonte (no topo do bottom) com offset fino
        horizon_y = bot.top + HORIZON_OFFSET
        center_x  = w // 2

        # Offset animado para linhas horizontais (move "pra baixo" no tempo)
        offset = int((t * GRID_SPEED) % GRID_SPACING)

        # Linhas horizontais com "perspectiva simples"
        for i in range(GRID_LINES):
            # i=0 perto do horizonte; i grande = mais perto do observador
            scale = (i + 1) / float(GRID_LINES)  # 0..1
            y = horizon_y + offset + i * GRID_SPACING
            y = int(y)

            left_x  = int(center_x - (w // 2) * (1 + scale))
            right_x = int(center_x + (w // 2) * (1 + scale))

            pygame.draw.line(screen, GRID_COLOR, (left_x, y), (right_x, y), 2)

        # Linha do horizonte
        pygame.draw.line(screen, GRID_COLOR, (0, horizon_y), (w, horizon_y), 2)

        # Linhas verticais que convergem no horizonte
        pen_w = 1
        for i in range(-VERT_LINES_N // 2, VERT_LINES_N // 2 + 1):
            x_bottom = int(center_x + i * VERT_SPREAD_BOTTOM)
            x_top    = int(center_x + i * VERT_SPREAD_TOP)
            pygame.draw.line(
                screen, GRID_COLOR,
                (x_bottom, bot.bottom),
                (x_top, horizon_y),
                pen_w
            )

    # ------------------------------------------------------------------ #
    # Quebra de texto e layout
    # ------------------------------------------------------------------ #

    def _wrap_text(self, text: str, font: pygame.font.Font, max_width: int):
        """
        Quebra uma string em múltiplas linhas para caber em max_width.
        Retorna lista de strings.
        """
        words = text.split(" ")
        lines = []
        current = ""

        for w in words:
            test = w if current == "" else current + " " + w
            if font.size(test)[0] <= max_width:
                current = test
            else:
                if current:
                    lines.append(current)
                current = w

        if current:
            lines.append(current)

        if not lines:
            return [""]
        return lines

    def _build_lines(self, max_width: int):
        """
        Constrói uma lista de linhas com fonte e indentação,
        para renderizar tudo centralizado em uma coluna.
        """
        lines = []

        section_gap = 18
        paragraph_gap = 8
        line_gap = 4
        bullet_indent = 25

        first_section = True

        for heading, paragraphs in self.sections.items():
            # espaçamento antes de cada seção (menos na primeira)
            if not first_section:
                lines.append({
                    "text": "",
                    "font": self.font_body,
                    "indent": 0,
                    "gap_above": section_gap,
                    "color": FG,
                })
            first_section = False

            # título da seção (neon)
            lines.append({
                "text": heading,
                "font": self.font_heading,
                "indent": 0,
                "gap_above": 0,
                "color": NEON,
            })

            # parágrafos
            first_para = True
            for p in paragraphs:
                if p.strip() == "":
                    lines.append({
                        "text": "",
                        "font": self.font_body,
                        "indent": 0,
                        "gap_above": paragraph_gap,
                        "color": FG,
                    })
                    continue

                # bullet ("- ...")
                if p.lstrip().startswith("-"):
                    bullet_text = "• " + p.lstrip()[1:].strip()
                    wrapped = self._wrap_text(bullet_text, self.font_body,
                                              max_width - bullet_indent)
                    first_line = True
                    for part in wrapped:
                        lines.append({
                            "text": part,
                            "font": self.font_body,
                            "indent": bullet_indent,
                            "gap_above": paragraph_gap if first_line else line_gap,
                            "color": FG,
                        })
                        first_line = False
                else:
                    wrapped = self._wrap_text(p, self.font_body, max_width)
                    first_line = True
                    for part in wrapped:
                        lines.append({
                            "text": part,
                            "font": self.font_body,
                            "indent": 0,
                            "gap_above": paragraph_gap if first_para and first_line else line_gap,
                            "color": FG,
                        })
                        first_line = False
                first_para = False

        return lines

    # ------------------------------------------------------------------ #
    # Render
    # ------------------------------------------------------------------ #

    def render(self, screen: pygame.Surface):
        w, h = screen.get_size()

        # 1) fundo preto + grid
        screen.fill((0, 0, 0))
        self._draw_vaporwave_grid(screen, self.time)

        # 2) coluna central de texto
        #    (usa parte central da tela, respeitando a moldura)
        safe_w = w - 2 * FRAME_MARGIN - 80
        content_width = min(900, safe_w)
        left_x = (w - content_width) // 2

        # título principal "Regras do Jogo" separado do bloco
        title_surf = self.font_title.render("Regras do Jogo", True, NEON)
        title_y = FRAME_MARGIN + 80
        title_x = (w - title_surf.get_width()) // 2
        screen.blit(title_surf, (title_x, title_y))

        # constrói as linhas para o corpo de texto
        lines = self._build_lines(content_width)

        # calcula a altura total para centralizar verticalmente
        total_h = 0
        for line in lines:
            gap = line["gap_above"]
            font = line["font"]
            if line["text"] == "":
                total_h += gap + font.get_height() // 2
            else:
                total_h += gap + font.get_height()

        # começa um pouco abaixo do título, centralizando o bloco
        available_top = title_y + title_surf.get_height() + 20
        center_area_top = available_top
        center_area_h = h - available_top - FRAME_MARGIN - 40
        y_start = center_area_top + max(0, (center_area_h - total_h) // 2)

        panel_margin_y = 20  # espaço acima e abaixo do texto
        panel_top  = y_start - panel_margin_y

        # Primeiro calculamos a altura total real do bloco
        # então criamos o painel de acordo
        temp_y = y_start
        for line in lines:
            temp_y += line["gap_above"]
            if line["text"] == "":
                temp_y += self.font_body.get_height() // 2
            else:
                temp_y += line["font"].get_height()

        panel_bottom = temp_y + panel_margin_y
        panel_rect = pygame.Rect(
            left_x - 25,                # começa um pouco antes do texto
            panel_top,
            content_width + 50,         # bordas nas laterais
            panel_bottom - panel_top
        )

        # Painel semitransparente
        black_panel = pygame.Surface(panel_rect.size, pygame.SRCALPHA)
        black_panel.fill((0, 0, 0, 180))   # <-- AQUI ajusta a transparência
        screen.blit(black_panel, panel_rect.topleft)

        # desenha as linhas
        y = y_start
        for line in lines:
            gap = line["gap_above"]
            y += gap
            font = line["font"]
            text = line["text"]
            color = line["color"]
            indent = line["indent"]

            if text == "":
                y += font.get_height() // 2
                continue

            surf = font.render(text, True, color)
            x = left_x + indent
            screen.blit(surf, (x, y))
            y += surf.get_height()

        # dica inferior
        hint_text = "Pressione ESC para voltar ao menu"
        hint_surf = self.font_hint.render(hint_text, True, FG)
        hint_x = (w - hint_surf.get_width()) // 2
        hint_y = h - FRAME_MARGIN - hint_surf.get_height() - 10
        screen.blit(hint_surf, (hint_x, hint_y))

        # 3) CRT overlay + moldura externa
        self._ensure_crt_overlay(w, h)
        self._draw_crt_overlay(screen, self.time)

        frame = pygame.Rect(
            FRAME_MARGIN,
            FRAME_MARGIN,
            w - 2 * FRAME_MARGIN,
            h - 2 * FRAME_MARGIN,
        )
        pygame.draw.rect(screen, NEON, frame, BORDER_THICK)

        # opcional: mais um overlay leve por cima da moldura (igual menu)
        self._draw_crt_overlay(screen, self.time)

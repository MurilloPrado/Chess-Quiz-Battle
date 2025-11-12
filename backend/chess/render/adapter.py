# adapter.py
# CHANGED: agora integra com Board5x6 e expõe métodos usados pelo host/WS
from ..core.board import Board5x6
from ..utils.constants import BOARD_W, BOARD_H, WHITE
from ..utils.coordinates import sq_to_algebraic, fr

class ChessAPI:
    def __init__(self):
        self.b = Board5x6()
        self.was_capture = False  # CHANGED

    def try_move(self, src_xy, dst_xy) -> bool:
        # converte (x,y) de tela para UCI (a2a3)
        sx, sy = src_xy
        dx, dy = dst_xy
        # seu Board usa origem (0,0) em baixo. A cena usa (0,0) em cima.
        # então invertemos o Y para UCI:
        sy_inv = (BOARD_H - 1) - sy
        dy_inv = (BOARD_H - 1) - dy
        uci = f"{sq_to_algebraic((sx, sy_inv))}{sq_to_algebraic((dx, dy_inv))}"

        # captura?
        dst_idx = (dy_inv * BOARD_W) + dx
        self.was_capture = self.b.board[dst_idx] is not None  # CHANGED

        ok = self.b.push_sanlike(uci)
        return ok

    def render_pieces(self):
        out = []
        for idx, pc in enumerate(self.b.board):
            if pc is None:
                continue
            color, _type = pc
            x, y = fr(idx)                   # (x, y) com 0 no BOTTOM
            y = (BOARD_H - 1) - y            # CHANGED: inverte p/ desenho
            glyph = "♙♘♗♖♕♔"[_type-1] if color == WHITE else "♟♞♝♜♛♚"
            out.append((x, y, glyph, "white" if color == WHITE else "black"))
        return out

    def turn(self):
        return "white" if self.b.turn == WHITE else "black"

    # util para WS → BoardState
    def export_board_linear(self):
        m = []
        for pc in self.b.board:
            if pc is None:
                m.append(None)
            else:
                c, t = pc
                m.append(("w" if c == WHITE else "b") + "PNBRQK"[t-1])
        return m

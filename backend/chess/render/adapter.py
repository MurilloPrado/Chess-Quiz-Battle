# adapter.py
# CHANGED: agora integra com Board5x6 e expõe métodos usados pelo host/WS
from ..core.board import Board5x6
from ..utils.constants import BOARD_W, BOARD_H, WHITE, BLACK
from ..utils.coordinates import sq_to_algebraic, fr, sq

class ChessAPI:
    def __init__(self):
        self.b = Board5x6()
        self.was_capture = False  # CHANGED

    def get_board(self):
        """Usado pelo GameScene._iter_pieces() para desenhar as peças."""
        return self.b.board

    @property
    def board(self):
        """Alternativa de acesso direto, também usada por _iter_pieces()."""
        return self.b.board

    def try_move(self, src_xy, dst_xy) -> bool:
        # src_xy e dst_xy chegam do JS como (x, y) com origem no topo
        sx, sy = src_xy
        dx, dy = dst_xy

        # converte (x,y) -> índice linear do core
        src_idx = sq(sx, sy)
        dst_idx = sq(dx, dy)

        # Agora sim, sq_to_algebraic recebe um inteiro
        uci = f"{sq_to_algebraic(src_idx)}{sq_to_algebraic(dst_idx)}"

        # Marca se havia peça no destino antes da jogada (captura)
        self.was_capture = self.b.board[dst_idx] is not None

        # Executa o movimento no core
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
    

    def import_board_linear(self, cells):
        # converte as peças
        _map_type = {"P":1, "N":2, "B":3, "R":4, "Q":5, "K":6}
        _map_color = {"w":0, "b":1}  # 0 WHITE, 1 BLACK
        new_board = []
        for code in cells:
            if code is None:
                new_board.append(None)
                continue
            color = _map_color[code[0]]
            ptype = _map_type[code[1]]
            new_board.append( (color, ptype))
        # aplica no tabuleiro
        self.b.board = new_board

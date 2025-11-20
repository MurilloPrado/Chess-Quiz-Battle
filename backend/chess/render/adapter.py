# adapter.py
# CHANGED: agora integra com Board5x6 e expõe métodos usados pelo host/WS
from ..core.board import Board5x6
from ..utils.constants import BOARD_W, BOARD_H, WHITE, BLACK, PIECE_PAWN, PIECE_KNIGHT, PIECE_BISHOP, PIECE_ROOK, PIECE_QUEEN, PIECE_KING
from ..utils.coordinates import sq_to_algebraic, fr, sq

PIECE_NAME = {
    PIECE_PAWN:   "pawn",
    PIECE_KNIGHT: "knight",
    PIECE_BISHOP: "bishop",
    PIECE_ROOK:   "rook",
    PIECE_QUEEN:  "queen",
    PIECE_KING:   "king",
}

class ChessAPI:
    def __init__(self):
        self.b = Board5x6()
        self.was_capture = False  # CHANGED
        self.last_battle = None  # dict ou None

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

        # estado antes do movimento
        attacker_turn = self.b.turn                 # cor que está jogando
        attacker_piece = self.b.board[src_idx]      # (cor, tipo)
        defender_piece = self.b.board[dst_idx]      # pode ser None

        # Agora sim, sq_to_algebraic recebe um inteiro
        uci = f"{sq_to_algebraic(src_idx)}{sq_to_algebraic(dst_idx)}"

        # Executa o movimento no core
        ok = self.b.push_sanlike(uci)

        # se movimento inválido, não há batalha
        if not ok:
            self.was_capture = False
            self.last_battle = None
            return False
        
        # captura ocorreu
        self.was_capture = defender_piece is not None

        if self.was_capture and attacker_piece is not None:
            att_color, att_type = attacker_piece
            def_color, def_type = defender_piece

            self.last_battle = {
                "attacker_color": "white" if att_color == WHITE else "black",
                "attacker_type":  PIECE_NAME.get(att_type, "unknown"),
                "defender_color": "white" if def_color == WHITE else "black",
                "defender_type":  PIECE_NAME.get(def_type, "unknown"),
                "attacker_src": src_idx,
                "attacker_dst": dst_idx,
                "defender_idx": dst_idx,  # mesma casa, antes da captura
            }
        else:
            self.last_battle = None

        return True


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

    
    def resolve_battle(self, winner_side: str):
        """
        winner_side: "white" ou "black"
        - Se winner_side == attacker_color: mantém o board como está.
        - Se winner_side == defender_color: atacante morre, defensor permanece.
        """
        if not self.last_battle:
            return

        lb = self.last_battle
        attacker_color = lb["attacker_color"]
        defender_color = lb["defender_color"]

        # estado atual: atacante já andou para attacker_dst e defensor foi removido
        if winner_side == attacker_color:
            # captura confirmada, não mexe em nada
            self.last_battle = None
            return

        if winner_side == defender_color:
            # desfaz a captura e MATAMOS o atacante
            dst = lb["attacker_dst"]
            src = lb["attacker_src"]

            # defensor volta para casa dele
            if defender_color == "white":
                color_val = WHITE
            else:
                color_val = BLACK

            # descobrir tipo a partir do nome salvo
            inv_piece_name = {v: k for k, v in PIECE_NAME.items()}
            def_type = inv_piece_name.get(lb["defender_type"])

            self.b.board[dst] = (color_val, def_type)
            # atacante some (casa de origem fica vazia)
            self.b.board[src] = None

            self.last_battle = None

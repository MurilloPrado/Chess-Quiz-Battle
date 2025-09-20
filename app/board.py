from typing import List, Optional, Tuple
from .constants import (
    BOARD_W, BOARD_H, FILES, WHITE, BLACK,
    PIECE_PAWN, PIECE_KNIGHT, PIECE_BISHOP, PIECE_ROOK, PIECE_QUEEN, PIECE_KING,
    PIECE_SYMBOL
)
from .move import Move


# ---------- helpers de coordenadas ----------
def sq(file: int, rank: int) -> int:
    return rank * BOARD_W + file

def fr(sq_idx: int) -> Tuple[int, int]:
    return (sq_idx % BOARD_W, sq_idx // BOARD_W)

def in_bounds(f: int, r: int) -> bool:
    return 0 <= f < BOARD_W and 0 <= r < BOARD_H

def algebraic_to_sq(a: str) -> int:
    f = FILES.index(a[0])
    r = int(a[1]) - 1
    return sq(f, r)

def sq_to_algebraic(sq_idx: int) -> str:
    f, r = fr(sq_idx)
    return f"{FILES[f]}{r+1}"


class Board5x6:
    """
    MiniChess 5x6 (Gardner):
    - Sem roque, sem duplo passo, sem en passant.
    - Promoção ao atingir a última rank (padrão dama).
    - Retaguarda sem peças repetidas; peões (5) podem se repetir.
    """
    def __init__(self) -> None:
        self.board: List[Optional[Tuple[int, int]]] = [None] * (BOARD_W * BOARD_H)
        self.turn = WHITE
        self.halfmove_clock = 0
        self.fullmove_number = 1
        self._stack = []  # para undo
        self._place_start_position()

    # ---------- setup ----------
    def _place(self, f: int, r: int, color: int, p: int) -> None:
        self.board[sq(f, r)] = (color, p)

    def _place_start_position(self) -> None:
        # White: rank 1 (r=0) R N B Q K ; rank 2 (r=1) peões
        back_white = [PIECE_ROOK, PIECE_KNIGHT, PIECE_BISHOP, PIECE_QUEEN, PIECE_KING]
        for f, pt in enumerate(back_white):
            self._place(f, 0, WHITE, pt)
        for f in range(BOARD_W):
            self._place(f, 1, WHITE, PIECE_PAWN)

        # Black: rank 6 (r=5) r n b q k ; rank 5 (r=4) peões
        back_black = [PIECE_ROOK, PIECE_KNIGHT, PIECE_BISHOP, PIECE_QUEEN, PIECE_KING]
        for f, pt in enumerate(back_black):
            self._place(f, 5, BLACK, pt)
        for f in range(BOARD_W):
            self._place(f, 4, BLACK, PIECE_PAWN)

        self.turn = WHITE
        self.halfmove_clock = 0
        self.fullmove_number = 1
        self._stack.clear()

    # ---------- consultas ----------
    def piece_at(self, idx: int) -> Optional[Tuple[int, int]]:
        return self.board[idx]

    def king_square(self, color: int) -> Optional[int]:
        for i, pc in enumerate(self.board):
            if pc == (color, PIECE_KING):
                return i
        return None

    def is_occupied_by(self, idx: int, color: int) -> bool:
        pc = self.board[idx]
        return pc is not None and pc[0] == color

    def enemy(self, color: int) -> int:
        return BLACK if color == WHITE else WHITE

    # ---------- geração de lances ----------
    def legal_moves(self) -> List[Move]:
        moves: List[Move] = []
        for i, pc in enumerate(self.board):
            if pc is None or pc[0] != self.turn:
                continue
            color, pt = pc
            if pt == PIECE_PAWN:
                moves += self._pawn_moves(i, color)
            elif pt == PIECE_KNIGHT:
                moves += self._knight_moves(i, color)
            elif pt == PIECE_BISHOP:
                moves += self._slider_moves(i, color, [(1,1),(1,-1),(-1,1),(-1,-1)])
            elif pt == PIECE_ROOK:
                moves += self._slider_moves(i, color, [(1,0),(-1,0),(0,1),(0,-1)])
            elif pt == PIECE_QUEEN:
                moves += self._slider_moves(i, color, [
                    (1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)
                ])
            elif pt == PIECE_KING:
                moves += self._king_moves(i, color)

        legal: List[Move] = []
        for m in moves:
            self._push(m)
            if not self.is_check(self.enemy(self.turn)):
                legal.append(m)
            self._pop()
        return legal

    def _pawn_moves(self, i: int, color: int) -> List[Move]:
        f, r = fr(i)
        direction = 1 if color == WHITE else -1
        out: List[Move] = []
        # frente 1
        nf, nr = f, r + direction
        if in_bounds(nf, nr) and self.board[sq(nf, nr)] is None:
            out.append(self._maybe_promo(i, sq(nf, nr)))
        # capturas
        for df in (-1, 1):
            nf, nr = f + df, r + direction
            if in_bounds(nf, nr):
                j = sq(nf, nr)
                t = self.board[j]
                if t is not None and t[0] != color:
                    out.append(self._maybe_promo(i, j))
        return out

    def _maybe_promo(self, src: int, dst: int) -> Move:
        _, rdst = fr(dst)
        color, pt = self.board[src]
        assert pt == PIECE_PAWN
        if (color == WHITE and rdst == BOARD_H - 1) or (color == BLACK and rdst == 0):
            return Move(src, dst, PIECE_QUEEN)
        return Move(src, dst, None)

    def _knight_moves(self, i: int, color: int) -> List[Move]:
        f, r = fr(i)
        out: List[Move] = []
        for df, dr in [(1,2),(2,1),(2,-1),(1,-2),(-1,-2),(-2,-1),(-2,1),(-1,2)]:
            nf, nr = f+df, r+dr
            if not in_bounds(nf, nr):
                continue
            j = sq(nf, nr)
            if not self.is_occupied_by(j, color):
                out.append(Move(i, j))
        return out

    def _slider_moves(self, i: int, color: int, dirs: List[Tuple[int,int]]) -> List[Move]:
        f, r = fr(i)
        out: List[Move] = []
        for df, dr in dirs:
            nf, nr = f + df, r + dr
            while in_bounds(nf, nr):
                j = sq(nf, nr)
                if self.board[j] is None:
                    out.append(Move(i, j))
                else:
                    if not self.is_occupied_by(j, color):
                        out.append(Move(i, j))
                    break
                nf += df
                nr += dr
        return out

    def _king_moves(self, i: int, color: int) -> List[Move]:
        f, r = fr(i)
        out: List[Move] = []
        for df in (-1,0,1):
            for dr in (-1,0,1):
                if df == 0 and dr == 0:
                    continue
                nf, nr = f+df, r+dr
                if not in_bounds(nf, nr):
                    continue
                j = sq(nf, nr)
                if not self.is_occupied_by(j, color):
                    out.append(Move(i, j))
        return out

    # ---------- cheque / término ----------
    def is_check(self, color_in_check: int) -> bool:
        ks = self.king_square(color_in_check)
        if ks is None:
            return False
        opp = self.enemy(color_in_check)

        for i, pc in enumerate(self.board):
            if pc is None or pc[0] != opp:
                continue
            _, pt = pc
            f, r = fr(i)
            if pt == PIECE_PAWN:
                direction = 1 if opp == WHITE else -1
                for df in (-1, 1):
                    nf, nr = f + df, r + direction
                    if in_bounds(nf, nr) and sq(nf, nr) == ks:
                        return True
            elif pt == PIECE_KNIGHT:
                for df, dr in [(1,2),(2,1),(2,-1),(1,-2),(-1,-2),(-2,-1),(-2,1),(-1,2)]:
                    nf, nr = f+df, r+dr
                    if in_bounds(nf, nr) and sq(nf, nr) == ks:
                        return True
            elif pt in (PIECE_BISHOP, PIECE_ROOK, PIECE_QUEEN):
                dirs = []
                if pt in (PIECE_ROOK, PIECE_QUEEN):
                    dirs += [(1,0),(-1,0),(0,1),(0,-1)]
                if pt in (PIECE_BISHOP, PIECE_QUEEN):
                    dirs += [(1,1),(1,-1),(-1,1),(-1,-1)]
                for df, dr in dirs:
                    nf, nr = f+df, r+dr
                    while in_bounds(nf, nr):
                        j = sq(nf, nr)
                        if j == ks:
                            return True
                        if self.board[j] is not None:
                            break
                        nf += df
                        nr += dr
            elif pt == PIECE_KING:
                for df in (-1,0,1):
                    for dr in (-1,0,1):
                        if df == 0 and dr == 0:
                            continue
                        nf, nr = f+df, r+dr
                        if in_bounds(nf, nr) and sq(nf, nr) == ks:
                            return True
        return False

    def outcome(self) -> Optional[str]:
        legal = self.legal_moves()
        if legal:
            return None
        if self.is_check(self.turn):
            return "checkmate_white_wins" if self.turn == BLACK else "checkmate_black_wins"
        return "stalemate"

    # ---------- fazer/desfazer ----------
    def _push(self, m: Move) -> None:
        captured = self.board[m.dst]
        moved = self.board[m.src]
        self._stack.append((m, captured, moved, self.turn, self.halfmove_clock, self.fullmove_number))

        # move
        self.board[m.dst] = moved
        self.board[m.src] = None

        # promoção
        if m.promo is not None:
            color, _ = self.board[m.dst]
            self.board[m.dst] = (color, m.promo)

        # relógio
        if captured is not None or (moved and moved[1] == PIECE_PAWN):
            self.halfmove_clock = 0
        else:
            self.halfmove_clock += 1

        # turno
        self.turn = self.enemy(self.turn)
        if self.turn == WHITE:
            self.fullmove_number += 1

    def _pop(self) -> None:
        m, captured, moved, prev_turn, prev_half, prev_full = self._stack.pop()
        self.board[m.src] = moved
        self.board[m.dst] = captured
        self.turn = prev_turn
        self.halfmove_clock = prev_half
        self.fullmove_number = prev_full

    # ---------- interface pública ----------
    def push_sanlike(self, uci: str) -> bool:
        """Aceita 'a2a3' ou 'a2a3q' (promo) e executa se legal."""
        uci = uci.strip().lower()
        if len(uci) < 4:
            return False
        try:
            src = algebraic_to_sq(uci[:2])
            dst = algebraic_to_sq(uci[2:4])
        except Exception:
            return False
        promo = None
        if len(uci) > 4:
            promo_map = {"q": PIECE_QUEEN, "r": PIECE_ROOK, "b": PIECE_BISHOP, "n": PIECE_KNIGHT}
            if uci[4] not in promo_map:
                return False
            promo = promo_map[uci[4]]

        wanted = (src, dst, promo or 0)
        for m in self.legal_moves():
            if (m.src, m.dst, (m.promo or 0)) == wanted:
                self._push(m)
                return True
        return False

    def pretty(self) -> str:
        rows = []
        for r in range(BOARD_H - 1, -1, -1):
            row = []
            for f in range(BOARD_W):
                pc = self.board[sq(f, r)]
                row.append(PIECE_SYMBOL.get(pc, ".") if pc else ".")
            rows.append(str(r + 1) + " " + " ".join(row))
        rows.append("  " + " ".join(FILES[:BOARD_W]))
        turn = "White" if self.turn == WHITE else "Black"
        rows.append(f"Turn: {turn}")
        return "\n".join(rows)

import tkinter as tk
from tkinter import messagebox
from typing import List, Tuple, Optional

from .board import Board5x6, fr, sq, sq_to_algebraic
from .constants import (
    BOARD_W, BOARD_H, WHITE, BLACK,
    PIECE_PAWN, PIECE_KNIGHT, PIECE_BISHOP, PIECE_ROOK, PIECE_QUEEN, PIECE_KING
)

# ---------- Config visual ----------
SQUARE = 96  # tamanho de cada casa (px)
PADDING = 0  # sem bordas extras
LIGHT_COLOR = "#F0D9B5"
DARK_COLOR  = "#B58863"
SEL_COLOR   = "#F6F669"
MOVE_COLOR  = "#A9D18E"
CHECK_COLOR = "#E57373"

UNICODE_WHITE = {
    PIECE_PAWN: "♙", PIECE_KNIGHT: "♘", PIECE_BISHOP: "♗",
    PIECE_ROOK: "♖", PIECE_QUEEN: "♕", PIECE_KING: "♔",
}
UNICODE_BLACK = {
    PIECE_PAWN: "♟", PIECE_KNIGHT: "♞", PIECE_BISHOP: "♝",
    PIECE_ROOK: "♜", PIECE_QUEEN: "♛", PIECE_KING: "♚",
}

def piece_to_unicode(color: int, p: int) -> str:
    return (UNICODE_WHITE if color == WHITE else UNICODE_BLACK).get(p, "·")


class MiniChessApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("MiniChess 5x6")
        self.board = Board5x6()

        self.canvas = tk.Canvas(
            root,
            width=BOARD_W * SQUARE + PADDING * 2,
            height=BOARD_H * SQUARE + PADDING * 2,
            highlightthickness=0,
        )
        self.canvas.pack(fill="both", expand=False)

        bar = tk.Frame(root)
        bar.pack(fill="x")
        self.turn_label = tk.Label(bar, text="Vez: Brancas", font=("Arial", 12, "bold"))
        self.turn_label.pack(side="left", padx=10, pady=6)
        tk.Button(bar, text="Reiniciar", command=self.reset).pack(side="right", padx=10)

        self.selected: Optional[int] = None
        self.legal_dests_from_selected: List[int] = []
        self.game_over = False

        self.canvas.bind("<Button-1>", self.on_click)
        self.draw()

    # ---------- UI actions ----------
    def reset(self):
        self.board = Board5x6()
        self.selected = None
        self.legal_dests_from_selected = []
        self.game_over = False
        self.draw()

    def on_click(self, event):
        if self.game_over:
            return

        f = int(event.x // SQUARE)
        r = BOARD_H - 1 - int(event.y // SQUARE)
        if not (0 <= f < BOARD_W and 0 <= r < BOARD_H):
            return

        idx = sq(f, r)
        # clique 1: selecionar peça da vez
        if self.selected is None:
            pc = self.board.piece_at(idx)
            if pc is None or pc[0] != self.board.turn:
                # opcional: se clicou em peça do adversário, ignore
                return
            self.selected = idx
            self.legal_dests_from_selected = [m.dst for m in self.board.legal_moves() if m.src == idx]
            self.draw()
            return

        # clique 2: tentar mover
        if idx == self.selected:
            # des-selecionar
            self.selected = None
            self.legal_dests_from_selected = []
            self.draw()
            return

        if idx in self.legal_dests_from_selected:
            self._apply_move(self.selected, idx)
            self.selected = None
            self.legal_dests_from_selected = []
            self.draw()

            outcome = self.board.outcome()
            if outcome:
                self.game_over = True
                if outcome.startswith("checkmate"):
                    winner = "Brancas" if "white" in outcome else "Negras"
                    messagebox.showinfo("Fim de jogo", f"Xeque-mate! {winner} vencem.")
                else:
                    messagebox.showinfo("Fim de jogo", "Afogamento (empate).")
            return

        # se clicou em outra peça da vez, muda a seleção
        pc = self.board.piece_at(idx)
        if pc is not None and pc[0] == self.board.turn:
            self.selected = idx
            self.legal_dests_from_selected = [m.dst for m in self.board.legal_moves() if m.src == idx]
            self.draw()
        else:
            # clique inválido: apenas limpa seleção
            self.selected = None
            self.legal_dests_from_selected = []
            self.draw()

    def _apply_move(self, src: int, dst: int):
        """Aplica movimento procurando em legal_moves (lida com promo automaticamente)."""
        # Tente casar src/dst ignorando promo e usar a string UCI apropriada
        f_src, r_src = fr(src)
        f_dst, r_dst = fr(dst)
        uci_base = f"{sq_to_algebraic(src)}{sq_to_algebraic(dst)}"

        # Verifica se o lance legal exige promoção
        for m in self.board.legal_moves():
            if m.src == src and m.dst == dst:
                if m.promo:
                    self.board.push_sanlike(uci_base + "q")  # promo padrão: dama
                else:
                    self.board.push_sanlike(uci_base)
                break

    # ---------- Desenho ----------
    def draw(self):
        self.canvas.delete("all")
        # casas
        for rr in range(BOARD_H):
            for ff in range(BOARD_W):
                x0 = PADDING + ff * SQUARE
                y0 = PADDING + (BOARD_H - 1 - rr) * SQUARE
                x1 = x0 + SQUARE
                y1 = y0 + SQUARE
                base = LIGHT_COLOR if (ff + rr) % 2 == 0 else DARK_COLOR
                self.canvas.create_rectangle(x0, y0, x1, y1, fill=base, width=0)

        # destaques (seleção e destinos)
        if self.selected is not None:
            sf, sr = fr(self.selected)
            x0 = sf * SQUARE
            y0 = (BOARD_H - 1 - sr) * SQUARE
            self.canvas.create_rectangle(x0, y0, x0 + SQUARE, y0 + SQUARE, outline=SEL_COLOR, width=4)

            for d in self.legal_dests_from_selected:
                df, dr = fr(d)
                dx0 = df * SQUARE
                dy0 = (BOARD_H - 1 - dr) * SQUARE
                self.canvas.create_rectangle(dx0, dy0, dx0 + SQUARE, dy0 + SQUARE, outline=MOVE_COLOR, width=4)

        # marca rei em cheque
        for color in (WHITE, BLACK):
            if self.board.is_check(color) and not self.game_over:
                ks = self.board.king_square(color)
                if ks is not None:
                    kf, kr = fr(ks)
                    x0 = kf * SQUARE
                    y0 = (BOARD_H - 1 - kr) * SQUARE
                    self.canvas.create_rectangle(x0, y0, x0 + SQUARE, y0 + SQUARE, outline=CHECK_COLOR, width=5)

        # peças
        for idx, pc in enumerate(self.board.board):
            if pc is None:
                continue
            color, pt = pc
            f, r = fr(idx)
            cx = f * SQUARE + SQUARE // 2
            cy = (BOARD_H - 1 - r) * SQUARE + SQUARE // 2
            self.canvas.create_text(
                cx, cy,
                text=piece_to_unicode(color, pt),
                font=("Segoe UI Symbol", int(SQUARE * 0.6)),
            )

        # label de turno
        self.turn_label.config(text=f"Vez: {'Brancas' if self.board.turn == WHITE else 'Negras'}")


def main():
    root = tk.Tk()
    app = MiniChessApp(root)
    root.resizable(False, False)
    root.mainloop()


if __name__ == "__main__":
    main()

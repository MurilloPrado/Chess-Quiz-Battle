# gui_tk.py

import tkinter as tk
from tkinter import messagebox, simpledialog  # Importa simpledialog
from typing import List, Tuple, Optional

# --- Correção das importações ---
# Remove o "." para permitir a execução direta do script
from board import Board5x6, fr, sq, sq_to_algebraic
from constants import (
    BOARD_W, BOARD_H, WHITE, BLACK,
    PIECE_PAWN, PIECE_KNIGHT, PIECE_BISHOP, PIECE_ROOK, PIECE_QUEEN, PIECE_KING
)
from quiz import abrir_quiz
import database  # Importa o novo módulo de banco de dados
# -------------------------------


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
        self.turn_label = tk.Label(bar, text="Vez: ...", font=("Arial", 12, "bold"))
        self.turn_label.pack(side="left", padx=10, pady=6)
        tk.Button(bar, text="Ranking", command=self.show_ranking).pack(side="right", padx=10)
        tk.Button(bar, text="Reiniciar", command=self.reset).pack(side="right", padx=10)

        self.selected: Optional[int] = None
        self.legal_dests_from_selected: List[int] = []
        self.game_over = False

        # --- Nomes dos Jogadores ---
        self.jogador_branco = "Brancas"
        self.jogador_preto = "Pretas"
        self.ask_player_names()  # Pergunta os nomes ao iniciar
        # ---------------------------

       # Trecho de gui_tk.py (dentro da classe MiniChessApp)


        self.canvas.bind("<Button-1>", self.on_click)
        self.draw()

    # NOVO: Método para exibir o ranking
    def show_ranking(self):
        """Cria e exibe uma nova janela com o ranking dos jogadores."""
        
        ranking_data = database.get_ranking()
        
        # Cria a janela de ranking
        ranking_win = tk.Toplevel(self.root)
        ranking_win.title("Ranking de Jogadores")
        ranking_win.geometry("400x400")
        ranking_win.grab_set() # Faz com que esta janela fique em foco
        ranking_win.transient(self.root) # Centraliza em relação à janela principal

        tk.Label(
            ranking_win,
            text="🏆 Ranking de Vitórias 🏆",
            font=("Arial", 16, "bold"),
            pady=10
        ).pack()

        if not ranking_data:
            tk.Label(
                ranking_win,
                text="Nenhum jogador registrado ainda.",
                font=("Arial", 12),
                pady=20
            ).pack()
            return
        
        # Frame para a lista
        list_frame = tk.Frame(ranking_win)
        list_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Cabeçalhos
        tk.Label(list_frame, text="Pos.", font=("Arial", 12, "bold")).grid(row=0, column=0, padx=5, sticky="w")
        tk.Label(list_frame, text="Nome do Jogador", font=("Arial", 12, "bold")).grid(row=0, column=1, padx=5, sticky="w")
        tk.Label(list_frame, text="Vitórias", font=("Arial", 12, "bold")).grid(row=0, column=2, padx=5, sticky="e")
        
        # Separador
        tk.Frame(list_frame, height=2, bg="gray").grid(row=1, column=0, columnspan=3, sticky="ew", pady=(0, 5))


        # Listagem dos jogadores
        for i, row in enumerate(ranking_data):
            nome, vitorias = row['nome'], row['vitorias']
            
            # Posição
            tk.Label(list_frame, text=f"{i+1}.", font=("Arial", 11)).grid(row=i+2, column=0, padx=5, sticky="w")
            
            # Nome
            tk.Label(list_frame, text=nome, font=("Arial", 11)).grid(row=i+2, column=1, padx=5, sticky="w")
            
            # Vitórias
            tk.Label(list_frame, text=str(vitorias), font=("Arial", 11)).grid(row=i+2, column=2, padx=5, sticky="e")

        # Configura as colunas para que a coluna 1 (Nome) se expanda
        list_frame.grid_columnconfigure(1, weight=1)

    # ---------- UI actions ----------
    
    def ask_player_names(self):
        """Usa simpledialog para perguntar o nome dos jogadores."""
        nome_b = simpledialog.askstring(
            "Jogador 1", "Nome do Jogador (Brancas):", parent=self.root
        )
        nome_p = simpledialog.askstring(
            "Jogador 2", "Nome do Jogador (Pretas):", parent=self.root
        )
        
        # Define nomes padrão caso o usuário cancele ou não digite
        self.jogador_branco = nome_b if nome_b else "Jogador Branco"
        self.jogador_preto = nome_p if nome_p else "Jogador Preto"
        self.update_turn_label() # Atualiza o label com o nome correto

    def update_turn_label(self):
        """Atualiza o label de turno com o nome do jogador."""
        player_name = self.jogador_branco if self.board.turn == WHITE else self.jogador_preto
        self.turn_label.config(text=f"Vez: {player_name}")

    def reset(self):
        self.board = Board5x6()
        self.selected = None
        self.legal_dests_from_selected = []
        self.game_over = False
        self.ask_player_names() # Pergunta os nomes novamente no reset
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
            self.draw() # draw() chama update_turn_label()

            outcome = self.board.outcome()
            if outcome:
                self.game_over = True
                if outcome.startswith("checkmate"):
                    
                    # --- LÓGICA DE VITÓRIA ---
                    winner_name = self.jogador_branco if "white" in outcome else self.jogador_preto
                    
                    # Registra a vitória no banco de dados
                    database.registrar_vitoria(winner_name)
                    
                    messagebox.showinfo("Fim de jogo", f"Xeque-mate! {winner_name} vence!")
                    # -------------------------
                    
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
        """Aplica movimento com quiz em capturas."""
        alvo = self.board.piece_at(dst)
        atacante = self.board.piece_at(src)

        print(f"Tentando mover de {src} para {dst}")
        if atacante:
            print(f"Atacante: {atacante}")
        if alvo:
            print(f"Alvo: {alvo}")

        # Se for captura, abre quiz
        if alvo is not None and atacante is not None and alvo[0] != atacante[0]:
            print("⚔️ Movimento de captura detectado, chamando quiz...")
            # from .constants import WHITE # Não precisamos mais disso aqui
            jogador_inicial = 1 if atacante[0] == WHITE else 2
            acertou = abrir_quiz(self.root, jogador_inicial=jogador_inicial)
            print(f"Resultado do quiz: {acertou}")

            if not acertou:
                print("❌ Alguém errou → removendo atacante")
                self.board.board[src] = None
                self.update_turn_label() # Atualiza o turno caso o quiz falhe
                self.draw()
                return
            else:
                print("✅ Ambos acertaram → continua com o movimento")
        # --- NOVO TRECHO DE VERIFICAÇÃO DE REI CAPTURADO ---
                from constants import PIECE_KING # Garante que PIECE_KING está acessível
                
                # Se o alvo é o Rei, o jogo terminou
                if alvo[1] == PIECE_KING: 
                    self.game_over = True
                    winner_color = atacante[0]
                    winner_name = self.jogador_branco if winner_color == 0 else self.jogador_preto
                    
                    # 1. Aplica o movimento para remover o rei do tabuleiro
                    for m in self.board.legal_moves():
                        if m.src == src and m.dst == dst:
                            if m.promo:
                                self.board.push_sanlike(f"{sq_to_algebraic(src)}{sq_to_algebraic(dst)}q")
                            else:
                                self.board.push_sanlike(f"{sq_to_algebraic(src)}{sq_to_algebraic(dst)}")
                            break
                            
                    # 2. Registra a vitória e exibe a mensagem
                    database.registrar_vitoria(winner_name)
                    messagebox.showinfo("Fim de jogo", f"Rei capturado! {winner_name} vence por captura!")
                    self.update_turn_label()
                    self.draw() # Desenha o estado final
                    return # Sai daqui, pois o jogo acabou
                
        # Movimento normal
        # from .board import fr, sq_to_algebraic # Imports já estão no topo
        f_src, r_src = fr(src)
        f_dst, r_dst = fr(dst)
        uci_base = f"{sq_to_algebraic(src)}{sq_to_algebraic(dst)}"

        for m in self.board.legal_moves():
            if m.src == src and m.dst == dst:
                if m.promo:
                    print("Promoção detectada")
                    self.board.push_sanlike(uci_base + "q")
                else:
                    self.board.push_sanlike(uci_base)
                break
        
        # Atualiza o label de turno APÓS o movimento ser feito
        self.update_turn_label()


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
        self.update_turn_label()


def main():
    # --- INICIALIZA O BANCO DE DADOS ---
    database.init_db()
    # -----------------------------------
    
    root = tk.Tk()
    app = MiniChessApp(root)
    root.resizable(False, False)
    root.mainloop()


if __name__ == "__main__":
    main()
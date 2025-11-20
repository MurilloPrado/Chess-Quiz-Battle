from typing import List, Optional, Tuple
from ..utils.constants import BOARD_W, BOARD_H, FILES, WHITE, PIECE_SYMBOL
from ..utils.coordinates import sq

def pretty(self) -> str:
    linhasRenderizadas = []
    for linha in range(BOARD_H - 1, -1, -1):
        linhaRender = []
        for coluna in range(BOARD_W):
            peca = self.board[sq(coluna, linha)]
            linhaRender.append(PIECE_SYMBOL.get(peca, "."))
        linhasRenderizadas.append(str(linha + 1) + " " + " ". join(linhaRender))
    linhasRenderizadas.append("  " + " ".join(FILES[:BOARD_W]))
    turnoTexto = "White" if self.turn == WHITE else "Black"
    linhasRenderizadas.append(f"Turn: {turnoTexto}")
    return "\n".join(linhasRenderizadas)

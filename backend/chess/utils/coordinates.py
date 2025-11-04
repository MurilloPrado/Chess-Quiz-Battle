from typing import Tuple
from .constants import BOARD_W, BOARD_H, FILES

# identificadores de coordenadas
def sq(coluna: int, linha: int) -> int:
    return linha * BOARD_W + coluna

def fr(indiceCasa: int) -> Tuple[int, int]:
    return (indiceCasa % BOARD_W, indiceCasa // BOARD_W)

def in_bounds(coluna: int, linha: int) -> bool:
    return 0 <= coluna < BOARD_W and 0 <= linha < BOARD_H

def algebraic_to_sq(a: str) -> int:
    coluna = FILES.index(a[0])
    linha = int(a[1]) - 1
    return sq(coluna, linha)

def sq_to_algebraic(indiceCasa: int) -> str:
    coluna, linha = fr(indiceCasa)
    return f"{FILES[coluna]}{linha+1}"

from typing import List, Optional, Tuple
from ..utils.constants import ( WHITE, BLACK, PIECE_PAWN, PIECE_KNIGHT, PIECE_BISHOP, PIECE_ROOK, PIECE_QUEEN, PIECE_KING, )
from ..utils.coordinates import sq, fr, in_bounds, algebraic_to_sq

# identificador de inimigo
def enemy(cor: int) -> int:
    return BLACK if cor == WHITE else WHITE


# casa do rei
def king_square(board: list, cor: int) -> Optional[int]:
    for indiceCasa, peca in enumerate(board):
        if peca == (cor, PIECE_KING):
            return indiceCasa
    return None


# cheque mate
def is_check(board: list, corEmXeque: int) -> bool:
    casaRei = king_square(board, corEmXeque)
    if casaRei is None:
        return False
    inimigo = enemy(corEmXeque)

    for indiceCasa, peca in enumerate(board):
        if peca is None or peca[0] != inimigo:
            continue
        _, tipoPeca = peca
        colunaPeca, linhaPeca = fr(indiceCasa)

        if tipoPeca == PIECE_PAWN:
            direcao = 1 if inimigo == WHITE else -1
            for deltaColuna in (-1, 1):
                novaColuna, novaLinha = colunaPeca + deltaColuna, linhaPeca + direcao
                if in_bounds(novaColuna, novaLinha) and sq(novaColuna, novaLinha) == casaRei:
                    return True
                                        
        elif tipoPeca == PIECE_KNIGHT:
            deslocamentos = [(1, 2), (2, 1), (2, -1), (1, -2), (-1, -2), (-2, -1), (-2, 1), (-1, 2)]
            for deltaColuna, deltaLinha in deslocamentos:
                novaColuna, novaLinha = colunaPeca + deltaColuna, linhaPeca + deltaLinha
                if in_bounds(novaColuna, novaLinha) and sq(novaColuna, novaLinha) == casaRei:
                    return True
                    
        elif tipoPeca in (PIECE_BISHOP, PIECE_ROOK, PIECE_QUEEN):
            direcoes: List[Tuple[int, int]] = []
            if tipoPeca in (PIECE_ROOK, PIECE_QUEEN):
                direcoes += [(1, 0), (-1, 0), (0, 1), (0, -1)]
                if tipoPeca in (PIECE_BISHOP, PIECE_QUEEN):
                    direcoes += [(1, 1), (1, -1), (-1, 1), (-1, -1)]

            for deltaColuna, deltaLinha in direcoes:
                novaColuna, novaLinha = colunaPeca + deltaColuna, linhaPeca + deltaLinha
                while in_bounds(novaColuna, novaLinha):
                    indiceAtual = sq(novaColuna, novaLinha)
                    if indiceAtual == casaRei:
                        return True
                    if board[indiceAtual] is not None:
                        break
                    novaColuna += deltaColuna
                    novaLinha += deltaLinha

        elif tipoPeca == PIECE_KING:
            for deltaColuna in (-1, 0, 1):
                for deltaLinha in (-1, 0, 1):
                    if deltaColuna == 0 and deltaLinha == 0:
                        continue
                    novaColuna, novaLinha = colunaPeca + deltaColuna, linhaPeca + deltaLinha
                    if in_bounds(novaColuna, novaLinha) and sq(novaColuna, novaLinha) == casaRei:
                        return True
    return False
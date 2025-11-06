from typing import List, Optional, Tuple
from ..utils.constants import ( BOARD_W, BOARD_H, FILES, WHITE, BLACK, PIECE_PAWN, PIECE_KNIGHT, PIECE_BISHOP, PIECE_ROOK, PIECE_QUEEN, PIECE_KING, )
from ..utils.coordinates import sq, fr, in_bounds, algebraic_to_sq
from .move import Move

# identifica qual peça esta ocupando
def is_occupied_by(board, idx: int, cor: int) -> bool:
    peca = board[idx]
    return peca is not None and peca[0] == cor


# movimentos possíveis das peças
# peão
def _pawn_moves(indiceOrigem: int, corPeao: int, board: list) -> List[Move]:
    colunaOrigem, linhaOrigem = fr(indiceOrigem)
    direcao = 1 if corPeao == WHITE else -1
    movimentos: List[Move] = []

    # avanço simples
    novaColuna, novaLinha = colunaOrigem, linhaOrigem + direcao
    if in_bounds(novaColuna, novaLinha) and board[sq(novaColuna, novaLinha)] is None:
        movimentos.append(Move(indiceOrigem, sq(novaColuna, novaLinha)))

    # capturas diagonais
    for deltaColuna in (-1, 1):
        novaColuna, novaLinha = colunaOrigem + deltaColuna, linhaOrigem + direcao
        if in_bounds(novaColuna, novaLinha):
            indiceDestino = sq(novaColuna, novaLinha)
            pecaAlvo = board[indiceDestino]
            if pecaAlvo is not None and pecaAlvo[0] != corPeao:
                movimentos.append(Move(indiceOrigem, indiceDestino))
    return movimentos
    

def _knight_moves(indiceOrigem: int, corCavalo: int, board: list) -> List[Move]:
    colunaOrigem, linhaOrigem = fr(indiceOrigem)
    movimentos: List[Move] = []
    deslocamentos: List[Tuple[int, int]] = [
        (1, 2), (2, 1), (2, -1), (1, -2), (-1, -2), (-2, -1), (-2, 1), (-1, 2)
    ]

    for deltaColuna, deltaLinha in deslocamentos:
        novaColuna, novaLinha = colunaOrigem + deltaColuna, linhaOrigem + deltaLinha
        if not in_bounds(novaColuna, novaLinha):
            continue
        indiceDestino = sq(novaColuna, novaLinha)
        if not is_occupied_by(board, indiceDestino, corCavalo):
            movimentos.append(Move(indiceOrigem, indiceDestino))
    return movimentos


def _slider_moves(indiceOrigem: int, corPeca: int, board: list, direcoes: List[Tuple[int, int]]) -> List[Move]:
    colunaOrigem, linhaOrigem = fr(indiceOrigem)
    movimentos: List[Move] = []
        
    for deltaColuna, deltaLinha in direcoes:
        novaColuna, novaLinha = colunaOrigem + deltaColuna, linhaOrigem + deltaLinha
        while in_bounds(novaColuna, novaLinha):
            indiceDestino = sq(novaColuna, novaLinha)

            if board[indiceDestino] is None:
                movimentos.append(Move(indiceOrigem, indiceDestino))
            else:
                if not is_occupied_by(board, indiceDestino, corPeca):
                    movimentos.append(Move(indiceOrigem, indiceDestino))
                break

            novaColuna += deltaColuna
            novaLinha += deltaLinha
        
    return movimentos
        

def _king_moves(indiceOrigem: int, corRei: int, board: list) -> List[Move]:
    colunaOrigem, linhaOrigem = fr(indiceOrigem)
    movimentos: List[Move] = []

    for deltaColuna in (-1, 0, 1):
        for deltaLinha in (-1, 0, 1):
            if deltaColuna == 0 and deltaLinha == 0:
                continue
            novaColuna, novaLinha = colunaOrigem + deltaColuna, linhaOrigem + deltaLinha

            if not in_bounds(novaColuna, novaLinha):
                continue
            indiceDestino = sq(novaColuna, novaLinha)

            if not is_occupied_by(board, indiceDestino, corRei):
                movimentos.append(Move(indiceOrigem, indiceDestino))
    return movimentos
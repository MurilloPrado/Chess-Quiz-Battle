from typing import List, Optional, Tuple
from ..utils.constants import (
    BOARD_W, BOARD_H, FILES, WHITE, BLACK,
    PIECE_PAWN, PIECE_KNIGHT, PIECE_BISHOP, PIECE_ROOK, PIECE_QUEEN, PIECE_KING, PIECE_SYMBOL
)
from .move import Move

# criação do jogo
class Board5x6:
    def __init__(self) -> None:
        self.board: List[Optional[Tuple[int, int]]] = [None] * (BOARD_W * BOARD_H)
        self.turn = WHITE
        self.halfmove_clock = 0  #antes do movimento
        self.fullmove_number = 1 # faz o movimento
        self._stack = [] # limpa o movimento
        self._place_start_position()

    
    def _place(self, coluna: int, linha: int, cor: int, tipoPeca: int) -> None:
        self.board[sq(coluna, linha)] = (cor, tipoPeca)

    
    def _place_start_position(self) -> None:
        # gera as peças brancas
        back_white = [PIECE_ROOK, PIECE_QUEEN, PIECE_KING, PIECE_KNIGHT, PIECE_BISHOP]
        for colunaIndex, tipoPeca in enumerate(back_white):
            self._place(colunaIndex, 0, WHITE, tipoPeca)
        for f in range(BOARD_W):
            self._place(colunaIndex, 1, WHITE, PIECE_PAWN)

        # gera as peças pretas
        back_black = [PIECE_ROOK, PIECE_QUEEN, PIECE_KING, PIECE_KNIGHT, PIECE_BISHOP]
        for colunaIndex, tipoPeca in enumerate(back_black):
            self._place(colunaIndex, 5, BLACK, tipoPeca)
        for f in range(BOARD_W):
            self._place(colunaIndex, 4, BLACK, PIECE_PAWN)

        self.turn = WHITE
        self.halfmove_clock = 0
        self.fullmove_number = 1
        self._stack.clear()

    
    # identificadores de posição
    def piece_at(self, idx: int) -> Optional[Tuple[int, int]]:
        return self.board[idx]
    
    def king_square(self, cor: int) -> Optional[int]:
        for indiceCasa, peca in enumerate(self.board):
            if peca == (cor, PIECE_KING):
                return indiceCasa
        return None
    
    # identifica qual peça esta ocupando
    def is_occupied_by(self, idx: int, cor: int) -> bool:
        peca = self.board[idx]
        return peca is not None and peca[0] == cor
    
    # identificador de inimigo
    def enemy(self, cor: int) -> int:
        return BLACK if cor == WHITE else WHITE
    
    # geração de lances
    def legal_moves(self) -> List[Move]:
        moves: List[Move] = []
        for indiceCasa, peca in enumerate(self.board):
            if peca is None or peca[0] != self.turn:
                continue
            corPeca, tipoPeca = peca
            # movimentos de cada peça
            if tipoPeca == PIECE_PAWN:
                moves += self._pawn_moves(indiceCasa, corPeca)
            elif tipoPeca == PIECE_KNIGHT:
                moves += self._knight_moves(indiceCasa, corPeca)
            elif tipoPeca == PIECE_BISHOP:
                moves += self._slider_moves(
                    indiceCasa, corPeca, 
                    [(1, 1), (1, -1), (-1, 1), (-1, -1)]
                )
            elif tipoPeca == PIECE_ROOK:
                movimentosGerados += self._slider_moves(
                    indiceCasa, corPeca, 
                    [(1, 0), (-1, 0), (0, 1), (0, -1)]
                )
            elif tipoPeca == PIECE_QUEEN:
                movimentosGerados += self._slider_moves(
                    indiceCasa, corPeca,
                    [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]
                )
            elif tipoPeca == PIECE_KING:
                movimentosGerados += self._king_moves(indiceCasa, corPeca)
            
        
        # verifica se movimento é legal
        legal: List[Move] = []
        for movimento in moves:
            self._push(movimento)
            if not self.is_check(self.enemy(self.turn)):
                legal.append(movimento)
            self._pop()
        return legal
    

    # movimentos possíveis das peças
    # peão
    def _pawn_moves(self, indiceOrigem: int, corPeao: int) -> List[Move]:
        colunaOrigem, linhaOrigem = fr(indiceOrigem)
        direcao = 1 if corPeao == WHITE else -1
        movimentos: List[Move] = []

        # avanço simples
        novaColuna, novaLinha = colunaOrigem, linhaOrigem + direcao
        if in_bounds(novaColuna, novaLinha) and self.board[sq(novaColuna, novaLinha)] is None:
            movimentos.append(self._talvez_promova(indiceOrigem, sq(novaColuna, novaLinha)))

        # capturas diagonais
        
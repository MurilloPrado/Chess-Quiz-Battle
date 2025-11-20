from typing import List, Optional, Tuple
from ..utils.constants import ( BOARD_W, BOARD_H, WHITE, BLACK, PIECE_PAWN, PIECE_KNIGHT, PIECE_BISHOP, PIECE_ROOK, PIECE_QUEEN, PIECE_KING, )
from ..utils.coordinates import sq, fr, algebraic_to_sq
from .move import Move
from .pieces import _pawn_moves, _knight_moves, _slider_moves, _king_moves
from .rules import is_check, enemy, king_square

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
        for colunaIndex in range(BOARD_W):
            self._place(colunaIndex, 1, WHITE, PIECE_PAWN)

        # gera as peças pretas
        back_black = [PIECE_ROOK, PIECE_QUEEN, PIECE_KING, PIECE_KNIGHT, PIECE_BISHOP]
        for colunaIndex, tipoPeca in enumerate(back_black):
            self._place(colunaIndex, 5, BLACK, tipoPeca)
        for colunaIndex in range(BOARD_W):
            self._place(colunaIndex, 4, BLACK, PIECE_PAWN)

        self.turn = WHITE
        self.halfmove_clock = 0
        self.fullmove_number = 1
        self._stack.clear()

    
    # identificadores de posição
    def piece_at(self, idx: int) -> Optional[Tuple[int, int]]:
        return self.board[idx]
    

    def is_check(self, color: int) -> bool:
        return is_check(self.board, color)
    

    def king_square(self, color: int): 
        return king_square(self.board, color)


    # geração de lances
    def legal_moves(self) -> List[Move]:
        moves: List[Move] = []
        for indiceCasa, peca in enumerate(self.board):
            if peca is None or peca[0] != self.turn:
                continue
            corPeca, tipoPeca = peca
            # movimentos de cada peça
            if tipoPeca == PIECE_PAWN:
                moves += [ self._talvez_promova(indiceCasa, m.dst) for m in _pawn_moves(indiceCasa, corPeca, self.board) ]
            elif tipoPeca == PIECE_KNIGHT:
                moves += _knight_moves(indiceCasa, corPeca, self.board)
            elif tipoPeca == PIECE_BISHOP:
                moves += _slider_moves(
                    indiceCasa, corPeca, self.board, 
                    [(1, 1), (1, -1), (-1, 1), (-1, -1)]
                )
            elif tipoPeca == PIECE_ROOK:
                moves += _slider_moves(
                    indiceCasa, corPeca, self.board, 
                    [(1, 0), (-1, 0), (0, 1), (0, -1)]
                )
            elif tipoPeca == PIECE_QUEEN:
                moves += _slider_moves(
                    indiceCasa, corPeca, self.board,
                    [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]
                )
            elif tipoPeca == PIECE_KING:
                moves += _king_moves(indiceCasa, corPeca, self.board)
            
        
        # verifica se movimento é legal
        legal: List[Move] = []
        for movimento in moves:
            self._push(movimento)
            if not self.is_check(enemy(self.turn)):
                legal.append(movimento)
            self._pop()
        return legal
    

    # promoção de peão 
    def _talvez_promova(self, indiceOrigem: int, indiceDestino: int) -> Move:
        _, linhaDestino = fr(indiceDestino)
        corPeca, tipoPeca = self.board[indiceOrigem]
        assert tipoPeca == PIECE_PAWN
        if (corPeca == WHITE and linhaDestino == BOARD_H - 1) or (corPeca == BLACK and linhaDestino == 0):
            return Move(indiceOrigem, indiceDestino, PIECE_QUEEN)
        return Move(indiceOrigem, indiceDestino, None)
    

    # fim de jogo
    def outcome(self) -> Optional[str]:
        white_king_sq = king_square(self.board, WHITE)
        black_king_sq = king_square(self.board, BLACK)

        if white_king_sq is None and black_king_sq is not None:
            return "checkmate_black_wins"

        # se só o rei preto sumiu => brancas venceram
        if black_king_sq is None and white_king_sq is not None:
            return "checkmate_white_wins"

        # se os dois reis sumiram (bem improvável) trata como empate
        if white_king_sq is None and black_king_sq is None:
            return "stalemate"

        # 2) lógica normal de checkmate / stalemate
        legalMoves = self.legal_moves()
        if legalMoves:
            return None

        if self.is_check(self.turn):
            return "checkmate_white_wins" if self.turn == BLACK else "checkmate_black_wins"

        return "stalemate"
    

    # faz/desfaz movimento
    def _push(self, movimento: Move) -> None:
        pecaCapturada = self.board[movimento.dst]
        pecaMovida = self.board[movimento.src]

        self._stack.append((movimento, pecaCapturada, pecaMovida, self.turn, self.halfmove_clock, self.fullmove_number))
        # move peça
        self.board[movimento.dst] = pecaMovida
        self.board[movimento.src] = None

        # promoção
        if movimento.promo is not None:
            corPeca, _ = self.board[movimento.dst]
            self.board[movimento.dst] = (corPeca, movimento.promo)

        # relógio de 50 lances
        if pecaCapturada is not None or (pecaMovida and pecaMovida[1] == PIECE_PAWN):
            self.halfmove_clock = 0
        else:
            self.halfmove_clock += 1

        # troca de turno
        self.turn = enemy(self.turn)
        if self.turn == WHITE:
            self.fullmove_number += 1


    def _pop(self) -> None:
        movimento, pecaCapturada, pecaMovida, turnoAnterior, meioLanceAnterior, lanceCompletoAnterior = self._stack.pop()
        self.board[movimento.src] = pecaMovida
        self.board[movimento.dst] = pecaCapturada
        self.turn = turnoAnterior
        self.halfmove_clock = meioLanceAnterior
        self.fullmove_number = lanceCompletoAnterior

    
    # interface
    def push_sanlike(self, uci: str) -> bool:
        uci = uci.strip().lower()
        if len(uci) < 4:
            return False
        try:
            indiceOrigem = algebraic_to_sq(uci[:2])
            indiceDestino = algebraic_to_sq(uci[2:4])
        except Exception:
            return False
        
        promocao = None
        if len(uci) > 4:
            mapaPromocao = {"q": PIECE_QUEEN, "r": PIECE_ROOK, "b": PIECE_BISHOP, "n": PIECE_KNIGHT}
            if uci[4] not in mapaPromocao:
                return False
            promocao = mapaPromocao[uci[4]]

        desejado = (indiceOrigem, indiceDestino, promocao or 0)
        for movimento in self.legal_moves():
            if(movimento.src, movimento.dst, (movimento.promo or 0)) == desejado:
                self._push(movimento)
                return True
        return False
    
            
        
            
        
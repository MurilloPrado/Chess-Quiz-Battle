import os
import pygame
from chess.utils.constants import (
    WHITE, BLACK,
    PIECE_PAWN, PIECE_KNIGHT, PIECE_BISHOP,
    PIECE_ROOK, PIECE_QUEEN, PIECE_KING,
)
# CHANGED: mapeia (cor,tipo) -> nome de arquivo
_CODE = {
    (WHITE, PIECE_KING):   "wK.png",
    (WHITE, PIECE_QUEEN):  "wQ.png",
    (WHITE, PIECE_ROOK):   "wR.png",
    (WHITE, PIECE_BISHOP): "wB.png",
    (WHITE, PIECE_KNIGHT): "wN.png",
    (WHITE, PIECE_PAWN):   "wP.png",
    (BLACK, PIECE_KING):   "bK.png",
    (BLACK, PIECE_QUEEN):  "bQ.png",
    (BLACK, PIECE_ROOK):   "bR.png",
    (BLACK, PIECE_BISHOP): "bB.png",
    (BLACK, PIECE_KNIGHT): "bN.png",
    (BLACK, PIECE_PAWN):   "bP.png",
}

def load_piece_surfaces(base_dir: str, tile_size: int) -> dict:
    atlas = {}
    for key, fname in _CODE.items():
        path = os.path.join(base_dir, fname)
        img = pygame.image.load(path).convert_alpha()
        if img.get_width() != tile_size or img.get_height() != tile_size:
            img = pygame.transform.smoothscale(img, (tile_size, tile_size))
        atlas[key] = img
    return atlas

from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class Move:
    src: int
    dst: int
    promo: Optional[int] = None  # peça de promoção (ex: QUEEN)

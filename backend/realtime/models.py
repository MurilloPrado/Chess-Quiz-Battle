# mensagens e estados
from typing import Literal, Optional, List, Tuple
from pydantic import BaseModel, Field

# Tipos básicos
Coord = Tuple[int, int]  # (x, y)

# Estado do tabuleiro (simplificado): você pode trocar pelo seu objeto real
class BoardState(BaseModel):
    cells: List[Optional[str]]  # len = 64 (ou seu tamanho), ex: "wP", "bQ", None
    width: int = 8
    height: int = 8

class Phase(str):
    CHESS = "chess"
    QUIZ = "quiz"
    LOBBY = "lobby"

# Mensagens Host -> Client
class StateMsg(BaseModel):
    type: Literal["state"] = "state"
    phase: Literal["lobby", "chess", "quiz"]
    board: Optional[BoardState] = None
    turn: Optional[Literal["white", "black"]] = None
    quiz: Optional[dict] = None  # {question, answers, timer} se phase == "quiz"
    players: List[dict] = Field(default_factory=list)  # [{id, name, avatar}]

# Mensagens Client -> Host
class JoinMsg(BaseModel):
    type: Literal["join"]
    name: str
    avatar: Optional[str] = None

class MoveMsg(BaseModel):
    type: Literal["move"]
    from_: Coord = Field(alias="from")
    to: Coord

class QuizAnswerMsg(BaseModel):
    type: Literal["quiz_answer"]
    answer: str

IncomingMsg = JoinMsg | MoveMsg | QuizAnswerMsg

# Envelope “any”
class AnyMsg(BaseModel):
    type: str

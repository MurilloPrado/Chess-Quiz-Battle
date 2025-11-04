from fastapi import FastAPI
from pydantic import BaseModel, Field
from typing import Optional, List
from uuid import uuid4

app = FastAPI(
    title="Chess Quiz Battle API",
    version="0.1.0",
    description="Rotas básicas para criar sessão (/launch), registrar pontuação (/score) e checagem de saúde (/health)."
)

@app.get("/health", tags=["health"])
def health():
    return {"status": "ok"}

# ======= Models =======
class LaunchRequest(BaseModel):
    player_name: str = Field(..., description="Nome do jogador (ex.: 'jogador1')")
    mode: Optional[str] = Field(default="quiz", description="Modo da partida (ex.: 'quiz')")

class LaunchResponse(BaseModel):
    session_id: str = Field(..., description="UUID da nova sessão")
    message: str = Field(..., description="Mensagem simples indicando criação da sessão")
    mode: str = Field(..., description="Modo retornado para conferência")

class ScoreItem(BaseModel):
    question_id: Optional[str] = Field(default=None, description="ID da pergunta (opcional enquanto não há lógica)")
    correct: bool = Field(..., description="Se a resposta foi correta")
    points: int = Field(..., description="Pontuação atribuída a esta resposta")

class ScoreRequest(BaseModel):
    session_id: str = Field(..., description="UUID da sessão")
    player_name: str = Field(..., description="Nome do jogador (ex.: 'jogador1')")
    items: List[ScoreItem] = Field(default_factory=list, description="Lista de itens de pontuação")

class ScoreResponse(BaseModel):
    accepted: bool = Field(..., description="Se o registro foi aceito")
    session_id: str = Field(..., description="UUID da sessão")
    player_name: str = Field(..., description="Jogador relacionado ao score")
    total_points: int = Field(..., description="Soma simples dos pontos informados")

# ======= Endpoints =======
@app.post("/launch", response_model=LaunchResponse, tags=["match"])
def launch(req: LaunchRequest):
    # Lógica simples: apenas gerar um UUID e devolver
    session_id = str(uuid4())
    return LaunchResponse(
        session_id=session_id,
        message=f"Sessão criada para {req.player_name}.",
        mode=req.mode or "quiz",
    )

@app.post("/score", response_model=ScoreResponse, tags=["match"])
def score(req: ScoreRequest):
    # Lógica simples: somar pontos informados
    total = sum(item.points for item in req.items) if req.items else 0
    return ScoreResponse(
        accepted=True,
        session_id=req.session_id,
        player_name=req.player_name,
        total_points=total,
    )

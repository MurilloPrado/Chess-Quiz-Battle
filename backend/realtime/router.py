# realtime/router.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Request
from fastapi.responses import JSONResponse
from .ws_manager import ConnectionManager
from .models import StateMsg, JoinMsg, MoveMsg, QuizAnswerMsg

router = APIRouter()

# ---------- Dependencies SEPARADAS para HTTP e para WebSocket ----------

# HTTP deps (Request é injetado no handler HTTP)
def get_manager_http(request: Request) -> ConnectionManager:
    return request.app.state.conn_manager

def get_ctx_http(request: Request) -> dict:
    return request.app.state.game_ctx

# WS deps (WebSocket é injetado no handler WS)
def get_manager_ws(websocket: WebSocket) -> ConnectionManager:
    return websocket.app.state.conn_manager  # starlette injeta app no websocket

def get_ctx_ws(websocket: WebSocket) -> dict:
    return websocket.app.state.game_ctx

# ----------------------------------------------------------------------

@router.get("/health")
async def health():
    return {"status": "ok"}

@router.get("/state")
async def state_snapshot(
    mgr: ConnectionManager = Depends(get_manager_http),
    ctx: dict = Depends(get_ctx_http),
):
    payload = StateMsg(
        phase=ctx["phase"],
        board=ctx.get("board"),
        turn=ctx.get("turn"),
        quiz=ctx.get("quiz"),
        players=mgr.list_players(),   # <-- bater com ws_manager.py
    )
    return JSONResponse(payload.model_dump())

@router.websocket("/ws")
async def ws_endpoint(
    ws: WebSocket,
    mgr: ConnectionManager = Depends(get_manager_ws),
    ctx: dict = Depends(get_ctx_ws),
):
    import json, uuid
    cid = str(uuid.uuid4())
    await mgr.connect(ws, cid)

    # snapshot inicial para o cliente recém-conectado
    await mgr.send_personal(cid, StateMsg(   # <-- bater com ws_manager.py
        phase=ctx["phase"],
        board=ctx.get("board"),
        turn=ctx.get("turn"),
        quiz=ctx.get("quiz"),
        players=mgr.list_players(),          # <-- bater com ws_manager.py
    ).model_dump())

    try:
        while True:
            data = json.loads(await ws.receive_text())
            kind = data.get("type")

            if kind == "join":
                msg = JoinMsg.model_validate(data)
                mgr.set_meta(cid, {"name": msg.name, "avatar": msg.avatar})
                await mgr.broadcast(StateMsg(
                    phase=ctx["phase"],
                    board=ctx.get("board"),
                    turn=ctx.get("turn"),
                    quiz=ctx.get("quiz"),
                    players=mgr.list_players(),
                ).model_dump())

            elif kind == "move":
                msg = MoveMsg.model_validate(data)
                ok, capture = await ctx["on_move"](msg.from_, msg.to)
                await mgr.broadcast(StateMsg(
                    phase=ctx["phase"],
                    board=ctx.get("board"),
                    turn=ctx.get("turn"),
                    quiz=ctx.get("quiz"),
                    players=mgr.list_players(),
                ).model_dump())

            elif kind == "quiz_answer":
                msg = QuizAnswerMsg.model_validate(data)
                await ctx["on_quiz_answer"](cid, msg.answer)

                # Sempre manda o snapshot atualizado, independente de ter acabado ou não
                await mgr.broadcast(StateMsg(
                    phase=ctx["phase"],
                    board=ctx.get("board"),
                    turn=ctx.get("turn"),
                    quiz=ctx.get("quiz"),
                    players=mgr.list_players(),
                ).model_dump())

    except WebSocketDisconnect:
        mgr.remove(cid)
        await mgr.broadcast(StateMsg(
            phase=ctx["phase"],
            board=ctx.get("board"),
            turn=ctx.get("turn"),
            quiz=ctx.get("quiz"),
            players=mgr.list_players(),
        ).model_dump())

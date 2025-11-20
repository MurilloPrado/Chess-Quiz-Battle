# realtime/router.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Request
from fastapi.responses import JSONResponse
from .ws_manager import ConnectionManager
from .models import StateMsg, JoinMsg, MoveMsg, QuizAnswerMsg
import time 

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

def _build_state_payload(mgr: ConnectionManager, ctx: dict) -> dict:
    quiz = ctx.get("quiz")
    quiz_out = None
    if quiz:
        quiz_out = dict(quiz)  # cópia rasa (preserva attacker/defender/choices/etc)
        side = quiz_out.get("currentSide", "white")
        pool = quiz_out.get("timePool") or {}
        started = quiz_out.get("turnStartedAt")
        # se temos banco+start, calcula remaining do turno; senão mantém compat
        if isinstance(pool, dict) and side in pool and started:
            bank = float(pool.get(side, 0.0))
            elapsed = max(0.0, time.time() - float(started))
            remaining = max(0.0, bank - elapsed)
            quiz_out["maxTime"] = bank
            quiz_out["remainingTime"] = remaining
        else:
            mx = float(quiz_out.get("maxTime", quiz_out.get("timer", 15)))
            rem = float(quiz_out.get("remainingTime", mx))
            quiz_out["maxTime"] = mx
            quiz_out["remainingTime"] = max(0.0, min(rem, mx))

    payload = StateMsg(
        phase=ctx["phase"],
        board=ctx.get("board"),
        turn=ctx.get("turn"),
        quiz=quiz_out,
        players=mgr.list_players(),
    ).model_dump()
    
    payload["inCheckSide"] = ctx.get("inCheckSide")   # "white" | "black" | None
    payload["inCheckKing"] = ctx.get("inCheckKing")   # {"x":int,"y":int} | None

    return payload

@router.get("/health")
async def health():
    return {"status": "ok"}

@router.get("/state")
async def state_snapshot(mgr: ConnectionManager = Depends(get_manager_http), ctx: dict = Depends(get_ctx_http)):
    return JSONResponse(_build_state_payload(mgr, ctx))

@router.websocket("/ws")
async def ws_endpoint(ws: WebSocket,
                      mgr: ConnectionManager = Depends(get_manager_ws),
                      ctx: dict = Depends(get_ctx_ws)):
    import json, uuid
    cid = str(uuid.uuid4())
    await mgr.connect(ws, cid)

    await mgr.send_personal(cid, _build_state_payload(mgr, ctx))

    try:
        while True:
            data = json.loads(await ws.receive_text())
            kind = data.get("type")

            if kind == "join":
                msg = JoinMsg.model_validate(data)
                mgr.set_meta(cid, {"name": msg.name, "avatar": msg.avatar})
                await mgr.send_personal(cid, _build_state_payload(mgr, ctx))   # <- NEW
                await mgr.broadcast(_build_state_payload(mgr, ctx))

            elif kind == "move":
                msg = MoveMsg.model_validate(data)
                ok, capture = await ctx["on_move"](msg.from_, msg.to)
                await mgr.broadcast(_build_state_payload(mgr, ctx))

            elif kind == "quiz_answer":
                msg = QuizAnswerMsg.model_validate(data)
                await ctx["on_quiz_answer"](cid, msg.answer)
                await mgr.broadcast(_build_state_payload(mgr, ctx))

            elif kind == "resign":
                side = None
                if hasattr(mgr, "slots"):
                    if mgr.slots.get("white") == cid: side = "white"
                    elif mgr.slots.get("black") == cid: side = "black"
                if side:
                    # finalize duelo/partida como preferir
                    ctx["phase"] = "chess"
                    ctx["quiz"] = None
                await mgr.broadcast(_build_state_payload(mgr, ctx))

    except WebSocketDisconnect:
        mgr.remove(cid)
        await mgr.broadcast(_build_state_payload(mgr, ctx))
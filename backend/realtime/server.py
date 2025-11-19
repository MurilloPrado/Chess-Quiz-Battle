import asyncio, socket, uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from .ws_manager import ConnectionManager
from .router import router, _build_state_payload

def get_local_ip() -> str:
    # tenta via socket “externo”
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        if ip and not ip.startswith("127."):
            return ip
    except Exception:
        pass
    # tenta pelo hostname
    try:
        host = socket.gethostname()
        ips = socket.gethostbyname_ex(host)[2]
        for ip in ips:
            if not ip.startswith("127."):
                return ip
    except Exception:
        pass
    # último recurso
    return "127.0.0.1"

def create_app(static_dir: str, game_ctx: dict) -> FastAPI:
    app = FastAPI(title="Chess-Quiz Realtime")
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
    app.state.conn_manager = ConnectionManager()
    app.state.game_ctx = game_ctx

    @app.on_event("startup")
    async def _start_quiz_broadcaster():
        async def _loop():
            while True:
                await asyncio.sleep(0.33)  # ~3x/seg
                mgr: ConnectionManager = app.state.conn_manager
                ctx: dict = app.state.game_ctx
                if not mgr.client_count(): continue
                if ctx.get("phase") != "quiz": continue
                if not ctx.get("quiz"): continue
                try:
                    await mgr.broadcast(_build_state_payload(mgr, ctx))
                except Exception:
                    pass
        asyncio.create_task(_loop())

    app.mount("/web", StaticFiles(directory=static_dir, html=True), name="web")
    app.include_router(router)
    return app

def run_uvicorn_in_bg(app: FastAPI, host: str, port: int):
    config = uvicorn.Config(app, host=host, port=port, log_level="warning")
    server = uvicorn.Server(config)
    import threading
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    return t

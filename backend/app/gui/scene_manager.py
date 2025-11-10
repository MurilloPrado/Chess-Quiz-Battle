from dataclasses import dataclass

@dataclass
class SceneResult:
    next_scene: str | None = None   # "menu" | "game" | None
    payload: dict | None = None

class Scene:
    def enter(self, ctx): ...
    def leave(self): ...
    def handle_event(self, ev): ...
    def update(self, dt): ...
    def render(self, screen): ...

class SceneManager:
    def __init__(self, registry: dict[str, Scene], first: str, ctx):
        self.registry = registry
        self.current_key = first
        self.current = registry[first]
        self.ctx = ctx
        self.current.enter(ctx)

    def switch(self, key, payload=None):
        self.current.leave()
        self.current_key = key
        self.current = self.registry[key]
        self.current.enter(self.ctx if payload is None else {**self.ctx, **(payload or {})})

    def tick(self, evts, dt, screen):
        for e in evts:
            res = self.current.handle_event(e)
            if isinstance(res, SceneResult) and res.next_scene:
                self.switch(res.next_scene, res.payload)
        self.current.update(dt)
        self.current.render(screen)

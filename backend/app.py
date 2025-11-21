import pygame, time
from app.gui.scene_manager import SceneManager
from app.gui.scenes.menu import MenuScene
from app.gui.scenes.game import GameScene
from app.gui.scenes.lobby import LobbyScene
from app.gui.scenes.rules import RulesScene
from app.gui.scenes.ranking import RankingScene

# importa tua API de xadrez
from chess.render.adapter import ChessAPI  # adapte ao teu caminho real

def run():
    pygame.init()
    size = (960, 540)
    screen = pygame.display.set_mode(size, pygame.DOUBLEBUF | pygame.RESIZABLE)
    pygame.display.set_caption("Chess Quiz Battle")

    # contexto compartilhado
    ctx = {"screen": pygame.display.get_surface()}

    api = ChessAPI()  # tua implementação

    mgr = SceneManager(
        registry={
            "menu": MenuScene(size),
            "lobby": LobbyScene((screen.get_width(), screen.get_height())),
            "game": GameScene(size, api),
            "rules": RulesScene(size),
            "ranking": RankingScene(size),
        },
        first="menu",
        ctx=ctx,
    )

    clock = pygame.time.Clock()
    running = True
    while running:
        dt = clock.tick(60) / 1000.0
        events = pygame.event.get()
        for e in events:
            if e.type == pygame.QUIT: running = False
            if e.type == pygame.VIDEORESIZE:
                ctx["screen"] = pygame.display.set_mode(
                    (e.w, e.h), pygame.DOUBLEBUF | pygame.RESIZABLE
                )

        mgr.tick(events, dt, ctx["screen"])
        pygame.display.flip()

    pygame.quit()

if __name__ == "__main__":
    run()

from pathlib import Path
import pygame

ROOT = Path(__file__).resolve().parents[2]  # vai até raiz do projeto
ASSETS = ROOT / "assets"
ui = ASSETS / "ui"
D3 = ASSETS / "3d"

def font_consolas(size: int) -> pygame.font.Font:
    pygame.font.init()
    f = pygame.font.SysFont("Consolas", size)
    if not f:  # fallback
        f = pygame.font.SysFont("Courier New", size)
    return f


import pygame
from app.gui.assets import font_consolas

class ConsoleWidget:
    def __init__(self, rect: pygame.Rect, lines=8):
        self.rect = rect
        self.font = font_consolas(18)
        self.lines = [""] * lines
        self.neon = (20, 230, 60)

    def push(self, text: str):
        self.lines.pop(0)
        self.lines.append(text)

    def draw(self, screen: pygame.Surface):
        pygame.draw.rect(screen, (0,0,0), self.rect)
        pygame.draw.rect(screen, self.neon, self.rect, 2)  # borda verde
        pad = 8
        y = self.rect.y + pad
        for ln in self.lines:
            surf = self.font.render(ln, True, (220, 255, 220))
            screen.blit(surf, (self.rect.x + pad, y))
            y += 20

import random, pygame
from app.gui.assets import font_consolas

class MatrixRain:
    def __init__(self, size: tuple[int,int], density=45):
        self.w, self.h = size
        self.font = font_consolas(16)
        self.cols = [ {"x": x*16, "y": random.randrange(-self.h, 0), "spd": random.randint(80,160)}
                      for x in range(self.w // 16) ]
        self.chars = [str(i) for i in range(10)]
        self.color = (20, 230, 60)

    def update(self, dt):
        for c in self.cols:
            c["y"] += c["spd"] * dt
            if c["y"] > self.h + 40:
                c["y"] = random.randrange(-200, 0)
                c["spd"] = random.randint(80,160)

    def draw(self, screen: pygame.Surface):
        overlay = pygame.Surface((self.w,self.h), pygame.SRCALPHA)
        overlay.fill((0,0,0,180))  # leve escurecida
        screen.blit(overlay, (0,0), special_flags=pygame.BLEND_PREMULTIPLIED)
        for c in self.cols:
            ch = random.choice(self.chars)
            surf = self.font.render(ch, True, self.color)
            screen.blit(surf, (c["x"], c["y"]))

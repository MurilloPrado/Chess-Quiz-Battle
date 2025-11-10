class ChessAPI:
    def __init__(self):
        pass

    def try_move(self, src, dst):
        print(f"movendo de {src} para {dst}")
        return True

    def render_pieces(self):
        return [(4, 6, "♙", "white")]

    def turn(self):
        return "white"

import os
import pygame
import json
import random
import subprocess
import sys
import time
import math
from pathlib import Path
from app.gui.scene_manager import Scene, SceneResult
from app.gui.widgets.console import ConsoleWidget
from app.gui.widgets.matrix_rain import MatrixRain
from app.gui.assets import font_consolas
from app.gui.sprites import load_piece_surfaces
from realtime.models import BoardState, StateMsg, MoveMsg
from chess.core.rules import is_check, king_square
from chess.utils.coordinates import fr

# Se seu core expõe BOARD_W/BOARD_H via utils.constants, usamos nos cálculos.
try:
    from chess.utils.constants import BOARD_W, BOARD_H, PIECE_SYMBOL, WHITE, BLACK, PIECE_KING
except Exception:
    # Fallback seguro (não deve acontecer no seu projeto)
    BOARD_W, BOARD_H, WHITE = 8, 8, 0
    PIECE_SYMBOL = {}

NEON = (20, 230, 60)
BG_BORDER = 3

QUIZ_TOTAL_TIME = 20.0          # tempo total por jogador em um duelo
QUIZ_PENALTY_RATIO = 0.6        # 5s pensando → ~3s de penalidade (5 * 0.6)
QUIZ_MIN_PENALTY = 1.0          # nunca perde menos que 1s
QUIZ_MAX_PENALTY = 10.0         # só pra não exagerar se ficar muito tempo

def _compute_time_penalty(elapsed: float) -> float:
    """
    Converte o tempo que o jogador ficou pensando (elapsed)
    em penalidade que será descontada do banco dele.

    Exemplo: elapsed=5s → penalty ≈ 3s (5 * 0.6).
    """
    raw = elapsed * QUIZ_PENALTY_RATIO
    penalty = round(raw)
    penalty = max(QUIZ_MIN_PENALTY, penalty)
    penalty = min(QUIZ_MAX_PENALTY, penalty)
    return penalty

def _load_quiz_data():
    # sobe 3 níveis e entra na pasta 'quiz'
    base_dir = Path(__file__).resolve().parents[3] / "quiz"
    
    quiz_file = base_dir / "QUIZ.json"

    if not quiz_file.exists():
        print(f"ATENÇÃO: quiz.json não encontrado em: {quiz_file}")
        return []

    with open(quiz_file, "r", encoding="utf-8") as f:
        return json.load(f)

QUIZ_DATA = _load_quiz_data()


class GameScene(Scene):
    """
    Cena principal do jogo:
    - esquerda: tabuleiro 2D jogável
    - direita (topo): mock de janela com imagem 3D do tabuleiro
    - direita (baixo): mock de janela com o Console (vez, eventos, etc.)
    """

    def __init__(self, window_size: tuple[int, int], chess_api):
        self.win_w, self.win_h = window_size
        self.api = chess_api
        self.quiz3d_proc = None

        # imagens opcionais do lado direito
        self._board3d_img = None
        self._try_load_3d_asset()

    # -------------- Ciclo de vida --------------

    def enter(self, ctx):
        self.ctx = ctx
        self.screen: pygame.Surface = ctx["screen"]
        self.font = font_consolas(18)

        # fundo
        self.matrix = MatrixRain((self.win_w, self.win_h))

        # layout calculado dinamicamente
        self._compute_layout(self.win_w, self.win_h)

        # load de imagens
        try:
            assets_pieces_dir = os.path.abspath(
                os.path.join(
                    os.path.dirname(__file__),  # app/gui
                    '..',                       # app
                    '..',                       # backend
                    '..',
                    '..',
                    'assets',
                    'chess-pieces'
                )
            )
            print("DEBUG peças:", assets_pieces_dir)
            self.atlas = load_piece_surfaces(assets_pieces_dir, self.tile)
            print("DEBUG atlas len:", len(self.atlas))
        except Exception as e:
            print("ERRO carregando sprites:", e)
            self.atlas = {}

        gc = (ctx.get("realtime") or {}).get("game_ctx", {}) or {}
        players_ctx = ctx.get("players") or gc.get("players") or {}
        white_name = players_ctx.get("whiteName") or players_ctx.get("p1") or "Player 1"
        black_name = players_ctx.get("blackName") or players_ctx.get("p2") or "Player 2"
        self.players = {"whiteName": white_name, "blackName": black_name}

        rt = ctx.get("realtime")
        if rt:
            self.fastapi_app = rt["app"]
            self.conn_mgr = rt["conn_mgr"]
            self.game_ctx = rt["game_ctx"]
            self.ws_url = rt["ws_url"]
        else:
            # Fallback (se alguém abrir a cena direto sem lobby)
            self.fastapi_app = None
            self.conn_mgr = None
            self.ws_url = None
            self.game_ctx = {
                "phase": "chess", "board": None, "turn": self.api.turn(),
                "quiz": None, "on_move": self._on_move_async, "on_quiz_answer": self._on_quiz_answer_async
            }

        # CHANGED: agora que estamos na cena do jogo, garantimos fase e callbacks reais
        self.game_ctx["phase"] = "chess"
        self.game_ctx["on_move"] = self._on_move_async
        self.game_ctx["on_quiz_answer"] = self._on_quiz_answer_async
        self.game_ctx["turn"] = self.api.turn()
        self.game_ctx["check_quiz_timeout"] = self._check_quiz_timeout
        self._sync_board_state()
        self._update_turn_ctx(log_to_console=False)


        # console (logo abaixo do 3D)
        self.console = ConsoleWidget(self.right_console_inner)
        self.console.push("Partida iniciada...")
        self._update_turn_ctx(log_to_console=True) 

        # seleção de casa no tabuleiro
        self.sel = None

        # estado de fim de jogo
        self.game_over = False
        self.game_over_at = None
        self.winner_side = None
        self.winner_name = None

        # limpa flags no contexto compartilhado (realtime)
        self.game_ctx["gameOver"] = False
        self.game_ctx["winnerSide"] = None
        self.game_ctx["winnerName"] = None
        self.game_ctx["outcome"] = None


    def _pick_random_question(self):
        return random.choice(QUIZ_DATA)
    
    
    def _launch_ursina_viewer(self):
        """
        Abre o quiz3d_client.py apenas se ainda não tiver um processo rodando.
        O próprio viewer se encerra quando o quiz termina (phase != 'quiz').
        """
        # se já existe e ainda está rodando, não faz nada
        if self.quiz3d_proc and self.quiz3d_proc.poll() is None:
            return

        script_path = Path(__file__).resolve().parent / "quiz.py"
        if not script_path.exists():
            print("Viewer 3D não encontrado:", script_path)
            return

        try:
            self.quiz3d_proc = subprocess.Popen([sys.executable, str(script_path)])
            print("Viewer 3D iniciado (pid:", self.quiz3d_proc.pid, ")")
        except Exception as e:
            print("Falha ao iniciar viewer 3D:", e)


    def _check_quiz_timeout(self) -> bool:
        if self.game_ctx.get("phase") != "quiz":
            return False

        quiz = self.game_ctx.get("quiz") or {}
        side = quiz.get("currentSide")
        pool = quiz.get("timePool") or {}
        started = quiz.get("turnStartedAt")

        if side not in ("white", "black") or not started:
            return False

        bank = float(pool.get(side, 0.0))
        elapsed = max(0.0, time.time() - float(started))

        # Se o tempo real da vez já excedeu o banco restante => derrota por tempo
        if elapsed >= bank:
            loser = side
            winner = "white" if loser == "black" else "black"

            if hasattr(self.api, "resolve_battle"):
                self.api.resolve_battle(winner)

            self.console.push(
                f"As {'Brancas' if loser=='white' else 'Pretas'} estouraram o tempo!"
            )

            self.game_ctx["phase"] = "chess"
            self.game_ctx["quiz"] = None
            self._sync_board_state()
            self._update_turn_ctx(log_to_console=True)

            if self._check_king_absent_and_gameover():
                return True
            self._check_game_over()

            return True

        return False

    def _start_quiz(self):
        """
        Inicia o modo quiz depois de uma captura.
        Usa self.api.last_battle pra montar o 'duelo' que o front 3D vai renderizar.
        """
        battle = getattr(self.api, "last_battle", None)
        if not battle:
            # não deveria acontecer se was_capture == True, mas garantimos
            return

        # atacante SEMPRE começa respondendo
        current_side = battle["attacker_color"]  # "white" ou "black"
        q = self._pick_random_question()

        # CHANGED: Muda a fase pro front saber que agora é tela de quiz
        self.game_ctx["phase"] = "quiz"

        # Banco de tempo por jogador (new!)
        time_pool = {
            "white": QUIZ_TOTAL_TIME,
            "black": QUIZ_TOTAL_TIME,
        }

        now = time.time()

        # Estrutura que o front (web / 3D) vai usar para montar a tela
        self.game_ctx["quiz"] = {
            "battleId": random.randint(1, 10_000_000),   # só pra diferenciar batalhas
            "attacker": {
                "color": battle["attacker_color"],       # "white"/"black"
                "piece": battle["attacker_type"],        # "pawn"/"bishop"/...
                # nomes de modelos 3D (você casa isso no front):
                "model": f"{battle['attacker_type'].capitalize()} hologram",
            },
            "defender": {
                "color": battle["defender_color"],
                "piece": battle["defender_type"],
                "model": f"{battle['defender_type'].capitalize()} hologram",
            },
            # lado da vez no quiz
            "currentSide": current_side,                 # "white" ou "black"
            # pergunta atual
            "question": q["pergunta"],
            "choices": q["alternativas"],
            "correctIndex": q["correta"],
            "timePool": time_pool,      # banco de tempo dos dois jogadores
            "turnStartedAt": now,       # quando essa vez começou (para medir elapsed deste turno)

            # campos auxiliares pro front (opcional, se quiser mostrar algo direto)
            "maxTime": time_pool[current_side],   # tempo atual disponível pra quem está jogando
            "remainingTime": time_pool[current_side],  # front pode usar como seed para countdown local
        }

        # log no console
        atacante_nome = "Brancas" if current_side == "white" else "Pretas"
        self.console.push(f"Quiz iniciado! {atacante_nome} atacaram, vez delas responderem.")

        self._launch_ursina_viewer()

    def _next_quiz_round(self, next_side: str):
        quiz = self.game_ctx.get("quiz")
        if not quiz:
            return

        q = self._pick_random_question()
        self.game_ctx["phase"] = "quiz"

        # ⬇️ GRAVA TUDO NA RAIZ DO OBJETO quiz (sem quiz["quiz"])
        quiz["currentSide"]  = next_side
        quiz["question"]     = q["pergunta"]
        quiz["choices"]      = q["alternativas"]
        quiz["correctIndex"] = q["correta"]

        now = time.time()
        quiz["turnStartedAt"] = now

        pool = quiz.get("timePool") or {}
        current_bank = float(pool.get(next_side, QUIZ_TOTAL_TIME))
        quiz["maxTime"]       = current_bank
        quiz["remainingTime"] = current_bank

        nome = "Brancas" if next_side == "white" else "Pretas"
        self.console.push(f"Quiz continua! Agora é a vez das {nome}.")
        
        core = getattr(self.api, "board", None) or self.api
        wk = self._king_square_from_any(core, WHITE)
        bk = self._king_square_from_any(core, BLACK)
        print("DEBUG kings wk,bk:", wk, bk)


    def _sync_board_state(self):
        board_list = self.api.export_board_linear()
        self.game_ctx["board"] = BoardState(
            cells=board_list, width=BOARD_W, height=BOARD_H
        )

    # Arquivo: game.py - método _update_check_status(self)

    def _update_check_status(self):
        # 1. ACESSO AO TABULEIRO E DEFINIÇÃO DE VARIÁVEIS BÁSICAS
        try:
            # Acessa a lista de peças (o 'list' object) a partir do ChessAPI (self.api) -> Board5x6 (b)
            board_list = self.api.b.board
        except AttributeError:
            # Se 'self.api' ou 'self.api.b' não existirem (inicialização falhou)
            print("Erro: Instância do tabuleiro ChessAPI não acessível.")
            return

        current_turn = self.game_ctx["turn"]
        color_int = WHITE if current_turn == "white" else BLACK
        side_str = current_turn

        # 2. VERIFICAÇÃO DE XEQUE
        # Chama a função is_check (agora corretamente importada e passando a lista)
        in_check = is_check(board_list, color_int)

        # 3. RESET DE ESTADO (Limpa o estado de xeque a cada chamada)
        self.game_ctx["inCheckSide"] = None
        self.game_ctx["inCheckKing"] = None

        # 4. ATUALIZAÇÃO DO ESTADO APENAS SE HOUVER XEQUE
        if in_check:
            try:
                # Encontra a casa do rei (king_square retorna o índice: 0 a N-1)
                king_sq_idx = king_square(board_list, color_int)

                if king_sq_idx is not None:
                    # Converte o índice (0..29) para coordenadas (col, row) que o frontend espera: (x, y)
                    king_col, king_row = fr(king_sq_idx)
                    
                    # Preenche o contexto para que o frontend (chess.js) possa desenhar a cor vermelha
                    self.game_ctx["inCheckSide"] = side_str
                    # O frontend (chess.js) espera um dicionário {"x": x, "y": y}
                    self.game_ctx["inCheckKing"] = {"x": king_col, "y": king_row}

            except Exception as e:
                # Captura qualquer erro ao encontrar/converter a casa do rei
                print("Erro ao processar a casa do rei em xeque:", e)
                # Garante que o estado não será inconsistente
                self.game_ctx["inCheckSide"] = None
                self.game_ctx["inCheckKing"] = None
                

    def _king_square_from_any(self, core_or_board, color: int):
        """
        Retorna o índice linear da casa do rei (0..n-1) para a cor dada,
        independente se 'core_or_board' é um objeto com .king_square()
        ou uma lista linear de casas.
        """
        try:
            # Caso 1: objeto com método king_square
            if hasattr(core_or_board, "king_square"):
                return core_or_board.king_square(color)

            # Caso 2: lista linear ou objeto com atributo .board (lista)
            board_list = core_or_board
            if not isinstance(board_list, list):
                board_list = getattr(core_or_board, "board", None)

            if not isinstance(board_list, list):
                return None

            # Espera células como tuplas/listas (color, piece, ...)
            for idx, cell in enumerate(board_list):
                if not cell:
                    continue
                if isinstance(cell, (tuple, list)) and len(cell) >= 2:
                    c, piece = cell[0], cell[1]
                    if c == color and piece == PIECE_KING:
                        return idx
            return None
        except Exception as e:
            print("DEBUG _king_square_from_any error:", e)
            return None

    def _check_king_absent_and_gameover(self) -> bool:
        """
        Se um dos reis não existe no tabuleiro, dispara Game Over imediatamente.
        Retorna True se finalizou o jogo, False caso contrário.
        """
        try:
            core = getattr(self.api, "board", None) or self.api

            wk = self._king_square_from_any(core, WHITE)
            bk = self._king_square_from_any(core, BLACK)

            # evita falso positivo durante boot (ambos None)
            if wk is None and bk is None:
                return False

            if wk is None and bk is not None:
                winner_side = "black"
                winner_name = self.players.get("blackName", "Pretas")
            elif bk is None and wk is not None:
                winner_side = "white"
                winner_name = self.players.get("whiteName", "Brancas")
            else:
                return False  # ambos vivos

            self._start_game_over(winner_side, winner_name)
            return True

        except Exception as e:
            print("Erro em _check_king_absent_and_gameover:", e)
            return False
        
    def _start_game_over(self, winner_side: str | None, winner_name: str | None):
        self.game_over = True
        self.game_over_at = time.time()
        self.winner_side = winner_side
        self.winner_name = winner_name or "Empate"

        # expõe pro realtime/web
        self.game_ctx["gameOver"] = True
        self.game_ctx["winnerSide"] = winner_side
        self.game_ctx["winnerName"] = self.winner_name

        try:
            if getattr(self, "conn_mgr", None) and getattr(self, "fastapi_app", None):
                from realtime.router import _build_state_payload  # evita import circular no topo
                payload = _build_state_payload(self.conn_mgr, self.game_ctx)
                import asyncio
                asyncio.run(self.conn_mgr.broadcast(payload))
        except Exception as e:
            print("WARN broadcast gameOver:", e)

    def _check_game_over(self):
        try:
            core = getattr(self.api, "board", None) or self.api
            if not hasattr(core, "outcome"):
                return

            res = core.outcome()
            if not res:
                return

            # guarda outcome bruto (se quiser usar no front)
            self.game_ctx["outcome"] = res

            winner_side = None
            if res.startswith("checkmate_white_wins"):
                winner_side = "white"
            elif res.startswith("checkmate_black_wins"):
                winner_side = "black"

            if winner_side:
                name_key = "whiteName" if winner_side == "white" else "blackName"
                winner_name = self.players.get(name_key, "Jogador vencedor")
                self._start_game_over(winner_side, winner_name)
            else:
                # empate / stalemate
                self._start_game_over(None, "Empate")

        except Exception as e:
            print("Erro em _check_game_over:", e)

    
    async def _on_move_async(self, src_xy, dst_xy):
        ok = self.api.try_move(src_xy, dst_xy)
        if not ok:
            self.console.push("Movimento rejeitado")
            return False, False

        # descobre se o último movimento foi captura
        was_capture = getattr(self.api, "was_capture", False)

        
        # atualiza estado local
        self._sync_board_state()
        self._update_check_status()
        self._update_turn_ctx(log_to_console=True)
            
        # quiz
        if was_capture:
            self._start_quiz()
        else:
            self._check_game_over()

        return ok, getattr(self.api, "was_capture", False)


    async def _on_quiz_answer_async(self, client_id: str, answer: str):
        """
        answer vem da web como string.
        Sugestão: mandar sempre o índice da alternativa ("0", "1", "2"...).
        """
        if self.game_ctx.get("phase") != "quiz":
            return False  # nada a fazer

        quiz = self.game_ctx.get("quiz") or {}
        if not quiz:
            return False

        current_side = quiz.get("currentSide")  # "white" ou "black"
        if current_side not in ("white", "black"):
            return False

        # Garante estrutura do timePool
        time_pool = quiz.get("timePool")
        if not isinstance(time_pool, dict):
            time_pool = {
                "white": QUIZ_TOTAL_TIME,
                "black": QUIZ_TOTAL_TIME,
            }
            quiz["timePool"] = time_pool

        # Tempo que o jogador ainda tinha antes dessa pergunta
        bank_before = float(time_pool.get(current_side, QUIZ_TOTAL_TIME))

        # Calcula quanto tempo ele demorou nessa vez
        now = time.time()
        turn_started_at = quiz.get("turnStartedAt") or now
        elapsed = max(0.0, now - turn_started_at)

        # 1) Checa se já deu timeout "hard" (demorou mais que o banco)
        if elapsed >= bank_before:
            loser_side = current_side
            winner_side = "white" if loser_side == "black" else "black"

            if hasattr(self.api, "resolve_battle"):
                self.api.resolve_battle(winner_side)

            self.console.push(
                f"As {'Brancas' if loser_side=='white' else 'Pretas'} estouraram o tempo!"
            )

            self.game_ctx["phase"] = "chess"
            self.game_ctx["quiz"] = None
            self._sync_board_state()
            self._update_turn_ctx(log_to_console=True)

            if self._check_king_absent_and_gameover():
                return True
            self._check_game_over()

            return True  # duelo acabou

        # 2) Calcula penalidade em cima do tempo que ele ficou pensando
        penalty = _compute_time_penalty(elapsed)
        new_bank = max(0.0, bank_before - penalty)
        time_pool[current_side] = new_bank

        # Se o banco zerou com a penalidade, ele perde o duelo
        if new_bank <= 0.0:
            loser_side = current_side
            winner_side = "white" if loser_side == "black" else "black"

            if hasattr(self.api, "resolve_battle"):
                self.api.resolve_battle(winner_side)

            self.console.push(
                f"As {'Brancas' if loser_side=='white' else 'Pretas'} ficaram sem tempo!"
            )

            self.game_ctx["phase"] = "chess"
            self.game_ctx["quiz"] = None
            self._sync_board_state()
            self._update_turn_ctx(log_to_console=True)

            if self._check_king_absent_and_gameover():
                return True
            self._check_game_over()

            return True  # duelo acabou

        # A partir daqui o jogador ainda tem tempo suficiente -> checa se errou/acertou

        # Tenta converter a resposta para índice
        try:
            answer_idx = int(answer)
        except Exception:
            # resposta inválida: considera como erro direto (poderia ser só ignorar)
            answer_idx = -1

        correct_idx = quiz.get("correctIndex", -1)

        if answer_idx == correct_idx:
            # ACERTOU -> continua o bate-bola, alternando a vez
            next_side = "white" if current_side == "black" else "black"

            # prepara próxima rodada SEM resetar timePool
            self._next_quiz_round(next_side)
            return False  # quiz continua

        # ERROU -> fim da batalha, exatamente como antes
        loser_side = current_side
        winner_side = "white" if loser_side == "black" else "black"

        if hasattr(self.api, "resolve_battle"):
            self.api.resolve_battle(winner_side)

        self.game_ctx["phase"] = "chess"
        self.game_ctx["quiz"] = None
        self._sync_board_state()
        self._update_turn_ctx(log_to_console=True)

        if self._check_king_absent_and_gameover():
            return True
        self._check_game_over()

        return True  # duelo acabou


    def on_realtime_message(self, msg):
        if isinstance(msg, StateMsg):
            if hasattr(self.api, "import_board_linear"):
                self.api.import_board_linear(msg.board.cells)
            self._update_check_status()
            if msg.turn:
                self.game_ctx["turn"] = msg.turn
            self.console.push("Estado do tabuleiro sincronizado.")

            if getattr(msg, "players", None):
                self.players = {
                    "whiteName": msg.players.get("whiteName", self.players["whiteName"]),
                    "blackName": msg.players.get("blackName", self.players["blackName"]),
                }
        elif isinstance(msg, MoveMsg):
            self.console.push(f"Movimento recebido: {msg.src} -> {msg.dst}")

    def leave(self):
        pass

    # -------------- Layout responsivo --------------

    def _compute_layout(self, w: int, h: int):
        """Calcula todas as áreas com base no tamanho da janela."""
        padding = 24
        gutter = 28  # espaço entre colunas
        top = padding
        left_col_w = int(w * 0.52)  # esquerda ~52%, direita ~48%
        right_col_w = w - left_col_w - padding * 2 - gutter

        # Tamanho do tile máximo respeitando altura e largura disponível
        max_board_side = min(
            left_col_w - padding * 2,
            h - padding * 2,
        )
        tile = max(28, max_board_side // max(BOARD_W, BOARD_H))
        board_w = tile * BOARD_W
        board_h = tile * BOARD_H

        # Centraliza o tabuleiro dentro da coluna esquerda
        board_x = padding + (left_col_w - board_w) // 2
        board_y = top + (h - top - padding - board_h) // 2

        self.tile = tile
        self.board_rect = pygame.Rect(board_x, board_y, board_w, board_h)

        # Coluna direita: duas "janelas" empilhadas
        right_x = padding + left_col_w + gutter
        right_w = right_col_w
        right_total_h = h - padding * 2

        # proporções: 3D ocupa ~55%, console ~45%, com pequeno gutter
        right_gutter = 18
        right_3d_h = int(right_total_h * 0.55)
        right_console_h = right_total_h - right_3d_h - right_gutter

        self.right_3d_rect = pygame.Rect(right_x, top, right_w, right_3d_h)
        self.right_console_rect = pygame.Rect(
            right_x, top + right_3d_h + right_gutter, right_w, right_console_h
        )

        # Áreas internas (conteúdo dentro da "janela" com barra de título)
        self.right_3d_inner = self._window_content_rect(self.right_3d_rect)
        self.right_console_inner = self._window_content_rect(self.right_console_rect)

    def _window_content_rect(self, outer: pygame.Rect) -> pygame.Rect:
        title_h = 28
        border = 2
        return pygame.Rect(
            outer.x + border,
            outer.y + border + title_h,
            outer.w - border * 2,
            outer.h - title_h - border * 2,
        )

    # -------------- Assets --------------

    def _try_load_3d_asset(self):
        """
        Carrega a primeira imagem encontrada em assets/3d (png/jpg), se houver.
        Se não existir, desenhamos um wireframe placeholder no render.
        """
        candidates = []
        base_candidates = [
            os.path.join("assets", "3d"),
            os.path.join("app", "assets", "3d"),
        ]
        exts = (".png", ".jpg", ".jpeg", ".webp")
        for base in base_candidates:
            if os.path.isdir(base):
                for f in os.listdir(base):
                    if f.lower().endswith(exts):
                        candidates.append(os.path.join(base, f))
        if candidates:
            try:
                img = pygame.image.load(candidates[0]).convert_alpha()
                self._board3d_img = img
            except Exception:
                self._board3d_img = None

    # -------------- Eventos --------------

    def handle_event(self, ev):
        if getattr(self, "game_over", False):
            if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                return SceneResult(next_scene="menu")
            return None

        if ev.type == pygame.VIDEORESIZE:
            self.win_w, self.win_h = ev.w, ev.h
            self._compute_layout(ev.w, ev.h)

        if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
            return SceneResult(next_scene="menu")

        # bloqueia movimento do host
        role = (self.game_ctx or {}).get("role", "players")
        if role == "host":
            if self.sel is not None:
                self.sel = None
            return None
        
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:  
            mx, my = ev.pos
            if self.board_rect.collidepoint(mx, my):
                cx = (mx - self.board_rect.x) // self.tile
                cy = (my - self.board_rect.y) // self.tile
                if 0 <= cx < BOARD_W and 0 <= cy < BOARD_H:
                    if self.sel is None:
                        self.sel = (cx, cy)
                    else:
                        ok = self._try_move_adapter(self.sel, (cx, cy))
                        if ok:
                            self.console.push(f"Movido de {self.sel} para {(cx,cy)}")
                        self.sel = None
        return None

    def _try_move_adapter(self, src_xy, dst_xy) -> bool:
        """
        Adapta a tentativa de movimento para o que seu adapter expõe.
        Preferência:
          1) api.try_move((x,y),(x,y))
          2) api.push_sanlike('a2a3') / api.push_uci('a2a3')
        """
        # 1) Método direto (tuplas)
        if hasattr(self.api, "try_move"):
            try:
                return bool(self.api.try_move(src_xy, dst_xy))
            except Exception:
                pass

        # 2) UCI-like (ex: a2a3). Precisamos converter (x,y) -> algébrica.
        try:
            from chess.utils.coordinates import to_algebraic
        except Exception:
            to_algebraic = None

        if to_algebraic and hasattr(self.api, "push_sanlike"):
            try:
                uci = to_algebraic(src_xy) + to_algebraic(dst_xy)
                return bool(self.api.push_sanlike(uci))
            except Exception:
                return False
        return False

    # -------------- Atualização / Render --------------

    def update(self, dt):
        self.matrix.update(dt)

        # se acabou o jogo, conta 10s e volta pro menu
        if getattr(self, "game_over", False) and self.game_over_at is not None:
            if time.time() - self.game_over_at >= 10.0:
                return SceneResult(next_scene="menu")


    def _update_turn_ctx(self, log_to_console: bool = False):
        """
        Lê o turno da API e normaliza para 'white' / 'black'
        dentro de game_ctx['turn'], além de escrever no console.
        """
        raw = self.api.turn()  # pode ser "white"/"black" ou WHITE/BLACK

        if raw in ("white", "w", WHITE):
            self.game_ctx["turn"] = "white"
            msg = "Vez das brancas"
        elif raw in ("black", "b", BLACK):
            self.game_ctx["turn"] = "black"
            msg = "Vez das pretas"
        else:
            # Só cai aqui se vier algo completamente inesperado
            self.game_ctx["turn"] = None
            msg = f"Vez indefinida (valor recebido: {raw!r})"

        if log_to_console and hasattr(self, "console"):
            self.console.push(msg)


    def render(self, screen: pygame.Surface):
        # fundo
        self.matrix.draw(screen)

        # moldura geral
        pygame.draw.rect(screen, NEON, screen.get_rect(), BG_BORDER)

        # esquerda: tabuleiro 2D
        self._draw_board(screen)
        self._draw_player_names(screen)

        # direita: mock janelas
        self._draw_mock_window(screen, self.right_3d_rect, "Tabuleiro 3D (visual)")
        self._draw_3d_preview(screen, self.right_3d_inner)

        self._draw_mock_window(screen, self.right_console_rect, "Status da Partida")
        self.console.draw(screen)

        if getattr(self, "game_over", False):
            self._draw_game_over_overlay(screen)

    # ---------- Desenho: esquerda (tabuleiro funcional) ----------

    def _draw_board(self, screen: pygame.Surface):
        # moldura do tabuleiro
        pygame.draw.rect(screen, NEON, self.board_rect, 2)
        self._name_font = font_consolas(28)

        light = (210, 240, 210)
        dark = (60, 140, 60)

        # casas (espelha o Y na tela: linha 0 do core fica em cima ou embaixo conforme BOARD_H)
        for y in range(BOARD_H):
            for x in range(BOARD_W):
                # linha desenhada (0 = topo da tela, BOARD_H-1 = base)
                draw_row = (BOARD_H - 1) - y
                r = pygame.Rect(
                    self.board_rect.x + x * self.tile,
                    self.board_rect.y + draw_row * self.tile,
                    self.tile,
                    self.tile,
                )
                pygame.draw.rect(screen, light if (x + y) % 2 == 0 else dark, r)

        # peças (usa o mesmo espelhamento)
        for (x, y, piece) in self._iter_pieces():
            surf = self.atlas.get(piece)
            draw_row = (BOARD_H - 1) - y

            if surf:
                draw_x = self.board_rect.x + x * self.tile
                draw_y = self.board_rect.y + draw_row * self.tile
                screen.blit(surf, (draw_x, draw_y))
            else:
                # fallback: desenha o glyph caso sprite não exista
                glyph = PIECE_SYMBOL.get(piece, "?")
                tx = self.board_rect.x + x * self.tile + self.tile // 2
                ty = self.board_rect.y + draw_row * self.tile + self.tile // 2
                font = font_consolas(36)
                img = font.render(glyph, True, (10, 10, 10))
                rect = img.get_rect(center=(tx, ty))
                screen.blit(img, rect)


    def _draw_player_names(self, screen):
        cx = self.board_rect.centerx
        pad = 8

        # Pretas (topo)
        top_y = self.board_rect.top - (self._name_font.get_height() + pad)
        txt_top = self._name_font.render(self.players["blackName"], True, (230, 234, 244))
        screen.blit(txt_top, txt_top.get_rect(midtop=(cx, top_y)))
        # Brancas (base)
        bot_y = self.board_rect.bottom + pad
        txt_bot = self._name_font.render(self.players["whiteName"], True, (230, 234, 244))
        screen.blit(txt_bot, txt_bot.get_rect(midtop=(cx, bot_y)))                                

    def _iter_pieces(self):
        """
        Retorna diretamente as peças do tabuleiro como:
        (x, y, piece_tuple)

        Onde piece_tuple é exatamente o que o core usa:
        (WHITE, PIECE_PAWN), (BLACK, PIECE_KING), etc.
        """
        # Fallback: tentar self.api.get_board() ou self.api.board
        board = None
        if hasattr(self.api, "get_board"):
            try:
                board = self.api.get_board()
            except Exception:
                board = None
        if board is None and hasattr(self.api, "board"):
            board = getattr(self.api, "board")

        if board is None:
            return

        # board esperado como lista linear; idx -> (x,y)
        from chess.utils.coordinates import fr  # idx -> (x,y)

        if isinstance(board, list) and len(board) == BOARD_W * BOARD_H:
            for idx, piece in enumerate(board):
                if piece is None:
                    continue
                x, y = fr(idx)
                # agora retornamos a peça inteira em vez de glyph
                yield (x, y, piece)


    def _draw_game_over_overlay(self, screen: pygame.Surface):
        w, h = screen.get_size()

        # fundo escurecido
        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 190))
        screen.blit(overlay, (0, 0))

        title_font = font_consolas(36)
        name_font = font_consolas(32)
        small_font = font_consolas(18)

        if self.winner_side is None:
            title_text = "Fim de jogo"
            name_text = self.winner_name or "Empate"
        else:
            title_text = "Xeque-mate!"
            name_text = self.winner_name or "Jogador vencedor"

        title_surf = title_font.render(title_text, True, NEON)
        title_rect = title_surf.get_rect(center=(w // 2, h // 2 - 60))
        screen.blit(title_surf, title_rect)

        name_surf = name_font.render(name_text, True, (240, 250, 255))
        name_rect = name_surf.get_rect(center=(w // 2, h // 2))
        screen.blit(name_surf, name_rect)

        if self.winner_side is not None:  # Apenas exibe se houver um vencedor claro
            winner_info_text = "é o vencedor!!"
            winner_info_surf = small_font.render(winner_info_text, True, (220, 230, 240))
            # Centraliza o texto e posiciona 20 pixels abaixo do nome
            winner_info_rect = winner_info_surf.get_rect(center=(w // 2, h // 2 + 20))
            screen.blit(winner_info_surf, winner_info_rect)

        # contador regressivo
        if self.game_over_at:
            remaining = max(0, int(10 - (time.time() - self.game_over_at)))
            info_text = f"Voltando ao menu em {remaining}s..."
            info_surf = small_font.render(info_text, True, (220, 230, 240))
            info_rect = info_surf.get_rect(center=(w // 2, h // 2 + 40))
            screen.blit(info_surf, info_rect)

        # fogos simples ao lado do nome
        self._draw_fireworks(screen, name_rect)

    def _draw_fireworks(self, screen: pygame.Surface, name_rect: pygame.Rect):
        """
        Desenha fogos bem simples à esquerda e à direita do nome do vencedor.
        """
        cx_left = name_rect.left - 40
        cx_right = name_rect.right + 40
        cy = name_rect.centery

        t = time.time()

        for base_x in (cx_left, cx_right):
            for i in range(8):
                ang = (t * 2.0) + (i * (math.pi / 4.0))
                r = 24 + 6 * math.sin(t * 3 + i)

                x2 = base_x + math.cos(ang) * r
                y2 = cy + math.sin(ang) * r

                pygame.draw.line(screen, NEON, (base_x, cy), (x2, y2), 1)
                pygame.draw.circle(screen, NEON, (int(x2), int(y2)), 2)


    # ---------- Desenho: direita (mock janelas + 3D) ----------

    def _draw_mock_window(self, screen: pygame.Surface, rect: pygame.Rect, title: str):
        # borda externa
        pygame.draw.rect(screen, NEON, rect, 2)

        # barra de título
        title_h = 28
        title_rect = pygame.Rect(rect.x + 2, rect.y + 2, rect.w - 4, title_h)
        pygame.draw.rect(screen, NEON, title_rect, 0)

        # Título
        label = self.font.render(title, True, (0, 0, 0))
        screen.blit(label, (title_rect.x + 10, title_rect.y + 6))

        # botões fake (min, max, close)
        bx = title_rect.right - 18
        by = title_rect.y + 6
        for i in range(3):
            pygame.draw.rect(screen, (0, 0, 0), (bx - i * 18, by, 12, 12), 1)

    def _draw_3d_preview(self, screen: pygame.Surface, rect: pygame.Rect):
        if self._board3d_img:
            img = self._scale_to_fit(self._board3d_img, rect.size)
            screen.blit(img, img.get_rect(center=rect.center))
        else:
            # placeholder: wireframe de tabuleiro isométrico
            self._draw_wireframe_board(screen, rect)

    def _scale_to_fit(self, surf: pygame.Surface, size: tuple[int, int]) -> pygame.Surface:
        sw, sh = surf.get_size()
        tw, th = size
        scale = min(tw / sw, th / sh)
        nw, nh = max(1, int(sw * scale)), max(1, int(sh * scale))
        return pygame.transform.smoothscale(surf, (nw, nh))

    def _draw_wireframe_board(self, screen: pygame.Surface, rect: pygame.Rect):
        cx, cy = rect.center
        w = int(rect.w * 0.7)
        h = int(rect.h * 0.5)
        # pontos de um losango
        pts = [
            (cx, cy - h // 2),
            (cx + w // 2, cy),
            (cx, cy + h // 2),
            (cx - w // 2, cy),
        ]
        pygame.draw.polygon(screen, NEON, pts, 2)

        # divisões (grade simples)
        divs = min(BOARD_W, 8)
        for i in range(1, divs):
            t = i / divs
            # linhas horizontais (aprox. em perspectiva)
            p1 = self._lerp(pts[0], pts[3], t)
            p2 = self._lerp(pts[1], pts[2], t)
            pygame.draw.line(screen, NEON, p1, p2, 1)
            # linhas verticais
            p3 = self._lerp(pts[0], pts[1], t)
            p4 = self._lerp(pts[3], pts[2], t)
            pygame.draw.line(screen, NEON, p3, p4, 1)

    @staticmethod
    def _lerp(a, b, t):
        return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)

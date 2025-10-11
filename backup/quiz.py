import tkinter as tk
import json
import random
from pathlib import Path
from .constants import WHITE

QUIZ_FILE = Path(__file__).parent / "QUIZ.json"
with open(QUIZ_FILE, "r", encoding="utf-8") as f:
    PERGUNTAS = json.load(f)


def abrir_quiz(root=None, tempo=15, jogador_inicial=1) -> bool:
    """
    Abre o quiz para dois jogadores com layout melhorado e feedback visual.
    jogador_inicial: 1 para começar com o Jogador Branco, 2 para começar com o Jogador Preto.
    """
    created_root = False
    if root is None:
        root = tk.Tk()
        root.withdraw()  # esconde a janela principal
        created_root = True

    result = {"value": None}
    perguntas = PERGUNTAS.copy()
    random.shuffle(perguntas)
    # divide perguntas para os dois jogadores (metade/metade)
    perguntas_j1 = perguntas[:len(perguntas)//2]
    perguntas_j2 = perguntas[len(perguntas)//2:]
    idx1, idx2 = 0, 0

    win = tk.Toplevel(root)
    win.title("Quiz")
    win.geometry("600x480")
    win.configure(bg="#f9f9f9")
    win.grab_set()
    win.transient(root)

    # Pergunta
    label_question = tk.Label(
        win,
        text="",
        wraplength=560,
        font=("Arial", 14, "bold"),
        justify="center",
        bg="#f9f9f9"
    )
    label_question.pack(pady=20)

    # Timer
    timer_label = tk.Label(
        win,
        text="",
        font=("Arial", 13, "bold"),
        fg="red",
        bg="#f9f9f9"
    )
    timer_label.pack(pady=5)

    # Frame dos botões
    botoes_frame = tk.Frame(win, bg="#f9f9f9")
    botoes_frame.pack(pady=15, fill="x")

    # cria 6 botões "reservados"
    botoes = []
    for i in range(6):
        b = tk.Button(
            botoes_frame,
            text="",
            width=60,
            height=2,
            wraplength=500,
            justify="left",
            anchor="w",
            font=("Arial", 11),
            bg="#ffffff",
            relief="raised"
        )
        botoes.append(b)  # não faz pack aqui!

    countdown_id = None
    tempo_restante = 0
    alternativas_atuais = []

    def atualizar_timer(jogador, correta):
        nonlocal tempo_restante, countdown_id
        if tempo_restante > 0:
            timer_label.config(text=f"⏱ Tempo: {tempo_restante}s")
            tempo_restante -= 1
            countdown_id = win.after(1000, atualizar_timer, jogador, correta)
        else:
            result["value"] = False
            win.destroy()

    def perguntar(jogador):
        nonlocal idx1, idx2, tempo_restante, countdown_id, alternativas_atuais
        # termina quando qualquer lista de perguntas acabar
        if idx1 >= len(perguntas_j1) or idx2 >= len(perguntas_j2):
            result["value"] = True
            win.destroy()
            return

        pergunta = perguntas_j1[idx1] if jogador == 1 else perguntas_j2[idx2]

        alternativas_atuais = list(enumerate(pergunta["alternativas"]))
        random.shuffle(alternativas_atuais)

        label_question.config(
            text=f"🎮 Jogador {'Branco' if jogador==1 else 'Preto'}:\n\n{pergunta['pergunta']}"
        )

        # esconde todos os botões antes
        for b in botoes:
            b.pack_forget()

        # só mostra a quantidade necessária
        for idx, (i_alt, texto) in enumerate(alternativas_atuais):
            botoes[idx].config(
                text=texto,
                bg="#ffffff",
                state="normal",
                command=lambda i=i_alt, correta=pergunta["correta"], j=jogador, btn=botoes[idx]: responder(i, correta, j, btn)
            )
            botoes[idx].pack(fill="x", pady=5, padx=20)

        if countdown_id:
            win.after_cancel(countdown_id)
        tempo_restante = tempo
        atualizar_timer(jogador, pergunta["correta"])

    def responder(indice_escolhido, indice_correto, jogador, botao):
        nonlocal idx1, idx2, countdown_id
        if countdown_id:
            win.after_cancel(countdown_id)

        # Desabilita todos os botões visíveis
        for b in botoes:
            b.config(state="disabled")

        # Marca resposta
        if indice_escolhido == indice_correto:
            botao.config(bg="#90EE90")  # verde
            win.after(1000, lambda: proxima_pergunta(jogador))
        else:
            botao.config(bg="#FF7F7F")  # vermelho
            result["value"] = False
            win.after(1000, win.destroy)

    def proxima_pergunta(jogador):
        nonlocal idx1, idx2
        if jogador == 1:
            idx1 += 1
            perguntar(2)
        else:
            idx2 += 1
            perguntar(1)

    # começa pelo jogador que foi passado no parâmetro
    perguntar(jogador_inicial)
    win.wait_window()

    if created_root:
        root.destroy()

    return result["value"] is True


def run_quiz_for_capture(root, atacante_cor: int, defensor_cor: int) -> str:
    """
    Retorna 'attacker' se o atacante errou, 'defender' se o defensor errou.
    """
    # exemplo: pergunta só para o defensor
    acertou_defensor = abrir_quiz(root, jogador_inicial=(1 if defensor_cor == 0 else 2))
    if acertou_defensor:
        return "attacker"
    else:
        return "defender"
    
def abrir_quiz_quem_errou(root=None, tempo=15, jogador_inicial=1):
    """
    Abre o mesmo quiz, mas retorna:
      - 1 se o Jogador 1 (Brancas) errou
      - 2 se o Jogador 2 (Negras) errou
      - None se ninguém errou (todos acertaram)
    """
    import tkinter as tk
    import random

    created_root = False
    if root is None:
        root = tk.Tk()
        root.withdraw()
        created_root = True

    perguntas = PERGUNTAS.copy()
    random.shuffle(perguntas)
    perguntas_j1 = perguntas[:len(perguntas)//2]
    perguntas_j2 = perguntas[len(perguntas)//2:]
    idx1, idx2 = 0, 0

    win = tk.Toplevel(root)
    win.title("Quiz")
    win.geometry("600x480")
    win.configure(bg="#f9f9f9")
    win.grab_set()
    win.transient(root)

    label_question = tk.Label(
        win, text="", wraplength=560, font=("Arial", 14, "bold"),
        justify="center", bg="#f9f9f9"
    )
    label_question.pack(pady=20)

    timer_label = tk.Label(
        win, text="", font=("Arial", 13, "bold"), fg="red", bg="#f9f9f9"
    )
    timer_label.pack(pady=5)

    botoes_frame = tk.Frame(win, bg="#f9f9f9")
    botoes_frame.pack(pady=15, fill="x")

    botoes = []
    for _ in range(6):
        b = tk.Button(
            botoes_frame, text="", width=60, height=2, wraplength=500,
            justify="left", anchor="w", font=("Arial", 11),
            bg="#ffffff", relief="raised"
        )
        botoes.append(b)

    countdown_id = None
    tempo_restante = 0
    alternativas_atuais = []
    result = {"loser": None}

    def atualizar_timer(jogador, correta):
        nonlocal tempo_restante, countdown_id
        if tempo_restante > 0:
            timer_label.config(text=f"⏱ Tempo: {tempo_restante}s")
            tempo_restante -= 1
            countdown_id = win.after(1000, atualizar_timer, jogador, correta)
        else:
            # tempo acabou => jogador atual errou
            result["loser"] = jogador
            win.destroy()

    def perguntar(jogador):
        nonlocal idx1, idx2, tempo_restante, countdown_id, alternativas_atuais
        # encerra quando alguma lista acabar
        if idx1 >= len(perguntas_j1) or idx2 >= len(perguntas_j2):
            result["loser"] = None
            win.destroy()
            return

        pergunta = perguntas_j1[idx1] if jogador == 1 else perguntas_j2[idx2]
        alternativas_atuais = list(enumerate(pergunta["alternativas"]))
        random.shuffle(alternativas_atuais)

        label_question.config(
            text=f"🎮 Jogador {'Branco' if jogador==1 else 'Preto'}:\n\n{pergunta['pergunta']}"
        )

        for b in botoes:
            b.pack_forget()

        for idx, (i_alt, texto) in enumerate(alternativas_atuais):
            botoes[idx].config(
                text=texto, bg="#ffffff", state="normal",
                command=lambda i=i_alt, correta=pergunta["correta"], j=jogador, btn=botoes[idx]: responder(i, correta, j, btn)
            )
            botoes[idx].pack(fill="x", pady=5, padx=20)

        if countdown_id:
            win.after_cancel(countdown_id)
        tempo_restante = tempo
        atualizar_timer(jogador, pergunta["correta"])

    def responder(indice_escolhido, indice_correto, jogador, botao):
        nonlocal idx1, idx2, countdown_id
        if countdown_id:
            win.after_cancel(countdown_id)

        for b in botoes:
            b.config(state="disabled")

        if indice_escolhido == indice_correto:
            botao.config(bg="#90EE90")  # verde
            if jogador == 1:
                idx1 += 1
                win.after(600, lambda: perguntar(2))
            else:
                idx2 += 1
                win.after(600, lambda: perguntar(1))
        else:
            botao.config(bg="#FF7F7F")  # vermelho
            result["loser"] = jogador
            win.after(600, win.destroy)

    # começa pelo jogador informado
    perguntar(jogador_inicial)
    win.wait_window()

    if created_root:
        root.destroy()

    return result["loser"]


def run_quiz_for_capture(root, attacker_color: int, defender_color: int) -> str:
    """
    Pergunta alternando entre os dois jogadores, começando pelo ATACANTE.
    Retorna:
      'attacker' se quem errou foi o atacante
      'defender' se quem errou foi o defensor
    Se ninguém errou (todos acertaram), permite a captura => 'defender'
    """
    jogador_atacante = 1 if attacker_color == WHITE else 2
    jogador_defensor = 1 if defender_color == WHITE else 2

    quem_errou = abrir_quiz_quem_errou(root, jogador_inicial=jogador_atacante)

    if quem_errou is None:
        # Ninguém errou => captura ocorre
        return "defender"

    return "attacker" if quem_errou == jogador_atacante else "defender"


if __name__ == "__main__":
    import tkinter as tk

    root = tk.Tk()
    resultado = abrir_quiz(root)
    print("Resultado do quiz:", resultado)
    root.mainloop()

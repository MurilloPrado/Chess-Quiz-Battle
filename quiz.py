import tkinter as tk

# Perguntas separadas por jogador
QUIZ_JOGADOR_1 = [
    ("Qual linguagem é usada para programar páginas web?", "JavaScript"),
    ("Qual o resultado de 2+2?", "4"),
]

QUIZ_JOGADOR_2 = [
    ("Qual a capital do Brasil?", "Brasília"),
    ("Qual cor do céu em um dia claro?", "Azul"),
]

def abrir_quiz(root) -> bool:
    """
    Quiz para dois jogadores com perguntas diferentes.
    Retorna True se ambos acertarem, False se algum errar.
    """
    result = {"value": None}
    idx1, idx2 = 0, 0  # índice das perguntas de cada jogador

    win = tk.Toplevel(root)
    win.title("Quiz")
    win.geometry("450x300")
    win.grab_set()
    win.transient(root)

    label_question = tk.Label(win, text="", font=("Arial", 12))
    label_question.pack(pady=20)

    botoes_frame = tk.Frame(win)
    botoes_frame.pack(pady=10)

    botoes = []

    # Função para exibir a pergunta de um jogador
    def perguntar(jogador):
        nonlocal idx1, idx2
        if idx1 >= len(QUIZ_JOGADOR_1) or idx2 >= len(QUIZ_JOGADOR_2):
            # Fim das perguntas → ambos acertaram tudo
            result["value"] = True
            win.destroy()
            return

        if jogador == 1:
            pergunta, correta = QUIZ_JOGADOR_1[idx1]
        else:
            pergunta, correta = QUIZ_JOGADOR_2[idx2]

        label_question.config(text=f"Jogador {jogador}: {pergunta}")

        # Atualiza botões
        alternativas = ["Python", "JavaScript", "C++", "Java", "Brasília", "Rio de Janeiro", "Azul", "Verde"]
        for idx, b in enumerate(botoes):
            b.config(text=alternativas[idx], command=lambda t=alternativas[idx]: responder(t, jogador, correta))

    def responder(resposta, jogador, correta):
        nonlocal idx1, idx2
        if resposta == correta:
            print(f"Jogador {jogador} acertou!")
            # Passa para a próxima pergunta do mesmo jogador
            if jogador == 1:
                idx1 += 1
                perguntar(2)  # agora jogador 2 responde
            else:
                idx2 += 1
                perguntar(1)  # volta para jogador 1
        else:
            print(f"Jogador {jogador} errou!")
            result["value"] = False
            win.destroy()

    # Cria botões
    for i in range(8):
        b = tk.Button(botoes_frame, text="", width=20)
        b.grid(row=i//2, column=i%2, padx=10, pady=5)
        botoes.append(b)

    # Começa pelo jogador 1
    perguntar(1)
    win.wait_window()
    return result["value"] is True
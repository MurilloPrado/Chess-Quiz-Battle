# Chess-Quiz-Battle

Um jogo gamificado que combina **xadrez reduzido** com **quiz de múltipla escolha**.

Sempre que uma peça é capturada no tabuleiro, acontece uma *batalha de quiz*:

- ✅ Se o jogador **acerta** a pergunta, mantém sua peça.
- ❌ Se **erra**, a peça é definitivamente capturada pelo oponente.

---

## 🎯 Objetivo do projeto

Tornar o aprendizado de xadrez e de conteúdos teóricos mais **dinâmico e divertido**, misturando:

- Raciocínio tático de xadrez;
- Perguntas de múltipla escolha (quiz);
- Uma experiência visual com **tabuleiro 2D** e **cena 3D/holográfica** para o quiz.

Além disso, o projeto serve como laboratório para:

- Sincronização em tempo real entre dois jogadores;
- Integração entre **backend em Python**, **cliente web em JavaScript** e visual 3D;
- Experimentos com engine 3D (Ursina/Panda3D) e efeitos de holograma.

---

## 🧱 Arquitetura geral

A estrutura do projeto é organizada em módulos:

- `backend/`  
  - Lógica principal do jogo em Python (menu, regras, partida, quiz…).
  - Gerencia o loop de jogo em **Pygame** e a integração com a cena 3D (Ursina/Panda3D) e o servidor de realtime.

- `realtime/`  
  - Servidor de comunicação em tempo real (WebSocket/HTTP).
  - Responsável por parear jogadores, sincronizar estados da partida e disparar eventos de “iniciar quiz” quando há captura.

- `clients/`  
  - Clientes web em **HTML/CSS/JavaScript**.
  - Inclui tabuleiro, telas auxiliares e comunicação com o servidor de realtime.

- `assets/`  
  - Sprites, imagens, ícones, fontes, modelos 3D e demais recursos visuais.

- Raiz do projeto:
  - `requirements.txt` – dependências Python completas do projeto. :contentReference[oaicite:0]{index=0}  
  - `.gitignore` – arquivos ignorados no Git.
  - `README.md` – esta documentação.

---

## 🛠 Tecnologias utilizadas

As principais libs Python estão definidas em `requirements.txt`: :contentReference[oaicite:1]{index=1}  

**Engine / Gráficos**

- **Pygame** – interface 2D, menus e tela principal do jogo.
- **Ursina** – engine de alto nível para 3D.
- **Panda3D**, `panda3d-gltf`, `panda3d-simplepbr` – base 3D e suporte a GLTF + PBR.
- `moderngl`, `glcontext`, `pyrr`, `numpy` – suporte a OpenGL moderno e matemática 3D.
- `screeninfo`, `pillow` – manipulação de telas e imagens.

**Backend / API / Realtime**

- **FastAPI** – API HTTP e endpoints WebSocket.
- **Starlette** – base assíncrona (FastAPI é construída sobre Starlette).
- **Uvicorn** – ASGI server para rodar a aplicação FastAPI.
- **websockets**, `anyio`, `sniffio` – comunicação assíncrona em tempo real.

**Outros utilitários**

- **Pydantic** (v2) – validação e tipagem de dados.
- `qrcode` – geração de QR Codes (para compartilhar partidas, sessão, etc.).
- `click`, `colorama`, `pyperclip` – CLIs, cores no terminal e utilidades de clipboard.

---

## 🚀 Como rodar o projeto localmente

> Os passos abaixo assumem que você tem **Python 3.10+** instalado.

### 1. Clonar o repositório

```bash
git clone https://github.com/MurilloPrado/Chess-Quiz-Battle.git
cd Chess-Quiz-Battle
```

## 2. Ativar o ambiente virtual

```bash
python -m venv venv
venv\Scripts\activate
```

## 3. Instalar as dependências

```bash
pip install -r requirements.txt
```

## 4. Iniciar o jogo

```bash
python backend/app.py
```

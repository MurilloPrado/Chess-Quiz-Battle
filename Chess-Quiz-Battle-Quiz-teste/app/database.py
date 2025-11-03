# database.py

import sqlite3
from pathlib import Path

# Define o caminho do banco de dados no mesmo diretório do script
DB_FILE = Path(__file__).parent / "ranking.db"

def get_db_conn():
    """Cria e retorna uma conexão com o banco de dados."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row  # Facilita o acesso aos dados por nome de coluna
    return conn

def init_db():
    """Cria a tabela 'jogadores' se ela não existir."""
    try:
        conn = get_db_conn()
        cursor = conn.cursor()
        
        # Cria a tabela
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS jogadores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT UNIQUE NOT NULL,
                vitorias INTEGER NOT NULL DEFAULT 0
            )
        """)
        
        conn.commit()
        print(f"Banco de dados '{DB_FILE}' inicializado com sucesso.")
        
    except sqlite3.Error as e:
        print(f"Erro ao inicializar o banco de dados: {e}")
    finally:
        if conn:
            conn.close()

def registrar_vitoria(nome_jogador: str):
    """
    Registra uma vitória para um jogador.
    Se o jogador não existir, ele é criado.
    Se existir, seu contador de vitórias é incrementado.
    """
    if not nome_jogador:
        print("Erro: Nome do jogador não pode ser vazio.")
        return

    try:
        conn = get_db_conn()
        cursor = conn.cursor()
        
        # Usa a sintaxe "UPSERT" (UPDATE or INSERT) do SQLite
        cursor.execute("""
            INSERT INTO jogadores (nome, vitorias)
            VALUES (?, 1)
            ON CONFLICT(nome) DO UPDATE SET
                vitorias = vitorias + 1
        """, (nome_jogador,))
        
        conn.commit()
        print(f"Vitória registrada para: {nome_jogador}")
        
    except sqlite3.Error as e:
        print(f"Erro ao registrar vitória para {nome_jogador}: {e}")
    finally:
        if conn:
            conn.close()

def get_ranking():
    """Retorna uma lista de tuplas (nome, vitorias) ordenadas por vitórias."""
    try:
        conn = get_db_conn()
        cursor = conn.cursor()
        
        cursor.execute("SELECT nome, vitorias FROM jogadores ORDER BY vitorias DESC")
        ranking = cursor.fetchall()
        return ranking
        
    except sqlite3.Error as e:
        print(f"Erro ao buscar ranking: {e}")
        return []
    finally:
        if conn:
            conn.close()

# --- Para testar o módulo diretamente ---
if __name__ == "__main__":
    print("Inicializando banco de dados...")
    init_db()
    
    print("\nRegistrando vitórias de teste...")
    registrar_vitoria("Alice")
    registrar_vitoria("Bob")
    registrar_vitoria("Alice") # Alice agora deve ter 2 vitórias
    
    print("\nBuscando ranking...")
    ranking_atual = get_ranking()
    
    print("--- RANKING ATUAL ---")
    for i, (nome, vitorias) in enumerate(ranking_atual):
        print(f"{i+1}. {nome} - {vitorias} vitórias")
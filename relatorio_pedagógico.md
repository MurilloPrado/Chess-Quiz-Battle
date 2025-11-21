**Relatório Pedagógico do Plugin Gamificado**

# 1\. Identificação do Plugin

Nome do jogo/plugin: **Chess Quiz Battle**

O projeto contempla todas as áreas da disciplina, abordando Fundamentos, Análise de Algoritmos, Técnicas de Computação e Modelos Computacionais.

Grupo:

- Murillo Rodrigues Araujo do Prado - 34594086
- Victor Hugo Rodrigues Araujo - 34147021
- Mariana Rodrigues de Carvalho Martinelli - 34672265

# 2\. Objetivo Pedagógico

O jogo tem como objetivo testar o conhecimento do jogador sobre os conceitos da disciplina Computabilidade e Complexidade de Algoritmos, com foco em revisão, consolidação e aplicação prática dos principais conceitos estudados, reforçando o entendimento da matéria, onde o vencedor será aquele que conseguiu desenvolver mais

# 3\. Descrição do Jogo

O jogo consistem em um jogo de xadrez reduzido, sem a repetição de peças (exceto peão) com suas regras padrões, misturado com um quiz que será chamado toda vez que um movimento de captura de uma peça for realizado. Neste quiz, será um jogo bate bola de perguntas entre os players, aquele que errar primeiro, ou estourar o tempo limite, terá sua peça comida, independente se foi ele que fez o ataque. O tempo limite é de 20 segundos tendo a punição que, se passar 5 segundos do tempo total, a próxima pergunta terá 3 segundos a menos.

# 4\. Conteúdo Relacionado à Disciplina

O jogo procura fixar mais facilmente os conceitos da matéria, além de estimular o raciocínio lógico. Ele aborda todos os tópicos presente na disciplina, então envolve:

- Notação Assintótica
- Autômatos Finitos e Linguagens Regulares
- Máquinas de Turing e Computabilidade
- Classes de Complexidade
- Problemas Decidíveis e Indecidíveis
- Técnicas de Projeto de Algoritmos
- Entre outras

# 5\. Critérios de Pontuação

O critério de pontuação é o mesmo que o do xadrez, ganha aquele que comer o rei adversário primeiro

# 6\. Testes Realizados

- Avanço após ganhar - Verificar se o jogo avança corretamente quando o jogador ganha do outro no duelo de xadrez.
- Erro esperado - Testar se o jogo mostra feedback correto quando o jogador erra uma pergunta.
- Tempo limite esgotado - Garantir que, quando o timer da pergunta acaba, o quiz termina e o jogo retorna ao tabuleiro corretamente.
- Vencedor registrado no banco de dados - Testar se o ganhador é salvo corretamente.
- Reconexão entre jogadores - Testar se após o quiz os dois jogadores voltam às suas posições corretas.
- Movimentos ilegais e check - Garantir comportamento correto quando o rei está em perigo.

# 7\. Roteiro de Demonstração

- Situação: Cenário Feliz
  - Ambos os jogadores se conectam e jogam o jogo.
  - Demonstração da sincronia entre tabuleiros
  - Realização de jogadas
  - Acertos e erros do quiz
  - Mostrar punição sendo realizada
  - Terminar partida e mostrar o vencedor registrado no ranking

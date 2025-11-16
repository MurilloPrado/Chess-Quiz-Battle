const params = new URLSearchParams(location.search);
const playerName = params.get('name') || 'Jogador';
const WS_URL = params.get('ws') || `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws`;

// CHANGED: mantém TILE fixo em 96 (combina com CSS), mas responsivo vem da var --tile
const TILE = 96;
let COLS = 5, ROWS = 6;

// estado de conexão / jogo
let ws, myRole = 'spectator', myColor = null, turn = null;
let board = new Array(COLS * ROWS).fill(null);
let baseBottomColor = null;
let gamePhase = "lobby";

function recomputeBaseBottomColor() {
  if (!Array.isArray(board) || board.length === 0) return;
  let w = 0, b = 0;
  for (let x = 0; x < COLS; x++) {
    const c = board[idx(x, ROWS - 1)];
    if (!c) continue;
    if (c[0] === 'w') w++;
    else if (c[0] === 'b') b++;
  }
  if (w > b) baseBottomColor = 'w';
  else if (b > w) baseBottomColor = 'b';
}

// CHANGED: estado de lobby / timer
let started = false;        // só vira true depois do countdown
let activePlayers = 0;      // 0,1,2
let countdown = null;       // número mostrado no centro (3..2..1)
let countdownTimer = null;  // setInterval
let lastTurnLogged = null;  // pra não spammar o console

// CHANGED: sprites das peças
const PIECES_PATH = 'chess-pieces'; // <- ajusta se precisar
const pieceImgs = {};
const PIECE_TYPES = ['P', 'N', 'B', 'R', 'Q', 'K'];
const PIECE_COLORS = ['w', 'b'];

// UI
const canvasBoard = document.getElementById('board');
const bctx = canvasBoard.getContext('2d');
const nameTop = document.getElementById('nameTop');
const nameBottom = document.getElementById('nameBottom');
const roleHint = document.getElementById('roleHint');
const consoleEl = document.getElementById('console');

const idx = (x, y) => y * COLS + x;
const log = (t) => {
  const e = document.createElement('div');
  e.innerHTML = t;
  consoleEl.appendChild(e);
  consoleEl.scrollTop = consoleEl.scrollHeight;
};

// busca estado inicial via HTTP (se disponível)
async function fetchStateSnapshot() {
  try {
    const res = await fetch('/state');
    if (!res.ok) return;
    const snap = await res.json();

    // 🔥 Primeiro: fase
    if (snap.phase) {
      gamePhase = snap.phase;

      // Se já estivermos em xadrez, não é mais lobby → não tem countdown
      if (gamePhase === 'chess') {
        started = true;
        stopLobbyCountdown();
      }
    }

    // board
    if (snap.board) {
      const { cells, width, height } = snap.board;
      COLS = width;
      ROWS = height;
      board = cells.slice();
      canvasBoard.width  = COLS * TILE;
      canvasBoard.height = ROWS * TILE;
    }

    // turno
    if (snap.turn) {
      setTurnFromMessage(snap.turn);
    }

    // players
    if (snap.players) {
      updatePlayersState(snap.players);
    }

    drawBoard();
  } catch (e) {
    console.error('Erro ao buscar /state', e);
  }
}

function stopLobbyCountdown() {
  if (countdownTimer) {
    clearInterval(countdownTimer);
    countdownTimer = null;
  }
  countdown = null;
  // Redesenha o tabuleiro sem overlay de "Começando em..."
  drawBoard();
}

/* ========== Sprites ========== */

function loadPieceImages(basePath = PIECES_PATH) {
  const tasks = [];

  for (const c of PIECE_COLORS) {
    for (const t of PIECE_TYPES) {
      const code = c + t;           // ex: "wP"
      const img = new Image();
      img.src = `${basePath}/${code}.png`;
      pieceImgs[code] = img;

      tasks.push(new Promise((res) => {
        img.onload = res;
        img.onerror = () => {
          console.warn('Falha ao carregar sprite:', img.src);
          res(); // não quebra o jogo, só vai cair no fallback de letra
        };
      }));
    }
  }

  return Promise.all(tasks);
}

function drawPiece(x, y, code) {
  const img = pieceImgs[code];
  //if (img && img.complete) {
    // desenha a sprite
    //bctx.drawImage(img, x * TILE, y * TILE, TILE, TILE);
 // } else {
    // fallback: desenha só a letra (funcão que você já tinha)
    drawGlyph(x, y, code);
  //}
}

/* ========== UI helpers ========== */

function setPlayersUI(whiteName, blackName) {
  nameBottom.textContent = whiteName || 'Aguardando…';
  nameTop.textContent = blackName || 'Aguardando…';
}

function setRoleUI() {
  roleHint.textContent = `Papel: ${myRole}${myColor ? ` (${myColor === 'w' ? 'brancas' : 'pretas'})` : ''}`;
}

// CHANGED: só deixa mexer se jogo começou + vez correta
function canMove() {
  return started && !!(myColor && turn === myColor);
}

// coord. do board (bx,by) -> tela (sx,sy)
function boardToScreen(bx, by) {
  // se eu sou da mesma cor que está "embaixo" no board, não inverto
  // se eu sou da cor oposta, espelho no eixo Y pra minhas peças ficarem embaixo
  let sy;
  if (!myColor || myColor === baseBottomColor) {
    sy = by;
  } else {
    sy = ROWS - 1 - by;
  }
  return { x: bx, y: sy };
}

// coord. da tela (sx,sy) -> board (bx,by)
function screenToBoard(sx, sy) {
  let by;
  if (!myColor || myColor === baseBottomColor) {
    by = sy;
  } else {
    by = ROWS - 1 - sy;
  }
  return { x: sx, y: by };
}


// coord. lógica -> desenhada (perspectiva preto/branco)
function renderXY(bx, by) {
  return boardToScreen(bx, by);
}

function inBounds(x, y) {
  return x >= 0 && x < COLS && y >= 0 && y < ROWS;
}

function computePreviewMoves(x, y) {
  const moves = [];
  const code = board[idx(x, y)];
  if (!code) return moves;

  const { color, type } = parseCode(code);
  if (!color || !type) {
    return moves; // se não entendeu a peça, não tenta gerar movimentos
  }
  const dir   = (color === 'w') ? -1 : 1; // peão branco sobe (y-1), preto desce (y+1)

  const isEnemy = (tx, ty) => {
    if (!inBounds(tx, ty)) return false;
    const c = board[idx(tx, ty)];
    return c && c[0] !== color;
  };

  const isEmpty = (tx, ty) => {
    if (!inBounds(tx, ty)) return false;
    return !board[idx(tx, ty)];
  };

  // Peão
  if (type === 'P') {
    const ny = y + dir;

    // uma casa à frente
    if (isEmpty(x, ny)) {
      moves.push([x, ny]);

      // avanço duplo inicial (aproximação – pode não existir na sua variante)
      const startRank = (color === 'w') ? (ROWS - 2) : 1;
      const ny2 = y + dir * 2;
      if (y === startRank && isEmpty(x, ny2)) {
        moves.push([x, ny2]);
      }
    }

    // capturas diagonais
    const caps = [
      [x - 1, ny],
      [x + 1, ny],
    ];
    for (const [cx, cy] of caps) {
      if (isEnemy(cx, cy)) moves.push([cx, cy]);
    }
  }

  // Cavalo
  if (type === 'N') {
    const deltas = [
      [ 1,  2], [ 2,  1],
      [ 2, -1], [ 1, -2],
      [-1, -2], [-2, -1],
      [-2,  1], [-1,  2],
    ];
    for (const [dx, dy] of deltas) {
      const nx = x + dx, ny = y + dy;
      if (!inBounds(nx, ny)) continue;
      const c = board[idx(nx, ny)];
      if (!c || c[0] !== color) moves.push([nx, ny]);
    }
  }

  // Bispo (diagonais)
  if (type === 'B' || type === 'Q') {
    const dirs = [
      [ 1,  1], [ 1, -1],
      [-1,  1], [-1, -1],
    ];
    for (const [dx, dy] of dirs) {
      let nx = x + dx, ny = y + dy;
      while (inBounds(nx, ny)) {
        const c = board[idx(nx, ny)];
        if (!c) {
          moves.push([nx, ny]);
        } else {
          if (c[0] !== color) moves.push([nx, ny]);
          break;
        }
        nx += dx;
        ny += dy;
      }
    }
  }

  // Torre (ortogonais)
  if (type === 'R' || type === 'Q') {
    const dirs = [
      [ 1,  0], [-1,  0],
      [ 0,  1], [ 0, -1],
    ];
    for (const [dx, dy] of dirs) {
      let nx = x + dx, ny = y + dy;
      while (inBounds(nx, ny)) {
        const c = board[idx(nx, ny)];
        if (!c) {
          moves.push([nx, ny]);
        } else {
          if (c[0] !== color) moves.push([nx, ny]);
          break;
        }
        nx += dx;
        ny += dy;
      }
    }
  }

  // Rei (1 casa em qualquer direção)
  if (type === 'K') {
    for (let dx = -1; dx <= 1; dx++) {
      for (let dy = -1; dy <= 1; dy++) {
        if (dx === 0 && dy === 0) continue;
        const nx = x + dx, ny = y + dy;
        if (!inBounds(nx, ny)) continue;
        const c = board[idx(nx, ny)];
        if (!c || c[0] !== color) moves.push([nx, ny]);
      }
    }
  }

  return moves;
}

// Interpreta o valor que vem do backend e tenta extrair cor + tipo
function parseCode(code) {
  if (!code) return { color: null, type: null };

  // Caso clássico: "wP", "bQ" etc.
  if (typeof code === 'string') {
    if (code.length >= 2 && (code[0] === 'w' || code[0] === 'b')) {
      return { color: code[0], type: code[1] };
    }

    // Só uma letra: "P", "p" etc.
    if (code.length === 1) {
      return { 
        color: code === code.toUpperCase() ? 'w' : 'b',
        type: code.toUpperCase()
      };
    }

    // Tenta achar uma letra de peça dentro do texto (P N B R Q K)
    const match = code.match(/[PNBRQK]/i);
    if (match) {
      const t = match[0];
      return { 
        color: t === t.toUpperCase() ? 'w' : 'b',
        type: t.toUpperCase()
      };
    }
  }

  // Se não entendeu, desenha um "?"
  return { color: null, type: '?' };
}


function drawGlyph(x, y, code) {
  const { color, type } = parseCode(code);

  const glyph = type || '?'; // se não conseguir, coloca ?

  bctx.fillStyle = (color === 'b') ? '#02110a' : '#eafff5';
  bctx.textAlign = 'center';
  bctx.textBaseline = 'middle';
  bctx.font = Math.floor(TILE * 0.56) + 'px Consolas, monospace';
  bctx.shadowColor = '#00ff6a';
  bctx.shadowBlur = 8;
  bctx.fillText(glyph, x * TILE + TILE / 2, y * TILE + TILE / 2);
  bctx.shadowBlur = 0;
}


/* ========== Draw board ========== */

function drawBoard() {
  // fundo canvas
  bctx.fillStyle = '#0f1320';
  bctx.fillRect(0, 0, canvasBoard.width, canvasBoard.height);

  // casas + peças
  for (let ry = 0; ry < ROWS; ry++) {
    for (let rx = 0; rx < COLS; rx++) {
      const { x, y } = renderXY(rx, ry);
      const light = ((rx + ry) % 2 === 0);

      // base da casa
      let fill = light ? '#0efb8f22' : '#0efb8f10';

      // selecionada?
      const isSel = sel && sel[0] === rx && sel[1] === ry;

      // em preview?
      const isPreview = previewMoves.some(([mx, my]) => mx === rx && my === ry);

      if (isPreview) {
        fill = 'rgba(0, 255, 106, 0.35)'; // verde mais forte
      }
      if (isSel) {
        fill = 'rgba(0, 255, 200, 0.6)';  // seleção mais brilhante
      }

      bctx.fillStyle = fill;
      bctx.fillRect(x * TILE, y * TILE, TILE, TILE);

      const code = board[idx(rx, ry)];
      if (!code) continue;
      drawPiece(x, y, code);
    }
  }

  // overlay de lobby/timer
  bctx.save();
  if (activePlayers < 2) {
    bctx.fillStyle = 'rgba(0,0,0,.7)';
    bctx.fillRect(0, 0, canvasBoard.width, canvasBoard.height);
    bctx.fillStyle = '#00ff6a';
    bctx.textAlign = 'center';
    bctx.textBaseline = 'middle';
    bctx.font = Math.floor(TILE * 0.4) + 'px Consolas, monospace';
    bctx.fillText('Aguardando outro jogador...', canvasBoard.width / 2, canvasBoard.height / 2);
  } else if (!started && countdown !== null) {
    bctx.fillStyle = 'rgba(0,0,0,.6)';
    bctx.fillRect(0, 0, canvasBoard.width, canvasBoard.height);
    bctx.fillStyle = '#00ff6a';
    bctx.textAlign = 'center';
    bctx.textBaseline = 'middle';
    bctx.font = Math.floor(TILE * 0.6) + 'px Consolas, monospace';
    bctx.fillText(`Começando em ${countdown}`, canvasBoard.width / 2, canvasBoard.height / 2);
  }
  bctx.restore();
}

/* ========== Input ========== */

let sel = null;           // casa selecionada [x,y] ou null
let previewMoves = [];    // array de [x,y] com casas sugeridas

canvasBoard.addEventListener('click', (e) => {
  if (!canMove()) return;

  const r = canvasBoard.getBoundingClientRect();
  const px = Math.floor((e.clientX - r.left) / r.width * COLS);
  const py = Math.floor((e.clientY - r.top) / r.height * ROWS);

  // tela -> board, usando o mesmo critério de boardToScreen/screenToBoard
  const { x, y } = screenToBoard(px, py);
  const code = board[idx(x, y)];

  // 1º clique: selecionar peça minha
  if (!sel) {
    if (!code || code[0] !== myColor) return;
    sel = [x, y];
    previewMoves = computePreviewMoves(x, y);
    drawBoard();
    return;
  }

  // já havia seleção
  const [sx, sy] = sel;

  // se clicar na mesma casa -> cancela seleção
  if (sx === x && sy === y) {
    sel = null;
    previewMoves = [];
    drawBoard();
    return;
  }

  // se clicar em outra peça minha -> troca seleção
  if (code && code[0] === myColor) {
    sel = [x, y];
    previewMoves = computePreviewMoves(x, y);
    drawBoard();
    return;
  }

  // tentativa de movimento
  sel = null;
  previewMoves = [];
  drawBoard();

  try {
    ws?.send(JSON.stringify({ type: 'move', from: [sx, sy], to: [x, y] }));
  } catch {
    // ignore
  }
});

/* ========== Helpers de estado ========== */

function updatePlayersState(playersArr) {
  const white = playersArr[0]?.name || null;
  const black = playersArr[1]?.name || null;
  
  // descobre meu papel/cor primeiro
  if (playerName && white === playerName) {
    myRole = 'player1';
    myColor = 'w';
  } else if (playerName && black === playerName) {
    myRole = 'player2';
    myColor = 'b';
  } else {
    myRole = 'spectator';
    myColor = null;
  }

  // nomes na UI, respeitando minha perspectiva
  if (myColor === 'b') {
    // Eu sou preto -> meu nome embaixo
    nameBottom.textContent = black || 'Aguardando…';
    nameTop.textContent = white || 'Aguardando…';
  } else if (myColor === 'w') {
    // Eu sou branco -> meu nome embaixo
    nameBottom.textContent = white || 'Aguardando…';
    nameTop.textContent = black || 'Aguardando…';
  } else {
    // Espectador: branco embaixo, preto em cima
    nameBottom.textContent = white || 'Brancas';
    nameTop.textContent = black || 'Pretas';
  }

  setRoleUI();

  // contabiliza jogadores ativos
  activePlayers = 0;
  if (white) activePlayers++;
  if (black) activePlayers++;

  // lógica do countdown (mantém o que você já tinha)
  if (activePlayers < 2) {
    started = false;
    if (countdownTimer) {
      clearInterval(countdownTimer);
      countdownTimer = null;
    }
    countdown = null;
  } else if (gamePhase === "lobby" && activePlayers >= 2 && !started) {
    countdown = 10;
    log('<i>Ambos os jogadores conectados. Iniciando em 10...</i>');
    countdownTimer = setInterval(() => {
      countdown--;
      if (countdown <= 0) {
        clearInterval(countdownTimer);
        countdownTimer = null;
        countdown = null;
        started = true;
        log('<b>Jogo iniciado. Boa sorte!</b>');

        // força snapshot no início
        fetch(`${location.origin}/state`)
          .then(r => r.json())
          .then(applyStateSnapshot)
          .catch(err => {
            console.error('Erro carregando snapshot /state', err);
            drawBoard();
          });
      } else {
        log(`<i>Começando em ${countdown}...</i>`);
      }
    }, 1000);
  }

  drawBoard();
}

function setTurnFromMessage(msgTurn) {
  let newTurn = null;
  if (msgTurn === 'white' || msgTurn === 'w') newTurn = 'w';
  else if (msgTurn === 'black' || msgTurn === 'b') newTurn = 'b';

  if (newTurn !== turn) {
    turn = newTurn;
    if (turn) {
      const label = (turn === 'w') ? 'brancas' : 'pretas';
      log(`<b>Vez das ${label}.</b>`);
      lastTurnLogged = turn;
    }
  }
}

/* ========== WebSocket ========== */

(function boot() {
  // nome local (UI otimista)
  setPlayersUI(playerName, null);
  setRoleUI();

  // carrega sprites e conecta
  loadPieceImages().then(() => {
    console.log('Sprites carregadas (ou fallback).');
    drawBoard(); // redesenha já com sprites disponíveis
  });

  ws = new WebSocket(WS_URL);
  ws.addEventListener('open', () => {
    log(`<b>Conectado</b> ${WS_URL}`);
    ws.send(JSON.stringify({ type: 'join', name: playerName }));
  });
  ws.addEventListener('close', () => log('<b>Desconectado</b>'));
  ws.addEventListener('error', () => log('<b>Erro de conexão</b>'));
  ws.addEventListener('message', onMessage);

  // tamanho interno do canvas já casa com 6x5 tiles
  canvasBoard.width = COLS * TILE;
  canvasBoard.height = ROWS * TILE;

  drawBoard();
})();

// CHANGED: helper pra reaproveitar a lógica de aplicar um "state"
function applyStateSnapshot(msg) {
  // LOG pra debug
  console.log(
    "[WEB] state recebido:",
    "phase =", msg.phase,
    "| quiz =", msg.quiz ? "presente" : "null"
  );

  if (msg.phase) {
    gamePhase = msg.phase;

    // Se o backend diz que já estamos em CHESS,
    // significa que o jogo já começou (não é mais lobby)
    if (gamePhase === "chess") {
      started = true;        // impede o countdown de rodar de novo
      // se você tiver algum overlay de countdown/lobby, esconda aqui:
      stopLobbyCountdown();  // vamos criar essa função abaixo
    }
  }

  if (msg.board) {
    const { cells, width, height } = msg.board;
    console.log('BOARD DO BACKEND:', cells);
    
    if (Array.isArray(cells)) board = cells.slice();
    if (width && height) {
      COLS = width;
      ROWS = height;
      canvasBoard.width  = COLS * TILE;
      canvasBoard.height = ROWS * TILE;
    }

    recomputeBaseBottomColor();
  }

  const phase = msg.phase || null;
  const hasQuiz = !!msg.quiz;

  if (phase === "quiz" || hasQuiz) {
  // Monta query string preservando o que já existe (ws, name, etc.)
  const params = new URLSearchParams(window.location.search);

  // Se ainda não tiver "color" na URL, colocamos com base em myColor do xadrez
  if (!params.get("color") && myColor) {
    // myColor aqui é 'w' ou 'b' (do chess.js)
    const colorStr = myColor === "w" ? "white" : "black";
    params.set("color", colorStr);
  }

  const search = params.toString() ? "?" + params.toString() : "";
  const basePath = window.location.pathname.replace(/[^/]+$/, "");
  const target = basePath + "quiz.html" + search;

  console.log("[WEB] Entrou em phase=quiz, redirecionando para:", target);
  window.location.href = target;
  return;
}

  if (Array.isArray(msg.players)) {
    updatePlayersState(msg.players);
  }

  if (msg.turn) {
    setTurnFromMessage(msg.turn);
  }

  drawBoard();
}

function onMessage(ev) {
  let msg; try { msg = JSON.parse(ev.data); } catch { return; }

  if (msg.type === 'Assigned') {
    myRole = msg.role || 'spectator';
    myColor = (myRole === 'player1') ? 'w' : (myRole === 'player2' ? 'b' : null);
    setRoleUI();
  }

  if (msg.type === 'state') {
    applyStateSnapshot(msg);
    return;
  }

  if (msg.type === 'MoveMsg') {
    if (msg.board && Array.isArray(msg.board.cells)) {
      board = msg.board.cells.slice();
      recomputeBaseBottomColor();
    }
    if (msg.turn) {
      setTurnFromMessage(msg.turn);
    }
    drawBoard();
  }

  if (msg.type === 'ConsoleMsg' && msg.text) {
    log(msg.text);
  }
}


const params = new URLSearchParams(location.search);
let playerName = params.get('name') || ('Jogador-' + Math.random().toString(36).slice(2,6));
const WS_URL = params.get('ws') || `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws`;

// CHANGED: mantém TILE fixo em 96 (combina com CSS), mas responsivo vem da var --tile
const TILE = 96;
let COLS = 5, ROWS = 6;

// estado de conexão / jogo
let ws, myRole = 'spectator', myColor = null, turn = null;
let myAssignedRole = null; 
let lastRoleShown  = null;
let board = new Array(COLS * ROWS).fill(null);
let baseBottomColor = null;
let gamePhase = "lobby";

const PIECE_IMG = {};


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
const btnLeave  = document.getElementById('btnLeave');
const btnResign = document.getElementById('btnResign');
let inCheckSide = null;            // "white" | "black" | null
let inCheckKing = null; 
let FLIP_Y = false;
let lastBoardSig = null;   // assinatura do board do último snapshot desenhado
let lastTurnKey  = null;   // 'white' | 'black'
let gameOverShown   = false;
let gameOverTimer   = null;
let gameOverInterval = null

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

if (activePlayers < 2) {
  btnLeave.style.display  = '';
  btnResign.style.display = 'none';
} else if (gamePhase === 'chess') {
  btnLeave.style.display  = 'none';
  btnResign.style.display = (myColor ? '' : 'none');
}

btnLeave.addEventListener('click', () => {
  try { ws?.close(); } catch {}
  location.href = location.pathname.replace(/[^/]+$/, '') + 'index.html';
});

btnResign.addEventListener('click', () => {
  if (!myColor) return;
  if (!confirm('Tem certeza que deseja desistir?')) return;
  ws?.send(JSON.stringify({ type: 'resign' }));
});

function boardSignature(cells) {
  if (!Array.isArray(cells)) return 'none';
  // assinatura leve: tamanho + alguns valores
  const n = cells.length;
  let a = 0, b = 0, c = 0;
  for (let i = 0; i < n; i += Math.max(1, Math.floor(n/97))) {
    const v = cells[i] ? cells[i].charCodeAt(0) + (cells[i].charCodeAt(1)||0) : 7;
    a = (a * 131 + v) >>> 0;
    b = (b * 97  + v) >>> 0;
    c = (c * 53  + v) >>> 0;
  }
  return `${n}:${a.toString(16)}:${b.toString(16)}:${c.toString(16)}`;
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

function drawPieceSprite(ctx, code, px, py, tile) {
  if (!(code in PIECE_IMG)) {
    const img = new Image();
    img.src = `chess-pieces/${code}.png`;   // ex.: chess-pieces/wK.png
    img.onload = () => { PIECE_IMG[code] = img; drawBoard(); };
    img.onerror = () => { PIECE_IMG[code] = null; };
    PIECE_IMG[code] = img; // placeholder enquanto carrega
  }

  const img = PIECE_IMG[code];
  if (!img || !img.complete || !img.naturalWidth) return false;

  const pad = Math.round(tile * 0.10);
  const w = tile - pad * 2;
  const h = tile - pad * 2;

  const ratio = img.width / img.height;
  let dw = w, dh = h;
  if (ratio > 1) dh = Math.round(w / ratio); else dw = Math.round(h * ratio);

  const dx = px + Math.round((tile - dw) / 2);
  const dy = py + Math.round((tile - dh) / 2);
  ctx.drawImage(img, dx, dy, dw, dh);
  return true;
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
  // recebe coordenadas do TABULEIRO e devolve coordenadas de DESENHO
  const sy = FLIP_Y ? (ROWS - 1) - by : by;
  return { x: bx, y: sy };
}
// coord. da tela (sx,sy) -> board (bx,by)
function screenToBoard(sx, sy) {
  // recebe coordenadas da TELA e devolve coordenadas do TABULEIRO
  const by = FLIP_Y ? (ROWS - 1) - sy : sy;
  return { x: sx, y: by };
}

function recomputePerspective() {
  if (!myColor || !Array.isArray(board) || !COLS || !ROWS) return;
  // média de Y das minhas peças em coordenadas de TABULEIRO
  let sumY = 0, count = 0;
  for (let y = 0; y < ROWS; y++) {
    for (let x = 0; x < COLS; x++) {
      const code = board[y * COLS + x];
      if (code && code[0] === myColor) { sumY += y; count++; }
    }
  }
  if (!count) return;
  const avgY = sumY / count;
  // se a média está na metade de CIMA do tabuleiro lógico, flipamos para trazê-la para baixo
  FLIP_Y = avgY <= (ROWS - 1) / 2;
}

// coord. lógica -> desenhada (perspectiva preto/branco)
function renderXY(bx, by) { 
  return boardToScreen(bx, by); 
}

function inBounds(x, y) {
  return x >= 0 && x < COLS && y >= 0 && y < ROWS;
}

function colorForwardDir(color) {
  // 1) tente pelos peões (melhor indicador)
  let sumY = 0, cnt = 0;
  for (let y = 0; y < ROWS; y++) {
    for (let x = 0; x < COLS; x++) {
      const c = board[idx(x, y)];
      if (c && c[0] === color && (c[1] === 'P' || c[1] === 'p')) {
        sumY += y; cnt++;
      }
    }
  }
  if (cnt > 0) {
    const avg = sumY / cnt;
    return (avg > (ROWS - 1) / 2) ? -1 : +1; // peões majoritariamente "embaixo" => -1
  }

  // 2) sem peões: tente pelo rei
  for (let y = 0; y < ROWS; y++) {
    for (let x = 0; x < COLS; x++) {
      const c = board[idx(x, y)];
      if (c && c[0] === color && (c[1] === 'K' || c[1] === 'k')) {
        return (y > (ROWS - 1) / 2) ? -1 : +1;
      }
    }
  }

  // 3) fallback: supor configuração clássica (brancas embaixo)
  return (color === 'w') ? -1 : +1;
}

function computePreviewMoves(x, y) {
  const moves = [];
  const code = board[idx(x, y)];
  if (!code) return moves;

  const { color, type } = parseCode(code);
  if (!color || !type) {
    return moves; // se não entendeu a peça, não tenta gerar movimentos
  }
   const dir = colorForwardDir(color);

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
      const { x, y } = boardToScreen(rx, ry);
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

      if (inCheckSide && inCheckKing && inCheckKing.x === rx && inCheckKing.y === ry) {
        const px = x * TILE;
        const py = y * TILE;
        bctx.fillStyle = fill;
        bctx.fillRect(px, py, TILE, TILE);

        bctx.save();
        bctx.fillStyle = '#e53935';
        bctx.globalAlpha = 0.55;
        bctx.fillRect(px, py, TILE, TILE);
        bctx.restore();
      }

      const code = board[idx(rx, ry)]
      if (!code) continue;

      const px = x * TILE;
      const py = y * TILE;
      const ok = drawPieceSprite(bctx, code, px, py, TILE);
      if (!ok) {
        // fallback enquanto a imagem não carregou
        bctx.fillStyle = (code[0] === 'w') ? '#eee' : '#222';
        bctx.font = Math.floor(TILE * 0.6) + 'px Arial';
        bctx.textAlign = 'center';
        bctx.textBaseline = 'middle';
        bctx.fillText(code[1], px + TILE/2, py + TILE/2);
      }
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

function showGameOverOverlay(msg) {
  const modal       = document.getElementById('gameOverModal');
  const nameEl      = document.getElementById('winnerName');
  const titleEl     = document.getElementById('gameOverTitle');
  const countdownEl = document.getElementById('backCountdown');

  if (!modal) return;

  modal.classList.add('is-open');

  let winnerName = msg.winnerName || null;
  const winnerSide = msg.winnerSide || null;

  // tenta inferir pelo lado, se o nome não veio direto
  if (!winnerName && winnerSide && Array.isArray(msg.players)) {
    if (winnerSide === 'white') {
      winnerName = msg.players[0]?.name || 'Brancas';
    } else if (winnerSide === 'black') {
      winnerName = msg.players[1]?.name || 'Pretas';
    }
  }

  if (!winnerName && !winnerSide) {
    winnerName = 'Empate';
  }

  if (nameEl && winnerName) {
    nameEl.textContent = winnerName;
  }

  const outcome = msg.outcome || '';
  if (titleEl) {
    if (outcome && outcome.startsWith('stalemate')) {
      titleEl.textContent = 'Empate!';
    } else {
      titleEl.textContent = 'Xeque-mate!';
    }
  }

  // só dispara timers uma vez
  if (!gameOverShown) {
    gameOverShown = true;

    let remaining = 10;
    if (countdownEl) countdownEl.textContent = remaining.toString();

    if (gameOverInterval) clearInterval(gameOverInterval);
    gameOverInterval = setInterval(() => {
      remaining--;
      if (remaining < 0) remaining = 0;
      if (countdownEl) countdownEl.textContent = remaining.toString();
      if (remaining <= 0 && gameOverInterval) {
        clearInterval(gameOverInterval);
        gameOverInterval = null;
      }
    }, 1000);

    if (gameOverTimer) clearTimeout(gameOverTimer);
    gameOverTimer = setTimeout(() => {
      const basePath = window.location.pathname.replace(/[^/]+$/, '');
      window.location.href = basePath + 'index.html';
    }, 10000);
  }
}

function hideGameOverOverlay() {
  const modal       = document.getElementById('gameOverModal');
  const countdownEl = document.getElementById('backCountdown');

  if (!modal) return;

  modal.classList.remove('is-open');

  if (countdownEl) countdownEl.textContent = '';

  if (gameOverInterval) {
    clearInterval(gameOverInterval);
    gameOverInterval = null;
  }
  if (gameOverTimer) {
    clearTimeout(gameOverTimer);
    gameOverTimer = null;
  }
  gameOverShown = false;
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
    if (myAssignedRole) {                    
      myRole  = myAssignedRole;
      myColor = (myRole === 'player1') ? 'w' : (myRole === 'player2' ? 'b' : null);
    } else {
      // fallback antigo só se ainda não recebi "Assigned"
      if (playerName && white === playerName) {
        myRole = 'player1'; myColor = 'w';
      } else if (playerName && black === playerName) {
        myRole = 'player2'; myColor = 'b';
      } else {
        myRole = 'spectator'; myColor = null;
      }
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
  activePlayers = Array.isArray(playersArr) ? playersArr.length : 0;

  // lógica do countdown (mantém o que você já tinha)
  if (activePlayers < 2) {
    started = false;
    stopLobbyCountdown();
    if (countdownTimer) {
      clearInterval(countdownTimer);
      countdownTimer = null;
    }
    countdown = null;
  } else if (gamePhase === "lobby" && activePlayers >= 2 && !started) {
  // Já tem countdown rodando? NÃO inicia de novo.
  if (countdownTimer) {
    // só redesenha UI se quiser
    drawBoard();
  } else {
    countdown = 10;
    log('<i>Ambos os jogadores conectados. Iniciando em 10...</i>');
    drawBoard();
    countdownTimer = setInterval(() => {
      countdown--;
      drawBoard();
      if (countdown <= 0) {
        clearInterval(countdownTimer);
        countdownTimer = null;
        countdown = null;
        started = true;
        log('<b>Jogo iniciado. Boa sorte!</b>');
        drawBoard();

        // força snapshot no início
        fetch(`${location.origin}/state`)
          .then(r => r.json())
          .then(applyStateSnapshot)
          .catch(err => {
            console.error('Erro carregando snapshot /state', err);
            drawBoard();
          });
      } else {
        // Mostra apenas o número (sem spammar várias linhas de log)
        // Se quiser manter o log, mantém — mas agora só há 1 intervalo.
        log(`<i>Começando em ${countdown}...</i>`);
      }
    }, 1000);
  }
}}

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
    fetchStateSnapshot(); 
  });

  ws = new WebSocket(WS_URL);
  ws.addEventListener('open', () => {
    log(`<b>Conectado</b> ${WS_URL}`);
    ws.send(JSON.stringify({ type: 'join', name: playerName, color: myColor === 'b' ? 'black' : (myColor === 'w' ? 'white' : null) }));
  });
  ws.addEventListener('close', () => log('<b>Desconectado</b>'));
  ws.addEventListener('error', () => log('<b>Erro de conexão</b>'));
  ws.addEventListener('message', onMessage);
  
  fetchStateSnapshot();
  setTimeout(() => {
    const anyPiece = Array.isArray(board) && board.some(c => !!c);
    if (!anyPiece) fetchStateSnapshot();  // <- NEW
  }, 600);

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

  // game-over
  if (msg.gameOver) {
      showGameOverOverlay(msg);
    } else {
      hideGameOverOverlay();
  }

  if (msg.phase) {
    gamePhase = msg.phase;

    // Se o backend diz que já estamos em CHESS,
    // significa que o jogo já começou (não é mais lobby)
    if (gamePhase === "chess") {
      started = true;        // impede o countdown de rodar de novo
      stopLobbyCountdown();  // vamos criar essa função abaixo

      // limpa seleção
      sel = null;
      previewMoves = [];
      recomputePerspective();
    }
  }

  inCheckSide = msg.inCheckSide || null;
  inCheckKing = (msg.inCheckKing && typeof msg.inCheckKing.x === 'number')
    ? { x: msg.inCheckKing.x, y: msg.inCheckKing.y }
    : null;

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
    
    const curSig  = boardSignature(cells);
    const curTurn = msg.turn || turn || null;

    // Limpa seleção/preview SOMENTE se houve mudança real de posição ou de turno
    const boardChanged = (lastBoardSig !== null && curSig !== lastBoardSig);
    const turnChanged  = (lastTurnKey !== null && curTurn && curTurn !== lastTurnKey);

    // Se você tinha limpeza incondicional, troque por:
    if (boardChanged || turnChanged) {
      sel = null;
      previewMoves = [];
    }

    lastBoardSig = curSig;
    lastTurnKey  = curTurn;

    recomputePerspective(); 
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

    if (!params.get("name") && playerName) {
      params.set("name", playerName);
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
    const newRole = msg.role || 'spectator'; 
    if (newRole !== myAssignedRole) {
      myAssignedRole = newRole;
      myRole  = newRole;
      myColor = (myRole === 'player1') ? 'w' : (myRole === 'player2' ? 'b' : null);
      recomputePerspective?.();
      if (myRole !== lastRoleShown) {
        setRoleUI();           // mostra boas-vindas uma vez
        lastRoleShown = myRole;
      }
      drawBoard();
    }
    return; // não deixe cair em lógicas de players por nome
  }

  if (msg.type === 'state') {
    applyStateSnapshot(msg);
    return;
  }

  if (msg.type === 'MoveMsg') {
    if (msg.board && Array.isArray(msg.board.cells)) {
      board = msg.board.cells.slice();
      if (msg.board.width && msg.board.height) {
        COLS = msg.board.width;
        ROWS = msg.board.height;
        canvasBoard.width  = COLS * TILE;
        canvasBoard.height = ROWS * TILE;
      }
    }
    if (msg.turn) setTurnFromMessage(msg.turn);
    sel = null;           // CHANGED: tira seleção obsoleta
    previewMoves = [];
    drawBoard();
  }

  if (msg.type === 'ConsoleMsg' && msg.text) {
    log(msg.text);
  }
}


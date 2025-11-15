/* =========================
   CONFIG & STATE
========================= */
const params = new URLSearchParams(location.search);
const WS_URL = params.get('ws') || `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws`;
let playerName = params.get('name') || 'Jogador'; // será sobrescrito pelo input no clique

const PIECES_PATH = 'chess-pieces';

const TILE = 96;             // manter sincronizado com --tile
let COLS = 5, ROWS = 5;      // pode vir do servidor

// Gate (bloqueio até Entrar)
let started = false;

// Conexão / jogo
let ws = null;
let myRole = 'spectator';     // 'player1' | 'player2' | 'spectator'
let myColor = null;           // 'w' | 'b'
let turn = null;              // 'w' | 'b'
let board = new Array(COLS * ROWS).fill(null);

// UI
const gate = document.getElementById('gate');
const enterBtn = document.getElementById('enterBtn');
const canvasBoard = document.getElementById('board');
const bctx = canvasBoard.getContext('2d');
const consoleEl = document.getElementById('console');
const roleHint = document.getElementById('roleHint');
const nameTop = document.getElementById('nameTop');
const nameBottom = document.getElementById('nameBottom');

// Helpers
const idx = (x,y) => y*COLS + x;
const log = (t) => { const e=document.createElement('div'); e.innerHTML=t; consoleEl.appendChild(e); consoleEl.scrollTop = consoleEl.scrollHeight; };

/* =========================
   GRID VAPORWAVE (fundo)
   — transp. do teu Python para JS canvas
========================= */
const gridCanvas = document.getElementById('bgGrid');
const gctx = gridCanvas.getContext('2d', { alpha: false });

const GRID_COLOR = '#00ff6a';
const GRID_SPEED = 60;          // px/s
const GRID_SPACING = 28;
const GRID_LINES = 18;
const VERT_LINES_N = 20;
const VERT_SPREAD_BOTTOM = 40;
const VERT_SPREAD_TOP = 10;
const HORIZON_OFFSET = 2;       // px do topo da metade inferior

function fitBg() {
  gridCanvas.width = innerWidth;
  gridCanvas.height = innerHeight;
}
addEventListener('resize', fitBg);
fitBg();

let t0 = performance.now();
function animGrid(now){
  const t = (now - t0) / 1000;
  drawVaporwaveGrid(gctx, t);
  requestAnimationFrame(animGrid);
}
requestAnimationFrame(animGrid);

function drawVaporwaveGrid(ctx, t){
  const w = ctx.canvas.width, h = ctx.canvas.height;
  ctx.clearRect(0,0,w,h);

  // metade de baixo
  const botTop = Math.floor(h * 0.52);
  const botBottom = h;
  const horizonY = botTop + HORIZON_OFFSET;
  const centerX = w >> 1;

  // fundo gradiente sutil
  const g = ctx.createLinearGradient(0,botTop,0,h);
  g.addColorStop(0,'#00110a');
  g.addColorStop(1,'#000000');
  ctx.fillStyle = g;
  ctx.fillRect(0, botTop, w, h - botTop);

  // glow
  ctx.strokeStyle = GRID_COLOR;
  ctx.shadowColor = GRID_COLOR;
  ctx.shadowBlur = 18;

  // offset animado (move pra baixo)
  const offset = Math.floor((t * GRID_SPEED) % GRID_SPACING);

  // linhas horizontais com “perspectiva” (simples)
  ctx.lineWidth = 2;
  for(let i=0;i<GRID_LINES;i++){
    const y = horizonY + offset + i * GRID_SPACING;
    const scale = (i+1) / GRID_LINES; // 0..1
    const leftX  = Math.floor(centerX - (w/2) * (1 + scale));
    const rightX = Math.floor(centerX + (w/2) * (1 + scale));

    ctx.beginPath();
    ctx.moveTo(leftX, y);
    ctx.lineTo(rightX, y);
    ctx.stroke();
  }

  // linha do horizonte
  ctx.beginPath();
  ctx.moveTo(0, horizonY);
  ctx.lineTo(w, horizonY);
  ctx.stroke();

  // verticais convergindo
  ctx.lineWidth = 1;
  for(let i = -Math.floor(VERT_LINES_N/2); i <= Math.floor(VERT_LINES_N/2); i++){
    const xBottom = Math.floor(centerX + i * VERT_SPREAD_BOTTOM);
    const xTop    = Math.floor(centerX + i * VERT_SPREAD_TOP);
    ctx.beginPath();
    ctx.moveTo(xBottom, botBottom);
    ctx.lineTo(xTop, horizonY);
    ctx.stroke();
  }

  // reset glow para não afetar o resto
  ctx.shadowBlur = 0;
}

/* =========================
   XADREZ (render mínimo)
========================= */
function setPlayersUI(whiteName, blackName){
  nameBottom.textContent = whiteName || 'Aguardando…';
  nameTop.textContent    = blackName || 'Aguardando…';
}
function setRoleUI(){
  roleHint.textContent = `Papel: ${myRole}${myColor ? ` (${myColor==='w'?'brancas':'pretas'})` : ''}`;
}

function myCanMove(){
  if (!started) return false;  // BLOQUEIO até clicar Entrar
  if (!myColor || myRole==='spectator') return false;
  if (!turn) return false;
  return turn === myColor;
}

function drawBoard(){
  // fundo
  bctx.fillStyle = '#0f1320';
  bctx.fillRect(0,0,canvasBoard.width,canvasBoard.height);

  for(let ry=0; ry<ROWS; ry++){
    for(let rx=0; rx<COLS; rx++){
      const {x,y} = renderXY(rx,ry);
      const light = ((rx+ry)%2===0);
      bctx.fillStyle = light ? '#0efb8f22' : '#0efb8f10';
      bctx.fillRect(x*TILE, y*TILE, TILE, TILE);

      const code = board[idx(rx,ry)];
      if(!code) continue;
      drawGlyph(x,y,code);
    }
  }

  // faixa de turno
  if (turn){
    bctx.save();
    bctx.globalAlpha = .12;
    bctx.fillStyle = (turn==='w') ? '#ffffff' : '#000000';
    const y = (turn==='w')
      ? (myColor==='b' ? 0 : (ROWS-1))
      : (myColor==='b' ? (ROWS-1) : 0);
    bctx.fillRect(0, y*TILE, COLS*TILE, TILE);
    bctx.restore();
  }
}

function drawGlyph(x,y,code){
  const color = code[0]; // w | b
  const type  = code[1]; // P/N/B/R/Q/K
  bctx.fillStyle = (color==='w') ? '#eafff5' : '#02110a';
  bctx.textAlign = 'center'; bctx.textBaseline='middle';
  bctx.font = Math.floor(TILE*0.56)+'px Consolas, monospace';
  bctx.shadowColor = '#00ff6a'; bctx.shadowBlur = 8;
  bctx.fillText(type, x*TILE + TILE/2, y*TILE + TILE/2);
  bctx.shadowBlur = 0;
}

function renderXY(rx,ry){
  if (myColor==='b') return { x:rx, y:(ROWS-1-ry) };
  return { x:rx, y:ry };
}

/* =========================
   INPUT
========================= */
let sel=null;
canvasBoard.addEventListener('click', (e)=>{
  if(!myCanMove()) return;

  const r = canvasBoard.getBoundingClientRect();
  const px = Math.floor((e.clientX - r.left)/r.width * COLS);
  const py = Math.floor((e.clientY - r.top )/r.height* ROWS);
  const {x,y} = (myColor==='b') ? { x:px, y:(ROWS-1-py) } : { x:px, y:py };

  if(!sel){
    const code = board[idx(x,y)];
    if(!code || code[0]!==myColor) return;
    sel = [x,y];
    return;
  }
  const [sx,sy] = sel; sel=null;
  try { ws?.send(JSON.stringify({ type:'move', from:[sx,sy], to:[x,y] })); } catch {}
});

/* =========================
   WEBSOCKET (mínimo)
========================= */
function ensureWS(){
  if(ws && ws.readyState===1) return Promise.resolve();
  return new Promise((resolve)=>{
    ws = new WebSocket(WS_URL);
    ws.addEventListener('open', ()=>{ log(`<b>Conectado</b> ${WS_URL}`); resolve(); });
    ws.addEventListener('close', ()=> log('<b>Desconectado</b>'));
    ws.addEventListener('error', ()=> log('<b>Erro de conexão</b>'));
    ws.addEventListener('message', onMessage);
  });
}


function onMessage(ev){
  let msg; try{ msg = JSON.parse(ev.data); }catch{ return; }

  if (msg.type==='state'){
   // board
    if (msg.board){
      const { cells, width, height } = msg.board;
      if (Array.isArray(cells)) board = cells.slice();
      if (width && height){
        COLS=width; ROWS=height;
        canvasBoard.width  = COLS*TILE;
        canvasBoard.height = ROWS*TILE;
      }
    }
    // players
    if (Array.isArray(msg.players)){
      const white = msg.players[0]?.name || null;
      const black = msg.players[1]?.name || null;
      setPlayersUI(white, black);
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
      setRoleUI();
    }

    // turn
    if (msg.turn) {
      turn = (msg.turn === 'white') ? 'w' : (msg.turn === 'black' ? 'b' : null); 
    }
    drawBoard();
    return;
  }

  if (msg.type==='ConsoleMsg' && msg.text) log(msg.text);
}

/* =========================
   BOOT / GATE
========================= */
enterBtn.addEventListener('click', async ()=>{
  const inputEl = document.getElementById('playerName');
  const typed = (inputEl.value || '').trim();
  if(typed) playerName = typed;

  started = true;         // libera o clique do tabuleiro
  gate.style.display='none';
  await ensureWS();
  ws.send(JSON.stringify({ type:'join', name: playerName }));
  log('<i>Jogo liberado.</i>');
});

// render inicial (placeholder vazio até estado do servidor)
drawBoard();

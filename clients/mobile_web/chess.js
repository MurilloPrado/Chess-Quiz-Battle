const params = new URLSearchParams(location.search);
const playerName = params.get('name') || 'Jogador';
const WS_URL = params.get('ws') || `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws`;

const TILE = 96;
let COLS=6, ROWS=5;
let ws, myRole='spectator', myColor=null, turn=null;
let board = new Array(COLS*ROWS).fill(null);

// UI
const canvasBoard = document.getElementById('board');
const bctx = canvasBoard.getContext('2d');
const nameTop = document.getElementById('nameTop');
const nameBottom = document.getElementById('nameBottom');
const roleHint = document.getElementById('roleHint');
const consoleEl = document.getElementById('console');

const idx = (x,y)=> y*COLS+x;
const log = (t)=>{ const e=document.createElement('div'); e.innerHTML=t; consoleEl.appendChild(e); consoleEl.scrollTop = consoleEl.scrollHeight; };

function setPlayersUI(whiteName, blackName){
  nameBottom.textContent = whiteName || 'Aguardando…';
  nameTop.textContent    = blackName || 'Aguardando…';
}
function setRoleUI(){
  roleHint.textContent = `Papel: ${myRole}${myColor ? ` (${myColor==='w'?'brancas':'pretas'})` : ''}`;
}

function drawBoard(){
  bctx.fillStyle = '#0f1320'; bctx.fillRect(0,0,canvasBoard.width,canvasBoard.height);
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
  if (turn){
    bctx.save(); bctx.globalAlpha=.12; bctx.fillStyle=(turn==='w')?'#fff':'#000';
    const y = (turn==='w') ? (myColor==='b' ? 0 : (ROWS-1)) : (myColor==='b' ? (ROWS-1) : 0);
    bctx.fillRect(0,y*TILE,COLS*TILE,TILE); bctx.restore();
  }
}
function renderXY(rx,ry){ return (myColor==='b') ? {x:rx,y:(ROWS-1-ry)} : {x:rx,y:ry}; }
function drawGlyph(x,y,code){
  const color=code[0], type=code[1];
  bctx.fillStyle=(color==='w')?'#eafff5':'#02110a';
  bctx.textAlign='center'; bctx.textBaseline='middle';
  bctx.font = Math.floor(TILE*0.56)+'px Consolas, monospace';
  bctx.shadowColor='#00ff6a'; bctx.shadowBlur=8;
  bctx.fillText(type, x*TILE+TILE/2, y*TILE+TILE/2); bctx.shadowBlur=0;
}

// Input (tentativa de movimento)
let sel=null;
canvasBoard.addEventListener('click',(e)=>{
  if(!canMove()) return;
  const r = canvasBoard.getBoundingClientRect();
  const px = Math.floor((e.clientX - r.left)/r.width * COLS);
  const py = Math.floor((e.clientY - r.top )/r.height* ROWS);
  const {x,y} = (myColor==='b') ? {x:px, y:(ROWS-1-py)} : {x:px, y:py};
  if(!sel){
    const code = board[idx(x,y)];
    if(!code || code[0]!==myColor) return; sel=[x,y]; return;
  }
  const [sx,sy]=sel; sel=null;
  try{ ws?.send(JSON.stringify({type:'move',src:[sx,sy],dst:[x,y]})); }catch{}
});
function canMove(){ return !!(myColor && turn===myColor); }

// WS
(async function boot(){
  // nome do jogador atual ocupa o primeiro slot livre (UI local)
  // Por padrão: assume você é o próximo a entrar como player disponível.
  setPlayersUI(playerName, null);
  setRoleUI();

  // conecta
  ws = new WebSocket(WS_URL);
  ws.addEventListener('open', ()=>{
    log(`<b>Conectado</b> ${WS_URL}`);
    ws.send(JSON.stringify({type:'join', name:playerName}));
  });
  ws.addEventListener('close', ()=>log('<b>Desconectado</b>'));
  ws.addEventListener('error', ()=>log('<b>Erro de conexão</b>'));
  ws.addEventListener('message', onMessage);

  drawBoard();
})();

function onMessage(ev){
  let msg; try{ msg=JSON.parse(ev.data); }catch{ return; }

  if (msg.type==='Assigned'){
    myRole = msg.role || 'spectator';
    myColor = (myRole==='player1') ? 'w' : (myRole==='player2' ? 'b' : null);
    setRoleUI();
  }
  if (msg.type==='state'){
    if (msg.board){
      const {cells,width,height} = msg.board;
      if (Array.isArray(cells)) board = cells.slice();
      if (width && height){
        COLS=width; ROWS=height;
        canvasBoard.width=COLS*TILE; canvasBoard.height=ROWS*TILE;
      }
    }
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
    if (msg.turn){
      turn = (msg.turn==='white') ? 'w' : (msg.turn==='black' ? 'b' : null);
    }
    drawBoard();
    return;
  }
  if (msg.type==='MoveMsg'){
    if (msg.board && Array.isArray(msg.board.cells)) board = msg.board.cells.slice();
    if (msg.turn) turn = msg.turn;
    drawBoard();
  }
  if (msg.type==='ConsoleMsg' && msg.text) log(msg.text);
}

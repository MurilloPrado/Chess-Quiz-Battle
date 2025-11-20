const c = document.getElementById('bgGrid');
const ctx = c.getContext('2d', { alpha:false });

const GRID_COLOR = '#00ff6a';
const GRID_SPEED = 60;
const GRID_SPACING = 28;
const GRID_LINES = 18;
const VERT_LINES_N = 20;
const VERT_SPREAD_BOTTOM = 40;
const VERT_SPREAD_TOP = 10;
const HORIZON_OFFSET = 2;

function fit(){ c.width = innerWidth; c.height = innerHeight; }
addEventListener('resize', fit); fit();

let t0 = performance.now();
requestAnimationFrame(function loop(now){
  draw((now - t0)/1000);
  requestAnimationFrame(loop);
});

function draw(t){
  const w = c.width, h = c.height;
  ctx.clearRect(0,0,w,h);

  const botTop = Math.floor(h*0.52), botBottom = h;
  const horizonY = botTop + HORIZON_OFFSET;
  const centerX = w>>1;

  const g = ctx.createLinearGradient(0,botTop,0,h);
  g.addColorStop(0,'#00110a'); g.addColorStop(1,'#000');
  ctx.fillStyle = g; ctx.fillRect(0,botTop,w,h-botTop);

  ctx.strokeStyle = GRID_COLOR; ctx.shadowColor = GRID_COLOR; ctx.shadowBlur = 18;

  const offset = Math.floor((t*GRID_SPEED)%GRID_SPACING);

  ctx.lineWidth = 2;
  for(let i=0;i<GRID_LINES;i++){
    const y = horizonY + offset + i*GRID_SPACING;
    const scale = (i+1)/GRID_LINES;
    const lx = Math.floor(centerX - (w/2)*(1+scale));
    const rx = Math.floor(centerX + (w/2)*(1+scale));
    ctx.beginPath(); ctx.moveTo(lx,y); ctx.lineTo(rx,y); ctx.stroke();
  }
  ctx.beginPath(); ctx.moveTo(0,horizonY); ctx.lineTo(w,horizonY); ctx.stroke();

  ctx.lineWidth = 1;
  for(let i=-Math.floor(VERT_LINES_N/2); i<=Math.floor(VERT_LINES_N/2); i++){
    const xb = Math.floor(centerX + i*VERT_SPREAD_BOTTOM);
    const xt = Math.floor(centerX + i*VERT_SPREAD_TOP);
    ctx.beginPath(); ctx.moveTo(xb,botBottom); ctx.lineTo(xt,horizonY); ctx.stroke();
  }
  ctx.shadowBlur = 0;
}

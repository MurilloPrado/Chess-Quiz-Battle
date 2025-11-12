(function () {
  const logEl = document.getElementById('log');
  const nameEl = document.getElementById('name');
  const joinBtn = document.getElementById('join');
  const log = (...a) => (logEl.textContent += a.join(' ') + '\n');

  // monta ws://<host>/ws
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  const wsUrl = `${proto}://${location.host}/ws`;
  let ws;

  function safeSend(obj) {
    try { ws && ws.readyState === 1 && ws.send(JSON.stringify(obj)); }
    catch (e) { log('send error:', e.message); }
  }

  function connect() {
    log('Conectando em', wsUrl);
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      log('WS aberto');
      joinBtn.disabled = false;
      // opcional: auto-join se já tem valor
      if (nameEl.value.trim()) doJoin();
    };

    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data);
        if (msg.type === 'state') {
          log('STATE players=', (msg.players||[]).map(p => p.name).join(', ') || '(nenhum)');
        } else {
          log('MSG', ev.data);
        }
      } catch (e) {
        log('Raw', ev.data);
      }
    };

    ws.onclose = () => {
      log('WS fechado (reconectando em 2s)');
      joinBtn.disabled = true;
      setTimeout(connect, 2000);
    };

    ws.onerror = (e) => log('WS erro', e?.message || '(sem msg)');
  }

  function doJoin() {
    const name = nameEl.value.trim() || 'Player';
    safeSend({ type: 'join', name });
    log('Enviado JOIN de', name);
  }

  joinBtn.addEventListener('click', doJoin);
  nameEl.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') doJoin();
  });

  connect();
})();

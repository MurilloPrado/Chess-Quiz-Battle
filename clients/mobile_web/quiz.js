// =====================
// ELEMENTOS DA UI
// =====================
const circleTimerValue = document.getElementById("circleTimerValue");
const bottomTimerFill = document.getElementById("bottomTimerFill");
const optionButtons = Array.from(document.querySelectorAll(".option-btn"));

const overlay = document.getElementById("quizOverlay");
const overlayTitle = document.getElementById("overlayTitle");
const overlaySub = document.getElementById("overlaySub");

// =====================
// ESTADO
// =====================
let ws = null;
let currentQuiz = null; // CHANGED: vamos usar isso para saber quem venceu/perdeu no final
let gamePhase = null;

let timerMax = 20;
let timerLeft = 20;
let timerInterval = null;
let lastTurnKey = null;

// minha cor: "white"/"black"
let myColor = null;

// =====================
// HELPERS DE URL
// =====================
function getQueryParams() {
  return new URLSearchParams(window.location.search);
}

function normalizeColorParam(raw) {
  if (!raw) return null;
  const v = raw.toLowerCase();
  if (v === "white" || v === "w" || v === "brancas") return "white";
  if (v === "black" || v === "b" || v === "pretas") return "black";
  return null;
}

// =====================
// TIMER
// =====================
function startTimer() {
  stopTimer();

  const startedAt = performance.now();
  timerLeft = Math.max(0, baseRemaining);
  updateTimerUI();

  timerInterval = setInterval(() => {
    const now = performance.now();
    const elapsed = (now - startedAt) / 1000;
    const remaining = Math.max(0, baseRemaining - elapsed); // CHANGED

    timerLeft = remaining;
    updateTimerUI();

    if (remaining <= 0) {
      stopTimer();
      disableOptions();
    }
  }, 100);
}


function stopTimer() {
  if (timerInterval) {
    clearInterval(timerInterval);
    timerInterval = null;
  }
}

function updateTimerUI() {
  if (circleTimerValue) {
    circleTimerValue.textContent = String(Math.max(0, Math.ceil(timerLeft)));
  }
  if (bottomTimerFill) {
    const pct = timerMax > 0 ? (timerLeft / timerMax) * 100 : 0;
    bottomTimerFill.style.width = pct + "%";
  }
}

// =====================
// OVERLAY
// =====================
function showOverlay(title, sub) {
  if (!overlay) return;
  overlayTitle.textContent = title || "";
  overlaySub.textContent = sub || "";
  overlay.classList.remove("hidden");
}

function hideOverlay() {
  if (!overlay) return;
  overlay.classList.add("hidden");
}

// =====================
// QUIZ UI
// =====================
function applyQuizToUI(q) {
  currentQuiz = q;

  optionButtons.forEach((btn) => {
    const idx = parseInt(btn.dataset.index, 10);
    const txt = btn.querySelector(".option-text");
    btn.classList.remove("correct", "wrong", "disabled");

    if (txt) {
      txt.textContent = (q.choices && q.choices[idx]) || "";
    }
  });

  const side = q.currentSide;
  const pool = q.timePool || {};
  const bankForSide =
    typeof pool[side] === "number" ? pool[side] : (q.maxTime || 20);

  const rem = (typeof q.remainingTime === "number") ? q.remainingTime : bankForSide;

  const tsa = q.turnStartedAt || 0;              // NEW (do backend)
  const turnKey = `${side}|${tsa}`;              // NEW
  timerMax = bankForSide;

  if (turnKey !== lastTurnKey) {                 // só quando de fato troca o turno
    lastTurnKey = turnKey;
    startTimer(rem);                             // NEW: usa o remaining do backend
  } else {
    // só sinc fino: atualiza UI se drift > ~300ms
    const drift = Math.abs(timerLeft - rem);
    if (drift > 0.3) {
      // não reinicia o intervalo; apenas corrige visualização
      timerLeft = rem;
      updateTimerUI();
    }
  }

  // quem responde?
  const itsMyTurn = myColor && myColor === side;

  if (itsMyTurn) {
    hideOverlay();
    enableOptions();
  } else {
    disableOptions();
    showOverlay(
      "Aguarde sua vez",
      `Vez das ${side === "white" ? "Brancas" : "Pretas"}`
    );
  }
}

function enableOptions() {
  optionButtons.forEach((btn) => {
    btn.classList.remove("disabled", "correct", "wrong");
  });
}

function disableOptions() {
  optionButtons.forEach((btn) => {
    btn.classList.add("disabled");
  });
}

// =====================
// CLIQUE NAS ALTERNATIVAS
// =====================
optionButtons.forEach((btn) => {
  btn.addEventListener("click", () => {
    if (!currentQuiz || !ws || ws.readyState !== WebSocket.OPEN) return;

    if (timerLeft <= 0) return;

    const idx = parseInt(btn.dataset.index, 10);
    if (Number.isNaN(idx)) return;

    // Só deixa clicar se for a sua vez
    const qSide = currentQuiz.currentSide || "white";
    if (!myColor || myColor !== qSide) return;

    // Feedback local com base no correctIndex que já veio no quiz
    const correctIdx =
      typeof currentQuiz.correctIndex === "number"
        ? currentQuiz.correctIndex
        : null;

    optionButtons.forEach((b) => {
      b.classList.add("disabled");
      b.classList.remove("correct", "wrong");
    });

    if (correctIdx !== null) {
      optionButtons.forEach((b) => {
        const i = parseInt(b.dataset.index, 10);
        if (i === correctIdx) {
          b.classList.add("correct");
        }
      });
      if (idx !== correctIdx) {
        btn.classList.add("wrong");
      }
    }

    // Envia resposta no formato que o _on_quiz_answer_async espera
    ws.send(
      JSON.stringify({
        type: "quiz_answer",
        answer: String(idx),
      })
    );
  });
});

// =====================
// WEBSOCKET
// =====================
function connectWS() {
  const params = getQueryParams();

  // mesma query string: ?ws=...&color=...
  const wsUrl = params.get("ws") || `ws://${window.location.host}/ws`;
  myColor = normalizeColorParam(params.get("color"));

  ws = new WebSocket(wsUrl);

  ws.addEventListener("open", () => {
    console.log("[QUIZ] WS conectado:", wsUrl);
    ws.send(JSON.stringify({ type: "join", name: "quiz-web", avatar: null }));
  });

  ws.addEventListener("message", (event) => {
    let data;
    try {
      data = JSON.parse(event.data);
    } catch (e) {
      console.error("Mensagem WS inválida", e, event.data);
      return;
    }

    if (data.type === "state") {
      handleStateMessage(data);
    }
  });

  ws.addEventListener("close", () => {
    console.log("[QUIZ] WS fechado");
  });

  ws.addEventListener("error", (err) => {
    console.error("[QUIZ] Erro WS", err);
  });
}

/**
 * Decide o texto de "você venceu / perdeu" com base
 * no último currentQuiz.currentSide conhecido e na minha cor.
 */
function getEndResultTexts() { // CHANGED: nova função
  let title = "Quiz encerrado";
  let sub = "Voltando para o tabuleiro...";

  if (!currentQuiz || !myColor) {
    return { title, sub };
  }

  // Quem errou é o lado que estava respondendo
  const loserSide = currentQuiz.currentSide || "white"; // "white"/"black"
  const winnerSide = loserSide === "white" ? "black" : "white";

  if (myColor === winnerSide) {
    title = "Você venceu a batalha!";
  } else if (myColor === loserSide) {
    title = "Você perdeu a batalha!";
  }

  return { title, sub };
}

function handleStateMessage(msg) {
  gamePhase = msg.phase || null;

  // Se não estiver em phase "quiz", significa que o backend já voltou pro xadrez
  if (gamePhase !== "quiz") {
    // CHANGED: aqui usamos o último currentQuiz + myColor pra dizer se venceu ou perdeu
    const { title, sub } = getEndResultTexts();
    showOverlay(title, sub);

    const params = window.location.search || "";
    setTimeout(() => {
      // Importante: apenas voltamos para o xadrez.
      // O estado do tabuleiro é todo controlado pelo backend (GameScene / BoardState).
      window.location.href = `game.html${params}`;
    }, 2500);
    return;
  }

  // Estamos em phase "quiz"
  const q = msg.quiz || null;
  if (!q) {
    showOverlay("Aguardando pergunta...", "");
    return;
  }

  applyQuizToUI(q);
}

// =====================
// INICIALIZA
// =====================
connectWS();

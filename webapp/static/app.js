const pieceSymbols = {
  white: { p: "♙", n: "♘", b: "♗", r: "♖", q: "♕", k: "♔" },
  black: { p: "♟", n: "♞", b: "♝", r: "♜", q: "♛", k: "♚" },
};

const lobbyScreen = document.getElementById("lobby-screen");
const gameScreen = document.getElementById("game-screen");
const boardElement = document.getElementById("board");
const createRoomButton = document.getElementById("create-room-button");
const joinRoomButton = document.getElementById("join-room-button");
const roomInput = document.getElementById("room-input");
const roomCodeText = document.getElementById("room-code");
const connectionStatusText = document.getElementById("connection-status");
const statusText = document.getElementById("status-text");
const playerRoleText = document.getElementById("player-role");
const whiteNameText = document.getElementById("white-name");
const blackNameText = document.getElementById("black-name");
const errorText = document.getElementById("error-text");
const playerNameInput = document.getElementById("player-name");
const saveNameButton = document.getElementById("save-name-button");
const copyLinkButton = document.getElementById("copy-link-button");
const copyCodeButton = document.getElementById("copy-code-button");
const whiteClockText = document.getElementById("white-clock");
const blackClockText = document.getElementById("black-clock");
const cheatPanel = document.getElementById("cheat-panel");
const removePieceButton = document.getElementById("remove-piece-button");
const stealTimeButton = document.getElementById("steal-time-button");
const jumpscareButton = document.getElementById("jumpscare-button");
const cheatHelpText = document.getElementById("cheat-help");
const jumpscareOverlay = document.getElementById("jumpscare-overlay");
const jumpscareText = document.getElementById("jumpscare-text");

if (!window.name) {
  window.name = `geram-tab-${Math.random().toString(36).slice(2)}${Date.now().toString(36)}`;
}

const clientTabId = window.name;

let socket = null;
let roomId = null;
let ownerToken = sessionStorage.getItem("chess-owner-token") || "";
let ownerRoomId = sessionStorage.getItem("chess-owner-room-id") || "";
let playerColor = "spectator";
let isOwner = false;
let hasCheats = false;
let boardState = null;
let selectedSquare = null;
let armedCheat = null;
let clockInterval = null;
let audioContext = null;
let soundUnlocked = false;

function ensureAudioContext() {
  if (!audioContext) {
    audioContext = new (window.AudioContext || window.webkitAudioContext)();
  }
  return audioContext;
}

async function unlockAudio() {
  const context = ensureAudioContext();
  if (!context) {
    return false;
  }
  try {
    if (context.state === "suspended") {
      await context.resume();
    }

    const osc = context.createOscillator();
    const gain = context.createGain();
    gain.gain.value = 0.0001;
    osc.connect(gain);
    gain.connect(context.destination);
    osc.start();
    osc.stop(context.currentTime + 0.01);
    soundUnlocked = true;
    jumpscareText.classList.add("hidden");
    return true;
  } catch {
    soundUnlocked = false;
    return false;
  }
}

function playJumpscareSound() {
  const context = ensureAudioContext();
  if (!context) {
    return false;
  }

  if (context.state !== "running") {
    soundUnlocked = false;
    return false;
  }

  const now = context.currentTime;
  const master = context.createGain();
  master.gain.setValueAtTime(0.0001, now);
  master.gain.exponentialRampToValueAtTime(0.8, now + 0.03);
  master.gain.exponentialRampToValueAtTime(0.28, now + 0.45);
  master.gain.exponentialRampToValueAtTime(0.0001, now + 1.55);
  master.connect(context.destination);

  const osc1 = context.createOscillator();
  osc1.type = "sawtooth";
  osc1.frequency.setValueAtTime(900, now);
  osc1.frequency.exponentialRampToValueAtTime(120, now + 1.4);
  osc1.connect(master);
  osc1.start(now);
  osc1.stop(now + 1.55);

  const osc2 = context.createOscillator();
  osc2.type = "square";
  osc2.frequency.setValueAtTime(1400, now);
  osc2.frequency.exponentialRampToValueAtTime(180, now + 1.3);
  osc2.connect(master);
  osc2.start(now);
  osc2.stop(now + 1.45);

  const buffer = context.createBuffer(1, context.sampleRate * 1.5, context.sampleRate);
  const data = buffer.getChannelData(0);
  for (let i = 0; i < data.length; i += 1) {
    data[i] = (Math.random() * 2 - 1) * (1 - i / data.length);
  }
  const noise = context.createBufferSource();
  noise.buffer = buffer;
  const noiseFilter = context.createBiquadFilter();
  noiseFilter.type = "bandpass";
  noiseFilter.frequency.setValueAtTime(1300, now);
  noiseFilter.Q.value = 2.4;
  const noiseGain = context.createGain();
  noiseGain.gain.setValueAtTime(0.4, now);
  noiseGain.gain.exponentialRampToValueAtTime(0.0001, now + 1.3);
  noise.connect(noiseFilter);
  noiseFilter.connect(noiseGain);
  noiseGain.connect(context.destination);
  noise.start(now);
  noise.stop(now + 1.35);
  soundUnlocked = true;
  return true;
}

async function triggerJumpscare() {
  jumpscareOverlay.classList.remove("hidden");
  const unlocked = await unlockAudio();
  const played = playJumpscareSound();
  jumpscareText.classList.toggle("hidden", unlocked && played);
  window.setTimeout(() => {
    jumpscareOverlay.classList.add("hidden");
    jumpscareText.classList.add("hidden");
  }, 1700);
}

function setLobbyMode() {
  lobbyScreen.classList.remove("hidden");
  gameScreen.classList.add("hidden");
}

function setGameMode() {
  lobbyScreen.classList.add("hidden");
  gameScreen.classList.remove("hidden");
}

function formatTime(secondsLeft) {
  const safeValue = Math.max(0, Math.floor(secondsLeft));
  const minutes = String(Math.floor(safeValue / 60)).padStart(2, "0");
  const seconds = String(safeValue % 60).padStart(2, "0");
  return `${minutes}:${seconds}`;
}

function currentDisplayedClock(color) {
  if (!boardState?.clocks) {
    return 300;
  }
  const base = boardState.clocks[color];
  if (!boardState.clockRunning || !boardState.clockUpdatedAt || boardState.turn !== color) {
    return base;
  }
  const elapsed = Math.max(0, (Date.now() / 1000) - boardState.clockUpdatedAt);
  return Math.max(0, base - elapsed);
}

function updateClockDisplay() {
  whiteClockText.textContent = formatTime(currentDisplayedClock("white"));
  blackClockText.textContent = formatTime(currentDisplayedClock("black"));
}

function syncClockTicker() {
  if (clockInterval) {
    window.clearInterval(clockInterval);
  }
  updateClockDisplay();
  clockInterval = window.setInterval(updateClockDisplay, 250);
}

function renderBoard() {
  boardElement.innerHTML = "";
  const files = playerColor === "black"
    ? ["h", "g", "f", "e", "d", "c", "b", "a"]
    : ["a", "b", "c", "d", "e", "f", "g", "h"];
  const ranks = playerColor === "black"
    ? [1, 2, 3, 4, 5, 6, 7, 8]
    : [8, 7, 6, 5, 4, 3, 2, 1];
  const canPlay = boardState && boardState.bothPlayersConnected && !boardState.isGameOver;

  for (const rank of ranks) {
    for (let fileIndex = 0; fileIndex < 8; fileIndex += 1) {
      const square = `${files[fileIndex]}${rank}`;
      const squareElement = document.createElement("button");
      squareElement.type = "button";
      squareElement.className = `square ${(rank + fileIndex) % 2 === 0 ? "light" : "dark"}`;

      if (square === selectedSquare) {
        squareElement.classList.add("selected");
      }
      if (armedCheat === "remove") {
        squareElement.classList.add("cheat-armed");
      }
      if (selectedSquare && boardState?.legalMoves?.[selectedSquare]?.includes(square)) {
        squareElement.classList.add("legal");
      }

      const piece = boardState?.pieces?.[square];
      if (piece) {
        const pieceElement = document.createElement("span");
        pieceElement.className = `piece ${piece.color}`;
        pieceElement.textContent = pieceSymbols[piece.color][piece.type];
        squareElement.appendChild(pieceElement);
      }

      squareElement.disabled = !canPlay && armedCheat !== "remove";
      squareElement.addEventListener("click", () => handleSquareClick(square));
      boardElement.appendChild(squareElement);
    }
  }
}

function setError(message) {
  errorText.textContent = message || "";
}

function setConnectionStatus(message) {
  connectionStatusText.textContent = message;
}

function updateSidebar() {
  roomCodeText.textContent = roomId ? roomId.toUpperCase() : "Not connected";
  playerRoleText.textContent =
    playerColor === "spectator"
      ? "Spectator"
      : `You are ${playerColor}`;
  statusText.textContent = boardState?.status || "Waiting for a room.";
  whiteNameText.textContent = boardState?.playerNames?.white || "White";
  blackNameText.textContent = boardState?.playerNames?.black || "Black";
  copyLinkButton.disabled = !roomId;
  copyCodeButton.disabled = !roomId;

  const canCheat = isOwner && playerColor !== "spectator" && Boolean(boardState?.bothPlayersConnected);
  const canUseCheats = hasCheats && playerColor !== "spectator" && Boolean(boardState?.bothPlayersConnected);
  cheatPanel.classList.toggle("hidden", !hasCheats || playerColor === "spectator");
  removePieceButton.disabled = !canUseCheats;
  stealTimeButton.disabled = !canUseCheats;
  jumpscareButton.disabled = !canUseCheats;
  cheatHelpText.textContent = armedCheat === "remove"
    ? "Cheat armed: click an opponent piece."
    : "Cheats unlock when the secret code is entered in the name field.";
  updateClockDisplay();
}

function applyState(payload) {
  playerColor = payload.playerColor;
  isOwner = Boolean(payload.isOwner);
  hasCheats = Boolean(payload.hasCheats);
  boardState = payload.state;
  setGameMode();
  updateSidebar();
  renderBoard();
  syncClockTicker();
}

function sendJson(payload) {
  if (!socket || socket.readyState !== WebSocket.OPEN) {
    setError("You are not connected to a room.");
    return false;
  }
  socket.send(JSON.stringify(payload));
  return true;
}

function clearSelections() {
  selectedSquare = null;
  armedCheat = null;
}

function isPromotionMove(fromSquare, toSquare) {
  const piece = boardState?.pieces?.[fromSquare];
  if (!piece || piece.type !== "p") {
    return false;
  }
  return (piece.color === "white" && toSquare.endsWith("8")) || (piece.color === "black" && toSquare.endsWith("1"));
}

function getPromotionSuffix() {
  const choice = window.prompt("Promote to: q, r, b, or n", "q");
  if (!choice) {
    return null;
  }
  const normalized = choice.trim().toLowerCase();
  if (["q", "r", "b", "n"].includes(normalized)) {
    return normalized;
  }
  setError("Promotion must be q, r, b, or n.");
  return null;
}

function handleSquareClick(square) {
  setError("");
  if (!boardState) {
    return;
  }

  if (!boardState.bothPlayersConnected) {
    setError("You cannot move yet. Wait for the second player.");
    return;
  }

  const piece = boardState.pieces?.[square];

  if (armedCheat === "remove") {
    if (sendJson({ type: "remove_piece", square })) {
      armedCheat = null;
      updateSidebar();
      renderBoard();
    }
    return;
  }

  const isOwnPiece = piece && piece.color === playerColor;
  const legalTargets = selectedSquare ? boardState.legalMoves?.[selectedSquare] || [] : [];

  if (selectedSquare && legalTargets.includes(square)) {
    let move = `${selectedSquare}${square}`;
    if (isPromotionMove(selectedSquare, square)) {
      const promotionSuffix = getPromotionSuffix();
      if (!promotionSuffix) {
        return;
      }
      move += promotionSuffix;
    }
    sendJson({ type: "move", move });
    selectedSquare = null;
    renderBoard();
    return;
  }

  if (isOwnPiece && boardState.turn === playerColor && !boardState.isGameOver) {
    selectedSquare = square;
    renderBoard();
    return;
  }

  selectedSquare = null;
  renderBoard();
}

function connectToRoom(nextRoomId) {
  if (!nextRoomId) {
    return;
  }

  roomId = nextRoomId.toLowerCase();
  clearSelections();
  boardState = null;
  setError("");

  if (socket) {
    socket.close();
  }

  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  const wsUrl = new URL(`${protocol}://${window.location.host}/ws/${roomId}`);
  wsUrl.searchParams.set("clientId", clientTabId);
  if (ownerRoomId === roomId && ownerToken) {
    wsUrl.searchParams.set("ownerToken", ownerToken);
  }
  socket = new WebSocket(wsUrl);

  setConnectionStatus("Connecting...");

  socket.addEventListener("open", () => {
    setConnectionStatus("Connected");
    const savedName = playerNameInput.value.trim();
    if (savedName) {
      socket.send(JSON.stringify({ type: "set_name", name: savedName }));
    }
    const url = new URL(window.location.href);
    url.searchParams.set("room", roomId);
    window.history.replaceState({}, "", url);
  });

  socket.addEventListener("message", (event) => {
    const payload = JSON.parse(event.data);
    if (payload.type === "state") {
      applyState(payload);
      return;
    }
    if (payload.type === "jumpscare") {
      triggerJumpscare();
      return;
    }
    if (payload.type === "notice") {
      setError(payload.message);
      return;
    }
    if (payload.type === "error") {
      setError(payload.message);
    }
  });

  socket.addEventListener("close", () => {
    setConnectionStatus("Disconnected");
  });
}

async function createRoom() {
  setError("");
  const ownerColor = document.querySelector('input[name="owner-color"]:checked').value;
  const response = await fetch("/api/rooms", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ owner_color: ownerColor, owner_session_id: clientTabId }),
  });
  const payload = await response.json();
  ownerToken = payload.ownerToken;
  ownerRoomId = payload.roomId;
  sessionStorage.setItem("chess-owner-token", ownerToken);
  sessionStorage.setItem("chess-owner-room-id", ownerRoomId);
  roomInput.value = payload.roomId;
  connectToRoom(payload.roomId);
}

createRoomButton.addEventListener("click", () => {
  createRoom().catch(() => setError("Unable to create a room right now."));
});

joinRoomButton.addEventListener("click", () => {
  const typedRoom = roomInput.value.trim();
  if (!typedRoom) {
    setError("Enter a room code first.");
    return;
  }
  connectToRoom(typedRoom);
});

saveNameButton.addEventListener("click", () => {
  const name = playerNameInput.value.trim();
  if (!name) {
    setError("Enter a name first.");
    return;
  }
  if (sendJson({ type: "set_name", name })) {
    setError("");
  }
});

removePieceButton.addEventListener("click", () => {
  armedCheat = armedCheat === "remove" ? null : "remove";
  updateSidebar();
  renderBoard();
});

stealTimeButton.addEventListener("click", () => {
  sendJson({ type: "steal_time" });
});

jumpscareButton.addEventListener("click", () => {
  sendJson({ type: "jumpscare" });
});

copyLinkButton.addEventListener("click", async () => {
  if (!roomId) {
    return;
  }
  const inviteUrl = `${window.location.origin}/?room=${roomId}`;
  try {
    await navigator.clipboard.writeText(inviteUrl);
    setError("Invite link copied.");
  } catch {
    setError(`Copy this link: ${inviteUrl}`);
  }
});

copyCodeButton.addEventListener("click", async () => {
  if (!roomId) {
    return;
  }
  try {
    await navigator.clipboard.writeText(roomId.toUpperCase());
    setError("Room code copied.");
  } catch {
    setError(`Room code: ${roomId.toUpperCase()}`);
  }
});

window.addEventListener("load", () => {
  localStorage.removeItem("chess-owner-token");
  localStorage.removeItem("chess-owner-room-id");

  const roomFromUrl = new URL(window.location.href).searchParams.get("room");
  renderBoard();
  syncClockTicker();
  if (roomFromUrl) {
    roomInput.value = roomFromUrl;
    connectToRoom(roomFromUrl);
  } else {
    setLobbyMode();
  }
});

window.addEventListener("pointerdown", () => { unlockAudio(); });
window.addEventListener("keydown", () => { unlockAudio(); });

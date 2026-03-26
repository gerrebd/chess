import asyncio
import json
import secrets
import time
from dataclasses import dataclass, field
from pathlib import Path

import chess
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
CLOCK_SECONDS = 300.0
TIME_STEAL_SECONDS = 15.0
CHEAT_CODE = "geramprank"

app = FastAPI(title="Gerams Chess Game")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class CreateRoomRequest(BaseModel):
    owner_color: str = "white"
    owner_session_id: str


@dataclass
class ClientSession:
    color: str
    client_id: str
    is_owner: bool = False
    has_cheats: bool = False


@dataclass
class Room:
    room_id: str
    owner_color: str
    owner_token: str
    owner_session_id: str
    board: chess.Board = field(default_factory=chess.Board)
    sockets: dict[WebSocket, ClientSession] = field(default_factory=dict)
    cheat_client_ids: set[str] = field(default_factory=set)
    player_names: dict[str, str] = field(
        default_factory=lambda: {"white": "White", "black": "Black"}
    )
    white_time_left: float = CLOCK_SECONDS
    black_time_left: float = CLOCK_SECONDS
    clock_started: bool = False
    clock_running: bool = False
    last_clock_update: float | None = None
    status_message: str | None = None

    def assign_color(self, requested_owner: bool) -> str:
        used_colors = {session.color for session in self.sockets.values() if session.color in ("white", "black")}
        if requested_owner and self.owner_color not in used_colors:
            return self.owner_color

        other_color = "black" if self.owner_color == "white" else "white"
        if other_color not in used_colors:
            return other_color
        if self.owner_color not in used_colors:
            return self.owner_color
        return "spectator"

    def remove_socket(self, websocket: WebSocket) -> None:
        if websocket in self.sockets:
            del self.sockets[websocket]
        self._refresh_clock_state()

    def has_connected_player(self, color: str) -> bool:
        return any(session.color == color for session in self.sockets.values())

    def both_players_connected(self) -> bool:
        return self.has_connected_player("white") and self.has_connected_player("black")

    def _opponent_color(self, color: str) -> str:
        return "black" if color == "white" else "white"

    def _time_for_turn(self) -> float:
        return self.white_time_left if self.board.turn == chess.WHITE else self.black_time_left

    def _set_time_for_turn(self, seconds_left: float) -> None:
        if self.board.turn == chess.WHITE:
            self.white_time_left = seconds_left
        else:
            self.black_time_left = seconds_left

    def _refresh_clock_state(self) -> None:
        if self.board.is_game_over(claim_draw=True):
            self.clock_running = False
            self.last_clock_update = None
            return

        if self.board.move_stack and self.both_players_connected():
            self.clock_started = True

        if self.clock_started and self.both_players_connected():
            self.clock_running = True
            if self.last_clock_update is None:
                self.last_clock_update = time.time()
        else:
            self.clock_running = False
            self.last_clock_update = None

    def update_clock(self) -> None:
        if not self.clock_running or self.last_clock_update is None:
            return

        now = time.time()
        elapsed = max(0.0, now - self.last_clock_update)
        if elapsed <= 0:
            return

        remaining = max(0.0, self._time_for_turn() - elapsed)
        self._set_time_for_turn(remaining)
        self.last_clock_update = now

        if remaining <= 0:
            winner = "Black" if self.board.turn == chess.WHITE else "White"
            loser = "White" if self.board.turn == chess.WHITE else "Black"
            self.status_message = f"{loser} ran out of time. {winner} wins."
            self.clock_running = False
            self.last_clock_update = None

    def status_text(self) -> str:
        if self.status_message:
            return self.status_message
        if not self.both_players_connected():
            return "Waiting for both players to connect."
        if not self.clock_started:
            return "Both players are here. The clock starts after the first move."
        if self.board.is_checkmate():
            return f"Checkmate. {'Black' if self.board.turn == chess.WHITE else 'White'} wins."
        if self.board.is_stalemate():
            return "Stalemate. Draw."
        if self.board.is_insufficient_material():
            return "Draw by insufficient material."
        if self.board.can_claim_threefold_repetition():
            return "Threefold repetition available."
        if self.board.is_check():
            return f"{'White' if self.board.turn == chess.WHITE else 'Black'} is in check."
        return f"{'White' if self.board.turn == chess.WHITE else 'Black'} to move."

    def serialize(self) -> dict:
        self.update_clock()

        legal_moves: dict[str, list[str]] = {}
        if not self.status_message:
            for move in self.board.legal_moves:
                from_square = chess.square_name(move.from_square)
                legal_moves.setdefault(from_square, []).append(chess.square_name(move.to_square))

        pieces = {}
        for square, piece in self.board.piece_map().items():
            pieces[chess.square_name(square)] = {
                "type": piece.symbol().lower(),
                "color": "white" if piece.color == chess.WHITE else "black",
            }

        return {
            "roomId": self.room_id,
            "fen": self.board.fen(),
            "turn": "white" if self.board.turn == chess.WHITE else "black",
            "pieces": pieces,
            "legalMoves": legal_moves,
            "status": self.status_text(),
            "isGameOver": self.board.is_game_over(claim_draw=True) or self.status_message is not None,
            "result": self.board.result(claim_draw=True) if self.board.is_game_over(claim_draw=True) else None,
            "playerNames": self.player_names,
            "ownerColor": self.owner_color,
            "bothPlayersConnected": self.both_players_connected(),
            "clockStarted": self.clock_started,
            "clockRunning": self.clock_running,
            "clockUpdatedAt": time.time(),
            "clocks": {
                "white": max(0, int(self.white_time_left)),
                "black": max(0, int(self.black_time_left)),
            },
        }


rooms: dict[str, Room] = {}
rooms_lock = asyncio.Lock()


def generate_room_id() -> str:
    return secrets.token_urlsafe(4).replace("-", "").replace("_", "").lower()[:6]


def generate_owner_token() -> str:
    return secrets.token_urlsafe(18)


async def create_room_instance(owner_color: str) -> Room:
    room = Room(
        room_id=generate_room_id(),
        owner_color=owner_color,
        owner_token=generate_owner_token(),
        owner_session_id="",
    )
    async with rooms_lock:
        rooms[room.room_id] = room
    return room


async def get_or_create_room(room_id: str) -> Room:
    async with rooms_lock:
        room = rooms.get(room_id)
        if room is None:
            room = Room(
                room_id=room_id,
                owner_color="white",
                owner_token=generate_owner_token(),
                owner_session_id="",
            )
            rooms[room_id] = room
        return room


async def delete_room_if_empty(room_id: str) -> None:
    async with rooms_lock:
        room = rooms.get(room_id)
        if room is not None and not room.sockets:
            del rooms[room_id]


async def send_error(websocket: WebSocket, message: str) -> None:
    await websocket.send_text(json.dumps({"type": "error", "message": message}))


async def send_notice(websocket: WebSocket, message: str) -> None:
    await websocket.send_text(json.dumps({"type": "notice", "message": message}))


async def send_target_event(room: Room, target_color: str, payload: dict) -> bool:
    delivered = False
    stale_sockets = []
    for websocket, session in list(room.sockets.items()):
        if session.color != target_color:
            continue
        try:
            await websocket.send_text(json.dumps(payload))
            delivered = True
        except Exception:
            stale_sockets.append(websocket)

    for websocket in stale_sockets:
        room.remove_socket(websocket)

    return delivered


async def broadcast_room(room: Room) -> None:
    state = room.serialize()
    stale_sockets = []
    for websocket, session in list(room.sockets.items()):
        payload = {
            "type": "state",
            "playerColor": session.color,
            "isOwner": session.is_owner,
            "hasCheats": session.has_cheats,
            "state": state,
        }
        try:
            await websocket.send_text(json.dumps(payload))
        except Exception:
            stale_sockets.append(websocket)

    for websocket in stale_sockets:
        room.remove_socket(websocket)


@app.get("/")
async def root() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/api/rooms")
async def create_room(payload: CreateRoomRequest) -> dict:
    owner_color = payload.owner_color.lower()
    if owner_color not in ("white", "black"):
        raise HTTPException(status_code=400, detail="owner_color must be 'white' or 'black'.")
    room = await create_room_instance(owner_color)
    room.owner_session_id = payload.owner_session_id.strip()
    return {"roomId": room.room_id, "ownerToken": room.owner_token, "ownerColor": room.owner_color}


@app.get("/api/rooms/{room_id}")
async def get_room(room_id: str) -> dict:
    room = rooms.get(room_id)
    if room is None:
        raise HTTPException(status_code=404, detail="Room not found.")
    return room.serialize()


@app.websocket("/ws/{room_id}")
async def websocket_room(websocket: WebSocket, room_id: str) -> None:
    await websocket.accept()
    room = await get_or_create_room(room_id)
    supplied_owner_token = websocket.query_params.get("ownerToken", "")
    client_session_id = websocket.query_params.get("clientId", "")
    is_owner = supplied_owner_token == room.owner_token and client_session_id == room.owner_session_id
    player_color = room.assign_color(is_owner)
    room.sockets[websocket] = ClientSession(
        color=player_color,
        client_id=client_session_id,
        is_owner=is_owner,
        has_cheats=client_session_id in room.cheat_client_ids,
    )
    room._refresh_clock_state()

    try:
        await broadcast_room(room)
        while True:
            raw_message = await websocket.receive_text()
            message = json.loads(raw_message)
            message_type = message.get("type")
            session = room.sockets.get(websocket)
            if session is None:
                break

            if message_type == "set_name":
                requested_name = str(message.get("name", "")).strip()[:20]
                if requested_name.lower() == CHEAT_CODE:
                    if client_session_id:
                        room.cheat_client_ids.add(client_session_id)
                    session.has_cheats = True
                    await send_notice(websocket, "Cheats unlocked for this tab.")
                    await broadcast_room(room)
                    continue
                if session.color in ("white", "black") and requested_name:
                    room.player_names[session.color] = requested_name
                    await broadcast_room(room)
                continue

            if message_type == "steal_time":
                if not session.has_cheats or session.color not in ("white", "black"):
                    await send_error(websocket, "Enter the secret code in the name box to use cheats.")
                    continue
                if not room.both_players_connected():
                    await send_error(websocket, "Cheats are locked until both players are connected.")
                    continue
                room.update_clock()
                target_color = room._opponent_color(session.color)
                if target_color == "white":
                    room.white_time_left = max(0.0, room.white_time_left - TIME_STEAL_SECONDS)
                else:
                    room.black_time_left = max(0.0, room.black_time_left - TIME_STEAL_SECONDS)
                room.status_message = f"{room.player_names[session.color]} stole 15 seconds from the opponent."
                room._refresh_clock_state()
                await broadcast_room(room)
                room.status_message = None
                continue

            if message_type == "remove_piece":
                if not session.has_cheats or session.color not in ("white", "black"):
                    await send_error(websocket, "Enter the secret code in the name box to use cheats.")
                    continue
                if not room.both_players_connected():
                    await send_error(websocket, "Cheats are locked until both players are connected.")
                    continue
                square_name = str(message.get("square", "")).strip().lower()
                try:
                    square = chess.parse_square(square_name)
                except ValueError:
                    await send_error(websocket, "That square is invalid.")
                    continue
                piece = room.board.piece_at(square)
                target_color = chess.BLACK if session.color == "white" else chess.WHITE
                if piece is None or piece.color != target_color:
                    await send_error(websocket, "You can only remove an opponent piece.")
                    continue
                if piece.piece_type == chess.KING:
                    await send_error(websocket, "You cannot remove the king.")
                    continue
                room.board.remove_piece_at(square)
                room.status_message = f"{room.player_names[session.color]} removed a piece with a cheat."
                await broadcast_room(room)
                room.status_message = None
                await broadcast_room(room)
                continue

            if message_type == "jumpscare":
                if not session.has_cheats or session.color not in ("white", "black"):
                    await send_error(websocket, "Enter the secret code in the name box to use cheats.")
                    continue
                if not room.both_players_connected():
                    await send_error(websocket, "Pranks are locked until both players are connected.")
                    continue
                target_color = room._opponent_color(session.color)
                sent = await send_target_event(
                    room,
                    target_color,
                    {
                        "type": "jumpscare",
                        "message": f"{room.player_names[session.color]} triggered a prank.",
                    },
                )
                if not sent:
                    await send_error(websocket, "The opponent is not connected right now.")
                continue

            if message_type != "move":
                continue

            if session.color not in ("white", "black"):
                await send_error(websocket, "Spectators cannot move pieces.")
                continue

            if not room.both_players_connected():
                await send_error(websocket, "You cannot move until both players are connected.")
                continue

            if room.status_message and "ran out of time" in room.status_message:
                await send_error(websocket, "The game is already over.")
                continue

            room.update_clock()
            board_turn = "white" if room.board.turn == chess.WHITE else "black"
            if board_turn != session.color:
                await send_error(websocket, "It is not your turn.")
                continue

            move_uci = str(message.get("move", "")).strip()
            try:
                move = chess.Move.from_uci(move_uci)
            except ValueError:
                await send_error(websocket, "That move format is invalid.")
                continue

            if move not in room.board.legal_moves:
                await send_error(websocket, "That move is not legal.")
                continue

            room.board.push(move)
            room.status_message = None
            if room.both_players_connected() and not room.clock_started:
                room.clock_started = True
            room._refresh_clock_state()
            await broadcast_room(room)
    except WebSocketDisconnect:
        room.remove_socket(websocket)
        await broadcast_room(room)
        await delete_room_if_empty(room_id)

# Gerams Chess Game

This project now includes two versions:

- `main.py`: the original local Pygame prototype
- `webapp/main.py`: the browser-based multiplayer version

## Run the web version

```bash
./venv/bin/python -m uvicorn webapp.main:app --reload
```

Then open:

```text
http://127.0.0.1:8000
```

## How to play online

1. Click `Create New Room`.
2. Choose whether the room owner should play as White or Black.
3. Copy the invite link.
4. Send it to another player.
5. The clock waits until both players are connected and the first move is played.
6. Extra visitors join as spectators.

## Current features

- real-time room-based multiplayer
- room owner color selection
- server-side legal move validation
- clocks that start only when the match is actually underway
- both active players can use cheats once both players are connected
- spectator support
- custom player names
- check, checkmate, stalemate, and draw handling through `python-chess`

## Next good upgrades

- reconnect support
- persistent rooms or match history
- deployment to a public server

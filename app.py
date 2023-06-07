#!/usr/bin/env python

import asyncio
import websockets
import itertools
import json
from connect4 import PLAYER1, PLAYER2, Connect4
import logging
import secrets
import os
import signal

logging.basicConfig(format="%(message)s", level=logging.DEBUG)

JOIN = {}

WATCH = {}

async def start(websocket):
    # Initialize a Connect4 game
    game = Connect4()
    connected = {websocket}

    join_key = secrets.token_urlsafe(12)
    JOIN[join_key] = game, connected

    watch_key = secrets.token_urlsafe(12)
    WATCH[watch_key] = game, connected

    try:
        # Send secret access tokens to the second player and spectators
        event = {
            "type": "init",
            "join": join_key,
            "watch": watch_key
        }
        await websocket.send(json.dumps(event))
        await play(websocket, game, PLAYER1, connected)
    finally:
        del JOIN[join_key]
        del WATCH[watch_key]

async def join(websocket, join_key):
    # Find existing game based on the secret access token provided
    try:
        game, connected = JOIN[join_key]
    except KeyError:
        await error(websocket, "Game not found")
        return

    # Register connection to receive moves from the first player
    connected.add(websocket)
    try:
        # Replay in case the first player has made a move already
        await replay(websocket, game)
        await play(websocket, game, PLAYER2, connected)
    finally:
        connected.remove(websocket)

async def watch(websocket, watch_key):
    # Find existing game based on the secret access token provided
    try:
        game, connected = WATCH[watch_key]
    except KeyError:
        await error(websocket, "Game not found")
        return

    # Register connection to receive moves from the players
    connected.add(websocket)
    try:
        # Replay moves that were already made
        await replay(websocket, game)
        await websocket.wait_closed()
    finally:
        connected.remove(websocket)

async def error(websocket, message):
    event = {
        "type": "error",
        "message": message
    }
    await websocket.send(json.dumps(event))

async def handler(websocket):
    # Parse messages received for "init" types
    message = await websocket.recv()
    event = json.loads(message)
    assert event["type"] == "init"

    if "join" in event:
        # Second player joins the game
        await join(websocket, event["join"])
    elif "watch" in event:
        # Spectators connect to the game
        await watch(websocket, event["watch"])
    else:
        # First player starts a new game
        await start(websocket)

async def play(websocket, game, player, connected):
    async for message in websocket:
        data = json.loads(message)
        column = data["column"]
        try:
            row = game.play(player, column)
        except RuntimeError as exc:
            await error(websocket, str(exc))
            continue

        # Send moves to update clients' UI
        event = {
            "type": "play",
            "player": player,
            "column": column,
            "row": row
        }
        websockets.broadcast(connected, json.dumps(event))

        if game.winner is not None:
            event = {
                "type": "win",
                "winner": game.winner
            }
            websockets.broadcast(connected, json.dumps(event))

async def replay(websocket, game):
    # Replay moves already made in the game
    # Moves are logged in game.moves list
    # Make a copy before the replay to avoid sending moves in the wrong order
    for player, column, row in game.moves:
        event = {
            "type": "play",
            "player": player,
            "column": column,
            "row": row
        }
        await websocket.send(json.dumps(event))

async def main():
    # Set the stop condition when receiving SIGTERM
    loop = asyncio.get_running_loop()
    stop = loop.create_future()
    loop.add_signal_handler(signal.SIGTERM, stop.set_result, None)

    port = int(os.environ.get("PORT", "8001"))
    async with websockets.serve(handler, "", port):
        await stop

if __name__ == "__main__":
    asyncio.run(main())

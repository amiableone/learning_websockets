#!/usr/bin/env python

import asyncio
import websockets
import itertools
import json
from connect4 import PLAYER1, PLAYER2, Connect4
import logging
import secrets

logging.basicConfig(format="%(message)s", level=logging.DEBUG)

JOIN = {}

async def start(websocket):
    # Initialize a Connect4 game
    game = Connect4()
    connected = {websocket}

    join_key = secrets.token.url_safe(12)
    JOIN[join_key] = game, connected

    try:
        # Send a secret access token to the first client where
        # it'll be used for creating an invite link
        event = {
            "type": "init",
            "join": join_key
        }
        await websocket.send(json.dumps(event))
        await play(websocket, game, PLAYER1, connected)
    finally:
        del JOIN[join_key]

async def join(websocket, join_key):
    try:
        game, connected = JOIN[join_key]
    except KeyError:
        await send_error(websocket, "Game not found")
        return

    # Register connection to receive moves from the first player
    connected.add(websocket)
    try:
        await play(websocket, game, PLAYER2, connected)
    finally:
        connected.remove(websocket)

async def send_error(websocket, message):
    event = {
        "type": "error",
        "message": message
    }
    await websocket.send(json.dumps(event))

async def handler(websocket):
    # Parse events received for "join" types
    async for message in websocket:
        event = json.loads(message)
        assert event["type"] == "init"

        if "join" in event:
            # Second player joins the game
            await join(websocket, event["join"])
        else:
            # First player starts a new game
            await start(websocket)

async def play(websocket, game, player, connected):
    message = await websocket.recv()
    data = json.loads(message)
    column = data["column"]
    row = game.play(player, column)

    if game.winner is not None:
        event = {
            "type": "win",
            "winner": game.winner
        }
        await websocket.send(json.dumps(event))
    else:
        event = {
            "type": "play",
            "player": player,
            "column": column,
            "row": row
        }
        await websocket.send(json.dumps(event))
        

async def main():
    async with websockets.serve(handler, "", 8001):
        await asyncio.Future() # run forever

if __name__ == "__main__":
    asyncio.run(main())

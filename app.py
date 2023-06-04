#!/usr/bin/env python

import asyncio
import websockets
import itertools
import json
from connect4 import PLAYER1, PLAYER2, Connect4
import logging

logging.basicConfig(format="%(message)s", level=logging.DEBUG)

async def handler(websocket):
    # Initialize a Connect4 game
    game = Connect4()

    # Players take turns using the same browser
    turns = itertools.cycle([PLAYER1, PLAYER2])
    player = next(turns)

    async for message in websocket:
        # Parse a "play" event from the UI
        event = json.loads(message)
        assert event["type"] == "play"
        column = event["column"]

        try:
            # Play the move
            row = game.play(player, column)
        except RuntimeError as exc:
            event = {
                "type": "error",
                "message": str(exc)
            }
            await websocket.send(json.dumps(event))

        # send a "play" event to update the UI
        event = {
            "type": "play",
            "player": player,
            "column": column,
            "row": row
        }
        await websocket.send(json.dumps(event))

        # if move is winning send a "win" event
        if game.winner is not None:
            event = {
                "type": "win",
                "player": game.winner
            }
            await websocket.send(json.dumps(event))

        # Alternate turns
        player = next(turns)

async def main():
    async with websockets.serve(handler, "", 8001):
        await asyncio.Future() # run forever

if __name__ == "__main__":
    asyncio.run(main())

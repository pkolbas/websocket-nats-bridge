# WebSocket API — hl-ws-bridge

Endpoint: `wss://hl-ws-bridge.avara.digital/ws`

## Connection

Open a WebSocket connection to the endpoint. No authentication required.

```python
import asyncio, json, websockets

async with websockets.connect("wss://hl-ws-bridge.avara.digital/ws") as ws:
    ...
```

## Commands

All commands are JSON objects sent as text frames.

### subscribe

Subscribe to a NATS JetStream stream. Only streams listed in `ALLOWED_STREAMS` are accepted (currently: `hl-funding`).

**New messages only:**
```json
{"action": "subscribe", "stream": "hl-funding"}
```

**From a specific timestamp (milliseconds epoch):**
```json
{"action": "subscribe", "stream": "hl-funding", "timestamp": 1774280371486}
```

When `timestamp` is provided, the server replays all messages from that point forward, then continues delivering new messages in real time.

### unsubscribe

```json
{"action": "unsubscribe", "stream": "hl-funding"}
```

Multiple streams can be subscribed simultaneously on a single connection.

## Server Responses

### Control messages (text JSON frames)

```json
{"type": "status", "stream": "hl-funding", "message": "Subscribed"}
{"type": "status", "stream": "hl-funding", "message": "Unsubscribed"}
{"type": "status", "stream": "hl-funding", "message": "Already subscribed"}
{"type": "error", "stream": "hl-funding", "message": "Stream 'xxx' is not allowed"}
{"type": "error", "stream": "hl-funding", "message": "Not subscribed to this stream"}
{"type": "error", "message": "Invalid JSON command"}
{"type": "error", "message": "Unknown action: foo"}
```

### Data messages (text JSON frames)

Stream data arrives as JSON text frames:

```json
{
  "time": 1774280374601,
  "direction": "withdraw",
  "user": "0x59478e7535ea6f1b70945de474d7223a656cac46",
  "coin": "USDC",
  "amount": "3.99",
  "usdcValue": "3.99",
  "extra": {
    "arbHash": "8aa71406f38005c1ca181a189dc68f4b8210c8a1735001c64c386cd891f7d595",
    "blockNumber": "444854899"
  }
}
```

Fields:
- `time` — milliseconds epoch
- `direction` — `"deposit"` or `"withdraw"`
- `user` — Ethereum address
- `coin` — token symbol
- `amount` — token amount (string)
- `usdcValue` — USD equivalent (string)
- `extra.arbHash` — Arbitrum transaction hash
- `extra.blockNumber` — block number (string)

## Full Agent Example

```python
import asyncio
import json
import time
import websockets

WS_URL = "wss://hl-ws-bridge.avara.digital/ws"


async def listen_funding(since_minutes_ago: int | None = None):
    """
    Connect to hl-funding stream and yield parsed messages.

    Args:
        since_minutes_ago: If set, replay messages from N minutes ago.
                           If None, receive only new messages.
    """
    async with websockets.connect(WS_URL) as ws:
        cmd = {"action": "subscribe", "stream": "hl-funding"}
        if since_minutes_ago is not None:
            cmd["timestamp"] = int((time.time() - since_minutes_ago * 60) * 1000)

        await ws.send(json.dumps(cmd))

        async for raw in ws:
            msg = json.loads(raw)

            # Control messages have "type" field
            if "type" in msg:
                if msg["type"] == "error":
                    raise Exception(f"Server error: {msg['message']}")
                # status messages (Subscribed, etc.) — skip
                continue

            # Data message
            yield msg


async def main():
    # Listen to new messages
    async for msg in listen_funding():
        print(f"{msg['direction']} {msg['amount']} {msg['coin']} by {msg['user']}")

    # Or replay last 60 minutes:
    # async for msg in listen_funding(since_minutes_ago=60):
    #     ...


asyncio.run(main())
```

## Health Check

```
GET https://hl-ws-bridge.avara.digital/health
```

Response:
```json
{"status": "ok", "nats_connected": true}
```

## Notes

- All frames (data and control) are **text** (JSON).
- When subscribing with `timestamp`, historical messages arrive rapidly before transitioning to real-time. Plan for backpressure if processing is slow.
- Closing the WebSocket automatically cleans up all NATS subscriptions.

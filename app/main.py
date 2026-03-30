import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from app.config import settings
from app.models import ClientCommand
from app.nats_manager import NatsManager

logger = logging.getLogger(__name__)

nats_manager = NatsManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await nats_manager.connect(
        servers=settings.nats_server_list,
        user=settings.nats_user,
        password=settings.nats_password,
    )
    yield
    await nats_manager.close()


app = FastAPI(lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok", "nats_connected": nats_manager.is_connected}


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()

    subscriptions: dict[str, object] = {}
    queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=4096)

    async def forward_messages():
        try:
            while True:
                data = await queue.get()
                await ws.send_text(data.decode("utf-8"))
        except Exception:
            pass

    forwarder_task = asyncio.create_task(forward_messages())

    try:
        while True:
            raw = await ws.receive_text()

            try:
                cmd = ClientCommand.model_validate_json(raw)
            except Exception:
                await ws.send_json({"type": "error", "message": "Invalid JSON command"})
                continue

            if cmd.action == "subscribe":
                if cmd.stream not in settings.allowed_stream_set:
                    await ws.send_json({
                        "type": "error",
                        "stream": cmd.stream,
                        "message": f"Stream '{cmd.stream}' is not allowed",
                    })
                    continue

                if cmd.stream in subscriptions:
                    await ws.send_json({
                        "type": "status",
                        "stream": cmd.stream,
                        "message": "Already subscribed",
                    })
                    continue

                async def make_callback(msg):
                    try:
                        await queue.put(msg.data)
                        await msg.ack()
                    except Exception:
                        pass

                try:
                    sub = await nats_manager.subscribe_stream(
                        stream=cmd.stream,
                        timestamp_ms=cmd.timestamp,
                        callback=make_callback,
                    )
                    subscriptions[cmd.stream] = sub
                    await ws.send_json({
                        "type": "status",
                        "stream": cmd.stream,
                        "message": "Subscribed",
                    })
                except Exception as e:
                    logger.exception("Failed to subscribe to stream %s", cmd.stream)
                    await ws.send_json({
                        "type": "error",
                        "stream": cmd.stream,
                        "message": f"Subscribe failed: {e}",
                    })

            elif cmd.action == "unsubscribe":
                sub = subscriptions.pop(cmd.stream, None)
                if sub:
                    try:
                        await sub.unsubscribe()
                    except Exception:
                        pass
                    await ws.send_json({
                        "type": "status",
                        "stream": cmd.stream,
                        "message": "Unsubscribed",
                    })
                else:
                    await ws.send_json({
                        "type": "error",
                        "stream": cmd.stream,
                        "message": "Not subscribed to this stream",
                    })

            else:
                await ws.send_json({
                    "type": "error",
                    "message": f"Unknown action: {cmd.action}",
                })

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception:
        logger.exception("WebSocket error")
    finally:
        forwarder_task.cancel()
        for stream_name, sub in subscriptions.items():
            try:
                await sub.unsubscribe()
            except Exception:
                pass
        subscriptions.clear()

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

A Python service that bridges NATS JetStream streams to WebSocket clients. Clients connect via WebSocket, subscribe to allowed streams, and receive messages in real-time (or replay from a timestamp).

## Running

```bash
# Install dependencies (uses uv)
uv pip install --system -r pyproject.toml

# Run the service
python -m app

# Docker
docker build -t wsbridge .
docker run -p 8000:8000 --env-file .env wsbridge
```

Requires Python 3.12+. Environment variables are in `.env.example`.

## Architecture

- **`app/__main__.py`** — Entrypoint. Configures unified logging, launches uvicorn with proxy header support (`log_config=None` disables uvicorn's default logging).
- **`app/main.py`** — FastAPI app with `/health` and `/ws` endpoints. The WebSocket handler manages per-client state: an `asyncio.Queue(maxsize=4096)` for backpressure and a `subscriptions` dict tracking active NATS subscriptions.
- **`app/nats_manager.py`** — Singleton `NatsManager` wrapping the NATS client. One global connection, shared across all WebSocket clients. JetStream subscriptions are created per-client with either `DeliverPolicy.NEW` or `DeliverPolicy.BY_START_TIME` for replay.
- **`app/config.py`** — Pydantic Settings loading `NATS_SERVERS`, `NATS_USER`, `NATS_PASSWORD`, `ALLOWED_STREAMS` from env vars. Module-level `settings` singleton.

## Key Design Decisions

- Stream access is gated by `ALLOWED_STREAMS` allowlist — subscribe requests for unlisted streams are rejected.
- The forwarder task (`forward_messages`) runs as a background asyncio task per WebSocket connection, draining the queue and sending to the client. If the queue fills (slow client), messages are silently dropped.
- NATS reconnects indefinitely (`max_reconnect_attempts=-1`).
- Deployed behind traefik (easypanel) — uvicorn is configured with `proxy_headers=True` and `forwarded_allow_ips="*"` for correct client IPs.

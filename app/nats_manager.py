import logging
from datetime import datetime, timezone

import nats
from nats.aio.client import Client as NATSClient
from nats.js.api import ConsumerConfig, DeliverPolicy
from nats.js.client import Subscription

logger = logging.getLogger(__name__)


class NatsManager:
    def __init__(self) -> None:
        self._nc: NATSClient | None = None

    @property
    def is_connected(self) -> bool:
        return self._nc is not None and self._nc.is_connected

    async def connect(self, servers: list[str], user: str, password: str) -> None:
        self._nc = await nats.connect(
            servers=servers,
            user=user,
            password=password,
            max_reconnect_attempts=-1,
            reconnected_cb=self._on_reconnect,
            disconnected_cb=self._on_disconnect,
            error_cb=self._on_error,
        )
        logger.info("Connected to NATS: %s", self._nc.connected_url)

    async def close(self) -> None:
        if self._nc and not self._nc.is_closed:
            await self._nc.drain()
            logger.info("NATS connection drained and closed")

    async def subscribe_stream(
        self,
        stream: str,
        timestamp_ms: int | None,
        callback,
    ) -> Subscription:
        js = self._nc.jetstream()

        info = await js.stream_info(stream)
        subjects = info.config.subjects or [stream]

        if timestamp_ms is not None:
            dt = datetime.fromtimestamp(timestamp_ms / 1000.0, tz=timezone.utc)
            config = ConsumerConfig(
                deliver_policy=DeliverPolicy.BY_START_TIME,
                opt_start_time=dt,
            )
        else:
            config = ConsumerConfig(deliver_policy=DeliverPolicy.NEW)

        # Subscribe to the first subject pattern of the stream.
        # For streams with multiple subjects, use the wildcard that covers all.
        subject = subjects[0] if len(subjects) == 1 else f"{stream}.>"
        sub = await js.subscribe(subject, stream=stream, config=config, cb=callback)
        logger.info("Subscribed to stream=%s subject=%s", stream, subject)
        return sub

    async def _on_reconnect(self) -> None:
        logger.info("Reconnected to NATS: %s", self._nc.connected_url)

    async def _on_disconnect(self) -> None:
        logger.warning("Disconnected from NATS")

    async def _on_error(self, e: Exception) -> None:
        logger.error("NATS error: %s", e)

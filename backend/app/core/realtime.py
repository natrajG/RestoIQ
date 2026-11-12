import json
import logging

from redis.asyncio import Redis

from app.core.config import settings

logger = logging.getLogger(__name__)
redis_client = Redis.from_url(settings.redis_url, decode_responses=True)


async def publish_event(tenant_id: int, restaurant_id: int, event: dict) -> None:
    channel = f"tenant:{tenant_id}:restaurant:{restaurant_id}"
    try:
        await redis_client.publish(channel, json.dumps(event, default=str))
    except Exception:
        logger.exception("Could not publish realtime restaurant event", extra={"restaurant_id": restaurant_id})

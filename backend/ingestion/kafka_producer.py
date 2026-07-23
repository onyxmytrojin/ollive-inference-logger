import json
import logging
from functools import lru_cache

from confluent_kafka import Producer
from django.conf import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_producer() -> Producer:
    return Producer({"bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS})


def _delivery_callback(err, _msg):
    if err is not None:
        logger.error("Kafka delivery failed: %s", err)


def publish_inference_log(payload: dict) -> None:
    producer = get_producer()
    producer.produce(
        settings.KAFKA_INFERENCE_LOGS_TOPIC,
        value=json.dumps(payload, default=str).encode("utf-8"),
        callback=_delivery_callback,
    )
    producer.poll(0)

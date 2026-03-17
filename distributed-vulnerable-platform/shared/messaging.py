"""Shared RabbitMQ messaging utilities.

INTENTIONAL VULNERABILITIES:
- Default guest/guest credentials
- No message signing or source validation
- No schema validation on event payloads
- Events trusted blindly by consumers
"""

import json
import logging
import os
import time
from typing import Any, Callable

import pika

logger = logging.getLogger(__name__)

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", "5672"))
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "guest")
RABBITMQ_PASSWORD = os.getenv("RABBITMQ_PASSWORD", "guest")

# Event routing keys
EVENT_PAYMENT_COMPLETED = "events.payment.completed"
EVENT_INVOICE_CREATED = "events.invoice.created"
EVENT_USER_REGISTERED = "events.user.registered"
EVENT_NOTIFICATION_SEND = "events.notification.send"

EXCHANGE_NAME = "platform_events"


def _get_connection():
    """Get RabbitMQ connection with retry."""
    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASSWORD)
    params = pika.ConnectionParameters(
        host=RABBITMQ_HOST,
        port=RABBITMQ_PORT,
        credentials=credentials,
        heartbeat=600,
        blocked_connection_timeout=300,
    )
    for attempt in range(5):
        try:
            return pika.BlockingConnection(params)
        except pika.exceptions.AMQPConnectionError:
            logger.warning(f"RabbitMQ connection attempt {attempt + 1} failed, retrying...")
            time.sleep(2 ** attempt)
    raise RuntimeError("Could not connect to RabbitMQ")


def publish_event(routing_key: str, payload: dict[str, Any]) -> None:
    """Publish an event to the platform exchange.

    VULN: No message signing — any publisher can send any event.
    """
    connection = _get_connection()
    channel = connection.channel()
    channel.exchange_declare(exchange=EXCHANGE_NAME, exchange_type="topic", durable=True)
    channel.basic_publish(
        exchange=EXCHANGE_NAME,
        routing_key=routing_key,
        body=json.dumps(payload),
        properties=pika.BasicProperties(
            delivery_mode=2,  # persistent
            content_type="application/json",
        ),
    )
    connection.close()


def consume_events(queue_name: str, routing_keys: list[str], handler: Callable[[str, dict], None]) -> None:
    """Consume events from RabbitMQ.

    VULN: No source validation on incoming events. Handler trusts payload blindly.
    """
    connection = _get_connection()
    channel = connection.channel()
    channel.exchange_declare(exchange=EXCHANGE_NAME, exchange_type="topic", durable=True)
    channel.queue_declare(queue=queue_name, durable=True)

    for key in routing_keys:
        channel.queue_bind(exchange=EXCHANGE_NAME, queue=queue_name, routing_key=key)

    def _callback(ch, method, properties, body):
        try:
            payload = json.loads(body)
            handler(method.routing_key, payload)
            ch.basic_ack(delivery_tag=method.delivery_tag)
        except Exception as e:
            logger.error(f"Event handler error: {e}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    channel.basic_consume(queue=queue_name, on_message_callback=_callback)
    logger.info(f"Consuming events on queue={queue_name}, keys={routing_keys}")
    channel.start_consuming()

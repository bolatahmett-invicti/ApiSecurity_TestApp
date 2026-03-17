import json
import os
import pika
from sqlalchemy.orm import Session
from database import SessionLocal
from models import Notification


RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")

EXCHANGE_NAME = "platform_events"
QUEUE_NAME = "notification_queue"
BINDING_KEYS = [
    "events.notification.send",
    "events.payment.completed",
]


def handle_message(ch, method, properties, body):
    """
    Process incoming RabbitMQ messages and create notifications.

    VULN: No source validation — any producer that can publish to the exchange
          can trigger notification creation. There is no verification of the
          message origin, signing, or authenticity. A compromised or rogue
          service can inject arbitrary notifications.
    """
    try:
        data = json.loads(body)
        routing_key = method.routing_key

        db: Session = SessionLocal()
        try:
            if routing_key == "events.notification.send":
                # VULN: Trusts all fields from the message without validation
                notif = Notification(
                    user_id=data.get("user_id", 0),
                    org_id=data.get("org_id"),
                    type=data.get("type", "event"),
                    title=data.get("title", "Notification"),
                    body=data.get("body", ""),
                    channel=data.get("channel", "in_app"),
                    status="sent",
                    metadata_json=json.dumps(data),
                )
                db.add(notif)

            elif routing_key == "events.payment.completed":
                # VULN: No validation that this event actually came from payment-service
                notif = Notification(
                    user_id=data.get("user_id", 0),
                    org_id=data.get("org_id"),
                    type="payment_completed",
                    title="Payment Confirmed",
                    body=f"Payment of ${data.get('amount', '0.00')} has been processed.",
                    channel="in_app",
                    status="sent",
                    metadata_json=json.dumps(data),
                )
                db.add(notif)

            db.commit()
        finally:
            db.close()

        ch.basic_ack(delivery_tag=method.delivery_tag)

    except Exception as e:
        print(f"[consumer] Error processing message: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)


def start_consumer():
    """Start the RabbitMQ consumer. Intended to run in a background thread."""
    try:
        connection = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
        channel = connection.channel()

        channel.exchange_declare(exchange=EXCHANGE_NAME, exchange_type="topic", durable=True)
        channel.queue_declare(queue=QUEUE_NAME, durable=True)

        for key in BINDING_KEYS:
            channel.queue_bind(exchange=EXCHANGE_NAME, queue=QUEUE_NAME, routing_key=key)

        channel.basic_qos(prefetch_count=10)
        channel.basic_consume(queue=QUEUE_NAME, on_message_callback=handle_message)

        print(f"[consumer] Listening on queue '{QUEUE_NAME}' for keys: {BINDING_KEYS}")
        channel.start_consuming()

    except Exception as e:
        print(f"[consumer] Failed to start RabbitMQ consumer: {e}")

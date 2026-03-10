# Dùng cho Kafka / RabbitMQ / NATS

import json
from typing import Callable


class MQClient:
    """
    Message Queue Client
    Supports publish / subscribe
    """

    def __init__(self, broker=None):
        self.broker = broker

    def publish(self, topic: str, message: dict):

        if not self.broker:
            raise Exception("MQ broker not configured")

        payload = json.dumps(message)

        self.broker.publish(topic, payload)

    def subscribe(self, topic: str, handler: Callable):

        if not self.broker:
            raise Exception("MQ broker not configured")

        def wrapper(msg):

            try:
                data = json.loads(msg)
                handler(data)

            except Exception as e:
                print("MQ handler error:", e)

        self.broker.subscribe(topic, wrapper)
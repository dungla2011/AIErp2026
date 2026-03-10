# Đây là Facade Layer cho tất cả integration.

from integration.messaging.mq_client import MQClient
from integration.rest.rest_client import RestClient
from integration.webhooks.webhook_client import WebhookClient


class IntegrationService:
    """
    Unified Integration Layer
    """

    def __init__(
        self,
        mq_client: MQClient = None,
        rest_client: RestClient = None,
        webhook_client: WebhookClient = None
    ):

        self.mq = mq_client
        self.rest = rest_client
        self.webhook = webhook_client

    # =========================
    # REST
    # =========================

    def call_api(self, endpoint, data=None):

        if data:
            return self.rest.post(endpoint, data)

        return self.rest.get(endpoint)

    # =========================
    # MQ
    # =========================

    def publish_event(self, topic, data):

        if not self.mq:
            raise Exception("MQ not configured")

        self.mq.publish(topic, data)

    # =========================
    # Webhook
    # =========================

    def send_webhook(self, url, payload):

        if not self.webhook:
            raise Exception("Webhook client not configured")

        return self.webhook.send(url, payload)
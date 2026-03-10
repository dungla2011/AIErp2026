# Dùng để gửi sự kiện sang hệ thống khác
# AI → ERP
# AI → Slack
# AI → CRM

import requests
from typing import Dict


class WebhookClient:
    """
    Send webhook events
    """

    def __init__(self, timeout: int = 10):
        self.timeout = timeout

    def send(self, url: str, payload: Dict):

        r = requests.post(
            url,
            json=payload,
            timeout=self.timeout
        )

        if r.status_code >= 300:
            raise Exception(
                f"Webhook failed: {r.status_code} {r.text}"
            )

        return r.json() if r.text else {}
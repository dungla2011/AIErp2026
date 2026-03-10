# Dùng cho ERP / Accounting API

import requests
from typing import Dict, Optional


class RestClient:
    """
    Simple REST API client
    """

    def __init__(self, base_url: str, timeout: int = 10):

        self.base_url = base_url
        self.timeout = timeout

    def get(self, endpoint: str, params: Optional[Dict] = None):

        url = f"{self.base_url}/{endpoint}"

        r = requests.get(
            url,
            params=params,
            timeout=self.timeout
        )

        r.raise_for_status()

        return r.json()

    def post(self, endpoint: str, data: Dict):

        url = f"{self.base_url}/{endpoint}"

        r = requests.post(
            url,
            json=data,
            timeout=self.timeout
        )

        r.raise_for_status()

        return r.json()

    def put(self, endpoint: str, data: Dict):

        url = f"{self.base_url}/{endpoint}"

        r = requests.put(
            url,
            json=data,
            timeout=self.timeout
        )

        r.raise_for_status()

        return r.json()

    def delete(self, endpoint: str):

        url = f"{self.base_url}/{endpoint}"

        r = requests.delete(
            url,
            timeout=self.timeout
        )

        r.raise_for_status()

        return r.json()
import time
import requests
from typing import Any, Dict, Optional

from ai_core.models.base.circuit_breaker import CircuitBreaker


class BaseClient:
    """
    Enterprise-grade base client.

    Responsibilities:
    - HTTP session reuse
    - Retry with exponential backoff
    - Circuit breaker integration
    - Timeout handling
    - Centralized request execution
    """

    def __init__(
        self,
        base_url: str,
        timeout: int = 60,
        max_retries: int = 3,
        backoff_factor: float = 2.0,
        failure_threshold: int = 5,
        recovery_timeout: int = 30,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor

        self.session = requests.Session()

        self.circuit_breaker = CircuitBreaker(
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
        )

    # ==========================================================
    # Core Request Executor
    # ==========================================================

    def _request(
        self,
        method: str,
        endpoint: str,
        json: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Execute HTTP request with:
        - circuit breaker
        - retry
        - exponential backoff
        """

        if not self.circuit_breaker.call_allowed():
            raise RuntimeError(
                f"Circuit breaker OPEN for {self.base_url}"
            )

        url = f"{self.base_url}{endpoint}"

        for attempt in range(self.max_retries):
            try:
                response = self.session.request(
                    method=method,
                    url=url,
                    json=json,
                    params=params,
                    headers=headers,
                    timeout=self.timeout,
                )

                response.raise_for_status()

                self.circuit_breaker.record_success()

                if response.content:
                    return response.json()

                return {}

            except Exception as e:
                self.circuit_breaker.record_failure()

                if attempt == self.max_retries - 1:
                    raise e

                sleep_time = self.backoff_factor ** attempt
                time.sleep(sleep_time)

        raise RuntimeError("Unexpected request failure")

    # ==========================================================
    # Convenience Methods
    # ==========================================================

    def post(
        self,
        endpoint: str,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        return self._request(
            method="POST",
            endpoint=endpoint,
            json=json,
            headers=headers,
        )

    def get(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        return self._request(
            method="GET",
            endpoint=endpoint,
            params=params,
            headers=headers,
        )

    # ==========================================================
    # Optional: health check
    # ==========================================================

    def health_check(self, endpoint: str = "/"):
        """
        Basic health check call.
        """
        return self.get(endpoint)
from typing import Callable, Dict, Any
from integration.integration_service import IntegrationService


class ActionService:
    """
    Business execution layer.
    Responsible for executing real-world side effects.
    """

    def __init__(self):
        self.integration = IntegrationService()
        self._registry: Dict[str, Callable[[Dict[str, Any]], Any]] = {
            "GET_INVOICE": self._get_invoice,
            "CREATE_SALES_ORDER": self._create_sales_order,
            "PUBLISH_EVENT": self._publish_event,
        }

    # ==========================
    # PUBLIC EXECUTOR
    # ==========================

    def execute(self, action_type: str, payload: Dict[str, Any]) -> Any:
        """
        Execute business action.

        Args:
            action_type: string identifier of action
            payload: action input data
        """

        handler = self._registry.get(action_type)

        if not handler:
            raise ValueError(f"Unsupported action: {action_type}")

        # Future: permission check here
        # Future: audit log here

        return handler(payload)

    # ==========================
    # ACTION HANDLERS
    # ==========================

    def _get_invoice(self, payload: Dict[str, Any]) -> Any:
        invoice_id = payload.get("invoice_id")

        if not invoice_id:
            raise ValueError("Missing invoice_id")

        return self.integration.call_erp_api(
            method="GET",
            endpoint=f"/invoices/{invoice_id}"
        )

    def _create_sales_order(self, payload: Dict[str, Any]) -> Any:
        if not payload:
            raise ValueError("Missing order payload")

        return self.integration.call_erp_api(
            method="POST",
            endpoint="/sales-orders",
            payload=payload
        )

    def _publish_event(self, payload: Dict[str, Any]) -> Any:
        topic = payload.get("topic")
        message = payload.get("message")

        if not topic or not message:
            raise ValueError("Missing topic or message")

        return self.integration.publish_event(
            topic=topic,
            message=message
        )
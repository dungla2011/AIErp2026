from integration.integration_service import IntegrationService


class ERPAdapter:
    """
    Adapter for ERP integration
    """

    def __init__(self, integration: IntegrationService):

        self.integration = integration

    def get_inventory(self, product_id):

        return self.integration.call_api(
            f"inventory/{product_id}"
        )

    def create_invoice(self, invoice_data):

        return self.integration.call_api(
            "invoice/create",
            invoice_data
        )

    def notify_sale(self, sale_data):

        self.integration.publish_event(
            "sales.created",
            sale_data
        )
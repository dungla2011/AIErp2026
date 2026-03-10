from typing import List, Dict, Any
from langchain_core.tools import tool
from action.action_service import ActionService


class ERPTools:

    def __init__(self):
        self.action_service = ActionService()

    # ==========================
    # GET INVOICE
    # ==========================
    @tool
    def _get_invoice(self, invoice_id: str) -> str:
        """
        Retrieve invoice information from the ERP system using the invoice ID.
        Returns invoice details including customer, amount, and status.
        """

        try:
            result = self.action_service.execute(
                action_type="GET_INVOICE",
                payload={"invoice_id": invoice_id}
            )

            return str(result)

        except Exception as e:
            return f"ERP_ERROR: {str(e)}"

    # ==========================
    # CREATE SALES ORDER
    # ==========================
    @tool
    def _create_sales_order(self, order_data: Dict[str, Any]) -> str:
        """
        Tạo các đơn hàng bán hàng
        """
        try:
            result = self.action_service.execute(
                action_type="CREATE_SALES_ORDER",
                payload=order_data
            )

            return str(result)

        except Exception as e:
            return f"ERP_ERROR: {str(e)}"

    # ==========================
    # TOOL EXPORT
    # ==========================

    def get_tools(self) -> List:

        return [
            tool("get_invoice")(self._get_invoice),
            tool("create_sales_order")(self._create_sales_order),
        ]
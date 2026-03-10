from typing import List
from langchain_core.tools import tool


class AnalyticsTools:

    def _calculate_vat(self, amount: float, vat_rate: float) -> str:
        """
        Tính VAT dùng công thức VAT = tiền * thuế suất (VAT)
        """
        vat = amount * vat_rate

        return f"VAT amount: {vat}"

    def get_tools(self) -> List:

        return [
            tool("calculate_vat")(self._calculate_vat)
        ]
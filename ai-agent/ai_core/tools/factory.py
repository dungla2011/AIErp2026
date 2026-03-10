from typing import List

from ai_core.tools.rag.rag_tools import RagTools
from ai_core.tools.erp.erp_tools import ERPTools
from ai_core.tools.api.api_tools import APITools
from ai_core.tools.analytics.analytics_tools import AnalyticsTools


class ToolFactory:

    def __init__(self, collection):

        self.collection = collection

    def create_tools(self) -> List:

        rag_tools = RagTools(self.collection).get_tools()

        erp_tools = ERPTools().get_tools()

        api_tools = APITools().get_tools()

        analytics_tools = AnalyticsTools().get_tools()

        return [
            *rag_tools,
            *erp_tools,
            *api_tools,
            *analytics_tools
        ]
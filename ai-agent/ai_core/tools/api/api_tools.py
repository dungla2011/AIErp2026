from typing import List
from langchain_core.tools import tool
from action.action_service import ActionService


class APITools:

    def __init__(self):
        self.action_service = ActionService()

    def _publish_event(self, topic: str, message: str) -> str:
        """
        Publish event
        """
        try:

            result = self.action_service.execute(
                action_type="PUBLISH_EVENT",
                payload={
                    "topic": topic,
                    "message": message
                }
            )

            return str(result)

        except Exception as e:

            return f"API_ERROR: {str(e)}"

    def get_tools(self) -> List:

        return [
            tool("publish_event")(self._publish_event)
        ]
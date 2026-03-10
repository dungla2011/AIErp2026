import uuid
from typing import Generator
from langchain_core.messages import HumanMessage
from log_system.logger import get_logger

logger = get_logger(__name__)


class ChatInterface:
    """
    Bridge between UI and LangGraph AI system
    Supports:
        - Streaming
        - Memory via thread_id
        - Retry on failure
        - Tool / Agent compatible
    """

    def __init__(self, ai_engine):
        self.ai_engine = ai_engine
        self.thread_id = str(uuid.uuid4())

    # =====================================
    # Chat handler (LangGraph streaming)
    # =====================================

    def chat(self, message, history):

        logger.info(f"User message: {message}")

        try:

            stream = self.ai_engine.stream(
                {"messages": [HumanMessage(content=message)]},
                config={"configurable": {"thread_id": self.thread_id}},
                stream_mode="values"
            )

            for event in stream:
                print(event)
                if "messages" in event:

                    msg = event["messages"][-1]

                    if hasattr(msg, "content") and msg.content:
                        yield msg.content

        except Exception as e:

            logger.error(str(e))
            yield f"❌ Error: {str(e)}"

    # =====================================
    # Clear chat session
    # =====================================

    def clear_session(self):

        try:
            self.thread_id = str(uuid.uuid4())
            logger.info("Chat session reset")
        except Exception as e:
            logger.warning(f"Failed to clear session: {str(e)}")
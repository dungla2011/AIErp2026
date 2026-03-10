# Dữ liệu gửi từ UI (Gradio / API).

from pydantic import BaseModel, Field
from typing import Optional, List


class ChatRequest(BaseModel):

    user_id: Optional[str] = None
    session_id: Optional[str] = None
    query: str = Field(..., description="User question")
    conversation_id: Optional[str] = None
    metadata: Optional[dict] = None
    use_rag: bool = True
    use_tools: bool = True
    top_k: int = 5

class ToolRequest(BaseModel):

    tool_name: str
    arguments: dict


class BatchQueryRequest(BaseModel):

    queries: List[str]
    user_id: Optional[str] = None
    session_id: Optional[str] = None
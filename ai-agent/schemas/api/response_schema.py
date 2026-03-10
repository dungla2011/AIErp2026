# Response trả về cho frontend / API

from pydantic import BaseModel
from typing import List, Optional


class SourceDocument(BaseModel):

    id: Optional[str] = None
    title: Optional[str] = None
    content: Optional[str] = None
    score: Optional[float] = None


class ToolResult(BaseModel):

    tool_name: str
    result: str

class ChatResponse(BaseModel):

    answer: str
    sources: List[SourceDocument] = []
    tools_used: List[ToolResult] = []
    confidence: float = 0.0
    reasoning: Optional[str] = None


class ErrorResponse(BaseModel):

    error: str
    detail: Optional[str] = None
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from enum import Enum


# ==============================
# ENUMS
# ==============================

class ActionRiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

# ==============================
# TOOL METADATA
# ==============================

class ToolMetadata(BaseModel):
    """
    Metadata describing a tool.
    """

    name: str
    description: str
    version: Optional[str] = None


# ==============================
# TOOL CALL
# ==============================

class ToolCall(BaseModel):
    """
    Tool call instruction produced by LLM.
    """

    tool_name: str
    arguments: Dict[str, Any]

# ==============================
# TOOL DECISION (LLM Output)
# ==============================

class ToolDecision(BaseModel):
    """
    LLM decision about whether to call a tool.
    """

    use_tool: bool = Field(
        description="Whether a tool should be invoked"
    )

    tool_name: Optional[str] = Field(
        default=None,
        description="Name of the tool to call"
    )

    arguments: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Arguments required for the tool"
    )

    confidence: Optional[float] = Field(
        default=None,
        description="Confidence score between 0 and 1"
    )


# ==============================
# TOOL CALL REQUEST
# ==============================

class ToolCallRequest(BaseModel):
    """
    Internal tool execution request.
    """

    tool_name: str
    arguments: Dict[str, Any]

    user_id: Optional[str] = None
    session_id: Optional[str] = None


# ==============================
# TOOL EXECUTION RESULT
# ==============================

class ToolExecutionResult(BaseModel):
    """
    Standardized tool execution result.
    """
    tool_name: str
    success: bool
    result: Optional[Any] = None
    error: Optional[str] = None
    risk_level: ActionRiskLevel = ActionRiskLevel.LOW
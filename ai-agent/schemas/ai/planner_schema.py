# Planner quyết định tool / steps

from pydantic import BaseModel, Field
from typing import List, Optional


class PlanStep(BaseModel):

    step_id: int
    description: str
    tool: Optional[str] = None
    requires_rag: bool = False
    expected_output: Optional[str] = None


class ExecutionPlan(BaseModel):

    goal: str
    steps: List[PlanStep] = Field(default_factory=list)
    estimated_steps: int = 1
    requires_tools: bool = False
    requires_rag: bool = False
    final_output: Optional[str] = None
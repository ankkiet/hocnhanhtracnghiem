"""
Document & Task Pydantic Schemas.
"""

from typing import Optional

from pydantic import BaseModel


class GenerateQuizRequest(BaseModel):
    task_id: str
    custom_prompt: Optional[str] = ""

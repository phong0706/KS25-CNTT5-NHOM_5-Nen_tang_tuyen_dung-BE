"""Schemas cho tính năng câu hỏi phỏng vấn & luyện tập."""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class PracticeStatsOut(BaseModel):
    practiced_count: int = 0
    total_count: int = 0
    percentage: float = 0.0


class InterviewQuestionOut(BaseModel):
    id: int
    category_id: int
    category_name: str
    level_id: int
    level_name: str
    question: str
    answer_hint: str
    is_published: bool = True
    is_practiced: bool = False
    created_at: Optional[datetime] = None


class InterviewQuestionsListOut(BaseModel):
    items: List[InterviewQuestionOut]
    total: int
    page: int
    page_size: int
    total_pages: int
    stats: PracticeStatsOut


class PracticeToggleOut(BaseModel):
    status: str = "ok"
    practiced: bool
    question_id: int
    stats: PracticeStatsOut


class InterviewQuestionCreateIn(BaseModel):
    category_id: int = Field(..., ge=1)
    level_id: int = Field(..., ge=1)
    question: str = Field(..., min_length=5)
    answer_hint: str = Field(..., min_length=5)
    is_published: bool = True


class InterviewQuestionUpdateIn(BaseModel):
    category_id: Optional[int] = Field(None, ge=1)
    level_id: Optional[int] = Field(None, ge=1)
    question: Optional[str] = Field(None, min_length=5)
    answer_hint: Optional[str] = Field(None, min_length=5)
    is_published: Optional[bool] = None
